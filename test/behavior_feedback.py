"""P6 pilot: two additional public-behavior repairs, with a frozen disjoint test split.

This new protocol reclassifies a subset of official tests as public. It never
changes the earlier wholly-hidden study or feeds its full scores to a model.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from gui_dna.budget import Ledger
from gui_dna.provider import ProviderError, parse_json
from test.interface_blind.core import ROOT, PROJECTS, BUILDERS, SEED, Server, browser_env, compile_plan, digest, dump, slug, write_files
from test.interface_blind.evaluate import HARNESS, NODE_MODULES, prepare
from test.review_stage import freeze
from test.streaming_provider_v2 import StreamingOpenRouter
from test.interface_blind_run_helpers import output_files

SOURCE = ROOT / 'artifacts/interface-blind-final-2'
BUILD = ROOT / 'artifacts/interface-blind-build-2'
OUT = ROOT / 'artifacts/behavior-feedback'
TASKS = (4, 8, 12, 16, 20)
SPLIT = ROOT / 'test/results/behavior-feedback-split.json'
ANSI = re.compile(r'\x1b\[[0-9;]*m')
SOURCE_FRAME = re.compile(r'^\s*(?:>\s*)?\d+\s*\|')


def feedback_message(message):
    """Playwright embeds neighboring source lines inside message, not just snippet."""
    lines = []
    for line in ANSI.sub('', message).splitlines():
        if SOURCE_FRAME.match(line) or re.match(r'^\s*at\s+', line):
            break
        lines.append(line)
    return '\n'.join(lines).strip()[:2200]


def list_specs(data):
    result = []
    def walk(suite):
        for spec in suite.get('specs', []):
            result.append({'title': spec['title'], 'line': spec['line'], 'file': Path(spec['file']).name})
        for child in suite.get('suites', []):
            walk(child)
    for suite in data.get('suites', []):
        walk(suite)
    return result


def split_cases(project, task, cases):
    if len(cases) < 2 or len({c['line'] for c in cases}) != len(cases):
        raise ValueError('Need at least two cases with unique source locations')
    ranked = sorted(cases, key=lambda c: digest(['public-behavior-pilot-v1', project, task, c]))
    n = max(1, len(ranked) // 2)
    return {'public': ranked[:n], 'hidden': ranked[n:]}


def prepare_split():
    manifest = prepare()
    rows = {}
    for project in PROJECTS:
        done = subprocess.run(['node', str(NODE_MODULES / '@playwright/test/cli.js'), 'test', '--config',
            'playwright.config.cjs', '--list', '--reporter=json'], cwd=HARNESS / project,
            capture_output=True, text=True, check=True, env=browser_env())
        specs = list_specs(json.loads(done.stdout))
        rows[project] = {}
        for k in TASKS:
            task = f'task-{k}'
            cases = [s for s in specs if s['file'] == f'{task}.spec.js']
            rows[project][task] = split_cases(project, task, cases)
    value = {'rule': 'SHA256 rank of [public-behavior-pilot-v1, project, task, case metadata]; floor-half public, rest hidden.',
             'milestones': TASKS, 'projects': rows, 'official_manifest': manifest,
             'scope': 'New evaluation protocol, not the historical wholly-hidden scores.'}
    if SPLIT.exists() and json.loads(SPLIT.read_text()) != json.loads(json.dumps(value)):
        raise ValueError('Public/hidden split changed')
    dump(SPLIT, value)
    print('split frozen:', hashlib.sha256(SPLIT.read_bytes()).hexdigest())
    for project, tasks in rows.items():
        print(project, {t: (len(r['public']), len(r['hidden'])) for t, r in tasks.items()})


def report_cases(data, expected):
    expected_by_line = {s['line']: s for s in expected}
    cases = []
    def walk(suite):
        for spec in suite.get('specs', []):
            if spec['line'] not in expected_by_line or spec['title'] != expected_by_line[spec['line']]['title']:
                raise ValueError('Unexpected test in selected subset; refusing to expose feedback')
            for test in spec.get('tests', []):
                runs = test.get('results', [])
                statuses = [r['status'] for r in runs]
                status = 'passed' if statuses and all(s == 'passed' for s in statuses) else (statuses[-1] if statuses else 'missing')
                # Deliberately exclude stack, snippet and the surrounding source.
                errors = [feedback_message(e.get('message', '')) for r in runs for e in r.get('errors', [])]
                cases.append({'title': spec['title'], 'line': spec['line'], 'status': status, 'errors': errors})
        for child in suite.get('suites', []):
            walk(child)
    for suite in data.get('suites', []):
        walk(suite)
    if {s['line'] for s in cases} != set(expected_by_line):
        raise ValueError('Selected test coverage changed')
    failed = any(s['status'] in ('failed', 'timedOut') for s in cases)
    passed = bool(cases) and all(s['status'] == 'passed' for s in cases)
    if not failed and not passed:
        raise ValueError('Incomplete subset without decisive failure')
    return {'all_passed': passed, 'tests': cases, 'candidate_outcome_exact': True}


def evaluate_subset(project, task, folder, subset, report):
    selected = json.loads(SPLIT.read_text())['projects'][project][task][subset]
    report = Path(report).resolve()
    report.parent.mkdir(parents=True, exist_ok=True)
    report.unlink(missing_ok=True)
    server = Server(folder)
    try:
        env = {**browser_env(), 'CANDIDATE_URL': f'http://127.0.0.1:{server.port}',
               'EVAL_PROJECT_ROOT': str(Path(folder).resolve()), 'REPORT_FILE': str(report), 'CI': '1'}
        result = subprocess.run(['node', str(NODE_MODULES / '@playwright/test/cli.js'), 'test', '--config',
            'playwright.config.cjs', *[f'test/{task}.spec.js:{s["line"]}' for s in selected],
            '--max-failures=1', '--output', str(report.parent / 'playwright-output')],
            cwd=HARNESS / project, env=env, capture_output=True, text=True, timeout=600)
    finally:
        server.close()
    if not report.exists():
        raise RuntimeError('Selected test runner produced no report: ' + result.stderr[-500:])
    data = json.loads(report.read_text())
    errors = [e for e in data.get('errors', []) if 'maximum allowed failures' not in e.get('message', '')]
    if errors:
        raise RuntimeError('Selected runner global errors: ' + str(errors))
    return report_cases(data, selected)


def jobs():
    models = json.loads((SOURCE / 'review-manifest.json').read_text())['config']['models']
    for project in PROJECTS:
        for builder in BUILDERS:
            for model in models:
                for method in ('free_lib', 'plan'):
                    for k in TASKS:
                        relative = Path(project) / slug(builder) / slug(model) / method / f'task-{k}'
                        yield relative


def repair_one(client, relative):
    folder, base = OUT / 'runs' / relative, SOURCE / 'runs' / relative
    target = folder / 'record.json'
    if target.exists():
        return json.loads(target.read_text())
    original = json.loads((base / 'record.json').read_text())
    result = {k: original[k] for k in ('project', 'builder', 'model', 'method', 'task')}
    result.update(status='complete', attempts=[], source=str(base.relative_to(ROOT)), initial=None, final=None)
    if original['status'] != 'complete':
        result.update(status='source_transport_missing')
        dump(target, result)
        return result
    package = json.loads((BUILD / 'libraries' / result['project'] / slug(result['builder']) / 'package.json').read_text())
    messages = json.loads((base / 'messages.json').read_text())
    if original['versions']:
        current = base / original['versions'][-1]
        number = int(current.name.split('-')[-1])
        raw = json.loads((base / f'output-{number}.json').read_text())['text']
        initial = evaluate_subset(result['project'], result['task'], current, 'public', folder / 'initial-public/report.json')
        feedback = json.dumps(initial, ensure_ascii=False)
        result.update(initial=str(current.relative_to(ROOT)), final=str(current.relative_to(ROOT)), initial_public=initial)
        good = initial['all_passed']
    else:
        raw = json.loads((base / f'output-{len(original["attempts"])-1}.json').read_text())['text']
        feedback = json.dumps(original['attempts'][-1]['feedback'])
        good = False
    messages += [{'role': 'assistant', 'content': raw}]
    for attempt in range(2):
        if good:
            break
        messages.append({'role': 'user', 'content': 'This separate repair protocol provides public behavior tests. Their observed feedback is:\n' + feedback +
                         '\nRepair these behaviors while preserving the cumulative requirements. Return the complete JSON output in the same format as before. Hidden tests are not included.'})
        try:
            raw = client.call(result['model'], messages, folder / f'call-{attempt}', f'behavior-feedback:{result["method"]}', seed=SEED)
        except ProviderError as error:
            result.update(status='transport_incomplete', error=str(error))
            break
        dump(folder / f'output-{attempt}.json', {'text': raw})
        try:
            parsed = parse_json(raw)
            if not isinstance(parsed, dict):
                raise ValueError('Output must be a JSON object')
            files = output_files(result['method'], package, parsed)
            current = folder / f'version-{attempt}'
            write_files(current, files)
            result['final'] = str(current.relative_to(ROOT))
        except (ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
            feedback = str(error)[:2000]
            result['attempts'].append({'attempt': attempt, 'compiler_error': feedback})
        else:
            # A runner/split error must stop the experiment, never become model feedback.
            public = evaluate_subset(result['project'], result['task'], current, 'public', folder / f'public-{attempt}/report.json')
            good = public['all_passed']
            feedback = json.dumps(public, ensure_ascii=False)
            result['attempts'].append({'attempt': attempt, 'public': public, 'files_sha256': digest(files)})
        messages.append({'role': 'assistant', 'content': raw})
    dump(target, result)
    print(f'behavior {relative}: {result["status"]}, calls={len(result["attempts"])}', flush=True)
    return result


def grade_one(relative):
    folder = OUT / 'runs' / relative
    target = folder / 'hidden.json'
    if target.exists():
        return
    result = json.loads((folder / 'record.json').read_text())
    if result['status'] != 'complete':
        dump(target, {'excluded': True, 'reason': result['status']})
        return
    values = {}
    for name in ('initial', 'final'):
        if not result[name]:
            values[name] = {'all_passed': False, 'reason': 'no executable version'}
        elif name == 'final' and result[name] == result['initial']:
            values[name] = values['initial']
        else:
            values[name] = evaluate_subset(result['project'], result['task'], ROOT / result[name], 'hidden', folder / f'{name}-hidden/report.json')
    dump(target, values)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['prepare', 'calibrate', 'repair', 'grade'])
    parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--archive-transport', action='store_true')
    args = parser.parse_args()
    if args.phase == 'prepare':
        prepare_split()
        return
    if args.phase == 'calibrate':
        prepare()
        for project in PROJECTS:
            for subset in ('public', 'hidden'):
                value = evaluate_subset(project, 'task-20', ROOT / f'artifacts/web-bench/projects/{project}/src', subset,
                                        OUT / 'calibration' / project / subset / 'report.json')
                assert value['all_passed'], value
                print(project, subset, 'calibrated')
        return
    if not (SOURCE / 'generation-complete.json').exists():
        raise ValueError('Base generation must finish first')
    if args.phase == 'repair':
        if (OUT / 'grading-started.json').exists():
            raise ValueError('Hidden scoring started; no more repairs')
        if args.archive_transport:
            batches = [int(p.name) for p in (OUT / 'discarded-transport').glob('[0-9]*')]
            archive = OUT / 'discarded-transport' / str(max(batches, default=0) + 1)
            moved = []
            for path in (OUT / 'runs').rglob('record.json'):
                if json.loads(path.read_text())['status'] != 'transport_incomplete':
                    continue
                relative = path.parent.relative_to(OUT / 'runs')
                dest = archive / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(path.parent), str(dest))
                moved.append(str(relative))
            if moved:
                dump(archive / 'archive.json', {'candidates': moved, 'policy': 'Transport failures only; all complete outputs retained; unchanged frozen repair protocol.'})
                barrier = OUT / 'generation-complete.json'
                if barrier.exists():
                    shutil.move(str(barrier), str(archive / 'generation-complete.json'))
        cfg = json.loads((SOURCE / 'review-manifest.json').read_text())['config']
        cfg.update(budget_usd=3, stop_new_requests_usd=2.8, max_repairs=2)
        freeze(OUT, cfg, ['test/behavior_feedback.py', 'test/results/behavior-feedback-split.json',
                          'test/streaming_provider_v2.py', 'test/interface_blind/core.py', 'test/interface_blind/compile.cjs',
                          'test/interface_blind_run_helpers.py', 'test/interface_blind/evaluate.py',
                          str((SOURCE / 'review-manifest.json').relative_to(ROOT)),
                          str((SOURCE / 'generation-complete.json').relative_to(ROOT))],
               {'source': str(SOURCE), 'milestones': TASKS, 'methods': ['free_lib', 'plan'],
                'daily_authorization_usd': 20, 'stage_cap_usd': 3, 'new_protocol': True,
                'public_test_split_sha256': hashlib.sha256(SPLIT.read_bytes()).hexdigest(),
                'base_generation_sha256': digest(json.loads((SOURCE / 'generation-complete.json').read_text()))})
        client = StreamingOpenRouter(cfg, Ledger(OUT / 'budget.sqlite3', 3, 2.8))
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            results = list(pool.map(lambda relative: repair_one(client, relative), jobs()))
        dump(OUT / 'generation-complete.json', {'n': len(results), 'records_sha256': digest(results)})
    else:
        if not (OUT / 'generation-complete.json').exists():
            raise ValueError('All repairs must finish before hidden evaluation')
        dump(OUT / 'grading-started.json', {'protocol': 'Disjoint hidden subset only, after all public-feedback repairs.'})
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for i, _ in enumerate(pool.map(grade_one, jobs()), 1):
                if i % 10 == 0:
                    print(f'behavior hidden {i}/80', flush=True)


if __name__ == '__main__':
    main()
