"""Build interfaces, then generate all candidates before any hidden grading."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from gui_dna.budget import BudgetStop, Ledger
from gui_dna.provider import ProviderError, parse_json
from test.provider_ext import ReasoningAwareOpenRouter
from test.review_stage import freeze
from .core import (ROOT, HERE, BUILDERS, PLANNERS, PROJECTS, SEED, builder_messages,
                   compile_plan, config, digest, dump, planner_messages, public_check,
                   requirements, slug, validate_package, write_files)

BUILD_OUT = ROOT / 'artifacts/interface-blind-build'
RUN_OUT = ROOT / 'artifacts/interface-blind-run'


def frozen_inputs(out, cfg, protocol, extras=()):
    files = [str(p.relative_to(ROOT)) for p in sorted(HERE.glob('*')) if p.suffix in ('.py', '.cjs') and p.name not in ('evaluate.py', 'analyze.py')]
    files += ['test/provider_ext.py', 'src/gui_dna/provider.py', 'src/gui_dna/budget.py']
    files += [f'artifacts/web-bench/projects/{p}/tasks.jsonl' for p in PROJECTS]
    files += [str(Path(p).relative_to(ROOT)) for p in extras]
    freeze(out, cfg, files, protocol)


def provider(cfg, out):
    ledger = Ledger(out / 'budget.sqlite3', cfg['budget_usd'], cfg['stop_new_requests_usd'])
    return ReasoningAwareOpenRouter(cfg, ledger)


def build_one(client, out, project, model):
    folder = out / 'libraries' / project / slug(model)
    target = folder / 'record.json'
    if target.exists():
        return json.loads(target.read_text())
    messages = builder_messages(project)
    dump(folder / 'messages.json', messages)
    record = {'project': project, 'builder': model, 'attempts': [], 'status': 'failed', 'manual_edits': []}
    for attempt in range(3):
        try:
            raw = client.call(model, messages, folder / f'call-{attempt}', 'library-interface-blind', seed=SEED)
        except BudgetStop:
            raise
        except ProviderError as error:
            record.update(status='transport_incomplete', error=str(error))
            break
        dump(folder / f'output-{attempt}.json', {'text': raw})
        try:
            package = parse_json(raw)
            feedback = validate_package(package, folder / f'validation-{attempt}')
        except (ValueError, KeyError, TypeError, TimeoutError, subprocess.TimeoutExpired) as error:
            feedback = [str(error)[:1600]]
        record['attempts'].append({'attempt': attempt, 'feedback': feedback})
        if not feedback:
            dump(folder / 'package.json', package)
            record.update(status='frozen', package_sha256=digest(package), selected_attempt=attempt)
            break
        messages += [{'role': 'assistant', 'content': raw},
                     {'role': 'user', 'content': 'Public format/compiler/load feedback:\n' + '\n'.join(feedback) + '\nReturn the complete corrected package as JSON. No behavioral tests were run.'}]
    dump(target, record)
    print(f"builder {project} {model}: {record['status']}", flush=True)
    return record


def candidate(client, out, project, builder, model, method, task, package):
    folder = out / 'runs' / project / (slug(builder) if builder else 'no_library') / slug(model) / method / task
    target = folder / 'record.json'
    if target.exists():
        return json.loads(target.read_text())
    messages = planner_messages(project, task, method, package)
    dump(folder / 'messages.json', messages)
    record = {'project': project, 'builder': builder, 'model': model, 'method': method, 'task': task,
              'package_sha256': digest(package) if package else None, 'attempts': [], 'versions': [], 'status': 'complete'}
    for attempt in range(3):
        try:
            raw = client.call(model, messages, folder / f'call-{attempt}', f'plan-interface-blind:{method}', seed=SEED)
        except BudgetStop:
            raise
        except ProviderError as error:
            record.update(status='transport_incomplete', error=str(error))
            break
        dump(folder / f'output-{attempt}.json', {'text': raw})
        try:
            parsed = parse_json(raw)
            files = compile_plan(package, parsed) if method == 'plan' else parsed['files']
            version = f'version-{attempt}'
            write_files(folder / version, files)
            record['versions'].append(version)
            dump(folder / version / 'source-manifest.json', {'files_sha256': {n: hashlib.sha256(v.encode()).hexdigest() for n, v in files.items()}, 'output_sha256': digest(files)})
            feedback = public_check(folder / version)
        except (ValueError, KeyError, TypeError, TimeoutError, subprocess.TimeoutExpired) as error:
            feedback = [str(error)[:1600]]
        record['attempts'].append({'attempt': attempt, 'feedback': feedback})
        if not feedback:
            break
        messages += [{'role': 'assistant', 'content': raw},
                     {'role': 'user', 'content': 'Public format/compiler/load feedback:\n' + '\n'.join(feedback) + '\nReturn the full corrected JSON output.'}]
    dump(target, record)
    print(f'{project} {builder or "none"} {model} {method} {task}: {record["status"]}, versions={len(record["versions"])}', flush=True)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['build', 'generate'])
    parser.add_argument('--out', type=Path)
    parser.add_argument('--build-out', type=Path, default=BUILD_OUT)
    parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args()
    out = (args.out or (BUILD_OUT if args.phase == 'build' else RUN_OUT)).resolve()
    cfg = config(args.phase == 'build')
    protocol = {'projects': PROJECTS, 'builders': BUILDERS, 'planners': PLANNERS,
                'input': 'Public tasks.jsonl only; no human schema, reference, tests, or shell.',
                'feedback': 'JSON, compiler, deterministic examples, and generic page-load errors only; max 2 repairs.',
                'selection': 'First publicly valid library; every builder reported, no hidden-score selection.',
                'generation': 'All 20 tasks, cumulative descriptions, independent from scratch; one seed; free reused across builders.',
                'budget_authorization': '2026-11-12 daily cap $20; builder cap $5.5 + planner cap $9 = $14.5 allocated.',
                'phase': args.phase}
    extras = []
    packages = {}
    if args.phase == 'generate':
        barrier = args.build_out / 'build-complete.json'
        if not barrier.exists():
            raise ValueError('All builder attempts must finish before planning')
        extras.append(barrier)
        for project in PROJECTS:
            for builder in BUILDERS:
                folder = args.build_out / 'libraries' / project / slug(builder)
                record = json.loads((folder / 'record.json').read_text())
                extras.append(folder / 'record.json')
                if record['status'] == 'frozen':
                    package = json.loads((folder / 'package.json').read_text())
                    assert digest(package) == record['package_sha256']
                    extras.append(folder / 'package.json')
                    packages[project, builder] = package
        if (out / 'grading-started.json').exists():
            raise ValueError('Hidden grading has started: generation is locked')
    frozen_inputs(out, cfg, protocol, extras)
    client = provider(cfg, out)
    if args.phase == 'build':
        jobs = [(project, builder) for project in PROJECTS for builder in BUILDERS]
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            records = list(pool.map(lambda j: build_one(client, out, *j), jobs))
        dump(out / 'build-complete.json', {'records': records, 'sha256': digest(records), 'hidden_feedback': False})
    else:
        jobs = []
        for project in PROJECTS:
            for task in requirements(project)[1:]:
                for model in PLANNERS:
                    jobs.append((project, None, model, 'free', task['id'], None))
                    for builder in BUILDERS:
                        if (project, builder) in packages:
                            for method in ('free_lib', 'plan'):
                                jobs.append((project, builder, model, method, task['id'], packages[project, builder]))
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            records = list(pool.map(lambda j: candidate(client, out, *j), jobs))
        dump(out / 'generation-complete.json', {'candidates': len(records), 'records_sha256': digest(records),
                                               'transport_incomplete': sum(r['status'] != 'complete' for r in records)})


if __name__ == '__main__':
    main()
