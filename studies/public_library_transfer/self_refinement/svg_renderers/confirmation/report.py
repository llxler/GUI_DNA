"""Pair new SVG libraries with previously sealed Direct pages and verify captured charges."""

from collections import Counter
from hashlib import sha256
import argparse
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, digest, read, sha
from . import run, launch
from ..source_delivery import run as delivery

RESULT = run.HERE / "result.json"
REPS = ("A", "B")


def controls():
    old = read(run.OLD)
    sealed = read(run.dom.OUT / "seal.json")
    assert old["seal_sha256"] == sha(run.dom.OUT / "seal.json")
    assert sealed["delivery_sha256"] == sha(delivery.OUT / "seal.json")
    out = []
    for r in old["rows"]:
        if (r["group"], r["arm"]) != ("direct", "delivery"):
            continue
        task = r["task"]
        src = next(
            s
            for s in sealed["rows"]
            if (s["group"], s["arm"], s["task"]) == ("direct", "delivery", task)
        )
        entry = {
            k: r[k]
            for k in (
                "group",
                "arm",
                "task",
                "status",
                "passed",
                "report_sha256",
                "page_digest",
            )
        }
        if src["status"] == "valid":
            browser.verify_page(ROOT / src["page"], src["files"], run.comp.CHART)
            assert digest(src["files"]) == r["page_digest"]
            frozen = read(
                run.dom.OUT
                / "browser/scores/svg-chart"
                / f"task-{task}"
                / r["page_digest"]
                / "score.json"
            )
            payload = run.dom.OUT / frozen["report"]
            assert sha(payload) == r["report_sha256"]
            assert (
                browser.verdict(read(payload), frozen["exit_code"], task) == r["passed"]
            )
        decision = read(delivery.OUT / "direct" / str(task) / "decision.json")
        receipt = (
            run.base.OUT
            / "calls/direct"
            / str(task)
            / str(decision["chosen_attempt"])
            / "response.json"
        )
        assert (
            sha(receipt) == read(receipt.with_name("settled.json"))["response_sha256"]
        )
        entry.update(
            response_sha256=sha(receipt), selected_attempt=decision["chosen_attempt"]
        )
        out.append(entry)
    assert [r["task"] for r in out] == list(run.base.TASKS)
    return out


def summarize(rows):
    expected = {(r["group"], r["arm"], r["task"]): r["passed"] for r in rows}
    assert len(rows) == len(expected) == 100
    out = {}
    for g in REPS:
        by = {
            "planned": (g, "planned"),
            "fixed": (g, "fixed"),
            "direct_delivery": ("direct", "delivery"),
        }
        common = [
            t
            for t in run.base.TASKS
            if all(expected[*v, t] is not None for v in by.values())
        ]
        sets = {k: {t for t in common if expected[*v, t]} for k, v in by.items()}
        out[g] = {
            "common": common,
            "passed": {k: sorted(v) for k, v in sets.items()},
            "non_asset": {k: sorted(v - {1}) for k, v in sets.items()},
            "only_plan_vs_delivery": sorted(sets["planned"] - sets["direct_delivery"]),
            "only_delivery_vs_plan": sorted(sets["direct_delivery"] - sets["planned"]),
        }
    return out


def evidence(reg):
    calls = ledger_read.calls(run.OUT / "budget.sqlite3")
    idx = {r["id"]: r for r in calls}
    previous_ids = {
        read(p).get("id") for p in (run.base.OUT / "calls").rglob("response.json")
    }
    seen = set()
    ids = set()
    out = []
    cost = {}
    for path in sorted((run.OUT / "calls").rglob("request.json")):
        request = read(path)
        row = idx[request["call_id"]]
        body = request["body"]
        assert row["purpose"] == str(path.parent.relative_to(run.OUT / "calls"))
        assert body["model"] == row["model"] == run.transport.MODEL and body[
            "provider"
        ]["only"] == ["SiliconFlow"]
        assert (
            body["provider"]["max_price"] == run.transport.MAX_PRICE
            and row["id"] not in seen
        )
        seen.add(row["id"])
        parts = row["purpose"].split("/")
        key = "/".join(parts[:2])
        v = cost.setdefault(
            key,
            {"calls": 0, "settled_microusd": 0, "unsettled": 0, "exposure_microusd": 0},
        )
        v["calls"] += 1
        v["exposure_microusd"] += (
            row["actual"] if row["actual"] is not None else row["reserved"]
        )
        call = {"purpose": row["purpose"], "request_sha256": sha(path)}
        if row["actual"] is None:
            v["unsettled"] += 1
            call["status"] = "unresolved"
        else:
            receipt = path.with_name("response.json")
            resp = read(receipt)
            provider_id = resp["id"]
            assert provider_id not in previous_ids and provider_id not in ids
            assert (
                sha(receipt) == read(path.with_name("settled.json"))["response_sha256"]
            )
            assert (
                resp["provider"] == "SiliconFlow"
                and abs(row["actual"] / 1e6 - float(resp["usage"]["cost"])) < 0.0000011
            )
            ids.add(provider_id)
            v["settled_microusd"] += row["actual"]
            raw = resp["choices"][0]["message"].get("content") or ""
            call.update(
                status="returned",
                provider_id=provider_id,
                response_sha256=sha(receipt),
                content_sha256=sha256(raw.encode()).hexdigest(),
                finish_reason=resp["choices"][0]["finish_reason"],
                prompt_tokens=resp["usage"]["prompt_tokens"],
                completion_tokens=resp["usage"]["completion_tokens"],
            )
        out.append(call)
    assert seen == set(idx)
    old = {
        g: {
            f: sha256(s.encode()).hexdigest()
            for f, s in read(run.base.OUT / g / "modules.json").items()
        }
        for g in REPS
    }
    new = {
        g: {
            f: sha256(s.encode()).hexdigest()
            for f, s in read(run.OUT / g / "modules.json").items()
        }
        for g in REPS
    }
    old_hashes = {h for v in old.values() for h in v.values()}
    same = [(g, n) for g, v in new.items() for n, h in v.items() if h in old_hashes]
    counts = Counter(h for v in new.values() for h in v.values())
    return (
        out,
        cost,
        {
            "new": new,
            "prior": old,
            "new_matching_any_prior": same,
            "repeated_new_source_hashes": {k: v for k, v in counts.items() if v > 1},
        },
    )


