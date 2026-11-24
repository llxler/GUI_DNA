"""Repeat staged self construction on the preregistered questionnaire targets."""

import argparse
from datetime import datetime, timezone
from pathlib import Path

from studies.public_library_transfer import core
from studies.public_library_transfer.self_refinement import run as staged
from studies.study_io import ROOT, sha

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/self-refinement-form-20261124"
OLD = ROOT / "studies/results/backbone-form-20261124.json"
MODELS = {
    "qwen9": ("qwen/qwen3.5-9b", 1.50, 0.35, 1.2),
    "oss": ("openai/gpt-oss-120b", 1.50, 0.25, 1.0),
}
END = datetime(2026, 11, 24, 5, 18, tzinfo=timezone.utc)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "generate", "score", "verify"))
    parser.add_argument("tag", nargs="?", choices=MODELS)
    args = parser.parse_args()
    staged.configure(OUT, "form", MODELS, END)
    if args.action == "register":
        core.save(
            OUT / "transfer-protocol.json",
            {
                "protocol": sha(HERE / "PROTOCOL.md"),
                "launcher": sha(Path(__file__)),
                "old_study": sha(OLD),
                "models": MODELS,
                "project": "form",
                "targets": list(range(1, 21)),
                "request_deadline": END.isoformat(),
                "earlier_exposure_usd": 6.478155,
                "separate_caps_usd": {
                    "table_self": 4.0,
                    "form_self": 3.0,
                    "table_gpt6": 2.5,
                },
            },
        )
        staged.register()
    elif args.action == "verify":
        staged.verify()
    elif args.tag:
        getattr(staged, args.action)(args.tag)
    else:
        parser.error("A model tag is required")


if __name__ == "__main__":
    main()
