"""Reconstruct the paper's end-to-end comparison without generating candidates.

Historical summaries and candidate records are immutable inputs. The reporting
choice is retrospective: only actual no-library records are the baseline.
Run from the repository root with ``uv run python -m studies.end_to_end``.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from decimal import Decimal, ROUND_CEILING
import hashlib
import json
from pathlib import Path
from studies.canvas_capacity.summarize import summarize as summarize_canvas_controls

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
            for field in ("current", "record"):
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
              for endpoint in ("current",)}
    for value in result.values():
        value["difference_pp"] = (
            value["plan"]["rate_percent"] - value["free"]["rate_percent"]
            if all(value[m]["total"] for m in METHODS) else None)
    return result


def builder_comparisons(rows):
    baseline = [r for r in rows if r["method"] == "free"]
    key = lambda r: (r["project"], r["model"], r["task"], r.get("seed"))
    result = {}
    for builder in sorted({r["builder"] for r in rows if r["method"] == "plan"}):
        plans = [r for r in rows if r["method"] == "plan" and r["builder"] == builder]
        assert {key(r) for r in plans} == {key(r) for r in baseline}, "Unmatched builder comparison"
        assert len(plans) == len(baseline)
        result[builder] = comparison(baseline + plans)
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
        } for endpoint in ("current",)}
    return result


def validate_matched_workflow(study):
    """Recompute matched targets, aggregate scores and micro-dollar charges from portable rows."""
    tasks = study["milestones"]
    assert len(tasks) == len(set(tasks)) == 5
    assert set(study["groups"]) == {f"{arm}-{rep}" for arm in METHODS for rep in (1, 2)}
    expected = {f"{arm}-{rep}/{t}" for arm in METHODS for rep in (1, 2) for t in tasks}
    assert set(study["rows"]) == expected
    for name, group in study["groups"].items():
        rows = [study["rows"][name + "/" + task] for task in tasks]
        assert name == f"{group['arm']}-{group['repetition']}"
        assert group["planned"] == len(rows)
        assert group["observed"] == sum(row["passed"] is not None for row in rows)
        assert group["passed"] == sum(row["passed"] is True for row in rows)
        for row in rows:
            assert (row["passed"] is None) == (row["status"] == "missing")
            assert bool(row.get("report_sha256")) == bool(row["page"])
            if not row["page"] and row["status"] != "missing":
                assert row["passed"] is False
        attempts = group["settled_attempts"]
        bill = group["cost"]
        assert len(attempts) + bill["unsettled_calls"] == bill["calls"]
        micros = sum((Decimal(str(a["cost_usd"])) * 1000000).to_integral_value(rounding=ROUND_CEILING)
                     for a in attempts.values())
        assert micros == Decimal(str(bill["settled_usd"])) * 1000000
        assert bill["settled_usd"] <= bill["exposure_usd"] <= bill["cap_usd"] == study["cap_per_repetition_arm_usd"]
    for rep in (1, 2):
        keys = {"direct_only": (True, False), "plan_only": (False, True),
                "both_pass": (True, True), "both_fail": (False, False)}
        pairs = [tuple(study["rows"][f"{arm}-{rep}/{task}"]["passed"] for arm in METHODS) for task in tasks]
        assert study["paired"][str(rep)] == {k: pairs.count(v) for k, v in keys.items()}
    return study


def observed_reuse_costs(study):
    """Charge preparation once, then add task-specific charges in milestone order."""
    out = {}
    for rep in (1, 2):
        series = []
        comparable = True
        by_arm = {}
        for arm in METHODS:
            group = study["groups"][f"{arm}-{rep}"]
            comparable &= group["observed"] == group["planned"] and not group["cost"]["unsettled_calls"]
            by_stage = defaultdict(Decimal)
            for key, attempt in group["settled_attempts"].items():
                by_stage[key.split("/")[0]] += Decimal(str(attempt["cost_usd"]))
            by_arm[arm] = by_stage
        running = {arm: by_arm[arm]["prepare"] for arm in METHODS}
        successes = dict.fromkeys(METHODS, 0)
        for task in study["milestones"]:
            for arm in METHODS:
                running[arm] += by_arm[arm][task]
                successes[arm] += study["rows"][f"{arm}-{rep}/{task}"]["passed"] is True
            series.append({"through": task, "provider_receipts_usd": {arm: float(running[arm]) for arm in METHODS},
                           "observed_passes_to_date": successes.copy()})
        available = study["groups"][f"plan-{rep}"]["prepare_status"] == "accepted"
        cheaper = [row["provider_receipts_usd"]["plan"] <= row["provider_receipts_usd"]["free"] for row in series]
        first = next((i + 1 for i in range(len(series)) if all(cheaper[i:])), None) if comparable and available else None
        out[str(rep)] = {"complete_cost_accounting": bool(comparable), "library_available": available,
                         "first_horizon_with_no_higher_cost_through_five": first, "milestones": series}
    return out


def reconstruct():
    sources = {}

    def read(name):
        path = ROOT / "studies/results" / name
        sources[path.relative_to(ROOT).as_posix()] = sha(path)
        return json.loads(path.read_text())

    draw = read("webbench-draw-20261117.json")
    interface = read("interface-blind.json")
    expansion = read("webbench-expand.json")
    assertion = read("assertion-audit-20261117.json")
    supplied = read("primary-replay.json")
    builder_costs = read("builder_costs.json")
    rows = []
    def original_row(cohort, stage, project, builder, model, method, task, passed):
        library = builder.replace("/", "__") if method == "plan" else "no_library"
        record = f"{stage}/runs/{project}/{library}/{model.replace('/', '__')}/{method}/{task}/record.json"
        return {"cohort": cohort, "project": project, "builder": builder if method == "plan" else None,
                "model": model, "method": method, "task": task, "record": record, "current": passed}

    for group in interface["groups"]:
        for row in group["rows"]:
            for method in METHODS:
                rows.append(original_row("interface", interface["stage"], group["project"],
                    group["builder"], group["model"], method, row["task"], row[method]))
    for row in expansion["rows"]:
        if row["method"] in METHODS:
            rows.append(original_row("expansion", expansion["stages"]["run"], row["project"],
                row["builder"], row["model"], row["method"], row["task"], row["final"]))
    draw_rows = {}
    for row in draw["rows"]:
        if row["label"] != "final" or row["method"] not in METHODS or row["endpoint"] != "current":
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
            "by_builder": builder_comparisons(selected),
            "by_project_builder": {p: builder_comparisons([r for r in selected if r["project"] == p])
                                   for p in sorted({r["project"] for r in selected})},
            "by_generator_builder": {m: builder_comparisons([r for r in selected if r["model"] == m])
                                     for m in sorted({r["model"] for r in selected})},
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

    historical = {}
    for suite in ("todomvc", "webbench"):
        data = next(s for s in supplied["suites"] if s["suite"] == suite and s["summary"] == "summary")
        historical[suite] = {m: {"passed": data["primary"][m]["final_all"],
                                 "total": data["primary"][m]["n"]} for m in ("free", "dna")}
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
    assert builder_costs["draw_summary_sha256"] == sources["studies/results/webbench-draw-20261117.json"]
    for cohort, values in builder_costs["construction_by_builder"].items():
        for field in ("settled_usd", "exposure_usd"):
            assert abs(sum(v[field] for v in values.values()) - construction[cohort][field]) < 1e-9
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
    pilots = {}
    diagnostics = {}
    for label, prefix, fixed_name in [
            ("scheduled", "matched-canvas-20261118", "canvas-fixed-reuse-20261118.json"),
            ("capacity_followup", "canvas-capacity-20261118", "canvas-capacity-20261118-reuse.json"),
            ("model_replication", "canvas-sonnet-20261118", "canvas-sonnet-20261118-reuse.json")]:
        study = validate_matched_workflow(read(prefix + ".json"))
        pilots[label] = study
        diagnostics[label] = summarize_canvas_controls(read(prefix + "-probe.json"), read(fixed_name), study)
    flex = validate_matched_workflow(read("matched-flex-20261118.json"))
    matched = {**pilots, "flex":flex}
    bills = [g["cost"] for study in matched.values() for g in study["groups"].values()]
    return {
        "schema_version": 4, "reporting_revision": "2026-11-18-matched-workflows",
        "canvas_pilots": pilots,
        "canvas_controls": diagnostics,
        "matched_flex": flex,
        "observed_reuse_costs": {k: observed_reuse_costs(s) for k,s in matched.items()},
        "matched_study_accounting": {"ledgers":len(bills), "calls":sum(b["calls"] for b in bills),
            "unsettled_calls":sum(b["unsettled_calls"] for b in bills),
            "settled_usd":sum_cost(bills,"settled_usd"), "exposure_usd":sum_cost(bills,"exposure_usd"),
            "scope":"Billing only, for the four matched stages of 2026-11-18. No pooling of outcome counts."},
        "table_behavior": read("table-behavior-probe-20261118.json"),
        "canvas_speed": read("canvas-speed-probe-20261118.json"),
        "input_controls": read("input-controls-20261118.json"),
        "evaluation_scope": "Current official task file only; not certification of the whole application.",
        "reporting_contract": "Report each builder separately, including project/generator breakdowns, sensitivity and cost. Each comparison uses the same target keys and denominator as the shared actual no-library baseline. Existing pooled fields are retained for internal reconciliation only, not presentation.",
        "selection_policy": "cohorts contains the retrospective comparison. The prospective canvas pilot, its capacity follow-up and the independent flex replication have distinct budgets, preparations and denominators.",
        "method_roles": {
            "free": {"role": "primary_baseline", "label": "Direct code without a library", "library_access": False},
            "plan": {"role": "proposed_pipeline", "label": "AI library construction + GUI-DNA assembly", "library_access": True},
            "free_lib": {"role": "archived_ablation", "reported_in_paper": False, "records_preserved": True},
        },
        "information_boundary": "In the retrospective cohorts, builders saw all twenty public requirements and had construction calls; no-library generators saw the target cumulative prefix and runtime contract. Builder reference implementations and behavioral tests were withheld. This is a whole-workflow contrast, not matched total information/compute or an isolated planning effect.",
        "unit": "Retrospective cohorts count a final saved candidate; the shared baseline is counted once. Prospective studies count scheduled target positions per workflow and repetition, including a failed build. Transport or budget gaps are missing. No pooling across protocols.",
        "cohorts": cohorts, "records": rows,
        "bom_sensitivity": {"excluded_tasks": excluded, "current": sensitivity,
                            "by_builder": {b: {"current": v["current"]}
                                           for b, v in builder_comparisons(sensitive).items()},
                            "posthoc": True, "original_scores_unchanged": True},
        "supplied_library_context": historical,
        "not_reported": [{"study": "webbench-expand-frontier", "reason": "No no-library candidates in this cohort; cannot form the primary comparison."}],
        "costs": {"construction": construction,
                  "construction_by_builder": builder_costs["construction_by_builder"],
                  "draw_by_generator_builder": builder_costs["draw_scenarios"],
                  "draw_per_generator_scenarios": draw_costs,
                  "draw_complete_original_study_ledger_usd": draw["costs"]["settled_usd"],
                  "draw_complete_original_study_receipts_usd": draw["provider_billed_usd"],
                  "expansion_used_generation_receipts_usd": {m: expansion["used_response_cost_usd"][m] for m in METHODS},
                  "limitations": "Method-selected receipts exclude unresolved historical transport reservations. Construction, failed build attempts and exposure are reported separately. Local compute and human time are unpriced. Original stage bills include archived conditions and are not rewritten."},
        "source_sha256": sources,
        "validation_scope": "Zero-API reconstruction from saved endpoint summaries with independent current-score cross-checks; not a new browser evaluation or new model generation.",
        "reconstruction_api_cost_usd": 0,
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
    print(json.dumps({k: v["by_builder"] for k, v in value["cohorts"].items()}, indent=2))


if __name__ == "__main__":
    main()
