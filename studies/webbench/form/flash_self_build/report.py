"""Score two pairs of sealed Flash-built libraries on the official current form tasks."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, digest, read, sha

OUT = ROOT / "artifacts/flash-form-self-20261125"
ORIGINAL = ROOT / "artifacts/backbone-form-20261124"
BASELINE = ROOT / "studies/results/backbone-form-20261124.json"
RESULT = Path(__file__).with_name("result.json")
MODEL = "deepseek/deepseek-v4-flash"
TASKS = tuple(range(1, 21))
BRANCHES = ("delivery-a", "delivery-b", "staged-a", "staged-b")
SUPPLEMENTS = ("contract-b", "contract-subset-b", "contract-entry-b", "staged-schema-a", "staged-schema-b")
HISTORICAL = {"direct": "direct", "human": "human", "gpt5-library": "gpt5-library", "self": "original-self"}


def check_receipt(root, task, files_digest, contract):
    where = root / "browser/scores/form" / f"task-{task}" / files_digest / "score.json"
    expected = dict(project="form", task=task, files_digest=files_digest, contract_digest=digest(contract))
    return browser.verify_receipt(root, where, expected)


def historical(contract):
    """Check archived target IDs and scores against the generation seal and raw official reports."""
    public = read(BASELINE)
    old = ORIGINAL / "deepseek-flash"
    source = public["models"][MODEL]
    scores = read(old / "scores.json")
    seal = read(old / "seal.json")
    assert source["seal_sha256"] == scores["seal_sha256"] == sha(old / "seal.json")
    assert seal["registration"] == public["registration_sha256"] == sha(ORIGINAL / "registered.json")
    assert source["rows"] == scores["rows"] and read(ORIGINAL / "inputs/form/browser.json") == contract
    index = {(r["task"], r["arm"]): r for r in seal["rows"]}
    output = {i: {} for i in TASKS}
    for row in scores["rows"]:
        arm, task = row["arm"], row["task"]
        if arm not in HISTORICAL:
            continue
        original = index[task, arm]
        status = row["status"]
        assert row["project"] == original["project"] == "form" and original["model"] == MODEL
        assert status == original["status"] and row.get("response_sha256") == original.get("response_sha256")
        if row.get("response_sha256"):
            assert row["response_sha256"] == sha(old / "form" / arm / str(task) / "call/response.json")
        if status == "valid":
            assert digest(original["files"]) == row["files_digest"]
            receipt = check_receipt(ORIGINAL, task, row["files_digest"], contract)
            assert receipt["passed"] == row["passed"] and receipt["report_sha256"] == row["report_sha256"]
        else:
            assert status in ("missing", "invalid", "build_failed")
            assert row["passed"] is (None if status == "missing" else False)
        name = HISTORICAL[arm]
        assert name not in output[task]
        output[task][name] = {k: v for k, v in row.items() if k not in ("project", "task", "arm")}
    assert all(set(cells) == set(HISTORICAL.values()) for cells in output.values())
    counts = {arm: sum(cells[arm]["passed"] is True for cells in output.values()) for arm in HISTORICAL.values()}
    assert counts == {"direct": 4, "human": 17, "gpt5-library": 13, "original-self": 0}
    return output


def delivery_stats(path):
    response = read(path)
    item = response["choices"][0]
    usage = response.get("usage", {})
    return {"finish_reason": item.get("finish_reason"), "visible_characters": len(item["message"].get("content") or ""),
            "completion_tokens": usage.get("completion_tokens"),
            "reported_reasoning_tokens": (usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
            "provider": response.get("provider"),
            "response_sha256": sha(path)}


def billing():
    accounting = ledger_read.totals(OUT / "budget.sqlite3")
    by_id = {r["id"]: r for r in ledger_read.calls(OUT / "budget.sqlite3")}
    seen = set()
    stages = {b: {} for b in (*BRANCHES, *SUPPLEMENTS)}
    for branch in stages:
        for stage in ("build", "plan"):
            stages[branch][stage] = dict(calls=0, unsettled=0, settled_microusd=0, exposure_microusd=0,
                                          finish_reasons={}, deliveries=[])
    for path in sorted(OUT.rglob("request.json")):
        req = read(path)
        call_id = req["call_id"]
        assert call_id not in seen
        seen.add(call_id)
        record = by_id[call_id]
        branch, stage, *_ = record["purpose"].split("/")
        stats = stages[branch][stage]
        assert record["model"] == req["body"]["model"] == MODEL
        assert path.is_relative_to(OUT / branch)
        stats["calls"] += 1
        actual = record["actual"]
        stats["exposure_microusd"] += record["reserved"] if actual is None else actual
        if actual is None:
            stats["unsettled"] += 1
            continue
        stats["settled_microusd"] += actual
        response_path = path.with_name("response.json")
        delivered = delivery_stats(response_path)
        assert delivered["response_sha256"] == read(path.with_name("settled.json"))["response_sha256"]
        assert abs(read(response_path)["usage"]["cost"] * 1e6 - actual) <= 1.01
        reason = delivered["finish_reason"] or "unknown"
        cnt = stats["finish_reasons"]
        cnt[reason] = cnt.get(reason, 0) + 1
        settings = {k: req["body"][k] for k in ("max_tokens", "temperature", "seed", "reasoning") if k in req["body"]}
        stats["deliveries"].append({"purpose": record["purpose"], "request_sha256": sha(path), "settings": settings, **delivered})
    assert seen == set(by_id)
    assert sum(g["exposure_microusd"] for b in stages.values() for g in b.values()) == round(accounting["exposure_usd"] * 1e6)
    def subtotal(names):
        entries = [stats for b in names for stats in stages[b].values()]
        keys = ("calls", "unsettled", "settled_microusd", "exposure_microusd")
        return {k: sum(entry[k] for entry in entries) for k in keys}
    return {"total": accounting, "by_branch": stages,
            "primary": subtotal(BRANCHES), "supplement": subtotal(SUPPLEMENTS)}


def package_source(package):
    """Ignore descriptions and example settings when testing whether implementations differ."""
    return digest({k: package.get(k) for k in ("anchor", "fragment", "css", "script", "files")})


def sealed_candidates(branch, evidence):
    folder = OUT / branch / "form"
    build_folder = folder / "build"
    state = read(build_folder / "status.json")
    assert evidence["build_sha256"] == sha(build_folder / "status.json") and state == evidence["build"]
    fixed_files = evidence["fixed_files"]
    build_summary = {"status": state["status"], "status_sha256": evidence["build_sha256"],
                     "package_sha256": evidence["package_sha256"], "source_sha256": None}
    if state["status"] == "valid":
        assert evidence["package_sha256"] == state["package_sha256"] == sha(build_folder / "package.json")
        pkg = read(build_folder / "package.json")
        assert pkg["examples"][0]["plan"] is not None
        build_summary["source_sha256"] = package_source(pkg)
        fixed_page = ROOT / state["fixed"]
        assert fixed_page.resolve().is_relative_to(build_folder.resolve())
        browser.verify_page(fixed_page, fixed_files, "form")
    else:
        assert state["status"] in ("build_failed", "missing") and not fixed_files and evidence["package_sha256"] is None
    original_request = read(ORIGINAL / "deepseek-flash/form/gpt5-library/1/call/request.json")["body"]
    planner_settings = {k: v for k, v in original_request.items() if k != "messages"}
    public_input = read(ORIGINAL / "inputs/form/public.json")
    raw = evidence["rows"]
    assert sorted(r["task"] for r in raw) == list(TASKS)
    candidates = []
    for row in raw:
        task = row["task"]
        original = folder / "self" / str(task) / "result.json"
        assert evidence["row_sha256"][str(task)] == sha(original) and row == read(original)
        assert row["project"] == "form" and row["arm"] == "self" and row["model"] == MODEL
        request_path = original.parent / "call/request.json"
        if request_path.exists():
            body = read(request_path)["body"]
            assert state["status"] == "valid" and body["messages"] == core.plan_messages(public_input, task, pkg)
            assert {k: v for k, v in body.items() if k != "messages"} == planner_settings
        if row.get("response_sha256"):
            assert request_path.exists()
            assert sha(original.parent / "call/response.json") == row["response_sha256"]
        if row["status"] == "valid":
            page = ROOT / row["page"]
            assert page.resolve().is_relative_to(original.parent.resolve())
            browser.verify_page(page, row["files"], "form")
        else:
            assert row["status"] in ("missing", "build_failed", "invalid") and not row.get("page") and not row.get("files")
        fixed = {"project": "form", "task": task, "arm": "fixed", "status": state["status"]}
        if state["status"] == "valid":
            fixed.update(page=state["fixed"], files=fixed_files)
        candidates.extend((row, fixed))
    return build_summary, candidates


def paired(rows, comparator):
    comparable = [r for r in rows if r["self"]["passed"] is not None and r[comparator]["passed"] is not None]
    selected, other = ({r["task"] for r in comparable if r[arm]["passed"]} for arm in ("self", comparator))
    return dict(tasks=[r["task"] for r in comparable], denominator=len(comparable),
                self_passed=len(selected), comparator_passed=len(other),
                self_only=sorted(selected - other), comparator_only=sorted(other - selected))


def confirmation_for(branches):
    confirmation = {}
    for method in ("delivery", "staged"):
        trials = [branches[f"{method}-{rep}"] for rep in ("a", "b")]
        source_ids = [trial["build"]["source_sha256"] for trial in trials]
        distinct = all(source_ids) and len(set(source_ids)) == 2
        reached = []
        for trial in trials:
            pairs = trial["comparisons"]
            reached.append(all(x["tasks"] == list(TASKS) for x in pairs.values()) and
                           pairs["direct"]["self_passed"] >= 10 and
                           all(pairs["direct"]["self_passed"] > pairs[c]["comparator_passed"]
                               for c in ("direct", "original-self")))
        confirmation[method] = dict(threshold=10, distinct_implementations=distinct,
                                    rep_passed=reached, confirmed=bool(distinct and all(reached)))
    return confirmation


def score_branches(prepared, comparators, contract, score, workers):
    """Score validated branch manifests, or verify their existing receipts in read-only mode."""
    jobs = {}
    for build, candidates in prepared.values():
        for row in candidates:
            if row["status"] == "valid":
                jobs[row["task"], digest(row["files"])] = row

    def evaluate(item):
        (task, files_digest), row = item
        if score:
            return browser.run_one(OUT, "form", task, ROOT / row["page"], row["files"], contract)
        return check_receipt(OUT, task, files_digest, contract)

    with patch.object(browser, "OUT", OUT), ThreadPoolExecutor(max_workers=workers) as pool:
        receipts = dict(zip(jobs, pool.map(evaluate, jobs.items())))
    branches = {}
    for name, (build, candidates) in prepared.items():
        targets = {n: {"task": n, **comparators[n]} for n in TASKS}
        for row in candidates:
            entry = {k: row[k] for k in ("status", "response_sha256") if k in row}
            entry["passed"] = None if entry["status"] == "missing" else False
            if entry["status"] == "valid":
                files_digest = digest(row["files"])
                receipt = receipts[row["task"], files_digest]
                entry.update(passed=receipt["passed"], report_sha256=receipt["report_sha256"], files_digest=files_digest)
            targets[row["task"]][row["arm"]] = entry
        rows = list(targets.values())
        comparisons = {arm: paired(rows, arm) for arm in (*HISTORICAL.values(), "fixed")}
        branches[name] = {"build": build, "rows": rows, "comparisons": comparisons,
                          "self_status_counts": dict(Counter(r["self"]["status"] for r in rows))}
    return branches


def assemble(score, workers):
    seal = read(OUT / "seal.json")
    assert set(seal["branches"]) == set(BRANCHES)
    for key, filename in (("registration_sha256", "registration.json"),
                          ("staged_registration_sha256", "staged-registration.json")):
        registration = OUT / filename
        assert sha(registration) == seal[key]
        frozen = read(registration)
        assert frozen["model"] == MODEL and frozen["scheduled"] == list(TASKS)
        assert frozen["utc"] <= seal["utc"] and set(frozen["branches"]) == set(BRANCHES)
        for relative, checksum in frozen["files"].items():
            assert sha(ROOT / relative) == checksum, f"Changed registered input: {relative}"
    for branch in BRANCHES:
        assert read(OUT / branch / "seal.json") == seal["branches"][branch]
    adapter_file = OUT / "deployment-adapter.json"
    adapter = read(adapter_file)
    assert adapter["adapter_sha256"] == sha(Path(__file__).with_name("resume.py"))
    assert adapter["original_registration_sha256"] == seal["registration_sha256"]
    assert adapter["target_request_sha256"] == sha(ORIGINAL / "deepseek-flash/form/gpt5-library/1/call/request.json")
    assert adapter["target_default"] == 8192 and adapter["utc"] <= seal["utc"]
    supplemental_seals = {branch: sha(OUT / branch / "seal.json") for branch in SUPPLEMENTS}
    contract = browser.verify_contract("form")
    comparators = historical(contract)
    # Validate all four branches and both registrations before launching the first official test.
    prepared = {name: sealed_candidates(name, seal["branches"][name]) for name in BRANCHES}
    branches = score_branches(prepared, comparators, contract, score, workers)
    return {"model": MODEL, "project": "form", "tasks": list(TASKS), "upstream_commit": browser.UPSTREAM_COMMIT,
            "contract_sha256": digest(contract), "seal_sha256": sha(OUT / "seal.json"),
            "deployment_adapter_sha256": sha(adapter_file), "supplemental_seal_sha256": supplemental_seals,
            **{k: seal[k] for k in ("registration_sha256", "staged_registration_sha256")},
            "original_report_sha256": sha(BASELINE),
            "original_build_deliveries": [
                delivery_stats(ORIGINAL / "deepseek-flash/form/build" / f"attempt-{i}" / "response.json")
                for i in (1, 2)],
            "branches": branches, "confirmation": confirmation_for(branches),
            "billing": billing()}


def check_public(result):
    """Recompute the published target pairs and thresholds without private pages or model replies."""
    assert result["tasks"] == list(TASKS) and result["model"] == MODEL and result["project"] == "form"
    assert result["original_report_sha256"] == sha(BASELINE) and set(result["branches"]) == set(BRANCHES)
    old = read(BASELINE)["models"][MODEL]["rows"]
    controls = {(r["task"], HISTORICAL[r["arm"]]): r for r in old if r["arm"] in HISTORICAL}
    for branch in result["branches"].values():
        rows = branch["rows"]
        assert [r["task"] for r in rows] == list(TASKS)
        for row in rows:
            for arm in HISTORICAL.values():
                expected = controls[row["task"], arm]
                for k in ("status", "passed", "response_sha256", "report_sha256", "files_digest"):
                    assert row[arm].get(k) == expected.get(k)
            for arm in ("self", "fixed"):
                cell = row[arm]
                if cell["status"] == "valid":
                    assert type(cell["passed"]) is bool and len(cell["report_sha256"]) == len(cell["files_digest"]) == 64
                else:
                    assert cell["status"] in ("missing", "build_failed", "invalid")
                    assert cell["passed"] is (None if cell["status"] == "missing" else False)
        assert branch["comparisons"] == {arm: paired(rows, arm) for arm in (*HISTORICAL.values(), "fixed")}
        assert branch["self_status_counts"] == dict(Counter(r["self"]["status"] for r in rows))
    assert result["confirmation"] == confirmation_for(result["branches"])
    stages = [stage for groups in result["billing"]["by_branch"].values() for stage in groups.values()]
    total = result["billing"]["total"]
    assert sum(x["calls"] for x in stages) == total["calls"]
    for name, ids in (("primary", BRANCHES), ("supplement", SUPPLEMENTS)):
        group = [g for b in ids for g in result["billing"]["by_branch"][b].values()]
        for k, subtotal in result["billing"][name].items():
            assert subtotal == sum(g[k] for g in group)
    for key in ("settled", "exposure"):
        assert sum(x[key + "_microusd"] for x in stages) == round(total[key + "_usd"] * 1e6)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", nargs="?", default="score", choices=("score", "check", "check-public", "historical"))
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    if args.action == "check-public":
        check_public(read(RESULT))
        print("Published four-branch corpus verified")
        return
    if args.action == "historical":
        values = historical(browser.verify_contract("form"))
        print({arm: sum(row[arm]["passed"] is True for row in values.values()) for arm in HISTORICAL.values()})
        return
    result = assemble(args.action == "score", args.workers)
    check_public(result)
    if args.action == "score":
        with browser.lock(OUT / ".public-result.lock"):
            if not RESULT.exists():
                browser.write_json(RESULT, result)
    if read(RESULT) != result:
        raise ValueError("Published result differs from sealed candidates, score receipts or billing")
    print({name: g["comparisons"]["direct"]["self_passed"] for name, g in result["branches"].items()})
    print(result["confirmation"], result["billing"]["total"])


if __name__ == "__main__":
    main()
