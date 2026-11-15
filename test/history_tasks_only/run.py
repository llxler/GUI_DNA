"""Freeze and complete task-only history evidence without changing old scores."""
from concurrent.futures import ThreadPoolExecutor
import argparse
from pathlib import Path
import shutil
import subprocess

from test.history_replay.run import (
    ROOT, RUNTIME, Server, browser_env, cases_by_file, digest, dump, now, read, sha,
)

HERE = Path(__file__).resolve().parent
ORIGINAL = ROOT / 'artifacts/history-replay-20261115'
OUT = ROOT / 'artifacts/history-tasks-only-20261115'


def observed(cases, specs):
    selected = {name: cases.get(name, []) for name in specs}
    if any(status in ('failed', 'timedOut') for group in selected.values()
           for case in group for status in case['statuses']):
        return False, 'observed_task_failure'
    if all(group and all(case['passed'] for case in group) for group in selected.values()):
        return True, 'all_task_files_observed_passed'
    return None, 'task_files_unresolved_after_init_failure'


def prepare():
    if OUT.exists():
        raise RuntimeError('Refuse to replace an existing diagnostic')
    from test.history_replay.run import verify as verify_original
    original = verify_original()
    assert (ORIGINAL / 'evaluation-complete.json').exists()
    decisions, jobs = {}, {}
    for key, job in original['jobs'].items():
        report = ORIGINAL / 'scores' / key / 'report.json'
        receipt = read(report.with_name('score.json'))
        assert sha(report) == receipt['report_sha256']
        cases = cases_by_file(read(report))
        specs = [s for s in job['specs'] if s != 'init']
        assert specs
        value, reason = observed(cases, specs)
        if value is None:
            assert any(s in ('failed', 'timedOut') for c in cases.get('init', []) for s in c['statuses'])
            jobs[key] = {**job, 'specs': specs}
        decisions[key] = {'observed': value, 'reason': reason, 'old_report': str(report.relative_to(ROOT)),
                          'old_report_sha256': sha(report), 'specs': specs}
    OUT.mkdir(parents=True)
    for harness in {j['harness'] for j in jobs.values()}:
        target = OUT / 'harness' / harness
        shutil.copytree(ORIGINAL / 'harness' / harness, target, ignore=shutil.ignore_patterns('node_modules'))
        runtime = next(j['runtime'] for j in jobs.values() if j['harness'] == harness)
        (target / 'node_modules').symlink_to(RUNTIME[runtime], target_is_directory=True)
    dump(OUT / 'inputs.json', {'posthoc': True, 'rows': original['rows'], 'decisions': decisions, 'jobs': jobs,
                              'scope': 'Task-1..k evidence only, original current/init-plus-history retained. Reuse decisive saved task observations; execute only unresolved reports.'})
    files = {}
    def freeze(path):
        files[str(path.relative_to(ROOT))] = sha(path)
    for name in ('run.py', '__init__.py', 'PROTOCOL.md'):
        freeze(HERE / name)
    for name in ('test/history_replay/run.py', 'test/todomvc_dna/evaluate.py',
                 'artifacts/history-replay-20261115/inputs.json', 'artifacts/history-tasks-only-20261115/inputs.json'):
        freeze(ROOT / name)
    for decision in decisions.values():
        freeze(ROOT / decision['old_report'])
    for job in jobs.values():
        for name in job['files']:
            freeze(ROOT / job['page'] / name)
    for path in (OUT / 'harness').rglob('*'):
        if path.is_file() and 'node_modules' not in path.parts:
            freeze(path)
    dump(OUT / 'snapshot.json', {'frozen_utc': now(), 'sha256': files})
    print('Frozen', len(original['rows']), 'comparisons;', len(jobs), 'unresolved jobs; others reuse decisive task evidence.', flush=True)


def verify():
    for name, expected in read(OUT / 'snapshot.json')['sha256'].items():
        assert sha(ROOT / name) == expected, name
    return read(OUT / 'inputs.json')


def grade(item):
    key, job = item
    folder = OUT / 'scores' / key
    if (folder / 'score.json').exists():
        old = read(folder / 'score.json')
        assert old['report_sha256'] == sha(folder / 'report.json')
        return old
    folder.mkdir(parents=True, exist_ok=True)
    report = folder / 'report.json'
    assert not report.exists(), 'Preserve incomplete reports for explicit recovery'
    page = ROOT / job['page']
    assert all(sha(page / n) == h for n, h in job['files'].items())
    server = Server(page)
    try:
        env = {**browser_env(), 'REPORT_FILE': str(report), 'CI': '1', 'WORKERS': '1',
               'CANDIDATE_URL': f'http://127.0.0.1:{server.port}', 'EVAL_PROJECT_ROOT': str(page)}
        args = ['node', str(RUNTIME[job['runtime']] / '@playwright/test/cli.js'), 'test',
                '--config', 'playwright.config.cjs', '--workers=1', '--max-failures=1',
                '--output', str(folder / 'playwright-output'),
                *['test/' + s + '.spec.js' for s in job['specs']]]
        done = subprocess.run(args, cwd=OUT / 'harness' / job['harness'], env=env,
                              capture_output=True, text=True, timeout=1500)
    finally:
        server.close()
    (folder / 'runner.txt').write_text(done.stdout + done.stderr)
    assert report.exists()
    raw = read(report)
    assert not [e for e in raw.get('errors', []) if 'maximum allowed failures' not in e.get('message', '')]
    cases = cases_by_file(raw)
    assert set(cases).issubset(job['specs'])
    passed, reason = observed(cases, job['specs'])
    assert passed is not None, 'No decisive task evidence'
    result = {'all_passed': passed, 'reason': reason, 'tests': cases,
              'report_sha256': sha(report), 'exit_code': done.returncode, 'finished_utc': now()}
    dump(folder / 'score.json', result)
    return result


def evaluate():
    inputs = verify()
    assert (ORIGINAL / 'evaluation-complete.json').exists()
    assert not (ROOT / 'artifacts/container-replay-20261115/launch.json').exists(), 'Finish the single BOM queue before starting the container'
    dump(OUT / 'grading-started.json', {'started_utc': now(), 'inputs_sha256': digest(inputs)})
    def group(items, workers, name):
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for index, _ in enumerate(pool.map(grade, items), 1):
                if index % 10 == 0 or index == len(items):
                    print(name, index, '/', len(items), flush=True)
    jobs = list(inputs['jobs'].items())
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(group, [j for j in jobs if (j[1]['project'] == 'bom') == bom],
                               1 if bom else 4, 'bom' if bom else 'other') for bom in (True, False)]
        for future in futures:
            future.result()
    dump(OUT / 'evaluation-complete.json', {'finished_utc': now(), 'inputs_sha256': digest(inputs), 'new_reports': len(jobs)})


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('prepare', 'evaluate'))
    globals()[p.parse_args().action]()
