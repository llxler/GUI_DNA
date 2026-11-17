"""Freeze all outputs, then score current-task and complete-history correctness."""
from concurrent.futures import ThreadPoolExecutor
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess

from .run import ROOT, OUT, HERE, MODELS, PREFIXES, METHODS, verify, now, read, dump, digest, slug, domain, evaluate
from test.prefix_history_audit.analyze import cases_by_file


def prepare():
    verify()
    assert not (OUT / 'scoring-inputs.json').exists()
    generation = read(OUT / 'generation-complete.json')
    rows, jobs, records, sources = [], {}, [], [Path(__file__), HERE / 'PROTOCOL.md', OUT / 'generation-complete.json']
    for model in MODELS:
        for prefix in PREFIXES:
            for method in METHODS:
                for task in domain.tasks():
                    folder = OUT / 'runs' / slug(model) / prefix / method / task['id']
                    record = read(folder / 'record.json')
                    records.append(record)
                    assert record['status'] == 'complete'
                    sources.extend(p for p in folder.rglob('*') if p.is_file())
                    for label in ('first', 'final'):
                        version = record['versions'][0 if label == 'first' else -1] if record['versions'] else None
                        for scope in ('current', 'history'):
                            row = {'model': model, 'prefix': prefix, 'method': method, 'task': task['id'],
                                   'k': task['k'], 'label': label, 'scope': scope, 'version': version,
                                   'source': str(folder.relative_to(ROOT)), 'score_key': None}
                            if version:
                                page = folder / version
                                sha = hashlib.sha256((page / 'index.html').read_bytes()).hexdigest()
                                assert sha == read(page / 'source-manifest.json')['html_sha256']
                                specs = [task['id']] if scope == 'current' else ['init', *[f'task-{i}' for i in range(1, task['k'] + 1)]]
                                key = digest({'html': sha, 'specs': specs})
                                jobs[key] = {'page': str(page.relative_to(ROOT)), 'html_sha256': sha, 'specs': specs}
                                row['score_key'] = key
                            rows.append(row)
    assert len(records) == 160 and digest(records) == generation['records_sha256'] and len(rows) == 640
    harness = OUT / 'harness'
    shutil.copytree(evaluate.HARNESS / 'dom1-tests', harness / 'dom1-tests')
    shutil.copy2(evaluate.HARNESS / 'playwright.config.js', harness / 'playwright.config.js')
    (harness / 'node_modules').symlink_to(evaluate.HARNESS / 'node_modules', target_is_directory=True)
    sources += [harness / 'playwright.config.js', *list((harness / 'dom1-tests').rglob('*.js')),
                ROOT / 'test/prefix_history_audit/analyze.py', evaluate.HARNESS / 'package-lock.json']
    dump(OUT / 'scoring-inputs.json', {'rows': rows, 'jobs': jobs, 'generation_sha256': digest(generation)})
    sources.append(OUT / 'scoring-inputs.json')
    dump(OUT / 'scoring-snapshot.json', {'frozen_utc': now(), 'sha256': {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}})
    print('Scoring frozen:', len(rows), 'comparisons;', len(jobs), 'distinct page/test-set checks', flush=True)


def verify_scoring():
    verify()
    for path, sha in read(OUT / 'scoring-snapshot.json')['sha256'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == sha, path
    inputs = read(OUT / 'scoring-inputs.json')
    assert inputs['generation_sha256'] == digest(read(OUT / 'generation-complete.json'))
    return inputs


def grade(key, job):
    folder = OUT / 'scores' / key
    if (folder / 'score.json').exists():
        return
    folder.mkdir(parents=True, exist_ok=True)
    report = folder / 'report.json'
    assert not report.exists(), 'Preserve partial infrastructure outputs; no silent reruns'
    server = evaluate.Server(ROOT / job['page'])
    try:
        env = {**evaluate.browser_env(), 'REPORT_FILE': str(report), 'WORKERS': '1', 'CI': '1',
               'CANDIDATE_URL': f'http://127.0.0.1:{server.port}'}
        command = ['node', str(evaluate.HARNESS / 'node_modules/@playwright/test/cli.js'), 'test',
            '--config', 'playwright.config.js', '--workers=1', '--max-failures=1',
            '--output', str(folder / 'playwright-output')]
        command += [f'dom1-tests/{name}.spec.js' for name in job['specs']]
        done = subprocess.run(command, cwd=OUT / 'harness', env=env, capture_output=True, text=True, timeout=900)
    finally:
        server.close()
    (folder / 'runner.txt').write_text(done.stdout + done.stderr)
    assert report.exists(), 'Missing Playwright report'
    payload = read(report)
    errors = [e for e in payload.get('errors', []) if 'maximum allowed failures' not in e.get('message', '')]
    assert not errors, errors
    cases = cases_by_file(payload)
    assert set(cases).issubset(job['specs'])
    passed = set(cases) == set(job['specs']) and all(c['passed'] for values in cases.values() for c in values)
    failed = any(s in ('failed', 'timedOut') for values in cases.values() for c in values for s in c['statuses'])
    assert passed or failed, 'Incomplete execution without a decisive failure'
    dump(folder / 'score.json', {'all_passed': passed, 'tests': cases, 'exit_code': done.returncode,
         'report_sha256': hashlib.sha256(report.read_bytes()).hexdigest(), 'candidate_outcome_exact': True,
         'test_level_mean_valid': passed, 'finished_utc': now()})


def evaluate_all():
    inputs = verify_scoring()
    start = OUT / 'grading-started.json'
    if not start.exists():
        dump(start, {'started_utc': now(), 'inputs_sha256': digest(inputs)})
    assert read(start)['inputs_sha256'] == digest(inputs)
    assert read(OUT / 'generation-complete.json')['finished_utc'] <= read(OUT / 'scoring-snapshot.json')['frozen_utc'] <= read(start)['started_utc']
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i, _ in enumerate(pool.map(lambda item: grade(*item), inputs['jobs'].items()), 1):
            if i % 10 == 0 or i == len(inputs['jobs']):
                print('scored', i, '/', len(inputs['jobs']), flush=True)
    dump(OUT / 'evaluation-complete.json', {'finished_utc': now(), 'inputs_sha256': digest(inputs)})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['prepare', 'evaluate'])
    {'prepare': prepare, 'evaluate': evaluate_all}[parser.parse_args().phase]()
