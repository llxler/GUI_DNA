"""Score sealed current-task candidates and verify public interaction and billing evidence."""

import argparse
from concurrent.futures import ThreadPoolExecutor

from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import digest, read, sha
from . import run

RESULT = run.HERE / "result.json"
TASKS = range(1, 21)
REPS = ("build-a", "build-b")


def billing():
    records = ledger_read.calls(run.OUT / "budget.sqlite3")
    lookup = {r["id"]: r for r in records}
    seen = set()
    stages = {}
    for f in run.OUT.rglob("request.json"):
        req = read(f)
        r = lookup[req["call_id"]]
        assert r["model"] == req["body"]["model"] == run.MODEL
        assert abs(r["reserved"] / 1e6 - req["reserved_usd"]) < 0.0000011
        seen.add(r["id"])
        v = stages.setdefault(
            r["purpose"],
            dict(
                calls=0,
                unresolved=0,
                settled_microusd=0,
                exposure_microusd=0,
                prompt_tokens=0,
                completion_tokens=0,
            ),
        )
        v["calls"] += 1
        v["exposure_microusd"] += r["reserved"] if r["actual"] is None else r["actual"]
        if r["actual"] is None:
            v["unresolved"] += 1
        else:
            receipt = f.with_name("response.json")
            assert sha(receipt) == read(f.with_name("settled.json"))["response_sha256"]
            usage = read(receipt)["usage"]
            assert abs(float(usage["cost"]) - r["actual"] / 1e6) < 0.0000011
            v["settled_microusd"] += r["actual"]
            v["prompt_tokens"] += usage.get("prompt_tokens", 0)
            v["completion_tokens"] += usage.get("completion_tokens", 0)
    assert seen == set(lookup)
    return ledger_read.totals(run.OUT / "budget.sqlite3"), stages


def comp(rows):
    out = {}
    for arm in ("direct_first", "direct", "fixed"):
        common = [
            r
            for r in rows
            if r[arm]["passed"] is not None and r["self"]["passed"] is not None
        ]
        selected, other = (
            {r["task"] for r in common if r[k]["passed"]} for k in ("self", arm)
        )
        out[arm] = {
            "tasks": [r["task"] for r in common],
            "self": len(selected),
            "other": len(other),
            "self_only": sorted(selected - other),
            "other_only": sorted(other - selected),
        }
    return out


def summarize_module(rep, name, state):
    path = run.OUT / rep / "modules" / name
    result = {k: v for k, v in state.items() if k != "attempts"}
    result["attempts"] = []
    for i, attempt in enumerate(state["attempts"]):
        folder = path / str(i)
        item = {k: v for k, v in attempt.items() if k != "public_feedback"}
        if (folder / "probe.json").exists():
            public = read(folder / "probe.json")
            item["public_probe"] = public
            item["probe_sha256"] = sha(folder / "probe.json")
            item["passed_probe"] = not bool(run.problem(public))
        if "response_sha256" in item:
            assert item["response_sha256"] == sha(folder / "call/response.json")
        result["attempts"].append(item)
    if state["status"] == "valid":
        assert state["source_sha256"] == sha(path / str(state["use"]) / "code.json")
    return result


def score(work):
    (task, key), (page, files, contract, items) = work
    raw = browser.run_one(run.OUT, "form", task, page, files, contract)
    assert key == raw["files_digest"]
    for cell in items:
        cell.update(passed=raw["passed"], report_sha256=raw["report_sha256"])


def direct_deliveries(sealed):
    deliveries = []
    for record in sealed:
        task = record["task"]
        attempts = []
        for index, attempt in enumerate(record["attempts"]):
            item = {key: value for key, value in attempt.items() if key != "files"}
            if item["status"] == "returned":
                receipt = (
                    run.OUT / "direct" / str(task) / str(index) / "call/response.json"
                )
                assert sha(receipt) == item["response_sha256"]
                item["finish_reason"] = read(receipt)["choices"][0]["finish_reason"]
                item["valid_files"] = bool(attempt.get("files"))
            attempts.append(item)
        deliveries.append(
            {
                "task": task,
                "status": record["status"],
                "used_attempt": record.get("use"),
                "attempts": attempts,
            }
        )
    return deliveries


