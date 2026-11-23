"""Audit receipt provenance, matched denominators and fallback controls for both chart studies."""
import argparse
from collections import Counter
from decimal import Decimal, ROUND_CEILING

from gui_dna.provider import parse_json
from studies.ledger_read import calls, totals
from studies.study_io import ROOT, digest, dump, read, sha
from .adapter import BUILD, ORIGINAL, OUT, TASKS, checked_score, old_package, source_files
from .recovery import COHORTS, DIR
from .run import ARMS

PUBLIC = ROOT / "studies/results/svg-chart-library-refinement-20261123.json"


def summary(cells):
    vals = [v["passed"] for v in cells]
    return {"targets": len(vals), "responses": sum(v is not None for v in vals),
            "materialized": sum(v["materialized"] for v in cells), "passes": vals.count(True),
            "missing": vals.count(None), "possible_total_passes": [vals.count(True), vals.count(True) + vals.count(None)]}


def paired(before, after):
    assert len(before) == len(after) and [c["task"] for c in before] == [c["task"] for c in after]
    common = [(old["task"], old["passed"], new["passed"]) for old, new in zip(before, after)
              if old["passed"] is not None and new["passed"] is not None]
    return {"registered_targets": list(c["task"] for c in before), "observed_pairs": len(common),
            "old_passes_on_pairs": sum(old for _, old, _ in common), "new_passes_on_pairs": sum(new for _, _, new in common),
            "gained_tasks": [n for n, old, new in common if new and not old],
            "lost_tasks": [n for n, old, new in common if old and not new]}


def audit_arm(origin, arm, variant, seed, raw_rows, cells, historical=False):
    ledger = {r["id"]: r for r in calls(origin / "budget.sqlite3")}
    records, costs, error_types, finish = [], [], Counter(), Counter()
    for row in sorted((r for r in raw_rows if r["arm"] == arm), key=lambda r: r["task"]):
        n = row["task"]
        folder = origin / "runs" / arm / f"task-{n}"
        assert read(folder / "record.json") == row
        request = folder / "call/request.json"
        receipt = folder / "call/response.json"
        baseline = read(ORIGINAL / "runs/ai" / f"task-{n}" / "call/request.json")["body"]
        model_method = {k: v for k, v in baseline.items() if k not in ("seed", "messages")}
        if request.exists():
            data = read(request)
            body = data["body"]
            assert body["seed"] == seed and body["messages"] == read(OUT / "prompts" / variant / f"task-{n}.json")
            assert {k: v for k, v in body.items() if k not in ("seed", "messages")} == model_method
            bill = ledger[data["call_id"]]
        assert receipt.exists() == row["response"]
        keys = None
        if receipt.exists():
            raw = read(receipt)
            cost = Decimal(str(raw["usage"]["cost"]))
            costs.append(cost)
            assert bill["actual"] == int((cost * 1_000_000).to_integral_value(rounding=ROUND_CEILING))
            finish[raw["choices"][0]["finish_reason"]] += 1
            try:
                obj = parse_json(raw["choices"][0]["message"]["content"])
            except ValueError:
                assert not row.get("files")
            else:
                keys = list(obj) if isinstance(obj, dict) else None
        if historical:
            assert row["response"]
            expected = checked_score(origin / "scores/ai" / f"task-{n}", n)["passed"] if row.get("files") else False
            assert expected == cells[str(n)]["passed"]
        else:
            assert (cells[str(n)]["passed"] is not None) == row["response"]
        err = None
        if not row["response"]:
            if request.exists():
                err = read(folder / "call/error.json")["error"]
                assert bill["actual"] is None
            else:
                err = row["error"]
            error_types[err] += 1
        records.append({"task": n, "requested": request.exists(), "response": row["response"],
                        "materialized": bool(row.get("files")), "plan_top_level_keys": keys,
                        "passed": cells[str(n)]["passed"], "missing_reason": err})
    assert [r["task"] for r in records] == list(TASKS)
    return {"seed": seed, "summary": summary(records), "finish_reasons": dict(finish),
            "receipt_cost_usd": float(sum(costs)), "missing_reasons": dict(error_types), "rows": records}


