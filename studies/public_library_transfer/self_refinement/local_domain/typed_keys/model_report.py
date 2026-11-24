"""Compare independently sampled model-only operations with the matched originals."""
import argparse
from collections import Counter
from pathlib import Path

from studies.public_library_transfer import core
from studies.study_io import ROOT, read, sha
from ..report import compact, passed_ids
from . import model
from .report import summarize

HERE = Path(__file__).resolve().parent
PUBLISHED = HERE / "model-result.json"


def outcomes(result):
    paired = summarize(result["target_rows"], result["rule_settings"])
    for tag, grp in paired["builds"].items():
        assigned = result["operations"][tag]
        grp["shared_linker_formula_count"] = sum(x["matches_linker"] is True for x in assigned)
    return paired


def build():
    typed = read(HERE / "result.json")
    own = read(model.OUT / "scores.json")["rows"]
    linker = [r for r in typed["target_rows"] if r["arm"] == "linker"]
    rows = [compact(r) for r in own] + linker
    formulas = {}
    input_tokens = output_tokens = calls = 0
    for tag in model.SEEDS:
        concept = read(model.TYPED / "builds" / tag / "library.json")
        registry = model.grammar.expressions(read(model.TYPED / "registered.json")["contract"]["domain_math"])
        base = model.OUT / "builds" / tag
        new = read(base / "library.json")["choices"]
        formulas[tag] = [{"label": k, "expression": v,
                          "matches_linker": (registry[concept["direct_links"][k]] == v) if k in concept["direct_links"] else None}
                         for k, v in new.items()]
        traces = [read(p) for p in base.glob("key-*.json")]
        calls += len(traces)
        input_tokens += sum(v["input_tokens"] for v in traces)
        output_tokens += sum(len(v["output_ids"]) for v in traces)
    manifest = read(model.OUT / "registered.json")["contract"]
    result = {"model": typed["model"], "revision": typed["revision"], "project": "calculator",
              "targets": typed["targets"], "operations": formulas, "target_rows": rows,
              "rule_settings": typed["public_rule_settings"], "source_hashes": manifest["sources"],
              "evidence_sha256": {str(p.relative_to(ROOT)): sha(p) for p in
                                  [model.OUT / "registered.json", model.OUT / "environment.json",
                                   model.OUT / "seal.json", model.OUT / "scores.json", HERE / "result.json"]},
              "accounting": {"new_api_usd": 0, "remote_calls": 0, "new_model_completions": calls,
                             "input_tokens": input_tokens, "output_tokens": output_tokens,
                             "shared": "The two panels per library, the task planner and Direct come from the registered typed phase"}}
    result["summary"] = outcomes(result)
    return result


def check(result):
    typed = read(HERE / "result.json")
    for path, digest in result["source_hashes"].items():
        if sha(ROOT / path) != digest:
            raise ValueError("Changed model-expression protocol")
    if sha(HERE / "result.json") != result["evidence_sha256"][str((HERE / "result.json").relative_to(ROOT))]:
        raise ValueError("Paired typed-domain inputs changed")
    fixed = [r for r in result["target_rows"] if r["arm"] in ("direct", "linker")]
    prior = [r for r in typed["target_rows"] if r["arm"] in ("direct", "linker")]
    if len(fixed) != len(prior) or {str(sorted(r.items())) for r in fixed} != {str(sorted(r.items())) for r in prior}:
        raise ValueError("Shared control differs")
    if len(result["target_rows"]) != 180 or outcomes(result) != result["summary"]:
        raise ValueError("Unverified model/target comparison")


def main():
    args = argparse.ArgumentParser()
    args.add_argument("action", choices=["write", "check", "rebuild"])
    action = args.parse_args().action
    if action == "write":
        core.save(PUBLISHED, build())
    value = read(PUBLISHED)
    check(value)
    if action == "rebuild" and build() != value:
        raise ValueError("Raw and published model-expression results differ")
    print("Verified every model-only operation and 20 paired targets.")


if __name__ == "__main__":
    main()
