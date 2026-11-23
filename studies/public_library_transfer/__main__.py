"""Validate published trial summaries without a browser, model weights or credentials."""

import argparse
import json
from pathlib import Path

from studies.study_io import sha

RESULTS = Path(__file__).resolve().parents[1] / "results"
DATE = "20261123"


def load(stem):
    return json.loads(
        (RESULTS / f"public-library-transfer-{stem}{DATE}.json").read_text()
    )


def result(row):
    if row["status"] == "missing":
        return None
    if row["status"] in {"invalid", "build_failed"}:
        return False
    if row["status"] != "valid" or type(row["passed"]) is not bool:
        raise ValueError("A valid deployment must have an observed official result")
    return row["passed"]


def check_pairs(summary):
    """Recompute paired candidate outcomes from the public per-target records."""
    groups = {}
    for row in summary["rows"]:
        key = (row["project"], row["arm"], row["builder"], row["rep"], row["planner"])
        targets = groups.setdefault(key, {})
        if row["task"] in targets:
            raise ValueError(f"Duplicate public result: {key}/{row['task']}")
        targets[row["task"]] = result(row)
    for entry in summary["pairs"]:
        project, builder, rep, model = (
            entry[k] for k in ("project", "builder", "rep", "planner")
        )
        plan = groups[(project, "plan", builder, rep, model)]
        other_key = (
            (project, "direct", None, 0, model)
            if entry["comparator"] == "direct"
            else (project, "fixed", builder, rep, None)
        )
        other = groups[other_key]
        if set(plan) != set(other):
            raise ValueError(f"Unmatched task identities in {other_key}")
        for field, subset in (
            ("all_tasks", set(plan)),
            ("milestones", set(plan) & {4, 8, 12, 16, 20}),
        ):
            given = entry[field]
            known = [
                (plan[t], other[t])
                for t in subset
                if plan[t] is not None and other[t] is not None
            ]
            expected = {
                "planned": len(subset),
                "paired": len(known),
                "both": known.count((True, True)),
                "plan_only": known.count((True, False)),
                "comparator_only": known.count((False, True)),
                "neither": known.count((False, False)),
                "plan_passed": sum(x for x, _ in known),
                "comparator_passed": sum(y for _, y in known),
            }
            if any(given[k] != value for k, value in expected.items()):
                raise ValueError(
                    f"Counts do not agree with the published task rows: {project}/{field}"
                )
    return len(summary["rows"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", required=True)
    parser.parse_args()
    overview = load("overview-")
    for src, fingerprint in overview["source_sha256"].items():
        if (
            src.startswith("studies/results/")
            and sha(RESULTS / Path(src).name) != fingerprint
        ):
            raise ValueError(f"Published source hash differs: {src}")
    rows = {
        label: check_pairs(load(stem))
        for label, stem in (
            ("Qwen", ""),
            ("remote", "remote-"),
            ("remote milestones", "remote-milestones-"),
        )
    }
    coverage = overview["public_targets_by_project"]
    if len(coverage) != 10 or any(
        targets != list(range(1, 21)) for targets in coverage.values()
    ):
        raise ValueError("Distinct public Web-Bench scope changed")
    if len(load("history-")["historical_cohorts"]) != 60:
        raise ValueError("Historical cohort count changed")
    billed = sum(v["settled_usd"] for v in overview["ledgers"].values())
    exposure = sum(v["exposure_usd"] for v in overview["ledgers"].values())
    if (
        round(billed, 6) != overview["ledger_settled_usd"]
        or round(exposure, 6) != overview["ledger_exposure_usd"]
        or exposure > 20
    ):
        raise ValueError("Budget reconciliation failed")
    print(
        json.dumps(
            {
                "check": "published paired rows, source identities, unique targets and stage budgets",
                "rows": rows,
                "distinct_webbench_targets": sum(map(len, coverage.values())),
                "settled_usd": round(billed, 6),
                "exposure_usd": round(exposure, 6),
                "new_api_calls": 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
