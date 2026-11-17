"""Budgeted development-only building and matched heldout generation."""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from gui_dna.budget import BudgetStop, Ledger
from gui_dna.provider import ProviderError, parse_json
from test.ledger_read import calls
from test.review_stage import freeze
from test.streaming_provider_v2 import StreamingOpenRouter
from .core import (ROOT, HERE, BUILDERS, PLANNERS, STRONG, SEED, config, dump, digest, slug,
                   builder_messages, messages_for, validate_package, output_files, public_check, write_files)
from .domain import PROJECTS, heldout, strong_tasks

DEFAULTS = {kind: ROOT / ('artifacts/heldout-composition-' + kind) for kind in ('build', 'run', 'strong')}


def feedback_message(build, feedback):
    title = 'Public development format/compiler/behavior feedback:' if build else 'Public format/compiler/load feedback (no current-task behavioral test):'
    return title + '\n' + '\n'.join(feedback) + '\nReturn the complete corrected JSON output.'


def resume_messages(folder, record, initial, build):
    messages = list(initial)
    for attempt in record['attempts']:
        raw = json.loads((folder / f'output-{attempt["attempt"]}.json').read_text())['text']
        messages += [{'role': 'assistant', 'content': raw},
                     {'role': 'user', 'content': feedback_message(build, attempt['feedback'])}]
    return messages


def archive_missing(out, folder, record, messages):
    index = len(record['attempts'])
    lost = folder / f'call-{index}'
    ledgers = [out / 'budget.sqlite3']
    continuation = out / 'continuation.json'
    if continuation.exists():
        ledgers += [ROOT / p for p in json.loads(continuation.read_text())['source_ledgers']]
    settled = {row['id'] for ledger in ledgers for row in calls(ledger) if row['actual'] is not None}
    for path in lost.rglob('request.json'):
        request = json.loads(path.read_text())
        assert request['call_id'] not in settled and request['body']['messages'] == messages
    parent = out / 'discarded-transport' / folder.relative_to(out)
    dest = parent / str(max((int(p.name) for p in parent.glob('[0-9]*')), default=0) + 1)
    dest.mkdir(parents=True)
    shutil.copy2(folder / 'record.json', dest / 'record.json')
    dump(dest / 'receipt.json', {'next_attempt': index, 'retained_valid_attempts': index, 'messages_sha256': digest(messages)})
    if lost.exists():
        shutil.move(str(lost), str(dest / lost.name))


def attempt_loop(client, out, folder, record, initial, build, package=None, resume=False):
    target = folder / 'record.json'
    if target.exists():
        record = json.loads(target.read_text())
        if record['status'] in ('complete', 'frozen', 'frozen_development_failed', 'failed'):
            return record
        assert json.loads((folder / 'messages.json').read_text()) == initial
        if record['attempts'] and not record['attempts'][-1]['feedback']:
            record['status'] = 'frozen' if build else 'complete'
            dump(target, record)
            return record
        messages = resume_messages(folder, record, initial, build)
        if record['status'] in ('transport_incomplete', 'budget_incomplete'):
            if not resume:
                return record
            archive_missing(out, folder, record, messages)
        record.pop('error', None)
    else:
        messages = initial
        dump(folder / 'messages.json', initial)
    record['status'] = 'in_progress'
    dump(target, record)
    for attempt in range(len(record['attempts']), 3):
        try:
            raw = client.call(record['builder'] if build else record['model'], messages,
                              folder / f'call-{attempt}', 'heldout-build' if build else 'heldout-' + record['method'], seed=SEED)
        except BudgetStop as error:
            record.update(status='budget_incomplete', error=str(error))
            dump(target, record)
            raise
        except ProviderError as error:
            record.update(status='transport_incomplete', error=str(error))
            dump(target, record)
            return record
        dump(folder / f'output-{attempt}.json', {'text': raw})
        try:
            parsed = parse_json(raw)
            if build:
                feedback, reports = validate_package(record['project'], parsed, folder / f'validation-{attempt}')
                dump(folder / 'package.json', parsed)
                record.update(package_sha256=digest(parsed), selected_attempt=attempt,
                              development_passes=sum(r['all_passed'] for r in reports.values()), development_total=5)
            else:
                files = output_files(record['method'], package, parsed)
                version = f'version-{attempt}'
                write_files(folder / version, files)
                record['versions'].append(version)
                dump(folder / version / 'source-manifest.json', {'files_sha256': {n: hashlib.sha256(v.encode()).hexdigest() for n, v in files.items()},
                                                                'output_sha256': digest(files)})
                feedback = public_check(folder / version)
        except (ValueError, KeyError, TypeError, AttributeError, TimeoutError, subprocess.TimeoutExpired) as error:
            feedback = [str(error)[:2000]]
        record['attempts'].append({'attempt': attempt, 'feedback': feedback})
        dump(target, record)
        if not feedback:
            break
        messages += [{'role': 'assistant', 'content': raw}, {'role': 'user', 'content': feedback_message(build, feedback)}]
    if build:
        record['status'] = ('frozen' if record.get('development_passes') == 5 else 'frozen_development_failed') if 'selected_attempt' in record else 'failed'
    else:
        record['status'] = 'complete'
    dump(target, record)
    print(f"{record['project']} {record.get('builder')} {record.get('model', '')} {record.get('method', 'build')} {record.get('task', '')}: {record['status']}", flush=True)
    return record


