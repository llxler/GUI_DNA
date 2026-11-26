"""Locate one published Table 1 result from a checkout, without running a study."""

import argparse
import json
from pathlib import Path

from studies import paper_performance as paper
from studies.webgen_bench import report as functional
from studies.study_io import ROOT, read

MATRIX = Path("studies/results/paper-performance-matrix.json")
TRANSFER = Path("studies/public_library_transfer")
WEBGEN = Path("studies/webgen_bench")
DATASETS = {
    **{f"web-bench/{p}": p for p in (*paper.WEB_PROJECTS, "dom1", "calculator")},
    "todomvc": "todomvc",
    "webapp1k-duo": "duo",
    "webgen-bench": "webgen-bench",
}
MODEL_NAMES = paper.BACKBONES | paper.components.LABELS
# Some rows combine multiple registered runs. Point readers to the actual join
# instead of attributing every method to the latest run.
ASSEMBLERS = {
    "source_diagnosis": paper.sources,
    "library_capabilities": paper.capabilities,
    "form_visible_targets": paper.table_protocols,
    "table_protocol_followup": paper.table_protocols,
    "extended_targets": paper.components,
    "component_followup": paper.components,
    "self_recovery": paper.recovery,
    "webgen_functional": functional,
}


def find_cell(matrix, dataset, model, method):
    project = DATASETS[dataset]
    path, row = paper.table_record(matrix[model], project)
    excluded = method in row.get("excluded_build_arms", ())
    if excluded:
        status = "build_failed"
    elif method in row.get("passed", {}):
        status = "measured"
    else:
        status = "unavailable"
    cell = {
        "dataset": dataset, "model": model, "method": method, "status": status,
        "matrix": str(MATRIX), "row_keys": [model, *path],
        "assembly_code": str(Path(ASSEMBLERS.get(path[0], paper).__file__).relative_to(ROOT)),
    }
    if status == "measured":
        cell.update(score=row["passed"][method], denominator=row["n"],
                    unit="functional points" if project == "webgen-bench" else "current-task passes")

    receipt = row.get("implementation_sources", {}).get(method)
    if path == ("form_visible_targets",):
        receipt = row.get("schema_source", row["source"]) if method == "gpt5-library" else row["source"]
    if project == "webgen-bench":
        primary_stage = read(functional.RESULT)["primary_stage"]
        directory = functional.STAGES[primary_stage]
        receipt = str((directory / "judgments.json").relative_to(ROOT))
        cell["candidates"] = str((directory / "candidates.json").relative_to(ROOT))
    if receipt:
        cell["method_record"] = receipt
    if row.get("additional_targets"):
        cell["additional_targets_record"] = str(paper.components.EXTENSION.relative_to(ROOT))
    if row.get("source") and row["source"] != receipt:
        cell["row_source"] = row["source"]
    if dataset.startswith("web-bench/"):
        guide = Path("studies/webbench/README.md")
    elif project == "webgen-bench":
        guide = WEBGEN / "README.md"
    else:
        guide = TRANSFER / "README.md"
    cell["study_guide"] = str(guide)
    return cell


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", nargs="?", choices=DATASETS)
    parser.add_argument("model", nargs="?", help="Generator ID or quoted Table 1 name")
    parser.add_argument("method", nargs="?", help="Direct, Human, GPT-5 or Self")
    args = parser.parse_args(argv)
    if not args.dataset:
        print("\n".join(DATASETS))
        return

    matrix = read(ROOT / MATRIX)
    models = paper.table_models(matrix, DATASETS[args.dataset])
    if not args.model:
        for model in models:
            print(f"{model}\t{MODEL_NAMES[model]}")
        return

    names = {alias.casefold(): model for model in models for alias in (model, MODEL_NAMES[model])}
    model = names.get(args.model.casefold())
    if model is None:
        parser.error(f"No displayed row for {args.model!r}. List this dataset's models by omitting the model.")
    if not args.method:
        print("\n".join(f"{key}\t{label}" for key, label in paper.METHODS.items()))
        return
    methods = {alias.casefold(): key for key, name in paper.METHODS.items() for alias in (key, name)}
    method = methods.get(args.method.casefold())
    if method is None:
        parser.error("Choose Direct, Human, GPT-5 or Self.")
    print(json.dumps(find_cell(matrix, args.dataset, model, method), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
