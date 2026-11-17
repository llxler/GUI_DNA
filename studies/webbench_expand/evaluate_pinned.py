"""Pinned upstream Playwright 1.57.0 evaluation; original 1.63 calibration retained."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .core import ROOT, UPSTREAM, PROJECTS, Server, browser_env, digest, dump

HARNESS = ROOT / 'artifacts/webbench-expand-harness-157'
NODE_MODULES = ROOT / 'artifacts/webbench-expand-runtime-157/node_modules'
SNAPSHOT = {}
SCORING_STAGE = None
CONFIG = '''const {defineConfig, devices} = require('@playwright/test');
module.exports = defineConfig({
 testDir: './test', timeout: 30000, expect: {timeout: 5000},
 fullyParallel: false, workers: 1, retries: 0, forbidOnly: true,
 reporter: [['json', {outputFile: process.env.REPORT_FILE}]],
 use: {baseURL: process.env.CANDIDATE_URL, trace: 'off', headless: true},
 projects: [{name: 'chromium', use: {...devices['Desktop Chrome']}}]
});
'''


def prepare():
    if (UPSTREAM / '.git').exists():
        commit = subprocess.check_output(['git', '-C', str(UPSTREAM), 'rev-parse', 'HEAD'], text=True).strip()
    else:
        commit = json.loads((UPSTREAM / 'REPLAY-UPSTREAM.json').read_text())['commit']
    assert commit == '7b31ca2b786eef120dd49ce63dd03d0c0006046d', 'Use the pinned upstream checkout'
    manifest = {'upstream_commit': commit, 'playwright_version': json.loads((NODE_MODULES / '@playwright/test/package.json').read_text())['version'], 'node_version': subprocess.check_output(['node', '--version'], text=True).strip(), 'runtime_lock_sha256': hashlib.sha256((NODE_MODULES.parent / 'package-lock.json').read_bytes()).hexdigest(),
                'official_files': {}, 'utility_sha256': hashlib.sha256((NODE_MODULES / '@web-bench/test-util/index.js').read_bytes()).hexdigest(), 'utility_scope': 'Existing official utility honors EVAL_PROJECT_ROOT for candidate file checks.', 'protocol': 'Official assertions unchanged. Production 30s/5s timeouts; Chromium; one worker; no retries. Stop after first failure for exact candidate-level pass/fail only.'}
    manifest['utility_files_sha256'] = {name: hashlib.sha256((NODE_MODULES / '@web-bench/test-util' / name).read_bytes()).hexdigest() for name in ('index.js', 'css.js')}
    assert manifest['playwright_version'] == '1.57.0'
    for project in PROJECTS:
        source = UPSTREAM / 'projects' / project / 'test'
        target = HARNESS / project
        (target / 'test').mkdir(parents=True, exist_ok=True)
        package_source = UPSTREAM / 'projects' / project / 'package.json'
        module_type = json.loads(package_source.read_text()).get('type', 'commonjs')
        dump(target / 'package.json', {'type': module_type})
        manifest['official_files'][f'{project}/package.json'] = hashlib.sha256(package_source.read_bytes()).hexdigest()
        for path in source.rglob('*'):
            if path.is_file():
                relative = path.relative_to(source)
                dest = target / 'test' / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists() and dest.read_bytes() != path.read_bytes():
                    raise ValueError(f'official test changed: {dest}')
                if not dest.exists():
                    shutil.copy2(path, dest)
                manifest['official_files'][f'{project}/{relative}'] = hashlib.sha256(path.read_bytes()).hexdigest()
        configuration = target / 'playwright.config.cjs'
        if not configuration.exists() or configuration.read_text() != CONFIG:
            configuration.write_text(CONFIG)
        link = target / 'node_modules'
        if not link.exists() and not link.is_symlink():
            link.symlink_to(NODE_MODULES, target_is_directory=True)
    manifest['config_sha256'] = hashlib.sha256(CONFIG.encode()).hexdigest()
    dump(HARNESS / 'manifest.json', manifest)
    return manifest


def grade(project, folder, task, report):
    folder, report = Path(folder).resolve(), Path(report).resolve()
    report.parent.mkdir(parents=True, exist_ok=True)
    report.unlink(missing_ok=True)
    server = Server(folder)
    try:
        env = {**browser_env(), 'CANDIDATE_URL': f'http://127.0.0.1:{server.port}',
               'EVAL_PROJECT_ROOT': str(folder), 'REPORT_FILE': str(report), 'CI': '1'}
        result = subprocess.run(['node', str(NODE_MODULES / '@playwright/test/cli.js'), 'test',
            '--config', 'playwright.config.cjs', f'test/{task}.spec.js', '--max-failures=1',
            '--output', str(report.parent / 'playwright-output')],
            cwd=HARNESS / project, env=env, capture_output=True, text=True, timeout=600)
    finally:
        server.close()
    if not report.exists():
        raise RuntimeError(f'no official report: {result.stderr[-600:]}')
    data = json.loads(report.read_text())
    errors = data.get('errors', [])
    # Playwright includes its maxFailures notice as a global error.
    errors = [e for e in errors if 'maximum allowed failures' not in e.get('message', '')]
    if errors:
        raise RuntimeError(f'global runner errors: {errors}')
    cases = []

    def walk(suite, prefix=()):
        for spec in suite.get('specs', []):
            for test in spec.get('tests', []):
                statuses = [r['status'] for r in test.get('results', [])]
                status = 'passed' if statuses and all(s == 'passed' for s in statuses) else (statuses[-1] if statuses else 'missing')
                cases.append({'title': ' / '.join((*prefix, spec['title'])), 'status': status})
        for child in suite.get('suites', []):
            walk(child, (*prefix, child.get('title', '')))
    for suite in data.get('suites', []):
        walk(suite)
    failed = any(c['status'] in ('failed', 'timedOut') for c in cases)
    complete = bool(cases) and all(c['status'] == 'passed' for c in cases)
    if not failed and not complete:
        raise RuntimeError('incomplete test execution without a decisive failure')
    return {'all_passed': complete, 'passed': sum(c['status'] == 'passed' for c in cases),
            'total_listed': len(cases), 'tests': cases, 'exact_candidate_outcome': True,
            'test_level_mean_valid': complete, 'report_sha256': hashlib.sha256(report.read_bytes()).hexdigest()}


def calibrate():
    prepare()
    outcomes = {}
    for project in PROJECTS:
        source = UPSTREAM / 'projects' / project
        out = HARNESS / 'calibration' / project
        for task, folder in [('init', source / 'src-init'), ('task-20', source / 'src')]:
            outcomes[f'{project}/{task}'] = grade(project, folder, task, out / task / 'report.json')
            outcomes[f'{project}/{task}']['expected_pass'] = not (project == 'bom' and task == 'init')
        if project == 'bom':
            # Upstream src-init/index.css is empty: the default body margin makes
            # its .browser 16px narrower than the viewport. Preserve this failure.
            for task in ('init', 'task-1'):
                key = f'{project}/final-{task}'
                outcomes[key] = grade(project, source / 'src', task, out / ('final-' + task) / 'report.json')
                outcomes[key]['expected_pass'] = True
        blank = out / 'blank'
        blank.mkdir(parents=True, exist_ok=True)
        (blank / 'index.html').write_text('<!doctype html><title>blank</title>')
        outcomes[f'{project}/negative'] = grade(project, blank, 'task-1', out / 'negative' / 'report.json')
        outcomes[f'{project}/negative']['expected_pass'] = False
    dump(HARNESS / 'calibration.json', outcomes)
    for key, value in outcomes.items():
        print(key, value['all_passed'], f"{value['passed']}/{value['total_listed']}", flush=True)
    assert all(v['all_passed'] == v['expected_pass'] for v in outcomes.values()), 'Calibration failed; inspect before generation.'


def grade_record(path):
    assert hashlib.sha256(path.read_bytes()).hexdigest() == SNAPSHOT[str(path.relative_to(SCORING_STAGE))]
    record = json.loads(path.read_text())
    target = path.with_name('hidden.json')
    if target.exists():
        return
    if record['status'] != 'complete':
        dump(target, {'excluded': True, 'reason': record['status']})
        return
    versions = record['versions']
    if not versions:
        first = final = {'all_passed': False, 'reason': 'no executable version', 'exact_candidate_outcome': True}
    else:
        def one(version):
            folder = path.parent / version
            manifest = json.loads((folder / 'source-manifest.json').read_text())
            source_manifest = folder / 'source-manifest.json'
            assert hashlib.sha256(source_manifest.read_bytes()).hexdigest() == SNAPSHOT[str(source_manifest.relative_to(SCORING_STAGE))]
            assert all(hashlib.sha256((folder / name).read_bytes()).hexdigest() == sha for name, sha in manifest['files_sha256'].items())
            return grade(record['project'], folder, record['task'], folder / 'official-report.json')
        first = one(versions[0])
        final = first if versions[-1] == versions[0] else one(versions[-1])
    dump(target, {'first': first, 'final': final})


def main():
    global SNAPSHOT, SCORING_STAGE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--calibrate', action='store_true')
    parser.add_argument('--stage', type=Path, default=ROOT / 'artifacts/webbench-expand-run')
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    if args.calibrate:
        calibrate()
        return
    barrier = args.stage / 'generation-complete.json'
    if not barrier.exists():
        raise ValueError('Generation must finish before hidden grading')
    snapshot = args.stage / 'candidate-files-sha256.json'
    saved = json.loads(snapshot.read_text())
    assert saved['generation_sha256'] == hashlib.sha256(barrier.read_bytes()).hexdigest()
    SNAPSHOT, SCORING_STAGE = saved['files'], args.stage
    provenance = prepare()
    dump(args.stage / 'grading-started.json', {'generation_sha256': digest(json.loads(barrier.read_text())),
                                              'evaluator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                              'protocol_sha256': hashlib.sha256(Path(__file__).with_name('EVALUATION.md').read_bytes()).hexdigest(),
                                              'candidate_snapshot_sha256': hashlib.sha256(snapshot.read_bytes()).hexdigest(),
                                              'harness': provenance})
    paths = sorted((args.stage / 'runs').rglob('record.json'))
    for project in PROJECTS:
        selected = [p for p in paths if p.relative_to(args.stage / 'runs').parts[0] == project]
        with ThreadPoolExecutor(max_workers=1 if project == 'bom' else args.workers) as pool:
            for i, _ in enumerate(pool.map(grade_record, selected), 1):
                if i % 10 == 0 or i == len(selected):
                    print(f'graded {project} {i}/{len(selected)}', flush=True)


if __name__ == '__main__':
    main()
