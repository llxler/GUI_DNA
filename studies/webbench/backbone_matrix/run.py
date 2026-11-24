"""Freeze inputs and run the registered table/chart target-model comparison."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import time

import httpx

from gui_dna.budget import BudgetStop, Ledger
from gui_dna.provider import parse_json
from scripts.check_openrouter_credits import check_credits
from studies.interface_blind.core import compile_plan as chart_compile, validate_files
from studies.public_library_transfer import browser, core as public
from studies.study_io import ROOT, read, sha
from studies.webbench_expand.core import compile_plan as table_compile

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/backbone-matrix-20261124'
browser.OUT = OUT
PROJECTS = ('table', 'svg-chart')
TASKS = range(1, 21)
ARMS = ('direct', 'human', 'gpt5-library', 'self')
END = datetime(2026, 11, 24, 5, 0, tzinfo=timezone.utc)
# Model identity, allocated dollars, maximum input/output USD per million tokens.
MODELS = {
    'qwen': ('qwen/qwen3-coder-30b-a3b-instruct', 1.15, .25, 1),
    'mistral': ('mistralai/mistral-small-3.2-24b-instruct', 1.10, .25, 1),
    'oss': ('openai/gpt-oss-120b', 1.15, .25, 1),
    'gemma': ('google/gemma-3-12b-it', 1, .24, .70),
    'mini': ('openai/gpt-5-mini', 1.95, .30, 2.20),
    'gpt5': ('openai/gpt-5', 3.75, 1.30, 10.2),
    'haiku': ('anthropic/claude-haiku-4.5', 2.8, 1.1, 5.2),
    'sonnet': ('anthropic/claude-sonnet-4.5', 4.9, 3.1, 15.2),
    'gemini': ('google/gemini-2.5-flash', 2.2, .40, 2.7),
}
OLD = {p: ROOT / 'artifacts' / name for p, name in
       [('table', 'table-library-sources-20261123'), ('svg-chart', 'svg-chart-interfaces-20261123')]}
save = public.save


def register():
    dest = OUT / 'registered.json'
    if dest.exists():
        verify()
        return
    cap = sum(Decimal(str(values[1])) for values in MODELS.values())
    assert cap <= 20
    balance = check_credits(float(cap))
    if not balance['sufficient']:
        raise BudgetStop('Insufficient available balance for the registered allocation')
    response = httpx.get('https://openrouter.ai/api/v1/models', timeout=30)
    response.raise_for_status()
    catalog = {m['id']: m for m in response.json()['data']}
    inputs = [Path(__file__), HERE / 'PROTOCOL.md', Path(public.__file__), Path(browser.__file__),
              ROOT/'studies/webbench_expand/core.py', ROOT/'studies/interface_blind/core.py',
              ROOT/'src/gui_dna/budget.py', ROOT/'studies/interface_blind/compile.cjs']
    for project in PROJECTS:
        d = OUT/'inputs'/project
        save(d/'public.json', public.public_input(project))
        save(d/'browser.json', browser.verify_contract(project))
        for arm, old_name in [('direct','direct'), ('human','reference' if project=='table' else 'reference_typed'),
                              ('gpt5-library','ai')]:
            if arm != 'direct':
                original = (OLD[project]/(old_name+'-package.json') if project=='table'
                            else OLD[project]/'packages'/(old_name+'.json'))
                save(d/(arm+'.json'), read(original))
            for n in TASKS:
                source = OLD[project]/('inputs' if project=='table' else 'prompts')/old_name/f'task-{n}.json'
                save(d/arm/f'{n}.json', read(source))
        inputs.extend(p for p in d.rglob('*') if p.is_file())
    save(dest, {'utc':public.now(), 'end':END.isoformat(), 'budget_usd':float(cap),
                'models':MODELS, 'balance':balance, 'parameters':{
                    m:catalog[m]['supported_parameters'] for m,*_ in MODELS.values()},
                'files':{str(p.relative_to(ROOT)):sha(p) for p in inputs}})


def verify():
    for path, value in read(OUT/'registered.json')['files'].items():
        if sha(ROOT/path) != value:
            raise ValueError(f'Frozen input changed: {path}')


class Unavailable(Exception):
    pass


def request(tag, ledger, folder, messages, purpose, limit=8192):
    model, _, pin, pout = MODELS[tag]
    allowed = read(OUT/'registered.json')['parameters'][model]
    body = {'model':model, 'messages':messages, 'max_tokens':limit,
            'provider':{'sort':'price', 'allow_fallbacks':True, 'max_price':{
                'prompt':pin, 'completion':pout, 'request':0}}}
    if 'temperature' in allowed:
        body['temperature'] = 0
    if 'seed' in allowed:
        body['seed'] = 20261124
    if tag in ('mini','gpt5','oss'):
        body['reasoning'] = {'effort':'low','exclude':True}
    if (folder/'settled.json').exists():
        assert read(folder/'request.json')['body']==body
        return read(folder/'response.json')['choices'][0]['message']['content'] or ''
    if (folder/'request.json').exists():
        raise Unavailable('Previously attempted; original reservation retained')
    if (OUT/tag/'route-closed.json').exists() or datetime.now(timezone.utc)>=END:
        raise Unavailable('Closed model route or generation deadline')
    bound = len(json.dumps(body,ensure_ascii=False).encode()) + 2048
    amount = (bound*Decimal(str(pin)) + limit*Decimal(str(pout))) / 1_000_000
    ticket = ledger.reserve(amount,purpose,model)
    save(folder/'request.json',{'body':body,'call_id':ticket,'input_bound':bound,'reserved_usd':float(amount)})
    started=time.monotonic()
    try:
        res=httpx.post('https://openrouter.ai/api/v1/chat/completions',json=body,
                       headers={'Authorization':'Bearer '+os.environ['OPENROUTER_API_KEY']},
                       timeout=httpx.Timeout(220,connect=25))
        res.raise_for_status()
        payload=res.json()
        save(folder/'response.json',payload)
        usage=payload.get('usage') or {}
        if usage.get('cost') is None:
            raise ValueError('Missing usage receipt')
        ledger.settle(ticket,usage['cost'],time.monotonic()-started,payload.get('id'),usage)
        choice=payload['choices'][0]
        if choice.get('finish_reason')=='error':
            raise ValueError('Provider error finish')
        content=choice['message'].get('content') or ''
        save(folder/'settled.json',{'ticket':ticket,'response_sha256':sha(folder/'response.json')})
        return content
    except (httpx.HTTPError,ValueError,KeyError,IndexError,TypeError) as exc:
        status=exc.response.status_code if isinstance(exc,httpx.HTTPStatusError) else None
        reason=f'HTTP {status}' if status else type(exc).__name__
        ledger.uncertain(ticket,reason)
        save(folder/'error.json',{'reason':reason})
        if status in (401,402,403,404):
            save(OUT/tag/'route-closed.json',{'reason':reason})
        raise Unavailable(reason) from None


def normalized(raw):
    for control in raw['controls']:
        if control.get('type')=='boolean':
            if control.get('values') in (['true','false'],['false','true'],[True,False],[False,True]):
                control['values']=[]
            for field in ('default','example'):
                if isinstance(control.get(field),bool):
                    control[field]=str(control[field]).lower()
    return raw


def build(tag, project, ledger):
    dest=OUT/tag/project/'build'
    if (dest/'status.json').exists():
        return read(dest/'status.json')
    data=read(OUT/'inputs'/project/'public.json')
    base=public.build_messages(data)
    base[0]['content']+=' Boolean values may also be listed as true and false. Use a verbatim unique starter anchor when inserting a fragment; otherwise leave both strings empty.'
    msg=base
    attempts=[]
    state={'status':'missing'}
    for n in (1,2):
        folder=dest/f'attempt-{n}'
        try:
            raw=request(tag,ledger,folder,msg,f'build/{project}/{n}',16000)
        except (BudgetStop,Unavailable) as exc:
            state={'status':'missing','reason':str(exc)}
            break
        try:
            pkg=public.package(data,normalized(public.parse(raw)))
            for name,plan in [('default',pkg['defaults']),('first',pkg['examples'][0]['plan'])]:
                page=folder/name
                public.materialize(project,pkg,plan,page)
                errors=browser.public_load(project,page)
                save(folder/(name+'.json'),errors)
                if errors:
                    raise ValueError(str(errors)[:1200])
            save(dest/'package.json',pkg)
            state={'status':'valid','package_sha256':sha(dest/'package.json'),'fixed':str((folder/'first').relative_to(ROOT))}
            break
        except (ValueError,TypeError,KeyError,IndexError,AttributeError) as exc:
            why=f'{type(exc).__name__}: {exc}'[:1200]
            attempts.append(why)
            state={'status':'build_failed'}
            msg=base+[{'role':'assistant','content':raw[:65000]},
                      {'role':'user','content':'Public format/load error: '+why+'. Return a complete replacement JSON package.'}]
    state['public_errors']=attempts
    save(dest/'status.json',state)
    return state


def target(tag, project, arm, n, ledger):
    dest=OUT/tag/project/arm/str(n)
    if (dest/'result.json').exists():
        return read(dest/'result.json')
    public_data=read(OUT/'inputs'/project/'public.json')
    row={'project':project,'task':n,'arm':arm,'model':MODELS[tag][0],'status':'missing'}
    if arm=='self':
        status=read(OUT/tag/project/'build/status.json')
        if status['status']!='valid':
            row.update(status=status['status'], reason='Preparation '+status['status'])
            save(dest/'result.json',row)
            return row
        pkg=read(OUT/tag/project/'build/package.json')
        msg=public.plan_messages(public_data,n,pkg)
    else:
        pkg=read(OUT/'inputs'/project/(arm+'.json')) if arm!='direct' else None
        msg=read(OUT/'inputs'/project/arm/f'{n}.json')
    try:
        raw=request(tag,ledger,dest/'call',msg,f'target/{project}/{arm}/{n}')
    except (BudgetStop,Unavailable) as exc:
        row['reason']=str(exc)
    else:
        row.update(status='invalid',response_sha256=sha(dest/'call/response.json'))
        try:
            parsed=parse_json(raw)
            page=dest/'page'
            if arm=='self':
                public.materialize(project,pkg,parsed,page)
            else:
                if arm=='direct':
                    if set(parsed)!={'files'} or not isinstance(parsed['files'],dict):
                        raise ValueError('Expected one files object')
                    added=public.files_map([{'path':k,'content':v} for k,v in parsed['files'].items()])
                else:
                    compiler=table_compile if project=='table' else chart_compile
                    added=compiler(pkg,parsed)
                files=validate_files(public_data['starter'] | added)
                # Apply the same mounted-asset and path checks to all arms.
                public.emit(project,files,page)
            row.update(status='valid',page=str(page.relative_to(ROOT)),files=browser.tree(page))
        except (ValueError,TypeError,KeyError,IndexError,AttributeError) as exc:
            row['reason']=str(exc)[:400]
    save(dest/'result.json',row)
    return row


def generate(tag):
    with browser.lock(OUT/tag/'.run.lock'):
        if (OUT/tag/'seal.json').exists():
            return
        verify()
        ledger=Ledger(OUT/tag/'budget.sqlite3',MODELS[tag][1],MODELS[tag][1])
        target(tag,'table','direct',1,ledger)
        for p in PROJECTS:
            build(tag,p,ledger)
        jobs=[(p,a,n) for n in TASKS for p in PROJECTS for a in ARMS]
        with ThreadPoolExecutor(max_workers=3) as pool:
            rows=list(pool.map(lambda j:target(tag,*j,ledger),jobs))
        builds={p:read(OUT/tag/p/'build/status.json') for p in PROJECTS}
        save(OUT/tag/'seal.json',{'utc':public.now(),'registration':sha(OUT/'registered.json'),
                                 'rows':rows,'builds':builds})
        print(tag,'sealed',len(rows),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('register','generate'))
    parser.add_argument('model',nargs='?',choices=MODELS)
    args=parser.parse_args()
    if args.action=='register':
        register()
    else:
        generate(args.model)
