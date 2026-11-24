"""Verify the public incremental study record without access to private artifacts."""

import argparse
from collections import Counter

from studies.study_io import ROOT, read, sha

SOURCE = ROOT / "studies/results/backbone-matrix-20261124.json"
REPORT = ROOT / "studies/results/incremental-self-table-20261124.json"


NATIVE_REPORT = ROOT / "studies/results/native-incremental-self-table-20261124.json"
RECOVERY_REPORT = ROOT / "studies/results/native-incremental-self-table-resume-20261124.json"


def audit(path=REPORT):
    result = read(path)
    for name, expected in result["files_at_registration"].items():
        if not name.startswith("artifacts/"):
            assert sha(ROOT / name) == expected, name
    original = read(SOURCE)["models"][result["model"]]["rows"]
    indexed = {(r["task"], r["arm"] + "_original"): r for r in original if r["project"] == "table"}
    assert result["tasks"] == [r["task"] for r in result["rows"]] == list(range(1, 21))
    arms = ("direct_original", "self_original", "self_refined", "fixed_refined")
    for arm in arms:
        rows = [(r["task"], r[arm]) for r in result["rows"]]
        outcomes = result["summary"][arm]
        missing = [n for n, r in rows if r["passed"] is None]
        assert outcomes == {"passed": sum(r["passed"] is True for _, r in rows), "observed": 20 - len(missing),
                            "scheduled": 20, "missing_ids": missing}
        for n, row in rows:
            if arm.endswith("_original"):
                old = indexed[n, arm]
                assert all(row[key] == old[key] for key in row)
            if row["status"] == "valid":
                assert type(row["passed"]) is bool and len(row["report_sha256"]) == 64
            elif row["status"] == "missing":
                assert row["passed"] is None
            else:
                assert row["status"] in ("invalid", "build_failed") and row["passed"] is False
        if arm != "self_refined":
            pairs = [(r["task"], r["self_refined"]["passed"], r[arm]["passed"]) for r in result["rows"]
                     if r["self_refined"]["passed"] is not None and r[arm]["passed"] is not None]
            assert result["paired_refined_to"][arm] == {
                "jointly_observed_ids": [n for n, _, _ in pairs],
                "gained_ids": [n for n, new, old in pairs if new and not old],
                "lost_ids": [n for n, new, old in pairs if old and not new]}
    phases = Counter(r["purpose"].split("/")[0] for r in result["calls"])
    assert len({r["request_sha256"] for r in result["calls"]}) == len(result["calls"]) == result["ledger"]["calls"]
    assert all(phases[k] == v["calls"] for k, v in result["cost_by_phase"].items())
    for field in ("settled_usd", "exposure_usd", "unsettled_calls"):
        assert abs(sum(v[field] for v in result["cost_by_phase"].values()) - result["ledger"][field]) < 0.0000005
    expected_cap = {NATIVE_REPORT: 1.99, RECOVERY_REPORT: 1.96, REPORT: 2}[path]
    assert result["ledger"]["exposure_usd"] <= result["budget_usd"] == expected_cap
    if path == NATIVE_REPORT:
        old = read(REPORT)
        assert result["previous_editor_exposure_usd"] == old["ledger"]["exposure_usd"]
        assert result["budget_usd"] + result["previous_editor_exposure_usd"] <= 2
    elif path == RECOVERY_REPORT:
        earlier = {"text_editor": read(REPORT)["ledger"]["exposure_usd"],
                   "native_editor": read(NATIVE_REPORT)["ledger"]["exposure_usd"]}
        assert result["earlier_exposures_usd"] == earlier
        assert result["budget_usd"] + sum(earlier.values()) <= 2
        native_receipts = {r["request_sha256"]: r for r in read(NATIVE_REPORT)["calls"]}
        assert all(r["response_sha256"] == native_receipts[r["request_sha256"]]["response_sha256"]
                   for r in result["reused_settled_tool_responses"])
    print(result["summary"], dict(phases))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    args = parser.add_mutually_exclusive_group()
    args.add_argument("--native", action="store_true")
    args.add_argument("--recovery", action="store_true")
    selected = parser.parse_args()
    path = RECOVERY_REPORT if selected.recovery else NATIVE_REPORT if selected.native else REPORT
    audit(path)
