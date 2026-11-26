"""Replay the original four deployment interfaces with visible answers enabled across arms."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.public_library_transfer.self_refinement.suite_recovery import run as recovery
from studies.study_io import ROOT,now,read,sha
from .. import run as prior,todo

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/todo-visible-choices-20261126pm'
TAGS=('qwen9','deepseek-flash')
CAP=.50
SUITE=todo.WEAK.suite
Q= recovery.OUT/'todomvc/qwen9/a'
FLASH=SUITE.OUT/'deepseek-flash/build/todomvc'

def request_source(tag,task,arm):
    if tag=='qwen9' and arm=='self':return Q/'targets'/task/'plan/transmission-1/request.json'
    return SUITE.OUT/tag/'targets'/task/arm/'call/request.json'

def delivery(folder):
    states=Counter()
    for path in folder.glob('**/transmission-*/settled.json'):
        response=path.with_name('response.json');assert sha(response)==read(path)['response_sha256']
        r=read(response)['choices'][0];part='joint' if 'joint' in path.parts else 'slot'
        states[(part,r['finish_reason'],bool((r['message'].get('content') or '').strip()))]+=1
    return [{'step':s,'finish':f,'visible':v,'count':n} for (s,f,v),n in sorted(states.items())]

def register():
    f=OUT/'registration.json'
    files=[Path(__file__),HERE/'PROTOCOL.md',Path(todo.__file__),Path(recovery.__file__),Path(SUITE.__file__),
           Q/'seal.json',Q/'build/todomvc/library.json',FLASH/'status.json',FLASH/'package.json',todo.WEAK.GPT,
           prior.OUT/'complete.json',SUITE.SOURCE/'targets.json',Path(todo.WEAK.domain.__file__)]
    tasks=todo.WEAK.domain.tasks();history={}
    for t in TAGS:
        history[t]={}
        for task in tasks:
            for arm in ('direct','self'):files.append(request_source(t,task['id'],arm))
        for a in ('human','gpt5-library'):
            previous=[prior.OUT/t/task['id']/a/'plan' for task in tasks]
            history[t][a]=[item for d in previous for item in delivery(d)]
            for d in previous:files.extend(d.glob('**/transmission-*/settled.json'))
    sums={str(p.relative_to(ROOT)):sha(p) for p in files}
    if not f.exists():
        b=check_credits(CAP);assert b['sufficient']
        core.save(f,dict(utc=now(),deadline=prior.END.isoformat(),cap=CAP,balance=b,targets=[t['id'] for t in tasks],
                         models={t:todo.WEAK.MODELS[t] for t in TAGS},sources=sums,prior_delivery=history))
    assert read(f)['sources']==sums
    return read(f)

def render(tag,task,arm,ledger):
    key=task['id'];dest=OUT/tag/key/arm
    if arm in ('human','gpt5-library'):
        lib=read(todo.WEAK.GPT) if arm=='gpt5-library' else todo.WEAK.library.library()
        return todo.render(ledger,tag,arm,task,OUT,lib)
    old=read(request_source(tag,key,arm))['body']
    def store(label,code):
        if not isinstance(code,str) or not code.strip():raise ValueError('Missing controller source')
        f=dest/label/'files.json';core.save(f,{'candidate.js':code})
        return dict(status='valid',file=str(f.relative_to(ROOT)),files_sha256=sha(f))
    def compile_self(plan):
        if tag=='qwen9':
            controller=read(Q/'build/todomvc/library.json');defaults=recovery.todo.literal(controller['ast'])['first']
            schema=controller['options']
            if plan is None:plan={k:defaults[k] for k in schema}
            create=lambda v:recovery.todo.instance(controller['ast'],defaults|v)
        else:
            pkg=read(FLASH/'package.json');menu=read(FLASH/'status.json')['menu'];schema=menu['schema']['properties']
            if plan is None:plan=menu['first']
            def create(v):return '(function(){\nconst DNA_CONFIG = Object.freeze('+json.dumps(v,sort_keys=True)+');\n'+pkg['source']+'\n})();\n'
        if not isinstance(plan,dict) or set(plan)!=set(schema) or any(type(b) is not bool for b in plan.values()):raise ValueError('Invalid Boolean plan')
        return create(plan)
    values={'fixed-self':store('fixed',compile_self(None))} if arm=='self' else {}
    try:
        raw=todo.BASE.request(ledger,(arm,tag,'a'),dest/'call',old['messages'],'plan',old['max_tokens'])
        obj=SUITE.parse_json(raw) if arm=='direct' or tag=='deepseek-flash' else recovery.web.parse_json(raw)
        values[arm]=store('page',obj['source'] if arm=='direct' else compile_self(obj))
    except todo.slots.EVENTS.MISSING as e:values[arm]=dict(status='missing',reason=str(e))
    except todo.BASE.ERRORS as e:values[arm]=dict(status='invalid',reason=str(e)[:240])
    return values

def generate(reg):
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    tasks=todo.WEAK.domain.tasks()
    def template(project,tag,stage):
        if project in ('direct','self'):
            original=read(request_source(tag,'todo-01',project))['body']
            settings={k:v for k,v in original.items() if k not in ('messages','max_tokens')}
        else:settings=todo.slots.EVENTS.template('todomvc',tag,'plan')
        return settings|{'reasoning':{'enabled':False}}
    with patch.multiple(todo.BASE,OUT=OUT,END=prior.END,template=template), ThreadPoolExecutor(max_workers=4) as pool:
        for tag in TAGS:
            f=OUT/tag/'seal.json'
            if f.exists():continue
            rows={task['id']:{} for task in tasks}
            jobs={(t['id'],a):pool.submit(render,tag,t,a,ledger) for t in tasks for a in ('direct','human','gpt5-library','self')}
            for (key,_),job in jobs.items():rows[key].update(job.result())
            core.save(f,dict(registration=sha(OUT/'registration.json'),rows=rows,libraries={}))

def score(reg):
    with patch.multiple(todo.WEAK,OUT=OUT,MODELS=reg['models']):todo.WEAK.score()
    groups={}
    for t in TAGS:
        current=read(OUT/t/'result.json')
        new_delivery={a:[r for k in reg['targets'] for r in delivery(OUT/t/k/a/'plan')] for a in ('human','gpt5-library')}
        groups[reg['models'][t]]=dict(rows=current['rows'],seal=current['seal_sha256'],old_delivery=reg['prior_delivery'][t],new_delivery=new_delivery)
    costs={}
    for row in ledger_read.calls(OUT/'budget.sqlite3'):
        seg=row['purpose'].split('/');k=row['model']+' / '+seg[3]
        v=costs.setdefault(k,dict(calls=0,settled_micro_usd=0,exposure_micro_usd=0))
        v['calls']+=1;v['settled_micro_usd']+=row['actual'] or 0;v['exposure_micro_usd']+=row['reserved'] if row['actual'] is None else row['actual']
    core.save(HERE/'result.json',dict(registration=sha(OUT/'registration.json'),models=groups,cost=ledger_read.totals(OUT/'budget.sqlite3'),costs_by_model_and_arm=costs))

if __name__=='__main__':
    with browser.lock(OUT/'run.lock'):
        reg=register();generate(reg);score(reg)
