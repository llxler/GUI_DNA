"""Official SVG-Chart assertions and upstream viewport, served with pinned Vite."""
import json
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from studies.interface_blind.core import ROOT, UPSTREAM, browser_env, dump
from studies.study_io import cases_by_file, sha
from studies.webbench_draw.browser import RUNTIME, Server

OUT = ROOT / 'artifacts/svg-chart-sources-20261121'
SOURCE = UPSTREAM / 'projects/svg-chart'
HARNESS = OUT / 'harness'
TARGETS = (4, 8, 12, 16, 20)


def harness():
    HARNESS.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCE / 'package.json', OUT / 'package.json')
    if not (OUT / 'node_modules').exists():
        (OUT / 'node_modules').symlink_to(RUNTIME / 'node_modules', target_is_directory=True)
    shutil.copytree(SOURCE / 'test', HARNESS / 'test', dirs_exist_ok=True)
    for name in ('package.json', 'playwright.config.js'):
        shutil.copyfile(SOURCE / name, HARNESS / name)
    link = HARNESS / 'node_modules'
    if not link.exists():
        link.symlink_to(RUNTIME / 'node_modules', target_is_directory=True)
    (HARNESS / 'run.config.js').write_text("""import base from './playwright.config.js';
export default {...base,webServer:undefined,workers:1,retries:0,fullyParallel:false,
reporter:[['json',{outputFile:process.env.REPORT_FILE}]],
use:{...base.use,baseURL:process.env.CANDIDATE_URL,trace:'off'}};""")


def grade(arm, n, page):
    folder = OUT / 'scores' / arm / f'task-{n}'
    if folder.exists():
        raise FileExistsError(folder)
    folder.mkdir(parents=True)
    report = folder / 'report.json'
    with Server(page) as server:
        env = dict(browser_env(), REPORT_FILE=str(report), CANDIDATE_URL=server.url,
                   EVAL_PROJECT_ROOT=str(page), IS_EVAL_PRODUCTION='1', CI='1')
        with (folder / 'console.log').open('w') as log:
            rc = subprocess.run(['node', str(RUNTIME / 'node_modules/@playwright/test/cli.js'), 'test',
                                 '--config=run.config.js', f'test/task-{n}.spec.js', '--max-failures=1',
                                 '--output', str(folder / 'output')], env=env, cwd=HARNESS,
                                stdout=log, stderr=subprocess.STDOUT, timeout=300).returncode
    data = json.loads(report.read_text())
    errors = [e for e in data.get('errors', []) if 'maximum allowed failures' not in e.get('message', '')]
    cases = cases_by_file(data)
    outcomes = [v for tests in cases.values() for v in tests]
    if errors or not outcomes:
        raise RuntimeError(f'Infrastructure error; see {report}')
    if rc and not any(set(v['statuses']) & {'failed', 'timedOut'} for v in outcomes):
        raise RuntimeError(f'Incomplete execution; see {report}')
    passed = rc == 0 and all(v['passed'] for v in outcomes)
    dump(folder / 'score.json', {'passed': passed, 'report_sha256': sha(report)})
    return passed


def calibrate():
    harness()
    pages = OUT / 'calibration-pages'
    shutil.copytree(SOURCE / 'src', pages / 'reference')
    blank = pages / 'blank'
    blank.mkdir()
    (blank / 'index.html').write_text('<!doctype html><title>Blank</title>')
    shutil.copytree(SOURCE / 'assets', blank / 'assets')
    def one(job):
        arm, n = job
        return arm, n, grade('calibration-' + arm, n, pages / arm)
    with ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(one, [(a, n) for a in ('reference', 'blank') for n in TARGETS]))
    dump(OUT / 'calibration.json', rows)
    assert all(passed == (arm == 'reference') for arm, _, passed in rows), rows


if __name__ == '__main__':
    calibrate()
