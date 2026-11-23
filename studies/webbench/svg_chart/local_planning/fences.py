"""Sensitivity to one enclosing Markdown JSON fence, with the same typed schema."""
import argparse
from collections import Counter
from pathlib import Path
import re

from studies.study_io import ROOT, dump, now, read, sha
from . import run as compact
from .full import ROOT_FULL

PUBLIC = ROOT / "studies/results/svg-chart-local-fences-20261123.json"
INSPECT = ROOT / "artifacts/svg-chart-local-fences-20261123"
FENCE = re.compile(r"\s*```(?:json)?[ \t]*\r?\n(.*?)\r?\n```\s*", re.DOTALL | re.IGNORECASE)
ARMS = {"compact": compact.OUT, "full": ROOT_FULL}


def freeze():
    path = INSPECT / "freeze.json"
    if path.exists():
        compact.verify(path)
        return
    paths = [Path(__file__), compact.HERE / "FENCES.md", compact.HERE / "run.py",
             compact.OUT / "freeze.json", ROOT_FULL / "freeze.json"]
    dump(path, {"utc": now(), "arms": list(ARMS), "targets": compact.TASKS,
                "sha256": {str(p.relative_to(ROOT)): sha(p) for p in paths}})


def assess(arm):
    root = ARMS[arm]
    strict = read(root / "results.json")
    responses = read(root / "local-generation.json")
    rows = []
    actions = []
    for row in strict["rows"]:
        n = row["task"]
        source = root / "runs" / f"task-{n}" / "response.json"
        assert sha(source) == responses["response_sha256"][str(n)]
        candidate = {"task": n, "response": False, "files": None}
        action = "keep"
        if row["response"] and not row["valid_plan"]:
            raw = read(source)["text"]
            matched = FENCE.fullmatch(raw)
            if matched:
                try:
                    plan = compact.read_plan(matched.group(1))
                    page = root / "fence-only-candidates" / f"task-{n}" / "page"
                    files = compact.materialize_plan(compact.old_package(), plan, page)
                    candidate.update(response=True, page=str(page.relative_to(ROOT)), files=files)
                    action = "new_valid"
                except (ValueError, TypeError, KeyError, OverflowError):
                    action = "still_invalid"
            else:
                action = "no_single_fence"
        rows.append(candidate)
        actions.append(action)
    sealed = INSPECT / arm / "candidates.json"
    frozen = {"generation_sha256": sha(root / "local-generation.json"), "actions": actions, "rows": rows}
    if sealed.exists():
        assert read(sealed) == frozen
    else:
        dump(sealed, frozen)
    cells = compact.score_run(compact.PREVIOUS / "replays/svg-chart-local-single-fence" / arm, rows, workers=1)
    result = []
    for baseline, action in zip(strict["rows"], actions):
        n = baseline["task"]
        if action == "new_valid":
            receipt = cells[str(n)]
            passed = receipt["passed"]
            recovered = passed
        else:
            passed = baseline["local_strict"]
            recovered = baseline["local_with_fallback"]
        result.append({"task": n, "response": baseline["response"], "strict": baseline["local_strict"],
                       "action": action, "fence_enabled": passed, "fence_plus_default": recovered})
    return {"responses": sum(r["response"] for r in result), "actions": dict(Counter(actions)),
            "valid_with_fences": sum(r["materialized"] for r in strict["rows"]) + actions.count("new_valid"),
            "passes": {k: sum(r[k] is True for r in result) for k in ("strict", "fence_enabled", "fence_plus_default")},
            "rows": result, "candidates_sha256": sha(sealed)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "compact", "full", "publish", "check"))
    action = parser.parse_args().action
    freeze()
    if action in ARMS:
        dump(INSPECT / action / "results.json", assess(action))
    elif action in ("publish", "check"):
        results = {name: read(INSPECT / name / "results.json") for name in ARMS}
        for name in ARMS:
            assert results[name]["candidates_sha256"] == sha(INSPECT / name / "candidates.json")
        public = {"project": "web-bench/svg-chart", "local_model": compact.MODEL, "local_revision": compact.REVISION,
                  "freeze_sha256": sha(INSPECT / "freeze.json"), "arms": results,
                  "interpretation": "A sensitivity prespecified after inspecting a fenced first local compact response, before official local candidate scoring."}
        if action == "publish":
            dump(PUBLIC, public)
        else:
            assert read(PUBLIC) == public
        print({k: v["passes"] for k, v in results.items()})
