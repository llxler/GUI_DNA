"""Derive the cross-project comparisons and reconcile unique preparations and ledgers."""

import argparse
from collections import Counter

from studies.ledger_read import totals
from studies.study_io import ROOT, read, sha
from . import core as c
from .report import comparison, observed

RESULTS = ROOT / "studies/results"
OUTPUT = RESULTS / "public-library-transfer-overview-20261123.json"
BILLING = {
    "GPT-OSS library and associated deployments": ROOT
    / "artifacts/public-library-transfer-open-20261123/oss-budget.sqlite3",
    "Mistral library and associated deployments": ROOT
    / "artifacts/public-library-transfer-open-20261123/mistral-budget.sqlite3",
    "GPT-5 library acquisition": c.OUT / "gpt5-budget.sqlite3",
    "Claude Sonnet 4.5 library acquisition": c.OUT / "claude-budget.sqlite3",
    "Mistral Web-Bench deployments": ROOT
    / "artifacts/public-library-transfer-remote-20261123/mistral/budget.sqlite3",
    "GPT-OSS Web-Bench deployments": ROOT
    / "artifacts/public-library-transfer-remote-20261123/oss/budget.sqlite3",
    "Mistral editor prefix-only deployments": ROOT
    / "artifacts/public-library-transfer-holdout-20261123/budget.sqlite3",
    "Other two benchmarks, remote deployments": ROOT
    / "artifacts/public-library-transfer-extra-remote-20261123/budget.sqlite3",
}


def local_projects(report):
    projects = []
    for project in c.PROJECTS:
        selected = [r for r in report["rows"] if r["project"] == project]
        direct = {r["task"]: r for r in selected if r["arm"] == "direct"}
        assert len(direct) == 20
        runs = []
        for tag, builder in c.BUILDERS.items():
            rep = 2 if tag == "codex-2" else 1
            state = c.read(c.OUT / "builds" / project / tag / "status.json")
            filtered = [
                r for r in selected if r["builder"] == builder and r["rep"] == rep
            ]
            plan, fixed = [
                {r["task"]: r for r in filtered if r["arm"] == arm}
                for arm in ("plan", "fixed")
            ]
            assert set(plan) == set(fixed) == set(direct)
            runs.append(
                {
                    "tag": tag,
                    "builder": builder,
                    "rep": rep,
                    "admission": state["status"],
                    "plan_vs_direct": comparison(plan, direct, range(1, 21)),
                    "plan_vs_fixed": comparison(plan, fixed, range(1, 21)),
                }
            )
        projects.append(
            {
                "project": project,
                "direct_valid": sum(r["status"] == "valid" for r in direct.values()),
                "direct_passed": sum(observed(r) is True for r in direct.values()),
                "builds": runs,
            }
        )
    return projects


def build_costs():
    models = {}
    for project in c.PROJECTS:
        for tag in c.BUILDERS:
            folder = c.OUT / "builds" / project / tag
            obj = {
                "project": project,
                "rep": 2 if tag == "codex-2" else 1,
                "admission": read(folder / "status.json")["status"],
            }
            if tag.startswith("codex"):
                usages = []
                for events in sorted(folder.glob("attempt-*/events.jsonl")):
                    import json

                    for line in events.read_text().splitlines():
                        e = json.loads(line)
                        if e["type"] == "turn.completed":
                            usages.append(e["usage"])
                obj.update(
                    completed_subscription_requests=len(usages),
                    input_tokens=sum(v["input_tokens"] for v in usages),
                    output_tokens=sum(v["output_tokens"] for v in usages),
                    openrouter_incremental_usd=0,
                    subscription_price_allocation=None,
                )
            else:
                from studies.ledger_read import calls

                rows = [
                    r
                    for r in calls(
                        BILLING[
                            "GPT-5 library acquisition"
                            if tag == "gpt5"
                            else "Claude Sonnet 4.5 library acquisition"
                        ]
                    )
                    if r["purpose"].startswith(project + "/")
                ]
                assert rows
                obj.update(
                    requests=len(rows),
                    settled_usd=sum((r["actual"] or 0) for r in rows) / 1e6,
                    exposure_usd=sum(
                        r["actual"] if r["actual"] is not None else r["reserved"]
                        for r in rows
                    )
                    / 1e6,
                )
            models.setdefault(c.BUILDERS[tag], []).append(obj)
    return models


def overview():
    source = c.OUT / "scoring.json"
    if not (c.OUT / "generation-sealed.json").is_file():
        raise ValueError("Unsealed generation")
    report = read(source)
    projects = local_projects(report)
    coverage = {
        p["project"]: sorted(
            {
                r["task"]
                for r in report["rows"]
                if r["project"] == p["project"]
                and r["arm"] == "plan"
                and r["status"] in ("valid", "invalid")
            }
        )
        for p in projects
    }
    cross = {}
    for comparator in ("plan_vs_direct", "plan_vs_fixed"):
        bins = Counter()
        for project in projects:
            for rec in project["builds"]:
                if not rec["tag"].startswith("codex"):
                    continue
                vals = rec[comparator]
                if vals["paired"] != 20:
                    bins["incomplete"] += 1
                    continue
                delta = vals["plan_passed"] - vals["comparator_passed"]
                bins["higher" if delta > 0 else "lower" if delta < 0 else "tied"] += 1
        cross[comparator] = dict(bins)
    ledger = {label: totals(p) for label, p in BILLING.items()}
    assert len(set(BILLING.values())) == len(BILLING)
    exposure = round(sum(v["exposure_usd"] for v in ledger.values()), 6)
    if exposure > 20:
        raise ValueError("Registered authorization exceeded")
    core_sources = [
        source,
        c.OUT / "generation-sealed.json",
        RESULTS / "public-library-transfer-20261123.json",
        RESULTS / "public-library-transfer-history-20261123.json",
        RESULTS / "public-library-transfer-extra-20261123.json",
    ]
    return {
        "study": "Public requirement libraries on previously studied public projects",
        "scope": "Normalized full-public-input protocol. Matched comparisons by target, builder and deployment model. "
        "Two Codex builds per project are dependent measurements within projects. Counts of project–library pairs are descriptive.",
        "registered_sha256": sha(c.OUT / "registered.json"),
        "source_sha256": {str(p.relative_to(ROOT)): sha(p) for p in core_sources},
        "local_planner": c.MODEL,
        "public_targets_by_project": coverage,
        "unique_webbench_targets": sum(map(len, coverage.values())),
        "local_groups": projects,
        "local_direction_counts": cross,
        "preparations": build_costs(),
        "ledgers": ledger,
        "ledger_settled_usd": round(sum(v["settled_usd"] for v in ledger.values()), 6),
        "ledger_exposure_usd": exposure,
        "billing_note": "Each distinct stage ledger counted once. Unknown reservations retained. "
        "No subscription price or local computation valuation. Remote ledger totals include any registered transport continuation.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = overview()
    if args.write:
        c.save(OUTPUT, data)
    elif read(OUTPUT) != data:
        raise SystemExit(
            "Summary differs from immutable results or final ledger totals"
        )
    print(data["local_direction_counts"], data["ledger_exposure_usd"])
