"""Run five saved table pages from an extracted anonymous bundle, without API calls."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from test.webbench_expand import evaluate_pinned as evaluator

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'artifacts/anonymous-browser-smoke'


def main():
    if not (ROOT / 'REPLAY-MANIFEST.json').is_file():
        raise RuntimeError('Run only inside an extracted anonymous replay bundle')
    if OUTPUT.exists():
        raise RuntimeError('Use a fresh extraction; do not overwrite browser observations')
    OUTPUT.mkdir(parents=True)
    runtime = evaluator.NODE_MODULES.parent
    assert not evaluator.NODE_MODULES.exists(), 'Dependencies must be installed afresh'
    runtime.mkdir(parents=True, exist_ok=True)
    for source, target in (('runtime-package.json', 'package.json'), ('runtime-lock.json', 'package-lock.json')):
        shutil.copy2(ROOT / 'test/webbench_expand' / source, runtime / target)
    shutil.copytree(ROOT / 'test/webbench_dna/harness/test-util', runtime / 'test-util', dirs_exist_ok=True)
    installed = subprocess.run(['npm', 'ci', '--offline', '--ignore-scripts', '--no-audit', '--no-fund'],
                               cwd=runtime, capture_output=True, text=True, timeout=180)
    (OUTPUT / 'npm-install.txt').write_text(installed.stdout + installed.stderr)
    installed.check_returncode()
    evaluator.HARNESS = OUTPUT / 'harness'
    environment = evaluator.prepare()
    # The npm and Python packages may select different cached browser versions.
    browser_path = Path(subprocess.check_output(
        ['node', '-e', "process.stdout.write(require('playwright').chromium.executablePath())"],
        cwd=runtime, text=True))
    environment['browser_sha256'] = hashlib.sha256(browser_path.read_bytes()).hexdigest()
    environment['browser_cache_directory'] = browser_path.parent.name
    saved = json.loads((ROOT / 'test/results/library-repair-mechanism.json').read_text())
    cases = [{'name': row['name'], 'page': row['page'], 'expected': row['all_passed'],
              'expected_tests': row['tests']} for row in saved['rows']]
    cases.append({'name': 'official_reference', 'page': 'artifacts/web-bench/projects/table/src',
                  'expected': True, 'expected_tests': None})
    result = {'scope': 'Five table/task-20 pages only. Fresh extracted source and npm dependencies; '
                       'same host OS, Node/Python interpreters and cached Chromium/system libraries. '
                       'Not an independent machine or replay of every historical browser test.',
              'environment': environment, 'rows': []}
    for case in cases:
        report = OUTPUT / 'scores' / case['name'] / 'report.json'
        observed = evaluator.grade('table', ROOT / case['page'], 'task-20', report)
        matches = observed['all_passed'] == case['expected']
        if case['expected_tests'] is not None:
            matches = matches and observed['tests'] == case['expected_tests']
        result['rows'].append({**case, **observed, 'matches': matches,
                               'report': str(report.relative_to(OUTPUT))})
        print(case['name'], matches, flush=True)
    result['all_passed'] = all(row['matches'] for row in result['rows'])
    (OUTPUT / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    if not result['all_passed']:
        raise SystemExit('Browser observations differ; preserve the new reports and investigate')


if __name__ == '__main__':
    main()
