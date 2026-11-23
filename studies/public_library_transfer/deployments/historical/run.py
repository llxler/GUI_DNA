"""Fresh historical-model deployments with separately capped, restartable ledgers."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
import fcntl
import json
import os
from pathlib import Path
import time

import httpx

from gui_dna.budget import BudgetStop, Ledger
from scripts.check_openrouter_credits import check_credits
from studies.study_io import ROOT, dump, now, read, sha

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/public-library-transfer-remote-20261123'
MAIN = ROOT / 'artifacts/public-library-transfer-20261123'
END = datetime(2026, 11, 23, 9, 24, tzinfo=timezone.utc)
CAP = 3.50
MODELS = {'mistral': 'mistralai/mistral-small-3.2-24b-instruct', 'oss': 'openai/gpt-oss-120b'}
BUILDERS = {'gpt5': 'openai/gpt-5', 'claude': 'anthropic/claude-sonnet-4.5'}
PRICES = {'prompt': .12, 'completion': .45, 'request': 0}
BOTH = ('table', 'dom1', 'form', 'calculator', 'bom')
PROJECTS = BOTH + ('svg-chart', 'expression-editor', 'draw')
RETRY = {408, 429, 502, 503, 504}


def scheduled():
    for project in PROJECTS:
        for model in (MODELS if project in BOTH else ('oss',) if project == 'draw' else ('mistral',)):
            tasks = range(4, 21, 4) if project == 'draw' else range(1, 21)
            for n in tasks:
                for arm in (('direct', 'gpt5') if project in ('svg-chart', 'expression-editor') else ('direct', 'gpt5', 'claude')):
                    yield project, model, n, arm


def request_format(name, schema):
    return {'type': 'json_schema', 'json_schema': {'name': name, 'strict': True, 'schema': schema}}


def register():
    from studies.public_library_transfer import core
    folder = OUT / 'registered.json'
    if folder.is_file():
        freeze = read(folder)
        for path, value in freeze['source_sha256'].items():
            if sha(ROOT / path) != value:
                raise ValueError(f'Registered dependency changed: {path}')
        return
    credits = check_credits(7)
    if not credits['sufficient']:
        raise BudgetStop('Remote deployment allocation unfunded')
    source = [Path(__file__), HERE / 'PROTOCOL.md', Path(core.__file__)]
    inputs = {project: sha(MAIN / 'inputs' / f'{project}.json') for project in PROJECTS}
    matched = list(scheduled())
    dump(folder, {'registered_utc': now(), 'deadline': END.isoformat(), 'models': MODELS, 'builders': BUILDERS,
                  'source_sha256': {str(p.relative_to(ROOT)): sha(p) for p in source}, 'inputs_sha256': inputs,
                  'models_budget_usd': {model: CAP for model in MODELS}, 'credit_check': credits,
                  'samples_per_target': 1, 'tasks': matched, 'price_caps_per_million_usd': PRICES})


def call(folder, model, messages, name, schema, ledger, purpose):
    """POST each fresh admission once; a transport retry uses its own reservation."""
    body = {'model': MODELS[model], 'messages': messages, 'temperature': 0, 'max_tokens': 8192 if name=='page' else 768,
            'provider': {'allow_fallbacks': True, 'require_parameters': True, 'sort': 'price', 'max_price': PRICES},
            'response_format': request_format(name, schema), 'stream': False}
    if model == 'oss':
        body['reasoning'] = {'effort': 'low', 'exclude': True}
    # Count UTF-8 bytes of the entire body, including JSON Schema and template headroom.
    bound = len(json.dumps(body, ensure_ascii=False).encode()) + 2048
    reserve = (Decimal(bound) * Decimal(str(PRICES['prompt'])) + Decimal(body['max_tokens']) * Decimal(str(PRICES['completion']))) / 1_000_000
    for retry in (0, 1):
        step = folder / f'attempt-{retry}'
        req = step / 'request.json'
        if req.is_file():
            request = read(req)
            if request['body'] != body:
                raise ValueError('Sealed request changed')
            if (step/'settled.json').is_file():
                response = read(step/'response.json')
                return response['choices'][0]['message']['content'] or '', sha(step/'response.json')
            if (step/'error.json').is_file() and read(step/'error.json').get('http_status') in RETRY and retry == 0:
                continue
            raise RuntimeError('Interrupted or unresolved admission; reservation retained')
        if datetime.now(timezone.utc) >= END:
            raise BudgetStop('New-request deadline reached')
        call_id = ledger.reserve(reserve, purpose, MODELS[model])
        dump(req, {'body': body, 'call_id': call_id, 'reserved_usd': float(reserve), 'input_token_bound': bound})
        begin = time.monotonic()
        try:
            response = httpx.post('https://openrouter.ai/api/v1/chat/completions', headers={
                'Authorization':'Bearer '+os.environ['OPENROUTER_API_KEY'], 'X-Title':'GUI-DNA public library transfer'},
                json=body, timeout=190)
            response.raise_for_status()
            payload = response.json()
            dump(step/'response.json', payload)
            usage = payload.get('usage') or {}
            if usage.get('cost') is None:
                raise RuntimeError('Response has no billed cost')
            ledger.settle(call_id, usage['cost'], time.monotonic()-begin, payload.get('id'), usage)
            dump(step/'settled.json', {'call_id':call_id,'billed_usd':usage['cost']})
            return payload['choices'][0]['message']['content'] or '', sha(step/'response.json')
        except Exception as error:
            status = error.response.status_code if isinstance(error,httpx.HTTPStatusError) else None
            detail = f'HTTP {status}' if status else type(error).__name__
            ledger.uncertain(call_id, detail)
            dump(step/'error.json', {'error': detail, 'http_status': status})
            if retry == 0 and status in RETRY:
                time.sleep(4)
                continue
            raise RuntimeError(detail) from None


def deploy(target, ledger):
    from studies.public_library_transfer import core
    project, model, task, arm = target
    folder = OUT / 'runs' / model / project / arm / f'task-{task}'
    dest = folder / 'result.json'
    if dest.is_file():
        return read(dest)
    public_file = MAIN / 'inputs' / f'{project}.json'
    if sha(public_file) != read(OUT/'registered.json')['inputs_sha256'][project]:
        raise ValueError('Public input changed')
    public = read(public_file)
    direct = arm == 'direct'
    row = {'project': project, 'task': task, 'arm': 'direct' if direct else 'plan', 'rep': 0 if direct else 1,
           'builder': None if direct else BUILDERS[arm], 'planner': MODELS[model], 'page':None, 'files':None}
    if direct:
        messages = core.direct_messages(public, task)
        schema = core.obj({'files':core.array(core.FILE)})
    else:
        built = MAIN / 'builds' / project / arm
        if not (built/'status.json').is_file():
            return None
        status = read(built/'status.json')
        if status['status'] != 'valid':
            dump(dest, row | {'status':'build_failed', 'build_status_sha256':sha(built/'status.json')})
            return read(dest)
        package = read(built/'package.json')
        row['package_sha256'] = sha(built/'package.json')
        if status['package_sha256'] != row['package_sha256']:
            raise ValueError('Builder package changed')
        schema = dict(package['plan_schema'], required=list(package['plan_schema']['properties']))
        messages = core.plan_messages(public, task, package)
    try:
        reply, response_sha = call(folder, model, messages, 'page' if direct else 'plan', schema, ledger,
                                  f'{project}/{arm}/task-{task}')
    except (RuntimeError,BudgetStop) as exc:
        dump(dest, row | {'status':'missing','reason':str(exc)[:500]})
        return read(dest)
    row['response_sha256'] = response_sha
    try:
        value = json.loads(reply)
        page = folder/'page'
        if direct:
            core.materialize_direct(project, public, value, page)
        else:
            if not isinstance(value,dict) or set(value) != set(schema['required']):
                raise ValueError('Expected every declared parameter')
            core.materialize(project, package, value, page)
        files = {p.relative_to(page).as_posix():sha(p) for p in sorted(page.rglob('*')) if p.is_file()}
        if 'index.html' not in files:
            raise ValueError('No entry page')
        row.update(status='valid', files=files, page=str(page.relative_to(ROOT)))
    except (KeyError,ValueError,TypeError) as exc:
        row.update(status='invalid',reason=str(exc)[:500])
    dump(dest,row)
    return row


def run(phase, projects, workers):
    register()
    ledgers = {name: Ledger(OUT/name/'budget.sqlite3', CAP, CAP) for name in MODELS}
    targets = [r for r in scheduled() if r[0] in projects and
               (phase == 'all' or (phase=='direct') == (r[3]=='direct'))]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(lambda r:deploy(r, ledgers[r[1]]), targets))
    print(f'{sum(r is not None for r in rows)}/{len(rows)} admitted or resolved')


def seal():
    from studies.public_library_transfer.browser import write_json
    all_rows = []
    complete = []
    for project in PROJECTS:
        rows=[]
        for _,model,task,arm in (row for row in scheduled() if row[0]==project):
            f=OUT/'runs'/model/project/arm/f'task-{task}'/'result.json'
            if not f.is_file():
                break
            rows.append(read(f))
        else:
            path = OUT/'project-seals'/f'{project}.json'
            content={'project':project,'rows':rows}
            if path.is_file() and read(path)!=content:
                raise ValueError(f'Prior seal changed for {project}')
            if not path.is_file():
                write_json(path, content)
            complete.append(project)
            all_rows.extend(rows)
    if set(complete)==set(PROJECTS):
        output=OUT/'generation-sealed.json'
        content={'rows':all_rows,'register_sha256':sha(OUT/'registered.json')}
        if output.is_file() and read(output)!=content:
            raise ValueError('Prior final seal changed')
        if not output.is_file():
            write_json(output,content)
    print('Sealed projects:', ', '.join(complete))


def main():
    p=argparse.ArgumentParser()
    p.add_argument('phase',choices=['register','direct','plan','all','seal'])
    p.add_argument('--projects',choices=PROJECTS,nargs='+',default=list(PROJECTS))
    p.add_argument('--workers',type=int,default=8)
    a=p.parse_args()
    if a.phase=='register': register()
    elif a.phase=='seal': seal()
    else:
        OUT.mkdir(parents=True,exist_ok=True)
        with (OUT/'generation.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            run(a.phase, a.projects, a.workers)


if __name__=='__main__':
    main()
