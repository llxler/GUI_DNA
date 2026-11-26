"""Verify the targeted file changes and pair every scored page with its frozen controls."""
import argparse
from pathlib import Path
from unittest.mock import patch

from studies import ledger_read
from studies.study_io import ROOT, read, sha
from .. import report as primary
from ..confirmation import report as prior
from . import run

RESULT = Path(__file__).with_name("result.json")


def review_sources(key, seal):
    folder = run.OUT / key / "form/build"
    state = seal["build"]
    public = read(run.OUT / "inputs/form/public.json")
    assert public == read(primary.ORIGINAL / "inputs/form/public.json")
    messages = run.core.build_messages(public)
    messages[0]["content"] += "\n" + run.GUIDE
    first = read(folder / "attempt-1/request.json")["body"]
    assert first["model"] == primary.MODEL and first["messages"] == messages
    assert first["reasoning"] == {"enabled": False}
    sources = None
    delivery = None
    format_attempts = []
    for attempt in sorted(folder.glob("attempt-*")):
        reply = attempt / "response.json"
        if reply.is_file():
            format_attempts.append(primary.delivery_stats(reply))
        accepted = attempt / "normalized-raw.json"
        if accepted.is_file():
            text = read(attempt / "response.json")["choices"][0]["message"]["content"]
            sources, adaptations = run.package_response(text, public)
            assert sources == read(accepted) and adaptations == read(attempt / "adaptations.json")
            delivery = {"attempt": attempt.name, **adaptations}
    versions = []
    selected = state.get("selected_version")
    for item in state["versions"]:
        v = item["version"]
        path = folder / f"v{v}"
        if v:
            patch_dir = folder / f"repair-{v}"
            edit = read(patch_dir / "patch.json")
            response = read(patch_dir / "call/response.json")["choices"][0]["message"]["content"]
            assert edit["content"] in response
            settled = read(patch_dir / "call/settled.json")
            assert sha(patch_dir / "call/response.json") == settled["response_sha256"]
            sources = run.public_checks.replace_source(sources, edit["path"], edit["content"])
        assert sources == read(path / "raw.json") and item["source_sha256"] == sha(path / "raw.json")
        observation = read(path / "diagnosis.json")
        assert sha(path / "diagnosis.json") == item["diagnosis_sha256"]
        assert observation["loadable"] == item["loadable"]
        assert item["issues"] == observation["issues"] + observation["advisories"]
        if v == selected:
            pkg = run.core.package(public, sources)
            assert pkg == read(folder / "package.json")
            assert sha(folder / "package.json") == seal["package_sha256"] == observation["package_sha256"]
            assert state["fixed"] == observation["fixed"]
        versions.append({**item, "file": edit["path"] if v else None})
    return {"selected_version": selected, "format_errors": state["format_errors"], "versions": versions,
            "delivery": delivery, "whole_response_receipts": format_attempts,
            "script_sha256": prior.script_fingerprint(read(folder / "package.json")) if selected is not None else None}


def coverage(rows):
    """Independent full-schedule outcomes; paired comparisons keep their own denominator."""
    assert [r["task"] for r in rows] == list(primary.TASKS)
    report = {}
    for arm in ("self", "fixed", *primary.HISTORICAL.values()):
        passed = [r["task"] for r in rows if r[arm]["passed"] is True]
        missing = [r["task"] for r in rows if r[arm]["passed"] is None]
        report[arm] = {"scheduled": len(rows), "observed": len(rows) - len(missing),
                       "passed": len(passed), "passed_tasks": passed, "missing_tasks": missing}
    return report


def missing_evidence(branches):
    """Link original unobserved transfers to their frozen request and read-only reservation."""
    out = run.OUT
    calls = {r["id"]: r for r in ledger_read.calls(out / "budget.sqlite3")}
    seen = set()
    evidence = []
    for branch, trial in branches.items():
        for row in trial["rows"]:
            if row["self"]["passed"] is not None:
                continue
            task = row["task"]
            destination = out / branch / "form/self" / str(task)
            original = read(destination / "result.json")
            assert original["status"] == "missing"
            item = {"branch": branch, "task": task, "status": "missing", "reason": original.get("reason"),
                    "result_sha256": sha(destination / "result.json")}
            req = destination / "call/request.json"
            if req.is_file():
                request = read(req)
                ticket = request["call_id"]
                assert ticket not in seen
                seen.add(ticket)
                record = calls[ticket]
                assert record["model"] == primary.MODEL and record["actual"] is None
                assert record["purpose"] == f"{branch}/plan/target/form/self/{task}"
                assert not req.with_name("response.json").exists() and not req.with_name("settled.json").exists()
                item.update(request_sha256=sha(req), reservation_microusd=record["reserved"],
                            ledger_purpose=record["purpose"], provider_reply_observed=False)
            evidence.append(item)
    unresolved_plans = {r["id"] for r in calls.values() if r["actual"] is None and "/plan/" in r["purpose"]}
    assert seen == unresolved_plans
    return evidence


