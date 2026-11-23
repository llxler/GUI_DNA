"""Public SVG-chart model inputs and an isolated replay of the frozen official evaluator."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import fcntl
import json
from pathlib import Path
import subprocess
import sys

from studies.interface_blind.core import compile_plan
from studies.study_io import ROOT, cases_by_file, dump, now, read, sha, source_files
from studies.svg_chart_interfaces.run import messages
from studies.svg_chart_sources import browser
from studies.svg_chart_sources.run import files_under, inputs, materialize, message


HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/library-refinement-chart-20261123"
ORIGINAL = ROOT / "artifacts/svg-chart-interfaces-20261123"
BUILD = ROOT / "artifacts/svg-chart-sources-20261121"
TASKS = tuple(range(1, 21))


def public_inputs():
    return inputs(), files_under(browser.SOURCE / "src-init"), files_under(browser.SOURCE / "assets")


def builder_messages():
    rows, starter, assets = public_inputs()
    context = ("Vite serves index.html, JS modules and SCSS. Start from these public initial files: " +
               json.dumps(starter) + "\nThese assets are mounted unchanged under assets/ on every candidate: " +
               json.dumps(assets) + "\nUse public DOM and relative imports. No external packages or network requests.\n")
    prompt = message(
        "Design an executable reusable chart library and a data-only composition interface. Choose semantic "
        "components and switches. No task IDs, tables of completed pages or executable code in plans. Return JSON.",
        context + json.dumps(rows) + "\nReturn {design,plan_schema,files,compiler,examples}. plan_schema is text "
        "documenting the JSON plan. compiler is pure synchronous JavaScript source defining function compile(plan,files) "
        "returning a complete file map with index.html. No Node or DOM in compiler. examples is two {description,plan} "
        "entries; both should compile and load.")
    assert prompt == read(BUILD / "builder/0/request.json")["body"]["messages"]
    return prompt


def old_package():
    package = read(BUILD / "ai-package.json")
    assert package == read(ORIGINAL / "packages/ai.json")
    return package


def planner_messages(task, package):
    if task not in TASKS:
        raise ValueError("Expected one of twenty chart targets")
    return messages("ai", task, (files_under(browser.SOURCE / "src-init"),
                                 files_under(browser.SOURCE / "assets"), {"ai": package}))


def materialize_plan(package, plan, page):
    starter = files_under(browser.SOURCE / "src-init")
    return materialize(Path(page), starter | compile_plan(package, plan))


def score_run(run_dir, rows, workers=3):
    """Grade one sealed twenty-target arm; no feedback is returned until the batch completes."""
    directory = Path(run_dir).resolve()
    if not directory.is_relative_to(OUT) or directory == OUT:
        raise ValueError(f"Choose an independent run directory below {OUT}")
    normalized = []
    for row in rows:
        task = row["task"]
        if type(task) is not int or task not in TASKS or type(row["response"]) is not bool:
            raise ValueError("Invalid chart target or response flag")
        files = row.get("files") or None
        value = {"task": task, "response": row["response"], "files": files}
        if files is not None:
            page = (ROOT / row["page"]).resolve()
            if not page.is_relative_to(ROOT / "artifacts") or not row["response"] or source_files(page) != files:
                raise ValueError(f"Unverified candidate files for task {task}")
            value["page"] = str(page.relative_to(ROOT))
        normalized.append(value)
    normalized.sort(key=lambda row: row["task"])
    if [r["task"] for r in normalized] != list(TASKS):
        raise ValueError("Need exactly one target record for every official file")
    directory.mkdir(parents=True, exist_ok=True)
    with lock(directory):
        frozen = directory / "evaluation-inputs.json"
        if frozen.exists():
            verify_inputs(read(frozen))
            if read(frozen)["rows"] != normalized:
                raise ValueError("Candidate set differs from previously sealed inputs")
        else:
            dump(frozen, {"utc": now(), "rows": normalized, "source_sha256": source_hashes()})
    subprocess.run([sys.executable, "-m", "studies.library_refinement_chart.adapter",
                    "evaluate", str(directory), "--workers", str(workers)], cwd=ROOT, check=True)
    result = read(directory / "evaluation-complete.json")
    assert result["inputs_sha256"] == sha(frozen)
    return result["cells"]


@contextmanager
def lock(directory):
    with (directory / ".evaluation.lock").open("a") as lockfile:
        fcntl.flock(lockfile, fcntl.LOCK_EX)
        yield


def source_hashes():
    paths = [HERE / "adapter.py", Path(browser.__file__), ROOT / "studies/webbench_draw/server.mjs",
             ROOT / "studies/webbench_draw/browser.py", browser.RUNTIME / "package-lock.json",
             browser.SOURCE / "package.json", browser.SOURCE / "playwright.config.js",
             ORIGINAL / "calibration.json", ORIGINAL / "freeze.json"]
    paths.extend(p for p in (browser.SOURCE / "test").rglob("*") if p.is_file())
    return {str(p.relative_to(ROOT)): sha(p) for p in paths}


def verify_inputs(freeze):
    assert freeze["source_sha256"] == source_hashes()
    old = read(ORIGINAL / "freeze.json")["sha256"]
    for name, value in freeze["source_sha256"].items():
        if name in old:
            assert value == old[name], name
    expected = {(arm, n): arm == "reference" or n == 1 for arm in ("reference", "blank") for n in TASKS}
    assert {(a, n): passed for a, n, passed in read(ORIGINAL / "calibration.json")} == expected


def checked_score(folder, task):
    receipt = read(folder / "score.json")
    raw = read(folder / "report.json")
    assert sha(folder / "report.json") == receipt["report_sha256"]
    assert all("maximum allowed failures" in e.get("message", "") for e in raw.get("errors", []))
    cases = cases_by_file(raw)
    assert set(cases) == {f"task-{task}"} and cases[f"task-{task}"]
    assert all(c["passed"] for c in cases[f"task-{task}"]) == receipt["passed"]
    return receipt


def evaluate(directory, workers):
    directory = Path(directory).resolve()
    if not directory.is_relative_to(OUT) or not 1 <= workers <= 6:
        raise ValueError("Invalid isolated scoring directory or number of workers")
    with lock(directory):
        frozen_path = directory / "evaluation-inputs.json"
        frozen = read(frozen_path)
        verify_inputs(frozen)
        assert [row["task"] for row in frozen["rows"]] == list(TASKS)
        browser.OUT, browser.HARNESS = directory, directory / "harness"
        browser.harness()
        def score(row):
            task = row["task"]
            files = row["files"]
            cell = {"passed": False if row["response"] else None, "materialized": bool(files),
                    "report_sha256": None}
            if files is None:
                return str(task), cell
            page = ROOT / row["page"]
            assert source_files(page) == files
            attempt = 1
            while True:
                arm = f"official-{attempt}"
                folder = directory / "scores" / arm / f"task-{task}"
                if (folder / "score.json").exists():
                    break
                if not folder.exists():
                    browser.grade(arm, task, page)
                    break
                # An incomplete infrastructure run is retained in its own directory.
                attempt += 1
            return str(task), cell | checked_score(folder, task)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            cells = dict(pool.map(score, frozen["rows"]))
        result = {"inputs_sha256": sha(frozen_path), "cells": cells}
        settled = directory / "evaluation-complete.json"
        if settled.exists():
            assert read(settled) == result
        else:
            dump(settled, result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["evaluate"])
    parser.add_argument("directory", type=Path)
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    evaluate(args.directory, args.workers)