def assemble():
    run.register()
    launch.register()
    sealed = read(run.OUT / "seal.json")
    reg = read(run.OUT / "registration.json")
    assert sealed["registration_sha256"] == sha(
        run.OUT / "registration.json"
    ) and sealed["previous_controls_sha256"] == sha(run.OLD)
    contract = browser.verify_contract(run.comp.CHART)
    assert contract == reg["spec"]["harness"]
    old = controls()
    browser.OUT = run.OUT
    scored = browser.evaluate(sealed["rows"], run.OUT, {run.comp.CHART: contract}, 5)
    rows = old + [
        {
            k: r.get(k)
            for k in (
                "group",
                "arm",
                "task",
                "status",
                "plan",
                "reason",
                "report_sha256",
            )
        }
        | {
            "page_digest": digest(r["files"]) if r.get("files") else None,
            "passed": False
            if r["status"] in ("build_failed", "invalid")
            else r["passed"],
        }
        for r in scored
    ]
    calls, cost, modules = evidence(reg)
    builds = {}
    for g, b in sealed["builds"].items():
        builds[g] = {k: v for k, v in b.items() if k not in ("first", "selected")}
        if "selected" in b:
            final = b["selected"]
            builds[g]["after"] = run.observe.observe(
                run.OUT, ROOT / final["page"], final["files"]
            )
    return {
        "model": run.transport.MODEL,
        "provider": "SiliconFlow",
        "registered_utc": reg["utc"],
        "sealed_utc": sealed["utc"],
        "registration_sha256": sha(run.OUT / "registration.json"),
        "seal_sha256": sha(run.OUT / "seal.json"),
        "protocol_sha256": sha(run.HERE / "PROTOCOL.md"),
        "implementation_sha256": sha(run.HERE / "run.py"),
        "observer_compatibility_sha256": sha(run.OUT / "observer-compatibility.json"),
        "control_source_sha256": sha(run.OLD),
        "budget": ledger_read.totals(run.OUT / "budget.sqlite3"),
        "cost_by_phase": cost,
        "calls": calls,
        "module_sources": modules,
        "builds": builds,
        "rows": rows,
        "paired": summarize(rows),
    }


def check(out):
    assert out["paired"] == summarize(out["rows"]) and out[
        "control_source_sha256"
    ] == sha(run.OLD)
    assert out["protocol_sha256"] == sha(run.HERE / "PROTOCOL.md") and out[
        "implementation_sha256"
    ] == sha(run.HERE / "run.py")
    assert (
        out["budget"]["calls"] == len(out["calls"])
        and out["budget"]["cap_usd"] == run.CAP
    )
    assert out["budget"]["exposure_usd"] <= run.CAP
    assert round(out["budget"]["settled_usd"] * 1e6) == sum(
        r["settled_microusd"] for r in out["cost_by_phase"].values()
    )
    assert out["budget"]["unsettled_calls"] == sum(
        r["unsettled"] for r in out["cost_by_phase"].values()
    )
    original = {
        r["task"]: r
        for r in read(run.OLD)["rows"]
        if (r["group"], r["arm"]) == ("direct", "delivery")
    }
    for r in out["rows"]:
        if r["group"] == "direct":
            assert (r["page_digest"], r["report_sha256"], r["passed"]) == tuple(
                original[r["task"]][v]
                for v in ("page_digest", "report_sha256", "passed")
            )
        if r["status"] == "valid":
            assert len(r["report_sha256"]) == 64 and isinstance(r["passed"], bool)
        elif r["status"] == "missing":
            assert r["passed"] is None
        else:
            assert r["status"] in ("build_failed", "invalid") and r["passed"] is False
    print(
        {
            g: {k: len(v) for k, v in r["passed"].items()}
            for g, r in out["paired"].items()
        },
        out["budget"],
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("phase", choices=["score", "check", "check-local"])
    phase = p.parse_args().phase
    result = read(RESULT) if phase == "check" else assemble()
    check(result)
    if phase == "score":
        core.save(RESULT, result)
    if phase == "check-local":
        assert result == read(RESULT)