def assemble(score, workers):
    out = run.OUT
    registered = read(out / "registration.json")
    seal = read(out / "seal.json")
    assert registered["utc"] <= seal["utc"] and registered["model"] == primary.MODEL
    assert registered["tasks"] == list(primary.TASKS) and set(seal["branches"]) == set(run.BRANCHES)
    assert seal["registration_sha256"] == sha(out / "registration.json")
    for p, checksum in registered["files"].items():
        assert sha(ROOT / p) == checksum
    previous = read(prior.RESULT)
    prior.check_public(previous)
    old_sources = dict(previous["pilot"]["candidate_sources"])
    for key, trial in previous["branches"].items():
        old_sources[key] = {k: trial["build"].get(k) for k in ("source_sha256", "script_sha256")}
    contract = primary.browser.verify_contract("form")
    baseline = primary.historical(contract)
    with patch.multiple(primary, OUT=out, BRANCHES=run.BRANCHES, SUPPLEMENTS=()):
        prepared = {}
        for key in run.BRANCHES:
            evidence = seal["branches"][key]
            assert read(out / key / "seal.json") == evidence
            build, candidates = primary.sealed_candidates(key, evidence)
            prepared[key] = ({**build, **review_sources(key, evidence)}, candidates)
        branches = primary.score_branches(prepared, baseline, contract, score, workers)
        billing = primary.billing()
    for trial in branches.values():
        trial["full_schedule"] = coverage(trial["rows"])
    transfers = missing_evidence(branches)
    with patch.object(prior, "REPS", run.BRANCHES):
        decision = prior.decision(branches, old_sources)
    return {"model": primary.MODEL, "project": "form", "tasks": list(primary.TASKS), "missing_transfers": transfers,
            "registration_sha256": seal["registration_sha256"], "seal_sha256": sha(out / "seal.json"),
            "previous_sha256": sha(prior.RESULT), "original_report_sha256": sha(primary.BASELINE),
            "branches": branches, "confirmation": decision, "previous_sources": old_sources,
            "billing": billing, "all_stages_billing": prior.expenses(previous["pilot_and_confirmation_billing"], billing["total"])}


def check_public(result):
    assert result["model"] == primary.MODEL and result["tasks"] == list(primary.TASKS)
    before = read(prior.RESULT)
    prior.check_public(before)
    assert result["previous_sha256"] == sha(prior.RESULT) and result["original_report_sha256"] == sha(primary.BASELINE)
    prior_rows = next(iter(before["branches"].values()))["rows"]
    assert set(result["branches"]) == set(run.BRANCHES)
    missing = set()
    for branch, trial in result["branches"].items():
        assert trial["full_schedule"] == coverage(trial["rows"])
        missing.update((branch, n) for n in trial["full_schedule"]["self"]["missing_tasks"])
        for row, baseline in zip(trial["rows"], prior_rows, strict=True):
            assert row["task"] == baseline["task"]
            assert all(row[k] == baseline[k] for k in primary.HISTORICAL.values())
            for k in ("self", "fixed"):
                cell = row[k]
                if cell["status"] == "valid":
                    assert type(cell["passed"]) is bool and len(cell["report_sha256"]) == 64
                else:
                    assert cell["passed"] is (None if cell["status"] == "missing" else False)
        assert trial["comparisons"] == {arm: primary.paired(trial["rows"], arm) for arm in (*primary.HISTORICAL.values(), "fixed")}
    missing_transfers = result["missing_transfers"]
    assert {(r["branch"], r["task"]) for r in missing_transfers} == missing and len(missing_transfers) == len(missing)
    for key in run.BRANCHES:
        pending = [r for r in missing_transfers if r["branch"] == key and "request_sha256" in r]
        stage = result["billing"]["by_branch"][key]["plan"]
        assert len(pending) == stage["unsettled"]
        assert sum(r["reservation_microusd"] for r in pending) == stage["exposure_microusd"] - stage["settled_microusd"]
    with patch.object(prior, "REPS", run.BRANCHES):
        assert result["confirmation"] == prior.decision(result["branches"], result["previous_sources"])
    assert result["all_stages_billing"] == prior.expenses(before["pilot_and_confirmation_billing"], result["billing"]["total"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check-public", "check", "score"))
    parser.add_argument("--workers", type=int, default=5)
    args = parser.parse_args()
    if args.action == "check-public":
        result = read(RESULT)
    else:
        result = assemble(args.action == "score", args.workers)
        if args.action == "score" and not RESULT.is_file():
            run.core.save(RESULT, result)
        assert read(RESULT) == result
    check_public(result)
    print(result["confirmation"], result["all_stages_billing"])
