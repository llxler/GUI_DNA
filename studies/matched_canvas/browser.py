"""Calibrate or score the five isolated current-task files."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
from studies import browser_jobs
from studies.study_io import ROOT, UPSTREAM, dump, sha, source_files

OUT = ROOT / 'artifacts/matched-canvas-20261118'
PROJECT = UPSTREAM / 'projects/canvas'
TASKS = tuple(f'task-{k}' for k in (4, 8, 12, 16, 20))


def add_assets(page):
    shutil.copytree(PROJECT / 'assets', page / 'assets')


def score(page, task, key, calibration=False):
    assert task in TASKS
    browser_jobs.OUT = OUT
    job = {'harness': '157-canvas', 'runtime': '157', 'page': str(page.relative_to(ROOT)),
           'files': source_files(page), 'specs': [task]}
    result = browser_jobs.grade(key, job, calibration)
    assert set(result['tests']) == {task}
    return {'passed': result['all_passed'], 'report_sha256': result['report_sha256']}


def calibrate():
    browser_jobs.OUT = OUT
    browser_jobs.prepare_harness('expansion', 'canvas')
    reference = OUT / 'controls/reference'
    blank = OUT / 'controls/blank'
    if not reference.exists():
        shutil.copytree(PROJECT / 'src', reference)
        add_assets(reference)
    if not blank.exists():
        blank.mkdir(parents=True)
        (blank / 'index.html').write_text('<!doctype html><title>Blank</title>')
        add_assets(blank)
    jobs = [(page, task) for task in TASKS for page in (reference, blank)]
    def run(job):
        page, task = job
        key = page.name + '/' + task
        return key, score(page, task, key, True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = dict(pool.map(run, jobs))
    dump(OUT / 'calibration.json', results)


if __name__ == '__main__':
    calibrate()
