"""Seal the parent relationship separately from immutable browser results."""

from argparse import ArgumentParser
from pathlib import Path
from unittest.mock import patch

from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, read, sha


def locations(project):
    web = ROOT / "studies/webbench"
    if project == "calculator":
        folder = web / "calculator/key_programs/individual_keys"
        parent = "calculator-key-programs"
        stage = "calculator-individual-keys"
    elif project == "table":
        folder = web / "table/model_modules/public_trace"
        parent = "table-structured-design"
        stage = "table-self-public-trace"
    else:
        raise ValueError(project)
    return (
        folder,
        ROOT / "artifacts" / (stage + "-20261128"),
        ROOT / "artifacts" / (parent + "-20261128"),
    )


def verify(project):
    folder, work, parent = locations(project)
    result = read(folder / "result.json")
    raw, old = read(work / "seal.json"), read(parent / "seal.json")
    assert result["seal"] == sha(work / "seal.json")
    assert result["registration"] == sha(work / "registration.json")
    assert old["registration"] == sha(parent / "registration.json")
    if project == "calculator":
        assert raw["parent_seal"] == sha(parent / "seal.json")
        choices = {(r["tag"], r["task"]): r for r in old["rows"] if r["arm"] == "self"}
        replay = [r for r in raw["rows"] if r["arm"] == "old-code-same-choice"]
        assert len(replay) == 20 * len(result["models"])
        for row in replay:
            before = choices[row["tag"], row["task"]]
            assert all(
                row.get(k) == before.get(k) for k in ("levels", "status", "files")
            )
    else:
        expected = {
            t for t, v in old["libraries"].items() if v["status"] == "build_failed"
        }
        assert set(result["libraries"]) == expected
        for tag, lib in result["libraries"].items():
            for attempt in lib["trials"]:
                original = (
                    parent
                    / "libraries"
                    / tag
                    / str(attempt["attempt"])
                    / "attempt.json"
                )
                assert attempt["source_sha256"] == sha(original)
    link = dict(
        result_sha256=sha(folder / "result.json"),
        parent_seal=sha(parent / "seal.json"),
        seal=result["seal"],
    )
    core.save(folder / "lineage.json", link)
    return link


def execute(project):
    folder, work, parent = locations(project)
    if project == "calculator":
        from studies.webbench.calculator.key_programs.individual_keys import (
            run as runner,
        )
    else:
        from studies.webbench.table.model_modules.public_trace import run as runner
    write = core.save
    date = sha(parent / "seal.json")
    raw_result = folder / "result.json"

    def save(path, value):
        # The original score writer seals the raw result before the runner supplies its parent.
        # Check that the second request contains only that reference; never replace the result.
        if (
            Path(path) == raw_result
            and raw_result.exists()
            and value == read(raw_result) | {"parent_seal": date}
        ):
            return
        write(path, value)

    with browser.lock(work / "study.lock"), patch.object(core, "save", save):
        if project == "calculator":
            runner.run(runner.register())
        else:
            runner.run()
        return verify(project)


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("project", choices=("calculator", "table"))
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute the registered study before verifying its receipts.",
    )
    args = parser.parse_args()
    print(execute(args.project) if args.execute else verify(args.project))