def report():
    original = read(ORIGINAL / "generation-complete.json")
    original_scores = {str(row["task"]): row for row in read(ORIGINAL / "results.json")["rows"] if row["arm"] == "ai"}
    main = {"full_original": audit_arm(ORIGINAL, "ai", "full", 20261123, original["rows"], original_scores, True)}
    complete = read(OUT / "generation-complete.json")
    for arm, (variant, seed) in ARMS.items():
        scored = read(OUT / "evaluations" / arm / "evaluation-complete.json")
        assert scored["inputs_sha256"] == sha(OUT / "evaluations" / arm / "evaluation-inputs.json")
        main[arm] = audit_arm(OUT, arm, variant, seed, complete["rows"], scored["cells"])
    comparisons = [paired(main[a]["rows"], main[b]["rows"])
                   for a, b in [("full_original", "compact_first"), ("full_replication", "compact_replication")]]
    confirmed = all(c["observed_pairs"] == 20 and c["new_passes_on_pairs"] > c["old_passes_on_pairs"] for c in comparisons)
    recovery = read(DIR / "results.json")
    assert recovery["freeze_sha256"] == sha(DIR / "freeze.json")
    fixed = recovery["fixed"]
    reconstructed = {}
    for key, (origin, tasks, _) in COHORTS.items():
        rows = recovery["recovery"][key]
        comp = paired([{"task": r["task"], "passed": r["original"]} for r in rows], rows)
        public_rows = [{k: v for k, v in row.items() if k != "report_sha256"} for row in rows]
        reconstructed[key] = {"paired": comp, "applied": sum(r["used_example"] for r in rows),
                              "rows": public_rows, "archived_seed": read(origin / "runs/ai" / f"task-{tasks[0]}" / "call/request.json")["body"]["seed"]}
    fields = [("artifacts/library-refinement-chart-20261123", OUT / "freeze.json"),
              ("artifacts/library-refinement-chart-20261123/example-recovery", DIR / "freeze.json")]
    pkg = old_package()
    body_sizes = {}
    for variant in ("full", "compact"):
        body_sizes[variant] = [len(read(OUT / "prompts" / variant / f"task-{n}.json")[1]["content"].encode()) for n in (1, 20)]
    return {"project": "web-bench/svg-chart", "builder": "openai/gpt-5", "builder_source": "existing 2026-11-21 package",
            "source_files": len(pkg["files"]), "planner": "mistralai/mistral-small-3.2-24b-instruct",
            "endpoint": "current official task file", "duration_scope": "one frozen library",
            "arms": main, "paired_projection": comparisons, "preregistered_projection_confirmed": confirmed,
            "fixed_first_example": {"page_digest": digest(read(DIR / "freeze.json")["fixed"][0]["files"]),
                                    "targets": len(fixed), "passes": sum(v["passed"] for v in fixed.values()),
                                    "passing_tasks": [n for n in TASKS if fixed[str(n)]["passed"]]},
            "response_only_fallback": reconstructed,
            "generation_ledger": totals(OUT / "budget.sqlite3"), "user_prompt_bytes_task_1_and_20": body_sizes,
            "provenance": {label: sha(path) for label, path in fields},
            "interpretation": "The interface projection is a planner deployment change. The fixed-first-example and parse/compile fallback use the unchanged AI-built package. Recovery cohorts share their library and five targets and remain separate."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    data = report()
    if args.write:
        dump(PUBLIC, data)
    else:
        assert data == read(PUBLIC)
    print("projection_confirmed", data["preregistered_projection_confirmed"], "fixed", data["fixed_first_example"]["passes"])
    for key, result in data["response_only_fallback"].items():
        comparison = result["paired"]
        print(key, comparison["old_passes_on_pairs"], comparison["new_passes_on_pairs"], comparison["observed_pairs"])
