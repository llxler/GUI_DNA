"""Paired full-package Qwen arm; share the frozen compact arm's scoring in an isolated process."""
import argparse
from pathlib import Path
import shutil

from studies.study_io import ROOT, dump, now, read, sha
from . import run as compact
from .local_planner import GENERATION, MODEL, REVISION

ROOT_FULL = ROOT / "artifacts/svg-chart-full-local-20261123"
ROOT_COMPACT = compact.OUT
FULL_EVAL = compact.PREVIOUS / "replays/svg-chart-full-local-20261123"
PUBLIC = ROOT / "studies/results/svg-chart-local-prompt-comparison-20261123.json"


def freeze():
    path = ROOT_FULL / "freeze.json"
    if path.exists():
        compact.verify(path)
        return
    paths = [Path(__file__), compact.HERE / "FULL.md", compact.HERE / "local_planner.py", compact.HERE / "run.py",
             ROOT_COMPACT / "freeze.json", compact.PREVIOUS / "freeze.json", compact.PREVIOUS / "projection.json"]
    for n in compact.TASKS:
        source = compact.PREVIOUS / "prompts/full" / f"task-{n}.json"
        dest = ROOT_FULL / "prompts" / source.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        paths.extend([source, dest])
    shutil.copyfile(compact.browser.SOURCE / "package.json", ROOT_FULL / "package.json")
    paths.append(ROOT_FULL / "package.json")
    modules = ROOT_FULL / "node_modules"
    if not modules.exists():
        modules.symlink_to(compact.browser.RUNTIME / "node_modules", target_is_directory=True)
    dump(path, {"utc": now(), "arms": ["full", "compact"], "targets": compact.TASKS, "model": MODEL,
                "revision": REVISION, "generation_config": GENERATION,
                "sha256": {str(p.relative_to(ROOT)): sha(p) for p in paths}})


def compare():
    assert (ROOT_COMPACT / "local-generation.json").exists()
    # The compact scoring script takes its experiment roots from module constants, as does the upstream harness.
    # This CLI process has its own full-package directories; scoring and validation otherwise run unchanged.
    compact.OUT, compact.EVAL, compact.prepare = ROOT_FULL, FULL_EVAL, freeze
    full = compact.run_evaluation()
    other = read(ROOT_COMPACT / "results.json")
    assert full["targets"] == other["targets"] and full["decoder"] == other["decoder"]
    pairs = []
    for a, b in zip(full["rows"], other["rows"]):
        n = a["task"]
        assert a["task"] == b["task"]
        p = read(ROOT_FULL / "prompts" / f"task-{n}.json")
        q = read(ROOT_COMPACT / "prompts" / f"task-{n}.json")
        assert p[0] == q[0] and p[1]["content"].split("\nFrozen package: ", 1)[0] == q[1]["content"].split("\nFrozen package: ", 1)[0]
        pairs.append({"task": n, "both_observed": a["response"] and b["response"],
                      "full_strict": a["local_strict"], "compact_strict": b["local_strict"],
                      "full_recovery": a["local_with_fallback"], "compact_recovery": b["local_with_fallback"]})
    common = [r for r in pairs if r["both_observed"]]
    return {"project": "web-bench/svg-chart", "model": MODEL, "revision": REVISION, "targets": list(compact.TASKS),
            "decoding": GENERATION, "paired_n": len(common), "pairs": pairs,
            "strict_gains": [r["task"] for r in common if r["compact_strict"] and not r["full_strict"]],
            "strict_losses": [r["task"] for r in common if r["full_strict"] and not r["compact_strict"]],
            "passes_on_pairs": {k: sum(r[k] for r in common) for k in ("full_strict", "compact_strict", "full_recovery", "compact_recovery")},
            "full": full, "compact_provenance": other["sha256"], "purpose": "Supplemental local planner study after remote rate limiting"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["freeze", "publish", "check"])
    stage = parser.parse_args().stage
    freeze()
    if stage != "freeze":
        data = compare()
        if stage == "publish":
            dump(PUBLIC, data)
        else:
            assert data == read(PUBLIC)
        print(data["paired_n"], data["passes_on_pairs"])
