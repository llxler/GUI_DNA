"""Freeze the local SVG prompts, strictly validate plans, and replay the official current files."""
import argparse
import json
import math
from pathlib import Path
import shutil

from studies.library_refinement_chart.adapter import BUILD, HERE as PREVIOUS_CODE, ORIGINAL, OUT as PREVIOUS, TASKS
from studies.library_refinement_chart.adapter import browser, checked_score, materialize_plan, old_package, score_run
from studies.study_io import ROOT, dump, now, read, sha, source_files
from .local_planner import GENERATION, MODEL, REVISION

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/svg-chart-compact-local-20261123"
EVAL = PREVIOUS / "replays/svg-chart-compact-local-20261123"
CONTROL = PREVIOUS / "example-recovery"
PUBLIC = ROOT / "studies/results/svg-chart-compact-local-20261123.json"

SCHEMA = {
    "theme": {"palette": "strings", "axisColor": "string", "gridColor": "string", "textColor": "string",
              "background": "string", "legend": {"height": "number"}, "axes": {"xHeight": "number", "yWidth": "number"}},
    "defaults": {"axes": "bool", "grids": "bool", "legends": "bool", "lineSmooth": "bool",
                 "pointStyle": "point", "dataLabels": "bool"},
    "text": {"baseSize": "number"},
}


def read_plan(raw):
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError("Duplicate JSON property")
            obj[key] = value
        return obj

    def bad_constant(value):
        raise ValueError(f"Nonfinite numeric literal {value}")

    data = json.loads(raw, object_pairs_hook=unique, parse_constant=bad_constant)

    def check(value, schema, field):
        if isinstance(schema, dict):
            if not isinstance(value, dict):
                raise ValueError(f"{field} must be an object")
            for k, v in value.items():
                if k not in schema:
                    raise ValueError(f"Unknown property {field}.{k}")
                check(v, schema[k], field + "." + k)
        else:
            valid = {"string": lambda x: isinstance(x, str) and bool(x.strip()),
                     "strings": lambda x: isinstance(x, list) and all(isinstance(s, str) and s.strip() for s in x),
                     "number": lambda x: type(x) in (int, float) and math.isfinite(x),
                     "bool": lambda x: type(x) is bool,
                     "point": lambda x: x in ("circle", "rect")}[schema]
            if not valid(value):
                raise ValueError(f"Unexpected value for {field} ({schema})")
    check(data, SCHEMA, "plan")
    return data


def verify(path):
    for name, value in read(path)["sha256"].items():
        assert sha(ROOT / name) == value, name


def prepare():
    path = OUT / "freeze.json"
    if path.exists():
        verify(path)
        return
    paths = [HERE / "PROTOCOL.md", HERE / "local_planner.py", Path(__file__),
             ORIGINAL / "results.json", BUILD / "ai-package.json", PREVIOUS / "freeze.json",
             PREVIOUS / "projection.json", CONTROL / "results.json", CONTROL / "freeze.json",
             PREVIOUS_CODE / "adapter.py", browser.SOURCE / "package.json"]
    pkg = old_package()
    for example in pkg["examples"]:
        assert read_plan(json.dumps(example["plan"])) == example["plan"]
    for n in TASKS:
        origin = PREVIOUS / "prompts/compact" / f"task-{n}.json"
        dest = OUT / "prompts" / origin.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, dest)
        paths.extend([dest, origin])
    shutil.copyfile(browser.SOURCE / "package.json", OUT / "package.json")
    paths.append(OUT / "package.json")
    modules = OUT / "node_modules"
    if not modules.exists():
        modules.symlink_to(browser.RUNTIME / "node_modules", target_is_directory=True)
    assert modules.resolve() == (browser.RUNTIME / "node_modules").resolve()
    dump(path, {"utc": now(), "targets": TASKS, "model": MODEL, "revision": REVISION, "decoder": GENERATION,
                "structural_schema": SCHEMA, "sha256": {str(p.relative_to(ROOT)): sha(p) for p in paths}})