def assemble():
    run.register()
    reg_path = run.OUT / "registration.json"
    seal_path = run.OUT / "seal.json"
    reg = read(reg_path)
    seal = read(seal_path)
    assert sha(reg_path) == seal["registration_sha256"]
    contract = reg["spec"]["official_contract"]
    assert contract == browser.verify_contract("form")
    browser.OUT = run.OUT
    jobs = {}
    replicas = {}

    def attach(cell, page, files, task):
        if files is None:
            cell["passed"] = None if cell["status"] == "missing" else False
        else:
            key = digest(files)
            browser.verify_page(page, files, "form")
            cell["files_digest"] = key
            jobs.setdefault((task, key), (page, files, contract, []))[3].append(cell)
        return cell

    for rep in REPS:
        modules = {
            n: summarize_module(rep, n, s) for n, s in seal["modules"][rep].items()
        }
        planned = seal["plans"][rep]
        fixed = seal["fixed"][rep]
        rows = []
        for task, direct, plan in zip(TASKS, seal["direct"], planned, strict=True):
            assert direct["task"] == task
            row = {"task": task}
            for arm, source, folder in (
                ("self", plan, run.OUT / rep / "selected" / str(task)),
                ("fixed", fixed, run.OUT / rep / "fixed/20"),
            ):
                state = source["status"]
                if source["call"]["status"] == "returned":
                    assert source["call"]["response_sha256"] == sha(
                        folder / "call/response.json"
                    )
                chosen = source.get("plan")
                if chosen and any(v["status"] == "missing" for v in modules.values()):
                    requested = {item["type"] for item in chosen.get("questions", [])}
                    if chosen.get("surveyTitle") is not None:
                        requested.add("Survey")
                    if any(
                        modules.get(n, {}).get("status") == "missing" for n in requested
                    ):
                        state = "missing"
                cell = {
                    "status": state,
                    "response_sha256": source["call"].get("response_sha256"),
                    "plan": chosen,
                }
                if "reason" in source:
                    cell["reason"] = source["reason"]
                row[arm] = attach(
                    cell,
                    folder / "page",
                    source.get("files") if state == "valid" else None,
                    task,
                )
            for arm, i in (("direct_first", 0), ("direct", direct.get("use"))):
                stages = direct["attempts"]
                if i is None:
                    row[arm] = attach({"status": direct["status"]}, None, None, task)
                    continue
                attempt = stages[i]
                folder = run.OUT / "direct" / str(task) / str(i)
                if attempt["status"] == "returned":
                    assert (
                        sha(folder / "call/response.json") == attempt["response_sha256"]
                    )
                files = attempt.get("files")
                status = (
                    "valid"
                    if files
                    else "missing"
                    if attempt["status"] == "missing"
                    else "invalid"
                )
                cell = {
                    "status": status,
                    "response_sha256": attempt.get("response_sha256"),
                    "attempt": i,
                }
                if (folder / "probe.json").exists():
                    probe = read(folder / "probe.json")
                    cell.update(
                        probe_sha256=sha(folder / "probe.json"),
                        public_errors=probe["errors"],
                        public_control_pass=sum(
                            all(
                                v.get(k)
                                for k in (
                                    "mounted",
                                    "control",
                                    "public_structure",
                                    "exported",
                                )
                            )
                            for v in probe["types"].values()
                        ),
                        public_types=len(probe["types"]),
                        actual_questions=probe.get("actual_questions"),
                    )
                row[arm] = attach(cell, folder / "page", files, task)
            rows.append(row)
        fixed_classes = sorted(
            {q["type"] for q in (fixed.get("plan") or {}).get("questions", [])}
        )
        replicas[rep] = {"modules": modules, "fixed_types": fixed_classes, "rows": rows}
    with ThreadPoolExecutor(max_workers=5) as pool:
        list(pool.map(score, jobs.items()))
    for group in replicas.values():
        group["paired"] = comp(group["rows"])
    cost, stages = billing()
    return {
        "model": run.MODEL,
        "registered_utc": reg["utc"],
        "sealed_utc": seal["utc"],
        "registration_sha256": sha(reg_path),
        "seal_sha256": sha(seal_path),
        "protocol_sha256": sha(run.HERE / "PROTOCOL.md"),
        "generation_sha256": sha(run.HERE / "run.py"),
        "compiler_sha256": sha(run.COMPILER),
        "test_contract_digest": digest(contract),
        "budget": cost,
        "cost_by_phase": stages,
        "projects": {
            "form": {
                "replicas": replicas,
                "direct_deliveries": direct_deliveries(seal["direct"]),
            }
        },
    }


def check(result):
    assert result["model"] == run.MODEL
    assert result["generation_sha256"] == sha(run.HERE / "run.py")
    assert result["protocol_sha256"] == sha(run.HERE / "PROTOCOL.md") and result[
        "compiler_sha256"
    ] == sha(run.COMPILER)
    budget = result["budget"]
    assert budget["cap_usd"] == run.CAP and budget["exposure_usd"] <= run.CAP
    stages = result["cost_by_phase"].values()
    assert budget["calls"] == sum(v["calls"] for v in stages)
    assert budget["unsettled_calls"] == sum(v["unresolved"] for v in stages)
    assert round(budget["exposure_usd"] * 1e6) == sum(
        v["exposure_microusd"] for v in stages
    )
    assert round(budget["settled_usd"] * 1e6) == sum(
        v["settled_microusd"] for v in stages
    )
    groups = result["projects"]["form"]["replicas"]
    deliveries = result["projects"]["form"]["direct_deliveries"]
    assert [entry["task"] for entry in deliveries] == list(TASKS)
    assert result["registered_utc"] < result["sealed_utc"]
    assert set(groups) == set(REPS)
    direct_first = []
    for rep, group in groups.items():
        assert group["paired"] == comp(group["rows"])
        assert set(group["modules"]) == {*run.TYPES, *run.SUPPORT}
        assert [r["task"] for r in group["rows"]] == list(TASKS)
        current = [(r["direct_first"], r["direct"]) for r in group["rows"]]
        if direct_first:
            assert current == direct_first
        direct_first = current
        for r, delivery in zip(group["rows"], deliveries, strict=True):
            assert r["direct"]["status"] == delivery["status"]
            for arm in ("self", "fixed", "direct_first", "direct"):
                if r[arm]["status"] == "valid":
                    assert (
                        r[arm]["files_digest"]
                        and r[arm]["report_sha256"]
                        and type(r[arm]["passed"]) is bool
                    )
                elif r[arm]["status"] == "missing":
                    assert r[arm]["passed"] is None
                else:
                    assert r[arm]["status"] == "invalid" and r[arm]["passed"] is False
        agg = {
            arm: (v["self"], v["other"], len(v["tasks"]))
            for arm, v in group["paired"].items()
        }
        print(rep, agg, group["fixed_types"])
    print(budget)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("score", "check", "check-local"))
    phase = parser.parse_args().phase
    result = read(RESULT) if phase == "check" else assemble()
    check(result)
    if phase == "score":
        core.save(RESULT, result)
    elif phase == "check-local":
        assert result == read(RESULT)
