"""Recheck single-target outcomes under joint vs split tokenizer boundaries."""
import argparse
from pathlib import Path

from studies.public_library_transfer import core
from studies.study_io import ROOT, read, sha
from ..report import compact
from . import model
from .report import summarize
from .token_boundary import OUT, HERE, TYPED

PUBLISHED = HERE / "token-boundary-result.json"


def count_matches(comparison):
    return {tag: {mode: sum(item[mode] == item["canonical"] for item in rows if item["canonical"])
                  for mode in ("split", "joint")} for tag, rows in comparison.items()}


def build():
    original = read(HERE / "model-result.json")
    base = read(HERE / "result.json")
    rows = [compact(row) for row in read(OUT / "scores.json")["rows"]]
    rows += [r for r in original["target_rows"] if r["arm"] == "linker"]
    comparison = read(OUT / "seal.json")["comparison"]
    env = read(model.OUT / "environment.json")
    logs = [read(p) for p in (OUT / "builds").glob("*/key-*.json")]
    proof = [OUT / "registered.json", OUT / "seal.json", OUT / "scores.json",
             HERE / "model-result.json", HERE / "result.json"]
    return {"project": "calculator", "model": original["model"], "revision": original["revision"], "environment": env,
            "targets": base["targets"], "target_rows": rows, "expressions": comparison,
            "public_rule_settings": base["public_rule_settings"], "matches_canonical_on_nine": count_matches(comparison),
            "summary": summarize(rows, base["public_rule_settings"]), "split_summary": original["summary"],
            "accounting": {"remote_calls": 0, "api_usd": 0, "new_model_completions": len(logs),
                           "input_tokens": sum(x["input_tokens"] for x in logs),
                           "output_tokens": sum(len(x["output_ids"]) for x in logs)},
            "sources_sha256": read(OUT / "registered.json")["contract"]["sources"],
            "evidence_sha256": {str(p.relative_to(ROOT)): sha(p) for p in proof}}


def check(value):
    for path, digest in value["sources_sha256"].items():
        if sha(ROOT / path) != digest:
            raise ValueError("Changed tokenization protocol")
    prior = read(HERE / "model-result.json")
    for path in (HERE / "result.json", HERE / "model-result.json"):
        if sha(path) != value["evidence_sha256"][str(path.relative_to(ROOT))]:
            raise ValueError("Changed shared control")
    if len(value["target_rows"]) != 180 or value["summary"] != summarize(value["target_rows"], value["public_rule_settings"]):
        raise ValueError("Incorrect joint-token outcome")
    if value["split_summary"] != prior["summary"] or count_matches(value["expressions"]) != value["matches_canonical_on_nine"]:
        raise ValueError("Changed previous tokenizer outcome")
    for tag, entries in value["expressions"].items():
        if len(entries) != 13 or sum(r["canonical"] is not None for r in entries) != 9:
            raise ValueError("Unexpected number of operations")
        initial = {r["label"]: r["expression"] for r in prior["operations"][tag]}
        if initial != {r["label"]: r["split"] for r in entries}:
            raise ValueError("Original expressions do not match the original study")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["write", "check", "rebuild"])
    action = parser.parse_args().action
    if action == "write":
        core.save(PUBLISHED, build())
    out = read(PUBLISHED)
    check(out)
    if action == "rebuild" and out != build():
        raise ValueError("Raw browser evidence differs")
    print("Verified joint tokenization and both libraries on all twenty tasks.")


if __name__ == "__main__":
    main()
