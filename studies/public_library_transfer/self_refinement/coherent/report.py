"""Verify matched Direct reuse and the same-design implementation comparison."""

import argparse

from studies.public_library_transfer import core
from studies.public_library_transfer.self_refinement.coherent import run
from studies.public_library_transfer.self_refinement.native import report as original
from studies.public_library_transfer.self_refinement.native import transport
from studies.study_io import ROOT, read, sha

OUT = ROOT / "studies/results/self-coherent-20261124.json"


def check(data, earlier):
    original.public_check(data)
    for project, block in data["projects"].items():
        reference = earlier["projects"][project]
        assert block["direct_seal_sha256"] == reference["direct_seal_sha256"]
        for group, model in block["replicas"].items():
            previous = reference["replicas"][group]
            assert model["controls"] == previous["controls"]
            for r, other in zip(model["rows"], previous["rows"], strict=True):
                assert r["task"] == other["task"]
                # Independent browser executions can serialize different durations.
                for key in ("status", "files_digest", "passed"):
                    assert r["direct"].get(key) == other["direct"].get(key)
            common = [
                (r["task"], r["self"]["passed"], o["self"]["passed"])
                for r, o in zip(model["rows"], previous["rows"], strict=True)
                if None not in (r["self"]["passed"], o["self"]["passed"])
            ]
            assert model["relative_to_same_design"] == {
                "common": [i for i, _, _ in common],
                "gained": [i for i, new, old in common if new and not old],
                "lost": [i for i, new, old in common if old and not new],
            }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "check-local"))
    args = parser.parse_args()
    earlier = read(original.RESULT)
    if args.action == "check":
        check(read(OUT), earlier)
        return
    run.verify()
    reg = run.OUT / "registered.json"
    data = {
        "model": transport.MODEL,
        "registered_utc": read(reg)["utc"],
        "registration_sha256": sha(reg),
        "protocol_sha256": sha(run.HERE / "PROTOCOL.md"),
        "reused_design_and_direct_source": sha(original.RESULT),
        "project_budget_usd": run.CAP,
        "end_utc": transport.END.isoformat(),
        "projects": {},
    }
    for project in run.native.PROJECTS:
        block = original.project_report(
            project, stage=run.OUT, schema_steps=("target",)
        )
        for group, model in block["replicas"].items():
            previous = earlier["projects"][project]["replicas"][group]
            new = {r["task"]: r["self"]["passed"] for r in model["rows"]}
            other = {r["task"]: r["self"]["passed"] for r in previous["rows"]}
            joint = [i for i in new if None not in (new[i], other[i])]
            model["relative_to_same_design"] = {
                "common": joint,
                "gained": [i for i in joint if new[i] and not other[i]],
                "lost": [i for i in joint if other[i] and not new[i]],
            }
        data["projects"][project] = block
    check(data, earlier)
    if args.action == "write":
        core.save(OUT, data)
    else:
        assert data == read(OUT)


if __name__ == "__main__":
    main()
