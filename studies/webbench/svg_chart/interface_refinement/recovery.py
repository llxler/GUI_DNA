"""Replay a documented default and a format-only fallback on two archived SVG cohorts."""
import argparse
from pathlib import Path

from gui_dna.provider import parse_json
from studies.interface_blind.core import compile_plan
from studies.study_io import ROOT, dump, now, read, sha, source_files
from .adapter import BUILD, HERE, ORIGINAL, OUT, TASKS, checked_score, files_under, browser, lock, materialize, old_package, score_run
from .environment import setup

DIR = OUT / "example-recovery"
COHORTS = {"original20": (ORIGINAL, TASKS, "response"), "earlier5": (BUILD, (4, 8, 12, 16, 20), "generated")}


def verify(freeze):
    for name, value in freeze["sha256"].items():
        assert sha(ROOT / name) == value, name


def prepare():
    DIR.mkdir(exist_ok=True)
    path = DIR / "freeze.json"
    if path.exists():
        verify(read(path))
        return
    package = old_package()
    starter = files_under(browser.SOURCE / "src-init")
    default = compile_plan(package, package["examples"][0]["plan"])
    assert default == (starter | default)
    page = DIR / "fixed-page"
    files = materialize(page, default)
    hashes = [HERE / "RECOVERY.md", Path(__file__), HERE / "environment.py", HERE / "adapter.py",
              BUILD / "ai-package.json", OUT / "freeze.json"]
    rows_by_cohort = {}
    for key, (origin, tasks, flag) in COHORTS.items():
        generated_path = origin / "generation-complete.json"
        saved = read(generated_path)
        saved = saved["rows"] if isinstance(saved, dict) else saved
        records = {r["task"]: r for r in saved if r["arm"] == "ai"}
        assert set(records) == set(tasks)
        hashes.extend([generated_path, origin / "results.json"])
        rows = []
        for n in tasks:
            record = records[n]
            target = origin / "runs/ai" / f"task-{n}"
            record_file = target / "record.json"
            assert read(record_file) == record
            hashes.append(record_file)
            row = {"task": n, "response": record[flag], "fallback": False, "files": None}
            if record[flag]:
                response = target / "call/response.json"
                hashes.extend([response, target / "call/request.json"])
                raw = read(response)["choices"][0]["message"]["content"]
                try:
                    generated = compile_plan(package, parse_json(raw))
                except (KeyError, TypeError, ValueError):
                    assert not record.get("files")
                    row.update(fallback=True, files=files, page=str(page.relative_to(ROOT)))
                else:
                    candidate = target / "page"
                    if origin == ORIGINAL:
                        generated = starter | generated
                    rebuilt = materialize(DIR / "audit" / key / f"task-{n}", generated)
                    assert rebuilt == source_files(candidate) == record["files"]
                    row.update(files=record["files"], page=str(candidate.relative_to(ROOT)))
            rows.append(row)
        rows_by_cohort[key] = rows
    fixed = [{"task": n, "response": True, "page": str(page.relative_to(ROOT)), "files": files} for n in TASKS]
    dump(path, {"utc": now(), "example_index": 0, "rows": rows_by_cohort, "fixed": fixed,
                "sha256": {str(p.relative_to(ROOT)): sha(p) for p in hashes}})


def evaluate():
    frozen = read(DIR / "freeze.json")
    verify(frozen)
    setup()
    fixed = score_run(DIR / "fixed-evaluation", frozen["fixed"])
    retained = {}
    for cohort, (origin, tasks, _) in COHORTS.items():
        # Rescore all retained historical pages using a separate arm of the unchanged evaluator.
        # Non-cohort positions are evaluation placeholders and never become observations.
        rows = {r["task"]: r for r in frozen["rows"][cohort] if r["files"] and not r["fallback"]}
        only_retained = [rows.get(n, {"task": n, "response": False, "files": None}) for n in TASKS]
        scored = score_run(DIR / (cohort + "-retained-evaluation"), only_retained)
        results = {r["task"]: r["passed"] for r in read(origin / "results.json")["rows"] if r["arm"] == "ai"}
        assert set(results) == set(tasks)
        for n in rows:
            archived = checked_score(origin / "scores/ai" / f"task-{n}", n)
            assert archived["passed"] == results[n] == scored[str(n)]["passed"]
        retained[cohort] = []
        for r in frozen["rows"][cohort]:
            n = r["task"]
            item = fixed[str(n)] if r["fallback"] else scored[str(n)]
            if r["fallback"]:
                assert r["files"] == frozen["fixed"][n - 1]["files"]
            retained[cohort].append({"task": n, "original": results[n], "used_example": r["fallback"],
                                     "passed": item["passed"], "report_sha256": item["report_sha256"]})
    result = {"freeze_sha256": sha(DIR / "freeze.json"), "fixed": fixed, "recovery": retained}
    path = DIR / "results.json"
    if path.exists():
        assert read(path) == result
    else:
        dump(path, result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["freeze", "evaluate"])
    stage = parser.parse_args().stage
    DIR.mkdir(exist_ok=True)
    with lock(DIR):
        prepare()
        if stage == "evaluate":
            evaluate()
