"""Split historical construction and draw receipts by builder (no API calls).

Rebuilding this index requires local raw artifacts. The end-to-end summary can
be reconstructed from the checked-in index alone.
"""
from collections import defaultdict
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from studies.ledger_read import calls

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "studies/results/builder_costs.json"


def reconstruct():
    draw_path = ROOT / "studies/results/webbench-draw-20261117.json"
    draw = json.loads(draw_path.read_text())
    construction = {}
    ledger_rows = {}
    stages = {
        "interface": ["interface-blind-build", "interface-blind-build-2"],
        "expansion": ["webbench-expand-build"],
        "draw": ["webbench-draw-build-20261117"],
    }
    for cohort, names in stages.items():
        grouped = defaultdict(lambda: {"settled_microusd": 0, "exposure_microusd": 0, "calls": 0})
        for name in names:
            path = ROOT / "artifacts" / name / "budget.sqlite3"
            rows = calls(path)
            # Preserve accounting fields without exposing provider identifiers.
            ledger_rows[path.relative_to(ROOT).as_posix()] = [
                {k: row[k] for k in ("model", "status", "reserved", "actual")} for row in rows]
            for row in rows:
                group = grouped[row["model"]]
                group["calls"] += 1
                group["settled_microusd"] += row["actual"] or 0
                group["exposure_microusd"] += row["actual"] if row["actual"] is not None else row["reserved"]
        construction[cohort] = {model: {**value, "settled_usd": value["settled_microusd"] / 1e6,
                                             "exposure_usd": value["exposure_microusd"] / 1e6}
                                for model, value in sorted(grouped.items())}
    records = {row["record"] for row in draw["rows"]
               if row["label"] == "final" and row["method"] in ("free", "plan")}
    receipts = []
    for record_path in sorted(records):
        record = json.loads((ROOT / record_path).read_text())
        for path in sorted((ROOT / record_path).parent.glob("call-*/response.json")):
            value = json.loads(path.read_text())
            receipts.append({"path": path.relative_to(ROOT).as_posix(),
                             "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                             "model": record["model"], "builder": record["builder"],
                             "method": record["method"], "cost_usd": value["usage"]["cost"]})
    groups = {}
    for model in sorted({r["model"] for r in receipts}):
        baseline = sum((Decimal(str(r["cost_usd"])) for r in receipts
                        if r["model"] == model and r["method"] == "free"), Decimal(0))
        for builder in sorted(construction["draw"]):
            plan = sum((Decimal(str(r["cost_usd"])) for r in receipts
                        if r["model"] == model and r["builder"] == builder and r["method"] == "plan"), Decimal(0))
            build = Decimal(str(draw["usage"][builder + "/build"]["cost_usd"]))
            groups[model + "|" + builder] = {
                "generator": model, "builder": builder, "targets_per_method": 5,
                "direct_usd": float(baseline), "build_usd": float(build), "selection_usd": float(plan),
                "pipeline_usd": float(build + plan), "direct_per_target_usd": float(baseline / 5),
                "pipeline_per_target_usd": float((build + plan) / 5)}
        for method in ("free", "plan"):
            total = sum(r["cost_usd"] for r in receipts if r["model"] == model and r["method"] == method)
            assert abs(total - draw["usage"][model + "/" + method]["cost_usd"]) < 1e-10
    return {"construction_by_builder": construction, "construction_ledger_rows": ledger_rows,
            "draw_scenarios": groups, "draw_receipts": receipts,
            "draw_summary_sha256": hashlib.sha256(draw_path.read_bytes()).hexdigest(),
            "scope": "Each draw scenario pays one builder once for five targets. Baseline receipts are shared across builder comparisons; construction is shared across generator scenarios. Do not sum these scenarios as the study bill. Failed calls and unresolved reservations remain in construction accounting."}


if __name__ == "__main__":
    value = reconstruct()
    OUT.write_text(json.dumps(value, indent=2) + "\n")
    print(json.dumps(value["draw_scenarios"], indent=2))
