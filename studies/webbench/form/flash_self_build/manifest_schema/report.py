"""Reproduce both typed-manifest scores from separately sealed candidate trees."""
import argparse
from pathlib import Path

from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, read, sha
from .. import report as primary
from .run import BRANCHES

HERE = Path(__file__).resolve().parent
SUMMARY = HERE / "result.json"


def assemble(score, workers):
    out = primary.OUT
    parent = read(out / "seal.json")
    reg = read(out / "manifest-schema-registration.json")
    assert all(sha(ROOT / name) == value for name, value in reg["files"].items())
    assert reg["branches"] == list(BRANCHES) and reg["utc"] <= parent["utc"]
    assert reg["parent_sha256"] == parent["staged_registration_sha256"]
    evidence = {}
    for k in BRANCHES:
        data = read(out / k / "seal.json")
        assert (out / k / "seal.json").stat().st_mtime <= (out / "seal.json").stat().st_mtime
        evidence[k] = primary.sealed_candidates(k, data)
    contract = browser.verify_contract("form")
    branches = primary.score_branches(evidence, primary.historical(contract), contract, score, workers)
    source_ids = {b["build"]["source_sha256"] for b in branches.values()}
    complete = all(len(b["comparisons"]["direct"]["tasks"]) == 20 for b in branches.values())
    passes = [b["comparisons"]["direct"]["self_passed"] for b in branches.values()]
    confirmed = complete and None not in source_ids and len(source_ids) == 2 and min(passes) >= 10
    return {"model": primary.MODEL, "project": "form", "confirmed": confirmed,
            "registration_sha256": sha(out / "manifest-schema-registration.json"), "parent_seal_sha256": sha(out / "seal.json"),
            "seal_sha256": {k: sha(out / k / "seal.json") for k in BRANCHES}, "branches": branches}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("score", "check"))
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    summary = assemble(args.action == "score", args.workers)
    if args.action == "score" and not SUMMARY.is_file():
        core.save(SUMMARY, summary)
    assert read(SUMMARY) == summary
    print({k: (v["comparisons"]["direct"]["self_passed"], v["comparisons"]["fixed"]["comparator_passed"])
           for k, v in summary["branches"].items()}, summary["confirmed"])
