"""Independently verify the frozen Flash source, narrowed domains, and paired outcomes."""
import argparse
from pathlib import Path

from studies import ledger_read
from studies.study_io import digest, read, sha
from .. import report as primary
from ..run import OUT as BASE, browser, core
from . import run as targeted
from . import subset, entry

RESULT = Path(__file__).with_name("result.json")
BRANCHES = ["contract-b", "contract-subset-b", "contract-entry-b"]


def bill(tag):
    rows = [r for r in ledger_read.calls(BASE / "budget.sqlite3") if r["purpose"].startswith(tag + "/")]
    return {stage: {"calls": len(group), "settled_microusd": sum(r["actual"] or 0 for r in group),
                    "exposure_microusd": sum(r["reserved"] if r["actual"] is None else r["actual"] for r in group)}
            for stage in ("build", "plan")
            for group in [[r for r in rows if r["purpose"].split("/")[1] == stage]]}


def assemble(score, workers):
    assert (BASE / "seal.json").is_file()
    assert primary.RESULT.is_file(), "Wait until the primary four branches have published their official receipts"
    gate = {b: sha(BASE / b / "seal.json") for b in (*primary.BRANCHES, *primary.SUPPLEMENTS)}
    ctx = browser.verify_contract("form")
    baseline = primary.historical(ctx)
    raw = core.parse(read(targeted.LAST)["choices"][0]["message"]["content"])
    updated, proof = subset.project(raw)
    assert read(subset.OUT / "form/build/projection.json") == proof
    assert read(subset.OUT / "form/build/corrected-raw.json") == updated
    module, module_proof = entry.relocate(read(BASE / "inputs/form/public.json"), updated)
    assert read(entry.OUT / "form/build/relocated-raw.json") == module
    assert read(entry.OUT / "form/build/relocation.json") == module_proof
    current = {}
    for branch in BRANCHES:
        seal = read(BASE / branch / "seal.json")
        reg = read(BASE / branch / "registration.json")
        assert sha(BASE / branch / "registration.json") == seal["registration_sha256"]
        assert reg["utc"] <= seal["utc"] and seal["unchanged_a_seal"] == sha(targeted.A_SEAL)
        assert all(sha(targeted.ROOT / p) == checksum for p, checksum in reg["files"].items())
        current[branch] = primary.sealed_candidates(branch, seal)
    results = primary.score_branches(current, baseline, ctx, score, workers)
    a = primary.sealed_candidates("delivery-a", read(targeted.A_SEAL))
    # A may only reuse existing official receipts. The primary run owns its scoring.
    shared_a = primary.score_branches({"delivery-a": a}, baseline, ctx, False, workers)["delivery-a"]
    assert shared_a == read(primary.RESULT)["branches"]["delivery-a"]
    for branch, record in results.items():
        assert record["comparisons"] == {c: primary.paired(record["rows"], c) for c in (*primary.HISTORICAL.values(), "fixed")}
    return {"study": "Flash questionnaire B schema correction", "model": targeted.batch.MODEL,
            "project": "form", "tasks": list(targeted.TASKS), "independent_confirmations": 0,
            "reused_a_sha256": sha(targeted.A_SEAL), "reused_a": shared_a,
            "primary_result_sha256": sha(primary.RESULT),
            "model_values_reply": core.parse(read(targeted.OUT / "form/build/edit/response.json")["choices"][0]["message"]["content"]),
            "projection": proof, "entry_relocation": module_proof, "registrations": {b: sha(BASE / b / "registration.json") for b in BRANCHES},
            "gate_sha256": gate, "public_build_outcomes": {b: read(BASE / b / "form/build/status.json") for b in BRANCHES},
            "billing": {b: bill(b) for b in BRANCHES}, "branches": results}


def check_public(result):
    reference = read(primary.RESULT)
    assert result["primary_result_sha256"] == sha(primary.RESULT)
    assert result["reused_a"] == reference["branches"]["delivery-a"]
    assert result["independent_confirmations"] == 0
    controls = result["reused_a"]["rows"]
    for name, branch in result["branches"].items():
        assert [row["task"] for row in branch["rows"]] == result["tasks"]
        for row, original in zip(branch["rows"], controls):
            assert all(row[k] == original[k] for k in primary.HISTORICAL.values())
        assert branch["comparisons"] == {c: primary.paired(branch["rows"], c)
                                          for c in (*primary.HISTORICAL.values(), "fixed")}
    proof = result["projection"]
    for k, before in proof["before"].items():
        after = proof["after"][k]
        assert len(after) == 8 and [v for v in before if v in after] == after
        assert [v for v in before if v not in after] == proof["removed"][k]
    ep = result["entry_relocation"]
    assert ep["source_sha256"] == ep["relocated_slice_sha256"]
    assert all(x["old"] == x["new"] for x in proof["unchanged_sha256"].values())
    assert result["billing"]["contract-entry-b"]["plan"]["calls"] <= 20
    assert all(result["billing"][n]["build"]["calls"] == 0 for n in ("contract-subset-b", "contract-entry-b"))
    assert result["billing"]["contract-b"]["build"]["calls"] == 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("score", "check", "check-public"))
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    result = read(RESULT) if args.action == "check-public" else assemble(args.action == "score", args.workers)
    check_public(result)
    if args.action == "score":
        core.save(RESULT, result)
    assert read(RESULT) == result
    print({b: v["comparisons"]["direct"] for b, v in result["branches"].items()})