def materialize():
    prepare()
    path = OUT / "candidates.json"
    generated = read(OUT / "local-generation.json")
    assert generated["inputs_sha256"] == sha(OUT / "local-inputs.json") and set(generated["response_sha256"]) == {str(n) for n in TASKS}
    if path.exists():
        assert read(path)["generation_sha256"] == sha(OUT / "local-generation.json")
        return
    pkg = old_package()
    control = read(CONTROL / "freeze.json")["fixed"]
    rows = []
    for n in TASKS:
        raw = OUT / "runs" / f"task-{n}" / "response.json"
        assert sha(raw) == generated["response_sha256"][str(n)]
        receipt = read(raw)
        assert receipt["task"] == n and receipt["prompt_sha256"] == sha(OUT / "prompts" / f"task-{n}.json")
        assert receipt["model"] == MODEL and receipt["revision"] == REVISION and receipt["generation_config"] == GENERATION
        row = {"task": n, "response": receipt["complete"], "valid_plan": False, "fallback": False,
               "files": None, "input_tokens": receipt["input_tokens"], "output_tokens": receipt["output_tokens"],
               "finish_reason": receipt["finish_reason"], "response_sha256": sha(raw)}
        if receipt["complete"]:
            try:
                plan = read_plan(receipt["text"])
                row["valid_plan"] = True
                row["top_level"] = list(plan)
                dest = OUT / "runs" / f"task-{n}" / "page"
                row["files"] = materialize_plan(pkg, plan, dest)
                row["page"] = str(dest.relative_to(ROOT))
                dump(dest.parent / "plan.json", plan)
            except (ValueError, TypeError, KeyError, OverflowError) as exc:
                row["error"] = str(exc)[:300]
                row["fallback"] = True
                item = control[n - 1]
                assert item["task"] == n and item["files"] == source_files(ROOT / item["page"])
        rows.append(row)
    dump(path, {"utc": now(), "generation_sha256": sha(OUT / "local-generation.json"), "rows": rows})


def run_evaluation():
    materialize()
    rows = read(OUT / "candidates.json")["rows"]
    scored = score_run(EVAL, rows)
    baseline = {r["task"]: r["passed"] for r in read(ORIGINAL / "results.json")["rows"] if r["arm"] == "ai"}
    fixed = read(CONTROL / "results.json")["fixed"]
    result = []
    for r in rows:
        n = r["task"]
        original_report = fixed[str(n)]
        assert checked_score(CONTROL / "fixed-evaluation/scores/official-1" / f"task-{n}", n)["report_sha256"] == original_report["report_sha256"]
        plain = scored[str(n)]
        clinical = original_report if r["fallback"] else plain
        result.append({k: v for k, v in r.items() if k not in ("page", "files")} |
                      {"materialized": bool(r["files"]), "old_mistral": baseline[n], "local_strict": plain["passed"],
                       "local_with_fallback": clinical["passed"], "fixed_first": fixed[str(n)]["passed"],
                       "strict_report_sha256": plain["report_sha256"], "deployed_report_sha256": clinical["report_sha256"]})
    data = {"project": "web-bench/svg-chart", "model": MODEL, "revision": REVISION,
            "builder": "reused 2026-11-21 GPT-5 library", "endpoint": "current official task file only",
            "targets": list(TASKS), "observed": sum(r["response"] for r in result),
            "strict_valid_plans": sum(r["valid_plan"] for r in result), "fallback_used": sum(r["fallback"] for r in result),
            "passes": {k: sum(r[k] is True for r in result) for k in ("old_mistral", "local_strict", "local_with_fallback", "fixed_first")},
            "rows": result, "decoder": GENERATION, "remote_calls": 0,
            "sha256": {name: sha(OUT / name) for name in ("freeze.json", "local-inputs.json", "local-generation.json", "candidates.json")}}
    dump(OUT / "results.json", data)
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("freeze", "materialize", "evaluate", "publish", "check"))
    stage = parser.parse_args().stage
    if stage == "freeze":
        prepare()
    elif stage == "materialize":
        materialize()
    else:
        result = run_evaluation()
        if stage == "publish":
            dump(PUBLIC, result)
        if stage == "check":
            assert result == read(PUBLIC)
        print("passes", result["passes"], "observed", result["observed"], "fallback", result["fallback_used"])
