"""Grade review-stage Web-Bench records with isolated Playwright output directories.

Official files, assertions, browser settings and timeouts are unchanged. No API
client or ledger is opened. Run only after generation has finished or stopped.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import domain, evaluate


def grade(folder, task, report):
    report = report.resolve()
    report.unlink(missing_ok=True)
    server = evaluate.Server(folder.resolve())
    try:
        env = {**evaluate.browser_env(), 'CANDIDATE_URL': f'http://127.0.0.1:{server.port}',
               'REPORT_FILE': str(report), 'CI': '1'}
        command = ['node', str(evaluate.HARNESS / 'node_modules/@playwright/test/cli.js'), 'test',
                   '--config', 'playwright.config.js', f'dom1-tests/{task["spec"]}',
                   '--workers=1', '--output', str(report.parent / 'playwright-output')]
        subprocess.run(command, cwd=evaluate.HARNESS, env=env, capture_output=True, text=True, timeout=600)
    finally:
        server.close()
    if not report.exists():
        raise RuntimeError(f'{folder}: official runner produced no report')
    raw = json.loads(report.read_text())
    if raw.get('errors'):
        raise RuntimeError(f'{folder}: official runner reported global errors')
    results = {}

    def walk(suite):
        for spec in suite.get('specs', []):
            statuses = [r['status'] for t in spec.get('tests', []) for r in t.get('results', [])]
            results[spec['title']] = 'passed' if statuses and all(s == 'passed' for s in statuses) else (statuses[-1] if statuses else 'missing')
        for child in suite.get('suites', []):
            walk(child)

    for suite in raw.get('suites', []):
        walk(suite)
    if not results or any(s in ['missing', 'skipped', 'interrupted'] for s in results.values()):
        raise RuntimeError(f'{folder}: incomplete official test execution')
    passed = sum(s == 'passed' for s in results.values())
    return {'passed': passed, 'total': len(results), 'all_passed': passed == len(results), 'tests': results, 'note': ''}


def grade_record(path):
    rec = json.loads(path.read_text())
    folder, target = path.parent, path.with_name('hidden.json')
    if target.exists():
        old = json.loads(target.read_text())
        if all((v.get('total') and not v.get('note')) or v.get('note') == 'no usable version' for v in old.values()):
            return
    task = next(t for t in domain.tasks() if t['id'] == rec['task'])
    if rec['versions']:
        first = grade(folder / rec['versions'][0], task, folder / rec['versions'][0] / 'review-report.json')
        final = first if rec['versions'][0] == rec['versions'][-1] else grade(folder / rec['versions'][-1], task, folder / rec['versions'][-1] / 'review-report.json')
    else:
        first = final = {'passed': 0, 'total': 0, 'all_passed': False, 'tests': {}, 'note': 'no usable version'}
    target.write_text(json.dumps({'first': first, 'final': final}, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=3)
    args = parser.parse_args()
    files = [Path(__file__), evaluate.HARNESS / 'playwright.config.js', *sorted((evaluate.HARNESS / 'dom1-tests').glob('*.js'))]
    provenance = {'sha256': {str(p.relative_to(domain.ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                  'protocol': 'Unchanged official tests, browser and timeouts; one worker per process; isolated output directories; reuse valid saved scores.'}
    (args.stage / 'isolated-evaluation.json').write_text(json.dumps(provenance, indent=2) + '\n')
    records = sorted((args.stage / 'runs').rglob('record.json'))
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for i, _ in enumerate(pool.map(grade_record, records), 1):
            if i % 20 == 0 or i == len(records):
                print(f'graded {i}/{len(records)}', flush=True)


if __name__ == '__main__':
    main()
