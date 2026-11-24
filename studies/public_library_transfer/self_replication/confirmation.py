"""Evaluate the preregistered repeat criteria on the complete table targets."""

import argparse

from studies.public_library_transfer import core
from studies.public_library_transfer.self_replication import run
from studies.study_io import ROOT, read, sha

DEST = ROOT / "studies/results/self-confirmation-20261124.json"
RESULTS = DEST.parent


def reconstruct():
    protocol = run.HERE / "CONFIRMATION.md"
    source = RESULTS / "self-line-contract-20261124.json"
    incremental = RESULTS / "incremental-self-table-20261124.json"
    lines = read(source)["models"]
    phases = {
        "line-qwen9": lines["qwen/qwen3.5-9b"],
        "line-oss": lines["openai/gpt-oss-120b"],
        "incremental-oss": read(incremental),
    }
    arms = {}
    for name, v in phases.items():
        rows = v["rows"]
        assert [r["task"] for r in rows] == list(range(1, 21))
        observed = [
            r
            for r in rows
            if None not in (r["self_refined"]["passed"], r["self_original"]["passed"])
        ]
        old = sum(r["self_original"]["passed"] for r in observed)
        new = sum(r["self_refined"]["passed"] for r in observed)
        arms[name] = {
            "old": old,
            "new": new,
            "common": [r["task"] for r in observed],
            "repeat_triggered": len(observed) == 20 and new > old,
        }
    return {
        "protocol_sha256": sha(protocol),
        "sources_sha256": {v.name: sha(v) for v in (source, incremental)},
        "lanes": arms,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check"))
    args = parser.parse_args()
    data = reconstruct()
    if args.action == "write":
        reg = ROOT / "artifacts/self-confirmation-20261124/registration.json"
        plan = read(reg)
        assert plan["protocol_sha256"] == data["protocol_sha256"] and set(
            data["lanes"]
        ) == set(plan["lanes"])
        core.save(
            DEST,
            {
                "registration_sha256": sha(reg),
                "registered_utc": plan["registered_utc"],
                **data,
            },
        )
    else:
        published = read(DEST)
        assert all(published[k] == v for k, v in data.items())
    print({k: v["repeat_triggered"] for k, v in data["lanes"].items()})


if __name__ == "__main__":
    main()
