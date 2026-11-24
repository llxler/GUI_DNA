"""Register and run the independent form transfer of the line-based builder."""

import argparse
from pathlib import Path

from studies.public_library_transfer import core
from studies.public_library_transfer.self_replication.run import END, HERE, OLD
from studies.study_io import ROOT, read, sha

OUT = ROOT / "artifacts/self-lines-form-20261124"
MODELS = {
    "qwen9": ("qwen/qwen3.5-9b", 1.49, 0.35, 1.2),
    "oss": ("openai/gpt-oss-120b", 1.49, 0.25, 1.0),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("enroll", "register", "generate", "score", "verify")
    )
    parser.add_argument("tag", nargs="?", choices=MODELS)
    args = parser.parse_args()
    design = {
        "project": "form",
        "models": MODELS,
        "tasks": list(range(1, 21)),
        "protocol": sha(HERE / "LINE_CONTRACT.md"),
        "launcher": sha(Path(__file__)),
        "old_study": sha(OLD),
        "end": END.isoformat(),
        "previous_attempt": sha(
            ROOT / "studies/results/self-refinement-form-20261124.json"
        ),
    }
    prereg = OUT / "transfer-protocol.json"
    if args.action == "enroll":
        core.save(prereg, {"registered_utc": core.now(), **design})
        return
    import json
    from studies.public_library_transfer.self_refinement.line_contract import run

    assert {
        k: v for k, v in read(prereg).items() if k != "registered_utc"
    } == json.loads(json.dumps(design))
    run.configure(OUT, "form", MODELS, END)
    if args.action in ("register", "verify"):
        getattr(run, args.action)()
    elif args.tag:
        getattr(run, args.action)(args.tag)
    else:
        parser.error("A model tag is required")


if __name__ == "__main__":
    main()
