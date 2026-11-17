"""Budgeted factorial generation; reference-prefix user messages are byte-identical."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from gui_dna.budget import Ledger, BudgetStop
from gui_dna.provider import ProviderError, parse_json
from test.ledger_read import totals, calls
from test.review_stage import freeze
from test.streaming_provider_v2 import StreamingOpenRouter
from test.webbench_expand.core import config as base_config
from test.webbench_dna import domain, evaluate
from test.webbench_dna.library import library
from test.webbench_dna.clean_prefix import clean_page
from test.library_repair.core import ROOT, read, dump, digest, slug
from test.library_repair.run import now

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/prefix-factorial-v2-20261114'
MODELS = ('openai/gpt-oss-120b', 'mistralai/mistral-small-3.2-24b-instruct')
PREFIXES = ('reference', 'self')
METHODS = ('free_lib', 'plan')


def config():
    return {**base_config(), 'models': list(MODELS), 'seed': 20261114,
            'budget_usd': 6., 'stop_new_requests_usd': 5.7, 'max_tokens': 12000}


def plan_output_schema():
    props = {'tools': {'type': 'array', 'items': {'type': 'string', 'enum': list(domain.TOOLS)}}}
    props.update({name: {'type': 'string', 'enum': choices} for name, choices in domain.SLOTS.items()})
    props['menu'] = {'type': 'object', 'properties': {
        name: {'type': 'array', 'items': {'type': 'string', 'enum': list(domain.COMMANDS)}} for name in domain.MENU_KINDS}, 'additionalProperties': False}
    props['shortcuts'] = {'type': 'object', 'properties': {
        name: {'type': 'string', 'enum': list(domain.COMMANDS)} for name in domain.SHORTCUT_KEYS}, 'additionalProperties': False}
    props.update({name: {'type': 'boolean'} for name in domain.FLAGS})
    return {'type': 'object', 'properties': props, 'additionalProperties': False}


def messages_for(task, method, starting_page, lib):
    description = domain.messages_for(task, 'dna', lib)[1]['content']
    schema = description.split('Allowed values — ', 1)[1].rsplit('Return the plan as JSON only.', 1)[0]
    material = {'requirements': task['descriptions'], 'features': task['features'],
                'starting_page_html': starting_page, 'shell_contract': domain.INTERFACE,
                'frozen_library': lib, 'assembly_plan_schema': plan_output_schema(), 'allowed_values_and_coverage': schema}
    system = ('Implement all cumulative requirements for this static file explorer. You receive a starting page and the complete same frozen library. '
              'Preserve required behavior; use no external resources. ')
    if method == 'free_lib':
        system += 'Return JSON only: {"html": "complete index.html including styles and scripts"}. You may reuse, adapt or ignore supplied functions and starting code.'
    else:
        system += 'Return only a JSON instance conforming to assembly_plan_schema, not the schema itself. Slot names such as select and fileClick are top-level string fields, not a nested slots object. Select library variants matching the requirements; include required tools, menu commands and shortcuts. You cannot add implementation code.'
    return [{'role': 'system', 'content': system}, {'role': 'user', 'content': json.dumps(material, ensure_ascii=False)}]


def prepare():
    assert not (OUT / 'review-manifest.json').exists()
    audit = read(ROOT / 'test/results/prefix-history-audit.json')
    assert audit['passed_pairs'] == audit['pairs'] == 210 and audit['passed_tests'] == audit['tests'] == 909
    lib = library()
    files = [HERE / 'run.py', HERE / 'PROTOCOL.md', ROOT / 'test/results/prefix-history-audit.json']
    for task in domain.tasks():
        html = clean_page(task, lib)
        page = OUT / 'prefixes' / task['id'] / 'index.html'
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(html)
        assert html == (ROOT / 'artifacts/prefix-history-audit-20261114/pages' / f'prefix-{task["k"]-1}' / 'index.html').read_text()
        assert messages_for(task, 'free_lib', html, lib)[1] == messages_for(task, 'plan', html, lib)[1]
        files.append(page)
    for name in ('domain.py', 'library.py', 'evaluate.py', 'run.py', 'clean_prefix.py', 'shell.html'):
        files.append(ROOT / 'test/webbench_dna' / name)
    files += [ROOT / p for p in ('test/provider_ext.py', 'test/streaming_provider_v2.py', 'test/webbench_expand/core.py',
              'src/gui_dna/provider.py', 'src/gui_dna/budget.py', 'test/todomvc_dna/evaluate.py')]
    freeze(OUT, config(), [str(p.relative_to(ROOT)) for p in files],
           {'models': MODELS, 'prefixes': PREFIXES, 'methods': METHODS, 'tasks': domain.tasks(),
            'library_sha256': lib['sha256'], 'candidates': 160, 'exploratory_protocol_correction': True,
            'abandoned_stage': 'artifacts/prefix-factorial-20261114', 'generation_deadline_utc': '2026-11-14T11:00:00Z'})
    Ledger(OUT / 'budget.sqlite3', 6, 5.7)
    print('Frozen matched inputs for 160 candidates', flush=True)


def verify():
    for name, sha in read(OUT / 'review-manifest.json')['sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha, name


def candidate(client, model, prefix, method, task, html, lib, resume):
    folder = OUT / 'runs' / slug(model) / prefix / method / task['id']
    record_path = folder / 'record.json'
    initial = messages_for(task, method, html, lib)
    if record_path.exists():
        record = read(record_path)
        assert read(folder / 'messages.json') == initial
        if record['status'] == 'complete' or not resume:
            return record
        if record['attempts'] and (not record['attempts'][-1]['feedback'] or len(record['attempts']) == 3):
            record.update(status='complete', finished_utc=now())
            dump(record_path, record)
            return record
    else:
        dump(folder / 'messages.json', initial)
        record = {'model': model, 'prefix': prefix, 'method': method, 'task': task['id'],
                  'initial_messages_sha256': digest(initial), 'starting_html_sha256': hashlib.sha256(html.encode()).hexdigest(),
                  'attempts': [], 'versions': [], 'status': 'generating', 'started_utc': now()}
    messages = initial
    for attempt in record['attempts']:
        if attempt['feedback']:
            messages += [{'role': 'assistant', 'content': read(folder / attempt['output'])['text']},
                         {'role': 'user', 'content': attempt['feedback']}]
    for index in range(len(record['attempts']), 3):
        if datetime.now(timezone.utc).isoformat() >= '2026-11-14T11:00:00+00:00':
            record.update(status='transport_incomplete', error='Generation time cutoff; no new request')
            dump(record_path, record)
            return record
        target = folder / f'call-{index}'
        if resume and target.exists():
            settled = {c['id'] for c in calls(OUT / 'budget.sqlite3') if c['actual'] is not None}
            requests = list(target.rglob('request.json'))
            assert all(read(p)['body']['messages'] == messages for p in requests)
            if not any(read(p)['call_id'] in settled and p.with_name('response.json').exists() for p in requests):
                parent = folder / 'discarded-transport' / f'call-{index}'
                destination = parent / str(max((int(p.name) for p in parent.glob('[0-9]*')), default=0) + 1)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(target), str(destination))
        try:
            raw = client.call(model, messages, target, f'prefix-factorial:{prefix}:{method}:{task["id"]}:a{index}', seed=20261114)
        except (ProviderError, BudgetStop) as error:
            record.update(status='transport_incomplete', error=str(error), finished_utc=now())
            dump(record_path, record)
            return record
        output = f'output-{index}.json'
        dump(folder / output, {'text': raw})
        error, public = None, None
        try:
            parsed = parse_json(raw)
            version = f'version-{index}'
            if method == 'free_lib':
                generated = parsed['html']
                if not isinstance(generated, str) or '<html' not in generated.lower():
                    raise ValueError('html must contain a complete HTML document')
                evaluate.write_candidate(folder / version, html=generated)
            else:
                script = domain.compile_plan(parsed, task['features'], lib)
                evaluate.write_candidate(folder / version, script=script)
            public = evaluate.public_check(folder / version)
            record['versions'].append(version)
            dump(folder / version / 'source-manifest.json', {'html_sha256': hashlib.sha256((folder / version / 'index.html').read_bytes()).hexdigest()})
        except (ValueError, KeyError, TypeError) as issue:
            error = str(issue)[:3000]
        feedback = None
        if error or public:
            feedback = ('Output could not be used: ' + error if error else 'Public page-load/tool-click errors: ' + json.dumps(public))
            feedback += '\nReturn a complete corrected output in the same JSON contract.'
        record['attempts'].append({'output': output, 'compile_error': error, 'public': public, 'feedback': feedback})
        dump(record_path, record)
        if not feedback:
            break
        messages += [{'role': 'assistant', 'content': raw}, {'role': 'user', 'content': feedback}]
    record.update(status='complete', finished_utc=now())
    dump(record_path, record)
    print(model, prefix, method, task['id'], len(record['attempts']), len(record['versions']), flush=True)
    return record


def generate(resume=False):
    verify()
    assert not (OUT / 'generation-stopped.json').exists()
    client = StreamingOpenRouter(config(), Ledger(OUT / 'budget.sqlite3', 6, 5.7))
    lib, tasks = library(), domain.tasks()
    def sequence(job):
        model, prefix, method = job
        html = (OUT / 'prefixes/task-1/index.html').read_text()
        records = []
        for task in tasks:
            start = (OUT / 'prefixes' / task['id'] / 'index.html').read_text() if prefix == 'reference' else html
            record = candidate(client, model, prefix, method, task, start, lib, resume)
            records.append(record)
            if record['status'] != 'complete':
                break
            if record['versions']:
                folder = OUT / 'runs' / slug(model) / prefix / method / task['id']
                html = (folder / record['versions'][-1] / 'index.html').read_text()
        return records
    jobs = [(m, p, f) for m in MODELS for p in PREFIXES for f in METHODS]
    with ThreadPoolExecutor(max_workers=4) as pool:
        records = [r for group in pool.map(sequence, jobs) for r in group]
    dump(OUT / 'cost-checkpoint.json', totals(OUT / 'budget.sqlite3'))
    complete = len(records) == 160 and all(r['status'] == 'complete' for r in records)
    if complete:
        dump(OUT / 'generation-complete.json', {'records_sha256': digest(records), 'records': records, 'finished_utc': now()})
        Ledger(OUT / 'budget.sqlite3', 6, 0)
        dump(OUT / 'generation-stopped.json', {'finished_utc': now(), 'complete': True})
        dump(OUT / 'cost-checkpoint.json', totals(OUT / 'budget.sqlite3'))
    print('complete', sum(r['status'] == 'complete' for r in records), '/160', totals(OUT / 'budget.sqlite3'), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['prepare', 'generate'])
    parser.add_argument('--resume-transport', action='store_true')
    args = parser.parse_args()
    prepare() if args.phase == 'prepare' else generate(args.resume_transport)
