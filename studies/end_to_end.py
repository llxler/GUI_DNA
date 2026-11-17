"""Reconstruct the paper's end-to-end comparison without generating candidates.

Historical summaries and candidate records are immutable inputs. The reporting
choice is retrospective: only actual no-library records are the baseline.
Run from the repository root with ``uv run python -m studies.end_to_end``.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from decimal import Decimal
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "studies/results/end_to_end.json"
METHODS = ("free", "plan")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unique_records(rows):
    """Count a shared no-library candidate once across library builders."""
    seen = {}
    for row in rows:
        if row["method"] not in METHODS:
            continue
        key = (row["cohort"], row["project"], row["model"], row["task"],
               row.get("seed"), row["method"],
               row.get("builder") if row["method"] == "plan" else None)
        if key in seen:
            for field in ("current", "history", "record"):
                if seen[key][field] != row[field]:
                    raise ValueError(f"Conflicting observations for {key}: {field}")
        else:
            seen[key] = {**row, "builder": key[-1]}
    return sorted(seen.values(), key=lambda r: (
        r["cohort"], r["project"], r["model"], r["builder"] or "",
        r["method"], int(r["task"].split("-")[-1])))


def count(rows, endpoint):
    n = len(rows)
    passed = sum(r[endpoint] for r in rows)
    return {"passed": passed, "total": n,
            "rate_percent": 100 * passed / n if n else None}


def comparison(rows):
    methods = {m: [r for r in rows if r["method"] == m] for m in METHODS}
    result = {endpoint: {m: count(group, endpoint) for m, group in methods.items()}
              for endpoint in ("current", "history")}
    for value in result.values():
        value["difference_pp"] = (
            value["plan"]["rate_percent"] - value["free"]["rate_percent"]
            if all(value[m]["total"] for m in METHODS) else None)
    return result


def paired_by_builder(rows):
    # The same baseline may appear in several descriptive comparisons, never
    # as additional independent baseline samples or pooled significance tests.
    baseline = {(r["project"], r["model"], r["task"]): r
                for r in rows if r["method"] == "free"}
    pairs = defaultdict(list)
    for row in rows:
        if row["method"] != "plan":
            continue
        other = baseline[(row["project"], row["model"], row["task"])]
        pairs[row["builder"]].append((row, other))
    result = {}
    for builder, values in sorted(pairs.items()):
        result[builder] = {endpoint: {
            "pairs": len(values),
            "plan_only": sum(p[endpoint] and not f[endpoint] for p, f in values),
            "free_only": sum(f[endpoint] and not p[endpoint] for p, f in values),
            "both_pass": sum(p[endpoint] and f[endpoint] for p, f in values),
            "both_fail": sum(not p[endpoint] and not f[endpoint] for p, f in values),
        } for endpoint in ("current", "history")}
    return result


def reconstruct():
    sources = {}

    def read(name):
        path = ROOT / "studies/results" / name
        sources[path.relative_to(ROOT).as_posix()] = sha(path)
        return json.loads(path.read_text())

    history = read("history-replay.json")
    draw = read("webbench-draw-20261117.json")
    interface = read("interface-blind.json")
    expansion = read("webbench-expand.json")
    assertion = read("assertion-audit-20261117.json")
    supplied = read("primary-replay.json")
    rows = []
    for row in history["rows"]:
        if row["label"] != "final" or row["cohort"] not in ("interface", "expansion"):
            continue
        if row["method"] not in METHODS:
            continue
        rows.append({k: row[k] for k in (
            "cohort", "project", "builder", "model", "method", "task", "record")}
                    | {"current": row["old_current_passed"],
                       "history": row["history_passed"]})
    draw_rows = {}
    for row in draw["rows"]:
        if row["label"] != "final" or row["method"] not in METHODS:
            continue
        key = row["record"]
        value = draw_rows.setdefault(key, {"cohort": "draw", **{k: row[k] for k in (
            "project", "builder", "model", "method", "task", "record")}})
        if row["endpoint"] in value:
            raise ValueError(f"Duplicate draw endpoint: {key}")
        value[row["endpoint"]] = row["passed"]
    rows = unique_records(rows + list(draw_rows.values()))
    cohorts = {}
    for cohort in ("interface", "expansion", "draw"):
        selected = [r for r in rows if r["cohort"] == cohort]
        cohorts[cohort] = {
            "projects": sorted({r["project"] for r in selected}),
            "generators": sorted({r["model"] for r in selected}),
            "builders": sorted({r["builder"] for r in selected if r["builder"]}),
            "results": comparison(selected),
            "by_project": {p: comparison([r for r in selected if r["project"] == p])
                           for p in sorted({r["project"] for r in selected})},
            "by_generator": {m: comparison([r for r in selected if r["model"] == m])
                             for m in sorted({r["model"] for r in selected})},
            "by_builder": {b: comparison([r for r in selected if r["builder"] in (b, None)])
                           for b in sorted({r["builder"] for r in selected if r["builder"]})},
            "paired_by_builder": paired_by_builder(selected),
        }
    # Independent agreement with the original current-file summaries.
    for method in METHODS:
        if method == "plan":
            saved = sum(r["plan"] for g in interface["groups"] for r in g["rows"])
        else:
            shared = {}
            for group in interface["groups"]:
                for row in group["rows"]:
                    key = (group["project"], group["model"], row["task"])
                    if key in shared:
                        assert shared[key] == row["free"]
                    shared[key] = row["free"]
            saved = sum(shared.values())
        assert cohorts["interface"]["results"]["current"][method]["passed"] == saved
        selected = [r for r in expansion["rows"] if r["method"] == method]
        assert cohorts["expansion"]["results"]["current"][method]["passed"] == sum(r["final"] for r in selected)
        assert cohorts["expansion"]["results"]["current"][method]["total"] == len(selected)
    excluded = assertion["six_file_sensitivity"]["excluded_bom_tasks"]
    sensitive = [r for r in rows if r["cohort"] == "expansion"
                 and not (r["project"] == "bom" and r["task"] in excluded)]
    sensitivity = {m: count([r for r in sensitive if r["method"] == m], "current") for m in METHODS}
    for m in METHODS:
        assert {k: sensitivity[m][k] for k in ("passed", "total")} == assertion["six_file_sensitivity"]["methods"][m]
    sensitivity["difference_pp"] = sensitivity["plan"]["rate_percent"] - sensitivity["free"]["rate_percent"]

    feedback = {}
    for name in ("matched-feedback.json", "matched-feedback-frontier.json"):
        data = read(name)
        feedback[name] = {
            "original_candidates_all_methods": data["candidates"],
            "reported_candidates": sum(data["public_summary"][m]["total"] for m in METHODS),
            "public": {m: data["public_summary"][m] for m in METHODS},
            "results": {key: value for key, value in data["groups"].items() if key.split("/")[0] in METHODS},
            "usage": {m: data["usage"][m] for m in METHODS},
        }
    historical = {}
    for suite in ("todomvc", "webbench"):
        data = next(s for s in supplied["suites"] if s["suite"] == suite and s["summary"] == "summary")
        historical[suite] = {m: {"passed": data["primary"][m]["final_all"],
                                 "total": data["primary"][m]["n"]} for m in ("free", "dna")}
    for m in ("free", "dna"):
        selected = [r for r in history["rows"] if r["cohort"] == "expert" and r["method"] == m and r["label"] == "final"]
        historical["webbench"][m]["history_passed"] = sum(r["history_passed"] for r in selected)

    def sum_cost(values, field):
        return float(sum((Decimal(str(v[field])) for v in values), Decimal(0)))

    draw_build = [v for k, v in draw["usage"].items() if k.endswith("/build")]
    construction = {
        "interface": {field: sum_cost([v for k, v in interface["costs"].items() if k.startswith("build")], field)
                      for field in ("settled_usd", "exposure_usd")},
        "expansion": {k: expansion["costs"]["build"][k] for k in ("settled_usd", "exposure_usd", "unsettled_calls")},
        "draw": {"settled_usd": draw["costs"]["stages"]["webbench-draw-build-20261117"]["settled_usd"],
                 "exposure_usd": draw["costs"]["stages"]["webbench-draw-build-20261117"]["exposure_usd"],
                 "provider_receipts_usd": sum_cost(draw_build, "cost_usd")},
    }
    draw_costs = {}
    for model in cohorts["draw"]["generators"]:
        free, plan = (draw["usage"][f"{model}/{m}"] for m in METHODS)
        build = Decimal(str(construction["draw"]["provider_receipts_usd"]))
        pipeline = build + Decimal(str(plan["cost_usd"]))
        draw_costs[model] = {
            "free_candidates": cohorts["draw"]["by_generator"][model]["current"]["free"]["total"],
            "plan_candidates": cohorts["draw"]["by_generator"][model]["current"]["plan"]["total"],
            "free_receipts_usd": free["cost_usd"], "selection_receipts_usd": plan["cost_usd"],
            "two_libraries_receipts_usd": float(build),
            "pipeline_receipts_usd": float(pipeline),
            "pipeline_per_target_receipts_usd": float(pipeline / 10),
            "free_per_target_receipts_usd": float(Decimal(str(free["cost_usd"])) / 5),
            "scope": "Each generator is charged both library builds once across ten plan targets (two builders x five milestones). Independent scenarios; do not sum construction across generators. Actual study built the two libraries only once.",
        }
    return {
        "schema_version": 1, "reporting_revision": "2026-11-17-end-to-end",
        "selection_policy": "Retrospective reporting of existing observations; not a preregistered new experiment.",
        "method_roles": {
            "free": {"role": "primary_baseline", "label": "Direct code without a library", "library_access": False},
            "plan": {"role": "proposed_pipeline", "label": "AI library construction + GUI-DNA assembly", "library_access": True},
            "free_lib": {"role": "archived_ablation", "reported_in_paper": False, "records_preserved": True},
        },
        "information_boundary": "Builders saw all twenty public requirements and had construction calls; no-library generators saw the target cumulative prefix and runtime contract. Builder reference implementations and behavioral tests were withheld. This is a whole-workflow contrast, not matched total information/compute or an isolated planning effect.",
        "unit": "One final saved candidate per project, generator, task and (for plans only) builder. The baseline is counted once, not repeated across builders. No pooling across study protocols.",
        "cohorts": cohorts, "records": rows,
        "bom_sensitivity": {"excluded_tasks": excluded, "current": sensitivity,
                            "posthoc": True, "original_scores_unchanged": True},
        "matched_feedback": feedback, "supplied_library_context": historical,
        "not_reported": [{"study": "webbench-expand-frontier", "reason": "No no-library candidates in this cohort; cannot form the primary comparison."}],
        "costs": {"construction": construction,
                  "draw_per_generator_scenarios": draw_costs,
                  "draw_complete_original_study_ledger_usd": draw["costs"]["settled_usd"],
                  "draw_complete_original_study_receipts_usd": draw["provider_billed_usd"],
                  "expansion_used_generation_receipts_usd": {m: expansion["used_response_cost_usd"][m] for m in METHODS},
                  "limitations": "Method-selected receipts exclude unresolved historical transport reservations. Construction, failed build attempts and exposure are reported separately. Local compute and human time are unpriced. Original stage bills include archived conditions and are not rewritten."},
        "source_sha256": sources,
        "validation_scope": "Zero-API reconstruction from saved endpoint summaries with independent current-score cross-checks; not a new browser evaluation or new model generation.",
        "new_api_cost_usd": 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Recompute and compare without rewriting the saved view")
    args = parser.parse_args()
    value = reconstruct()
    if args.check:
        assert json.loads(OUTPUT.read_text()) == value, "Saved primary view differs from its sources"
    else:
        OUTPUT.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v["results"] for k, v in value["cohorts"].items()}, indent=2))


if __name__ == "__main__":
    main()
