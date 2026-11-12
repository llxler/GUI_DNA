"""Whole-library preloading, fixed before the first planner request.

Builders can place implementations inside the compiler. Preload both compiler
and original file map for unrestricted code; never require retransmission.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from gui_dna.budget import BudgetStop
from gui_dna.provider import ProviderError, parse_json
from test.ledger_read import calls
from .core import (ROOT, PROJECTS, BUILDERS, PLANNERS, SEED, config, digest, dump, slug,
    requirements, planner_messages, compile_plan, public_check, write_files, validate_files)
from .run import frozen_inputs, provider
from .resume import continuation_messages

BUILD = ROOT / 'artifacts/webbench-expand-build'
OUT = ROOT / 'artifacts/webbench-expand-run'
COMPILER_PATH = '__gui_dna_support/compiler.mjs'
FILES_PATH = '__gui_dna_support/files.json'


def preloaded(package):
    assert COMPILER_PATH not in package['files'] and FILES_PATH not in package['files']
    return {**package['files'], COMPILER_PATH: package['compiler'] + '\nexport {compile};\n',
            FILES_PATH: json.dumps(package['files'], ensure_ascii=False)}


def messages_for(project, task, method, package):
    messages = planner_messages(project, task, method, package)
    if package is not None:
        messages[1]['content'] += (f'\nThe unrestricted-code runtime also preloads the exact frozen compiler as an ES module at /{COMPILER_PATH} '
            f'(named export compile), and the original frozen file map as JSON at /{FILES_PATH}. '
            'This includes implementations stored inside the compiler, not only library files. '
            'Code may import compile and fetch the original files to obtain the same output map, or replace any implementation. '
            'You still implement serving/loading its output in the browser; all candidate files are served statically. '
            'Plans continue to use the exact original library/compiler through the validated runtime.')
        messages[1]['content'] += ('\nUnrestricted code may alternatively return {"program":"function build(files, compile) { ...; return outputFiles; }"}. '
            'This JavaScript runs at build time in the same pure VM as the plan compiler, with the original frozen file map '
            'and exact frozen compile function preloaded. It may call compile(anyData, files), modify any returned file, '
            'or implement its own whole page. No plan-schema restriction applies to this code. Return a complete file map '
            'including index.html; no DOM/require/process/fetch is available at build time. Runtime files may use browser APIs. '
            'A one-line build function can reuse the compiler without copying it or implementing a browser-side loader.')
    if method == 'free_lib':
        messages[0]['content'] += ' Alternatively return the unrestricted build-time JavaScript program form documented below; choose either files or program.'
    return messages


def output_files(method, package, parsed):
    if method == 'plan':
        return compile_plan(package, parsed)
    if method == 'free_lib' and isinstance(parsed, dict) and 'program' in parsed:
        if set(parsed) != {'program'} or not isinstance(parsed['program'], str):
            raise ValueError('Return exactly program or files, not both')
        result = subprocess.run(['node', str(Path(__file__).with_name('free_build.cjs'))],
            input=json.dumps({'package': package, 'program': parsed['program']}), capture_output=True, text=True, timeout=15)
        if result.returncode:
            raise ValueError('code build: ' + result.stderr.strip()[:1200])
        return validate_files(json.loads(result.stdout))
    if not isinstance(parsed, dict) or not isinstance(parsed.get('files'), dict):
        raise ValueError('files must be an object')
    return {**preloaded(package), **parsed['files']} if method == 'free_lib' else parsed['files']


def candidate(client, project, builder, model, method, task, package, resume=False):
    folder = OUT / 'runs' / project / (slug(builder) if builder else 'no_library') / slug(model) / method / task
    target = folder / 'record.json'
    messages = messages_for(project, task, method, package)
    if target.exists():
        record = json.loads(target.read_text())
        if record['status'] == 'complete' or not resume:
            return record
        assert record['status'] == 'transport_incomplete'
        assert json.loads((folder / 'messages.json').read_text()) == messages
        messages = continuation_messages(folder, record, False)
        start = len(record['attempts'])
        lost = folder / f'call-{start}'
        settled = {r['id'] for r in calls(OUT / 'budget.sqlite3') if r['actual'] is not None}
        for path in lost.rglob('request.json'):
            request = json.loads(path.read_text())
            assert request['body']['messages'] == messages and request['call_id'] not in settled
        dest = OUT / 'discarded-transport' / folder.relative_to(OUT)
        dest /= str(max((int(p.name) for p in dest.glob('[0-9]*')), default=0) + 1)
        dest.mkdir(parents=True)
        shutil.copy2(target, dest / 'record.json')
        dump(dest / 'receipt.json', {'messages_sha256': digest(messages), 'next_attempt': start,
            'retained_valid_attempts': start, 'policy': 'Retry missing transport only; no extra valid attempts.'})
        if lost.exists():
            shutil.move(str(lost), str(dest / lost.name))
        record.pop('error', None)
        record['status'] = 'complete'
    else:
        dump(folder / 'messages.json', messages)
        record = {'project': project, 'builder': builder, 'model': model, 'method': method, 'task': task,
            'package_sha256': digest(package) if package else None, 'attempts': [], 'versions': [], 'status': 'complete'}
        start = 0
    for attempt in range(start, 3):
        try:
            raw = client.call(model, messages, folder / f'call-{attempt}', f'plan-webbench-expand:{method}', seed=SEED)
        except BudgetStop:
            record['status'] = 'transport_incomplete'
            dump(target, record)
            raise
        except ProviderError as error:
            record.update(status='transport_incomplete', error=str(error))
            break
        dump(folder / f'output-{attempt}.json', {'text': raw})
        try:
            files = output_files(method, package, parse_json(raw))
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
        messages += [{'role': 'assistant', 'content': raw}, {'role': 'user', 'content':
            'Public format/compiler/load feedback:\n' + '\n'.join(feedback) + '\nReturn the full corrected JSON output.'}]
    dump(target, record)
    print(f'{project} {builder or "none"} {model} {method} {task}: {record["status"]}, attempts={len(record["attempts"])}', flush=True)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=6)
    parser.add_argument('--resume-transport', action='store_true')
    args = parser.parse_args()
    assert not (OUT / 'grading-started.json').exists()
    barrier = BUILD / 'build-complete.json'
    assert barrier.exists()
    packages, extras = {}, [barrier, Path(__file__).resolve(), Path(__file__).with_name('resume.py'),
        Path(__file__).with_name('PRELOAD.md'), Path(__file__).with_name('free_build.cjs'), ROOT / 'artifacts/webbench-expand-harness/calibration.json',
        ROOT / 'artifacts/webbench-expand-harness/parallel-calibration.json', ROOT / 'artifacts/webbench-expand-harness/manifest.json']
    for project in PROJECTS:
        for builder in BUILDERS:
            folder = BUILD / 'libraries' / project / slug(builder)
            record = json.loads((folder / 'record.json').read_text())
            extras.append(folder / 'record.json')
            if record['status'] == 'frozen':
                package = json.loads((folder / 'package.json').read_text())
                assert digest(package) == record['package_sha256']
                preloaded(package)
                packages[project, builder] = package
                extras.append(folder / 'package.json')
    frozen_inputs(OUT, config(False), {'phase': 'generate', 'projects': list(PROJECTS),
        'builders': list(BUILDERS), 'models': list(PLANNERS), 'same_user_input': True,
        'preload': 'All frozen files plus exact compiler module/original file-map JSON. Unrestricted code may instead return a build(files,compile) JavaScript program in the same pure VM, without schema checks. Fixed before first planner call after observing builder code placement, no hidden candidate scores.',
        'generation': '20 cumulative tasks from scratch; free shared across builders; same 12000 output cap and 2 repairs.',
        'controls': 'Both examples and each planner final-task executable page reused unchanged on all tasks; no score-based selection.',
        'scope': 'Strict-format replication, all public requirements visible to builders; not heldout transfer.',
        'budget': 'Daily20; previous exposure3.259005 plus buildcap4.5 and plannercap5 <=20.'}, extras)
    client = provider(config(False), OUT)
    jobs = []
    for project in PROJECTS:
        for task in requirements(project)[1:]:
            for model in PLANNERS:
                jobs.append((project, None, model, 'free', task['id'], None))
                for builder in BUILDERS:
                    if (project, builder) in packages:
                        jobs.extend((project, builder, model, method, task['id'], packages[project, builder]) for method in ('free_lib', 'plan'))
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        records = list(pool.map(lambda job: candidate(client, *job, resume=args.resume_transport), jobs))
    if any(r['status'] != 'complete' for r in records):
        raise ValueError('Incomplete transports remain; use --resume-transport before hidden scoring')
    dump(OUT / 'generation-complete.json', {'candidates': len(records), 'records_sha256': digest(records), 'transport_incomplete': 0})


if __name__ == '__main__':
    main()
