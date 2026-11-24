"""Replay a post-hoc fixed-page delivery rule for the executable-option studies."""

import argparse

from studies.public_library_transfer import core
from studies.study_io import ROOT, read, sha

RESULTS = ROOT / "studies/results"
TABLE = RESULTS / "self-executable-options-20261124.json"
TODO = RESULTS / "self-todomvc-executable-options-20261124.json"
OUT = RESULTS / "self-fixed-delivery-20261124.json"


def outcome(selected, first):
    if selected["status"] in ("invalid", "missing") and first["status"] == "valid":
        return "fixed", first
    return "self", selected


def reconstruct():
    result = {}
    table = read(TABLE)["projects"]["table"]["replicas"]
    todos = read(TODO)["rows"]
    for project in ("table", "todomvc"):
        groups = {}
        for group in ("build-a", "build-b"):
            if project == "table":
                rows = table[group]["rows"]
            else:
                by_task = {}
                for item in todos:
                    if item["group"] in ("direct", group):
                        by_task.setdefault(item["task"], {"task": item["task"]})[
                            item["arm"]
                        ] = item
                rows = [by_task[k] for k in sorted(by_task)]
            observations = []
            for r in rows:
                mode, delivered = outcome(r["self"], r["fixed"])
                observations.append(
                    {
                        "target": r["task"],
                        "selected_source": mode,
                        "self": r["self"]["passed"],
                        "fixed": r["fixed"]["passed"],
                        "direct": r["direct"]["passed"],
                        "delivered": delivered["passed"],
                        "delivered_report_sha256": delivered.get("report_sha256"),
                    }
                )
            joint = [
                r
                for r in observations
                if all(
                    r[a] is not None for a in ("direct", "self", "fixed", "delivered")
                )
            ]
            groups[group] = {
                "joint_target_ids": [r["target"] for r in joint],
                "passed": {
                    a: sum(r[a] for r in joint)
                    for a in ("direct", "self", "fixed", "delivered")
                },
                "fallback_count": sum(
                    r["selected_source"] == "fixed" for r in observations
                ),
                "rows": observations,
            }
        result[project] = groups
    return {
        "post_hoc": True,
        "additional_api_calls": 0,
        "rule": "Keep a delivered plan. A missing or invalid plan may use its own publicly admitted fixed page.",
        "sources_sha256": {p.name: sha(p) for p in (TABLE, TODO)},
        "projects": result,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check"))
    args = parser.parse_args()
    new = reconstruct()
    if args.action == "write":
        core.save(OUT, new)
    else:
        assert new == read(OUT)
    print(
        {
            p: {g: v["passed"] for g, v in groups.items()}
            for p, groups in new["projects"].items()
        }
    )