def prepare_stage(out, source, kind, cfg, build_stage):
    assert not (out / 'grading-started.json').exists()
    plan = json.loads((ROOT / 'artifacts/review-20261112/budget-plan.json').read_text())
    allocated = plan['stages'][out.name]
    assert allocated['cap'] == cfg['budget_usd'] and allocated['stop'] == cfg['stop_new_requests_usd']
    if source:
        assert source != out and not (source / 'grading-started.json').exists()
        old = json.loads((source / 'review-manifest.json').read_text())
        strip_budget = lambda c: {k: v for k, v in c.items() if k not in ('budget_usd', 'stop_new_requests_usd')}
        assert strip_budget(old['config']) == strip_budget(cfg)
        for name, sha in old['sha256'].items():
            assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha
        target = out / 'continuation.json'
        if not target.exists():
            content = 'libraries' if kind == 'build' else 'runs'
            assert not (out / content).exists()
            shutil.copytree(source / content, out / content)
            prior = json.loads((source / 'continuation.json').read_text())['source_ledgers'] if (source / 'continuation.json').exists() else []
            dump(target, {'source': str(source.relative_to(ROOT)),
                          'source_manifest_sha256': hashlib.sha256((source / 'review-manifest.json').read_bytes()).hexdigest(),
                          'source_ledgers': [*prior, str((source / 'budget.sqlite3').relative_to(ROOT))],
                          'policy': 'Copy all records and valid attempts; only missing calls or unstarted candidates may proceed.'})
    files = [str((HERE / name).relative_to(ROOT)) for name in
             ('__init__.py', 'domain.py', 'fixtures.py', 'browser.py', 'reference.py', 'prepare.py', 'core.py', 'run.py',
              'PROTOCOL.md', 'public-development.json', 'controls.py', 'evaluate.py')]
    files += ['test/provider_ext.py', 'test/streaming_provider_v2.py', 'src/gui_dna/provider.py', 'src/gui_dna/budget.py',
              'test/interface_blind/core.py', 'test/interface_blind/compile.cjs', 'test/webbench_expand/core.py',
              'test/webbench_expand/schema.py', 'test/webbench_expand/generate.py', 'test/webbench_expand/free_build.cjs',
              'artifacts/heldout-composition-calibration/complete.json']
    if kind != 'build':
        files += [str((build_stage / 'build-complete.json').relative_to(ROOT))]
        files += [str(p.relative_to(ROOT)) for p in sorted((build_stage / 'libraries').rglob('package.json'))]
    freeze(out, cfg, files, {'kind': kind, 'source': str(source.relative_to(ROOT)) if source else None,
                            'build_stage': str(build_stage.relative_to(ROOT)) if kind != 'build' else None,
                            'projects': list(PROJECTS), 'scope': 'Synthetic policy composition, not official Web-Bench; five development examples, eleven heldout combinations per app.',
                            'selection': 'First public pass; otherwise last compilable package, with all development failures retained.',
                            'controls': 'All five development examples, fixed final full-change plan, conflict-rejecting example-delta composition.',
                            'sampling': 'One seed; 20000 builder/6000 candidate output tokens; max2 repairs; all model calls before hidden scores.'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=DEFAULTS)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--build-stage', type=Path, default=DEFAULTS['build'])
    parser.add_argument('--cap', type=float)
    parser.add_argument('--stop', type=float)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    out = (args.out or DEFAULTS[args.phase]).resolve()
    source = args.source.resolve() if args.source else None
    build_stage = args.build_stage.resolve()
    cfg = config(args.phase)
    if args.cap is not None:
        cfg['budget_usd'] = args.cap
    if args.stop is not None:
        cfg['stop_new_requests_usd'] = args.stop
    prepare_stage(out, source, args.phase, cfg, build_stage)
    client = StreamingOpenRouter(cfg, Ledger(out / 'budget.sqlite3', cfg['budget_usd'], cfg['stop_new_requests_usd']))
    jobs = []
    if args.phase == 'build':
        for project in PROJECTS:
            for builder in BUILDERS:
                folder = out / 'libraries' / project / slug(builder)
                record = {'project': project, 'builder': builder, 'attempts': [], 'status': 'in_progress', 'manual_edits': []}
                jobs.append((folder, record, builder_messages(project), True, None))
    else:
        assert (build_stage / 'build-complete.json').exists()
        built = [json.loads((build_stage / 'libraries' / project / slug(builder) / 'record.json').read_text())
                 for project in PROJECTS for builder in BUILDERS]
        assert digest(built) == json.loads((build_stage / 'build-complete.json').read_text())['records_sha256']
        models = PLANNERS if args.phase == 'run' else (STRONG,)
        for project in PROJECTS:
            tasks = heldout(project) if args.phase == 'run' else strong_tasks(project)
            for task in tasks:
                for model in models:
                    options = [(None, 'free', None)] if args.phase == 'run' else []
                    for builder in BUILDERS:
                        library = build_stage / 'libraries' / project / slug(builder)
                        r = json.loads((library / 'record.json').read_text())
                        package = json.loads((library / 'package.json').read_text()) if r['status'] != 'failed' else None
                        if package is not None:
                            assert digest(package) == r['package_sha256']
                        options.extend((builder, method, package) for method in ('free_lib', 'plan'))
                    for builder, method, package in options:
                        folder = out / 'runs' / project / (slug(builder) if builder else 'no_library') / slug(model) / method / task['id']
                        record = {'project': project, 'builder': builder, 'model': model, 'method': method, 'task': task['id'],
                                  'package_sha256': digest(package) if package else None,
                                  'attempts': [], 'versions': [], 'status': 'in_progress'}
                        if builder and package is None:
                            record.update(status='complete', unavailable_library=True)
                            if not (folder / 'record.json').exists():
                                dump(folder / 'record.json', record)
                        jobs.append((folder, record, messages_for(project, task, method, package), False, package))
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda j: attempt_loop(client, out, *j, resume=args.resume), jobs))
    statuses = {'frozen', 'frozen_development_failed', 'failed'} if args.phase == 'build' else {'complete'}
    if not all(r['status'] in statuses for r in results):
        raise ValueError('Missing requests remain; inspect and use --resume without changing valid attempts')
    dump(out / ('build-complete.json' if args.phase == 'build' else 'generation-complete.json'),
         {'candidates': len(results), 'records_sha256': digest(results), 'transport_incomplete': 0,
          'records_by_path_sha256': {str(job[0].relative_to(out)): digest(record) for job, record in zip(jobs, results)}})


if __name__ == '__main__':
    main()
