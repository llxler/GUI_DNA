"""Reconcile exact transport replacements with the first observed file-repair candidates."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
import tempfile
from unittest.mock import patch

from gui_dna.provider import parse_json
from studies import ledger_read
from studies.study_io import ROOT, read, sha, digest
from .. import report as primary
from ..confirmation import report as earlier
from ..file_repair import report as source
from ..file_repair import run as original
from ..run import browser, core

OUT = ROOT / "artifacts/flash-form-transport-20261125"
HERE = Path(__file__).resolve().parent
RESULT = HERE / "result.json"
TARGETS = ("file-a/18", "file-a/19", "file-a/20", "file-b/14", "file-b/15", "file-b/16")


def totals(rows):
    return {"calls": len(rows), "unsettled_calls": sum(r["actual"] is None for r in rows),
            "settled_usd": round(sum(r["actual"] or 0 for r in rows) / 1e6, 6),
            "exposure_usd": round(sum(r["reserved"] if r["actual"] is None else r["actual"]
                                       for r in rows) / 1e6, 6)}


def replacements(seal, reg):
    given = reg["original_requests"]
    assert set(given) == set(seal["rows"]) == set(TARGETS)
    old_calls = {r["id"]: r for r in ledger_read.calls(original.OUT / "budget.sqlite3")}
    new_calls = {r["id"]: r for r in ledger_read.calls(OUT / "budget.sqlite3")}
    seen = set()
    validated = []
    for key in TARGETS:
        branch, task = key.split("/")
        n = int(task)
        old = original.OUT / branch / "form/self" / task
        new = OUT / branch / "form/self" / task
        evidence = seal["rows"][key]
        old_req, new_req = (d / "call/request.json" for d in (old, new))
        assert sha(old_req) == given[key] == evidence["original_request_sha256"]
        assert sha(new_req) == evidence["request_sha256"]
        old_request, new_request = read(old_req), read(new_req)
        assert old_request["body"] == new_request["body"]
        assert old_calls[old_request["call_id"]]["actual"] is None
        assert not (old / "call/response.json").exists() and read(old / "result.json")["status"] == "missing"
        ticket = new_request["call_id"]
        assert ticket in new_calls and ticket not in seen
        seen.add(ticket)
        row = read(new / "result.json")
        assert row == evidence["row"] and sha(new / "result.json") == evidence["result_sha256"]
        assert row["model"] == primary.MODEL and row["task"] == n and row["arm"] == "self" and row["project"] == "form"
        pkg = read(original.OUT / branch / "form/build/package.json")
        original_seal = read(original.OUT / branch / "seal.json")
        assert sha(original.OUT / branch / "form/build/package.json") == original_seal["package_sha256"]
        prompt = core.plan_messages(read(original.OUT / "inputs/form/public.json"), n, pkg)
        assert new_request["body"]["messages"] == prompt
        if row.get("response_sha256"):
            receipt = new / "call/response.json"
            assert row["response_sha256"] == sha(receipt) == read(new / "call/settled.json")["response_sha256"]
            payload = read(receipt)
            actual = new_calls[ticket]["actual"]
            assert actual is not None and abs(actual - payload["usage"]["cost"]*1e6) <= 1.01
            if row["status"] == "valid":
                assert (ROOT / row["page"]).resolve() == (new / "page").resolve()
                browser.verify_page(ROOT / row["page"], row["files"], "form")
                text = payload["choices"][0]["message"].get("content") or ""
                with tempfile.TemporaryDirectory() as td:
                    rebuilt = core.materialize("form", pkg, parse_json(text), Path(td) / "page")
                    assert rebuilt == row["files"]
        else:
            assert row["status"] == "missing"
        provenance = {"original_request_sha256": sha(old_req), "replacement_request_sha256": sha(new_req),
                      "identical_body_sha256": digest(old_request["body"]),
                      "original_reserved_microusd": old_calls[old_request["call_id"]]["reserved"],
                      "replacement_result_sha256": sha(new / "result.json")}
        validated.append((key, branch, n, row, provenance))
    assert seen == set(new_calls)
    return validated, totals(list(new_calls.values()))


def merged(original_study, additions):
    branches = deepcopy(original_study["branches"])
    for key, record in additions.items():
        branch, task = key.split("/")
        rows = branches[branch]["rows"]
        row = next(r for r in rows if r["task"] == int(task))
        assert row["self"] == record["original"] and row["self"]["status"] == "missing"
        row["self"] = record["replacement"]
    for b in branches.values():
        rows = b["rows"]
        b["self_status_counts"] = dict(Counter(r["self"]["status"] for r in rows))
        b["comparisons"] = {c: primary.paired(rows, c) for c in (*primary.HISTORICAL.values(), "fixed")}
    with patch.object(earlier, "REPS", original.BRANCHES):
        decision = earlier.decision(branches, original_study["previous_sources"])
    return branches, decision


def assemble(score, workers):
    first = read(source.RESULT)
    source.check_public(first)
    original_seal = read(original.OUT / "seal.json")
    reg = read(OUT / "registration.json")
    seal = read(OUT / "seal.json")
    assert reg["protocol_sha256"] == sha(HERE / "PROTOCOL.md")
    assert reg["utc"] <= seal["utc"] and sha(OUT / "registration.json") == seal["registration_sha256"]
    assert reg["original_registration_sha256"] == original_seal["registration_sha256"]
    assert sha(original.OUT / "seal.json") == first["seal_sha256"]
    jobs, amount = replacements(seal, reg)
    contract = browser.verify_contract("form")

    def collect(job):
        key, branch, n, row, provenance = job
        status = row["status"]
        assert status in ("missing", "invalid", "valid")
        cell = {k: row[k] for k in ("status", "response_sha256") if k in row}
        if status == "valid":
            ds = digest(row["files"])
            receipt = (browser.run_one(OUT, "form", n, ROOT / row["page"], row["files"], contract) if score
                       else primary.check_receipt(OUT, n, ds, contract))
            cell.update(passed=receipt["passed"], report_sha256=receipt["report_sha256"], files_digest=ds)
        else:
            cell["passed"] = None if status == "missing" else False
        original_cell = next(r["self"] for r in first["branches"][branch]["rows"] if r["task"] == n)
        return key, {"original": original_cell, "replacement": cell, **provenance}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        added = dict(pool.map(collect, jobs))
    branches, decision = merged(first, added)
    pilot = read(earlier.RESULT)
    stage_bills = {"pilot": pilot["pilot"]["billing"], "first_confirmation": pilot["billing"]["total"],
                   "file_repair": first["billing"]["total"], "transport_completion": amount}
    return {"project": "form", "model": primary.MODEL, "tasks": list(primary.TASKS),
            "file_repair_result_sha256": sha(source.RESULT), "registration_sha256": sha(OUT / "registration.json"),
            "seal_sha256": sha(OUT / "seal.json"), "upstream_contract_sha256": digest(contract),
            "original_comparisons": {k: b["comparisons"] for k,b in first["branches"].items()},
            "original_confirmation": first["confirmation"], "replacements": added, "branches": branches,
            "confirmation": decision, "stage_billing": stage_bills,
            "all_stages_billing": earlier.expenses(first["all_stages_billing"], amount)}


def check_public(result):
    first = read(source.RESULT)
    source.check_public(first)
    assert sha(source.RESULT) == result["file_repair_result_sha256"]
    assert result["tasks"] == list(primary.TASKS) and result["model"] == first["model"]
    assert result["original_comparisons"] == {k:b["comparisons"] for k,b in first["branches"].items()}
    assert result["original_confirmation"] == first["confirmation"]
    added = result["replacements"]
    assert set(added) == set(TARGETS)
    for key, record in added.items():
        assert record["original"]["status"] == "missing" and record["original"]["passed"] is None
        new = record["replacement"]
        assert new["status"] in ("missing", "valid", "invalid")
        assert (type(new["passed"]) is bool and len(new["files_digest"]) == len(new["report_sha256"]) == 64
                if new["status"] == "valid" else new["passed"] is (None if new["status"]=="missing" else False))
        assert all(len(record[k]) == 64 for k in ("original_request_sha256","replacement_request_sha256",
                                                  "identical_body_sha256","replacement_result_sha256"))
        assert record["original_reserved_microusd"] > 0
    branches, decision = merged(first, added)
    assert branches == result["branches"] and decision == result["confirmation"]
    stage = result["stage_billing"]
    pilot = read(earlier.RESULT)
    assert stage["pilot"] == pilot["pilot"]["billing"] and stage["first_confirmation"] == pilot["billing"]["total"]
    assert stage["file_repair"] == first["billing"]["total"] and stage["transport_completion"]["calls"] == len(TARGETS)
    assert result["all_stages_billing"] == earlier.expenses(first["all_stages_billing"], stage["transport_completion"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("score","check","check-public"))
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    result = read(RESULT) if args.action == "check-public" else assemble(args.action == "score", args.workers)
    check_public(result)
    if args.action == "score":
        core.save(RESULT, result)
    else:
        assert read(RESULT) == result
    print(result["confirmation"], result["all_stages_billing"])
