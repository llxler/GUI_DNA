"""Serve new table packages and plans with the original November 23 target contract."""
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from studies import browser_jobs
from studies.study_io import ROOT, UPSTREAM, read, sha, source_files
from studies.table_library_sources import core
from studies.interface_blind.core import write_files

HARNESS = "157-table"


def build_messages(task, package):
    return core.messages("ai", task, package)


def materialize(package, plan, folder):
    files = core.render("ai", package, plan)
    write_files(folder, files)
    return source_files(folder)


def bind_starter(package):
    """Wrap an existing compiler whose compiled document loads the starter stylesheet."""
    starter = core.starter()
    wrapper = (Path(__file__).parent / "bind_starter.js").read_text()
    new = dict(package)
    new["compiler"] = (wrapper.replace("ORIGINAL_COMPILER", package["compiler"], 1)
                       .replace("STARTER_HTML", json.dumps(starter["index.html"]), 1)
                       .replace("STARTER_CSS", json.dumps(starter["index.css"]), 1))
    return new


def score_pages(out, jobs, workers=4):
    """Grade (key, task, frozen page) triples. Run each project's adapter in its own process."""
    previous = browser_jobs.OUT
    browser_jobs.OUT = out
    try:
        if browser_jobs.prepare_harness("expansion", "table") != HARNESS:
            raise ValueError("Unexpected table harness")
        old = core.OUT / "harness" / HARNESS
        current = out / "harness" / HARNESS
        for name in ("package.json", "playwright.config.cjs"):
            assert sha(old / name) == sha(current / name)
        for spec in (UPSTREAM / "projects/table/test").rglob("*"):
            if spec.is_file():
                assert sha(spec) == sha(current / "test" / spec.relative_to(UPSTREAM / "projects/table/test"))
        def grade(job):
            key, task, page = job
            scores = browser_jobs.grade(key, {"harness": HARNESS, "runtime": "157",
                "page": str(page.relative_to(ROOT)), "files": source_files(page),
                "specs": browser_jobs.current_task_specs(task)})
            return key, {"passed": scores["all_passed"], "report_sha256": scores["report_sha256"]}
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return dict(pool.map(grade, jobs))
    finally:
        browser_jobs.OUT = previous
