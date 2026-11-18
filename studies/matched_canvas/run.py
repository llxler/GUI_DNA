"""Generate both workflows under independent and identical spending limits."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import json
import subprocess

from gui_dna.budget import Ledger, BudgetStop
from gui_dna.provider import ProviderError, parse_json
from studies.streaming_provider_v2 import StreamingOpenRouter
from studies.study_io import ROOT, dump, read, sha, now
from studies.interface_blind.core import ENVIRONMENT, validate_files, write_files, public_check
from studies.webbench_expand.core import SCHEMA_RULES, compile_plan
from .browser import OUT, PROJECT, TASKS, add_assets

HERE = Path(__file__).resolve().parent
MODEL = 'openai/gpt-5'
LIMIT = 4
CONFIG = {'models': [MODEL], 'max_tokens': 16000, 'temperature': 0.6,
          'price_caps_per_million': {'prompt': 1.25, 'completion': 10},
          'reasoning_effort': {MODEL: 'medium'}, 'omit_params': {MODEL: ['seed', 'temperature']},
          'provider_order': {MODEL: ['OpenAI']}}
GROUPS = [(arm, rep) for arm in ('free', 'plan') for rep in (1, 2)]


class Client(StreamingOpenRouter):
    RATE_LIMIT_TRIES = 1

    def call(self, *args, **kwargs):
        if datetime.now(timezone.utc) >= datetime(2026,11,18,13,30,tzinfo=timezone.utc):
            raise BudgetStop('New-request deadline reached')
        return super().call(*args, **kwargs)


def messages(arm, task, preparation=None):
    requirements = [{k: row[k] for k in ('id', 'description')} for row in
                    map(json.loads, (PROJECT / 'tasks.jsonl').read_text().splitlines())]
    assets = sorted(p.name for p in (PROJECT / 'assets').iterdir())
    shared = (ENVIRONMENT + '\nProvided runtime assets under assets/: ' + ', '.join(assets)
              + '\nFull public scope:\n' + json.dumps(requirements, ensure_ascii=False))
    if task is None:
        if arm == 'free':
            instruction = ('Prepare written implementation notes for five subsequent independent code generations. '
                           'Return {"notes":"plain text"}. Explain state, interactions and relevant requirements. '
                           'Use prose only. Each target will implement its own source files from scratch.')
        else:
            instruction = ('Build a reusable library for this scope. Return exactly design (text), '
                'plan_documentation (text), plan_schema, files (text files), compiler (a pure synchronous '
                'function compile(plan, files) returning an index.html file map), examples (two objects with '
                'description and plan). Choose semantic behavior options, not per-task identifiers or code as data. '
                'The VM has no DOM, require, process or filesystem. Both examples must compile and load.\n'
                + SCHEMA_RULES)
    else:
        shared += '\nTarget: implement the sequence through ' + task + ', inclusive.'
        if preparation is not None:
            shared += '\nYour frozen preparation:\n' + json.dumps(preparation, ensure_ascii=False)
        instruction = ('Implement the full target from scratch. Return {"files":{"index.html":"...", ...}}.'
                       if arm == 'free' else 'Return just the data plan matching the supplied frozen schema.')
    return [{'role': 'system', 'content': instruction + ' Return one JSON object.'},
            {'role': 'user', 'content': shared}]


def write_page(page, files):
    validate_files(files)
    if any(name.split('/')[0] == 'assets' for name in files):
        raise ValueError('assets/ is reserved for the supplied image files')
    write_files(page, files)
    add_assets(page)
    return public_check(page)


def check(arm, task, value, preparation, folder):
    if task:
        files = compile_plan(preparation, value) if arm == 'plan' else value['files']
        return write_page(folder / 'page', files)
    if arm == 'free':
        if set(value) != {'notes'} or not isinstance(value['notes'], str):
            raise ValueError('Return exactly one notes string')
        return []
    if set(value) != {'design','plan_documentation','plan_schema','files','compiler','examples'}:
        raise ValueError('Unexpected or missing library envelope keys')
    if not all(isinstance(value[k], str) and value[k].strip()
               for k in ('design','plan_documentation','compiler')):
        raise ValueError('Design, documentation and compiler must be nonempty text')
    validate_files(value['files'])
    if len(value['examples']) != 2 or value['plan_schema'].get('type') != 'object':
        raise ValueError('Expected two examples and an object schema')
    feedback = []
    for i, example in enumerate(value['examples']):
        files = compile_plan(value, example['plan'])
        if files != compile_plan(value, example['plan']):
            raise ValueError('Compiler output is not deterministic')
        feedback += write_page(folder / f'example-{i}', files)
    return feedback


def chain(client, group, arm, task=None, preparation=None):
    folder = group / (task or 'prepare')
    result = folder / 'result.json'
    if result.exists():
        return read(result)
    msgs = messages(arm, task, preparation)
    dump(folder / 'messages.json', msgs)
    for i in range(2):
        attempt = folder / f'attempt-{i}'
        try:
            raw = client.call(MODEL, msgs, attempt / 'api', arm + '/' + (task or 'prepare'))
        except (ProviderError, BudgetStop) as err:
            state = {'status': 'missing', 'error': str(err), 'attempt': i}
            break
        try:
            parsed = parse_json(raw)
            if not isinstance(parsed, dict):
                raise ValueError('Expected a JSON object')
            # Replayed settled requests use the previously recorded public check.
            if (attempt / 'check.json').exists():
                feedback = read(attempt / 'check.json')
            else:
                feedback = check(arm, task, parsed, preparation, attempt)
        except (KeyError, TypeError, ValueError, subprocess.TimeoutExpired) as err:
            feedback = [str(err)[:1200]]
        dump(attempt / 'check.json', feedback)
        page = attempt / 'page'
        state = {'status': 'accepted' if not feedback else 'invalid', 'attempt': i,
                 'page': str(page.relative_to(ROOT)) if (page / 'index.html').is_file() else None}
        if not feedback:
            if task is None:
                dump(folder / 'frozen.json', parsed)
            break
        msgs = msgs + [{'role':'assistant','content':raw},{'role':'user','content':
                'Public format, compile or load feedback: ' + json.dumps(feedback) + '. Return a full corrected object.'}]
    dump(result, state)
    return state


def workflow(item):
    arm, rep = item
    group = OUT / f'{arm}-{rep}'
    if (group / 'complete.json').exists():
        return
    client = Client(CONFIG, Ledger(group / 'budget.sqlite3', LIMIT, LIMIT))
    prepared = chain(client, group, arm)
    package = read(group/'prepare/frozen.json') if prepared['status'] == 'accepted' else None
    def target(task):
        if package is None and arm == 'plan':
            status = 'missing' if prepared['status'] == 'missing' else 'build_failure'
            dump(group / task / 'result.json', {'status': status, 'page': None})
        else:
            chain(client, group, arm, task, package)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(target, TASKS))
    with client.ledger.connect() as db:
        db.execute('UPDATE policy SET stop=0 WHERE id=1')
    dump(group/'complete.json', {'utc': now()})


def freeze():
    paths = [HERE/'__init__.py', HERE/'run.py', HERE/'browser.py', HERE/'evaluate.py', HERE/'PROTOCOL.md', OUT/'calibration.json', ROOT/'uv.lock']
    for name in ('src/gui_dna/provider.py','src/gui_dna/budget.py','studies/streaming_provider_v2.py',
                 'studies/provider_ext.py','studies/study_io.py','studies/browser_jobs.py',
                 'studies/interface_blind/core.py','studies/interface_blind/compile.cjs',
                 'studies/webbench_expand/core.py','studies/webbench_expand/schema.py',
                 'artifacts/webbench-expand-runtime-157/package-lock.json'):
        paths.append(ROOT/name)
    paths += [p for p in PROJECT.rglob('*') if p.is_file()]
    paths += [p for p in (OUT/'harness').rglob('*') if p.is_file()]
    data = {str(p.relative_to(ROOT)): sha(p) for p in sorted(paths)}
    manifest = OUT/'protocol-freeze.json'
    if manifest.exists():
        assert read(manifest)['sha256'] == data
    else:
        dump(manifest, {'utc': now(), 'sha256': data, 'model': MODEL, 'config': CONFIG, 'cap_per_group': LIMIT})


def main():
    if (OUT/'generated.json').exists():
        raise ValueError('Generation already frozen')
    freeze()
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(workflow, GROUPS))
    files = [p for arm,rep in GROUPS for p in (OUT/f'{arm}-{rep}').rglob('*')
             if p.is_file() and not p.name.startswith('budget.sqlite3')]
    dump(OUT/'generated.json', {'utc': now(), 'sha256': {str(p.relative_to(ROOT)):sha(p) for p in files}})


if __name__ == '__main__':
    main()
