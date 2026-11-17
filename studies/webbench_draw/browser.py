"""Identical Vite serving and unchanged official assertions for every arm."""
from __future__ import annotations
import json
from pathlib import Path
import select
import shutil
import subprocess
import tempfile
from studies.browser_jobs import check_explicit_specs
from test.interface_blind.core import ROOT, UPSTREAM, browser_env, dump
from studies.study_io import cases_by_file, digest, now, read, sha, source_files

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/webbench-draw-current-only'
RUNTIME = ROOT / 'artifacts/webbench-draw-runtime-20261117'


class Server:
    def __init__(self, page):
        self.page = Path(page).resolve()

    def __enter__(self):
        self.cache = tempfile.TemporaryDirectory(prefix='gui-dna-draw-')
        self.process = subprocess.Popen(['node', str(HERE / 'server.mjs'), str(self.page), self.cache.name],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=browser_env())
        try:
            if not select.select([self.process.stdout], [], [], 30)[0]:
                raise RuntimeError('Vite startup timed out')
            line = self.process.stdout.readline().strip()
            if not line.startswith('READY '):
                raise RuntimeError('Vite startup failed: ' + line)
            self.url = line.removeprefix('READY ').rstrip('/')
            return self
        except Exception:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *args):
        self.process.terminate()
        try:
            self.process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.communicate()
        self.cache.cleanup()


def link_runtime(folder):
    folder.mkdir(parents=True, exist_ok=True)
    link = folder / 'node_modules'
    if not link.exists():
        link.symlink_to(RUNTIME / 'node_modules', target_is_directory=True)


def public_check(page):
    with Server(page) as server:
        process = subprocess.run(['node',str(HERE / 'check.cjs'),server.url],
            capture_output=True,text=True,env=browser_env(),timeout=40)
        if process.returncode:
            raise RuntimeError('Public browser process: ' + process.stderr[:1200])
        return json.loads(process.stdout)


def prepare_harness():
    target = OUT / 'harness/projects/draw'
    if target.exists():
        return target
    shutil.copytree(UPSTREAM / 'projects/draw/test', target / 'test')
    utility = RUNTIME / 'node_modules/@web-bench/test-util'
    if not utility.exists():
        shutil.copytree(UPSTREAM / 'libraries/test-util/src', utility / 'src')
        dump(utility / 'package.json', {'name':'@web-bench/test-util', 'main':'src/index.js'})
    libraries = OUT / 'harness/libraries'
    libraries.mkdir(parents=True, exist_ok=True)
    (libraries / 'test-util').symlink_to(utility, target_is_directory=True)
    link_runtime(OUT)
    link_runtime(OUT / 'harness')
    dump(target / 'package.json', {'type':'commonjs'})
    (target / 'playwright.config.cjs').write_text("""const {defineConfig, devices} = require('@playwright/test');
module.exports=defineConfig({testDir:'./test',timeout:30000,expect:{timeout:5000},
 fullyParallel:false,workers:1,retries:0,forbidOnly:true,
 reporter:[['json',{outputFile:process.env.REPORT_FILE}]],
 use:{baseURL:process.env.CANDIDATE_URL,trace:'off',headless:true},
 projects:[{name:'chromium',use:{...devices['Desktop Chrome']}}]});
""")
    return target


def grade(key, job, calibration=False):
    check_explicit_specs(job["specs"])
    folder = OUT / ('calibration' if calibration else 'scores') / key
    target = folder / 'score.json'
    if target.exists():
        result = read(target)
        assert sha(folder / 'report.json') == result['report_sha256']
        return result
    assert not folder.exists(), f'Partial evidence retained; do not overwrite: {folder}'
    page = ROOT / job['page']
    assert source_files(page) == job['files']
    harness = prepare_harness()
    folder.mkdir(parents=True)
    report = folder / 'report.json'
    with Server(page) as server:
        env = browser_env()
        env.update(CANDIDATE_URL=server.url, REPORT_FILE=str(report), EVAL_PROJECT_ROOT=str(page))
        command = ['node', str(RUNTIME / 'node_modules/@playwright/test/cli.js'), 'test',
            '--config', str(harness / 'playwright.config.cjs'), '--workers=1',
            '--max-failures=1', '--output', str(folder / 'test-results')]
        command += [f'{spec}.spec.js' for spec in job['specs']]
        with (folder / 'stdout.log').open('w') as output:
            process = subprocess.run(command, cwd=harness, env=env, stdout=output,
                stderr=subprocess.STDOUT, timeout=600)
    assert source_files(page) == job['files']
    raw = read(report)
    cases = cases_by_file(raw)
    statuses = [s for tests in cases.values() for case in tests for s in case['statuses']]
    failed = any(s in ('failed', 'timedOut') for s in statuses)
    passed = process.returncode == 0 and set(cases) == set(job['specs']) and all(
        case['passed'] for tests in cases.values() for case in tests)
    assert passed or failed, f'Infrastructure/incomplete score: {folder}'
    unexpected = [e for e in raw.get('errors', []) if 'maximum allowed failures' not in e.get('message','')]
    assert not unexpected, f'Unexpected global test error: {folder}'
    result = {'passed':passed, 'cases':cases, 'returncode':process.returncode,
        'report_sha256':sha(report), 'finished_utc':now(), 'job':job}
    dump(target, result)
    print(f'score {key[:12]} passed={passed}', flush=True)
    return result


def calibrate():
    prepare_harness()
    folder = OUT / 'calibration-pages'
    reference = folder / 'reference'
    if not reference.exists():
        shutil.copytree(UPSTREAM / 'projects/draw/src', reference)
    blank = folder / 'blank'
    blank.mkdir(parents=True, exist_ok=True)
    (blank / 'index.html').write_text('<!doctype html><html><body></body></html>')
    rows = []
    for kind, page, specs in [(f'reference-{k}', reference, [f'task-{k}']) for k in (4,8,12,16,20)]:
        job = {'page':str(page.relative_to(ROOT)), 'files':source_files(page), 'specs':specs}
        result = grade(kind, job, True)
        rows.append({'kind':kind, 'passed':result['passed'], 'score':'calibration/' + kind + '/score.json'})
    for k in (4,8,12,16,20):
        job = {'page':str(blank.relative_to(ROOT)), 'files':source_files(blank), 'specs':[f'task-{k}']}
        result = grade(f'blank-{k}', job, True)
        rows.append({'kind':f'blank-{k}', 'passed':result['passed'], 'score':f'calibration/blank-{k}/score.json'})
    dump(OUT / 'calibration.json', {'created_utc':now(), 'rows':rows,
        'valid':all(row['passed'] for row in rows[:5]) and not any(row['passed'] for row in rows[5:])})
    assert all(row['passed'] for row in rows[:5]) and not any(row['passed'] for row in rows[5:]), 'Calibration failed; no paid generation'


if __name__ == '__main__':
    calibrate()
