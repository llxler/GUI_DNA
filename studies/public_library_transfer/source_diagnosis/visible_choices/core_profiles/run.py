"""Enumerate public behavior first and deploy only a model-selected eligible profile."""
from concurrent.futures import ThreadPoolExecutor
from itertools import product
import json
from pathlib import Path
import re
import subprocess
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,now,read,sha
from .. import run as parent

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/todo-core-profiles-20261126pm'
CAP=.16
TAGS=parent.TAGS
todo=parent.todo

def resources(tag):
    if tag=='qwen9':
        lib=read(parent.Q/'build/todomvc/library.json')
        defaults=parent.recovery.todo.literal(lib['ast'])['first']
        opts={k:defaults[k] for k in lib['options']}
        return opts,lambda p:parent.recovery.todo.instance(lib['ast'],defaults|p)
    package=read(parent.FLASH/'package.json')
    opts=read(parent.FLASH/'status.json')['menu']['first']
    def compile_plan(plan):
        return '(function(){\nconst DNA_CONFIG = Object.freeze('+json.dumps(plan,sort_keys=True)+');\n'+package['source']+'\n})();\n'
    return opts,compile_plan

def register():
    f=OUT/'registration.json'
    files=[Path(__file__),HERE/'check.cjs',HERE/'PROTOCOL.md',Path(parent.__file__),parent.Q/'build/todomvc/library.json',
           parent.FLASH/'package.json',parent.FLASH/'status.json',parent.OUT/'registration.json',parent.SUITE.SOURCE/'targets.json']
    for t in TAGS:
        files.append(parent.OUT/t/'seal.json')
        files.extend((parent.OUT/t).glob('todo-*/self/call/transmission-*/settled.json'))
    sums={str(p.relative_to(ROOT)):sha(p) for p in files}
    if not f.exists():
        b=check_credits(CAP);assert b['sufficient']
        core.save(f,dict(utc=now(),cap=CAP,deadline=parent.prior.END.isoformat(),balance=b,sources=sums,models=read(parent.OUT/'registration.json')['models']))
    assert read(f)['sources']==sums
    return read(f)

def distance(a,b):return sum(v!=b[k] for k,v in a.items())

def generate():
    register();ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    tasks=todo.WEAK.domain.tasks()
    for t in TAGS:
        root=OUT/t;seal=root/'seal.json'
        if seal.exists():continue
        default,compile_plan=resources(t);keys=sorted(default)
        possibilities=sorted((dict(zip(keys,vals,strict=True)) for vals in product((False,True),repeat=len(keys))),
                             key=lambda p:(distance(p,default),[p[k] for k in keys]))
        def check(plan):
            proc=subprocess.run(['node',str(HERE/'check.cjs')],input=json.dumps({'source':compile_plan(plan)}),text=True,capture_output=True,check=True,timeout=8)
            return {'choices':plan,**json.loads(proc.stdout)}
        with ThreadPoolExecutor(max_workers=2) as pool:
            checks=list(pool.map(check,possibilities))
        options=[v['choices'] for v in checks if all(v['checks'].values()) and not v['error']]
        core.save(root/'profiles.json',dict(default=default,enumerated=checks,eligible=options))
        old=read(parent.OUT/t/'seal.json')
        def page(idx,folder):
            f=folder/'files.json';core.save(f,{'candidate.js':compile_plan(options[idx])})
            return dict(status='valid',file=str(f.relative_to(ROOT)),files_sha256=sha(f),choice=idx)
        def one(task):
            k=task['id'];base=old['rows'][k]
            rows={a:v for a,v in base.items() if a!='self'}
            rows['unfiltered']=base['self']
            if not options:
                rows.update({a:dict(status='build_failed') for a in ('self','fixed-core','projected')})
                return k,rows
            rows['fixed-core']=page(0,root/'fixed-core')
            raw=parent.OUT/t/k/'self/call'
            got=sorted(raw.glob('transmission-*/settled.json'))
            if base['self']['status']=='valid':
                choice=read(got[0].with_name('response.json'))['choices'][0]['message']['content']
                original=parent.SUITE.parse_json(choice) if t=='deepseek-flash' else parent.recovery.web.parse_json(choice)
                assert set(original)==set(keys)
                idx=min(range(len(options)),key=lambda i:distance(original,options[i]))
                rows['projected']=page(idx,root/k/'projected')
            else:rows['projected']=dict(status=base['self']['status'])
            try:
                active=[{'index':i,'enabled':[o for o,on in p.items() if on]} for i,p in enumerate(options)]
                msg=core.messages('Choose the public-core-valid profile for this requested task. Return only a decimal index.',
                                  dict(requirement=task['requirement'],profiles=active,always_required=['create trimmed todos','reject whitespace','persist and restore records']))
                text=todo.BASE.uncode(todo.BASE.request(ledger,('todomvc',t,'a'),root/k/'plan',msg,'plan',700)).strip()
                if not re.fullmatch('[0-9]+',text) or int(text)>=len(options):raise ValueError('Invalid profile number')
                rows['self']=page(int(text),root/k/'planned')
            except todo.slots.EVENTS.MISSING as e:rows['self']=dict(status='missing',reason=str(e))
            except ValueError as e:rows['self']=dict(status='invalid',reason=str(e))
            return k,rows
        def settings(p,tag,phase):return todo.slots.EVENTS.template('todomvc',tag,phase)|{'reasoning':{'enabled':False}}
        with patch.multiple(todo.BASE,OUT=OUT,END=parent.prior.END,template=settings),ThreadPoolExecutor(max_workers=3) as pool:rows=dict(pool.map(one,tasks))
        core.save(seal,dict(registration=sha(OUT/'registration.json'),prior=sha(parent.OUT/t/'seal.json'),profiles=sha(root/'profiles.json'),rows=rows,libraries={}))
        print('public core profiles',t,len(options),len(possibilities),flush=True)

def score(reg):
    with patch.multiple(todo.WEAK,OUT=OUT,MODELS=reg['models']):todo.WEAK.score()
    models={}
    for t in TAGS:
        d=read(OUT/t/'result.json');p=read(OUT/t/'profiles.json')
        models[reg['models'][t]]=dict(rows=d['rows'],profiles=p,seal=d['seal_sha256'])
    groups={}
    for r in ledger_read.calls(OUT/'budget.sqlite3'):
        g=groups.setdefault(r['model'],dict(calls=0,settled_micro_usd=0,exposure_micro_usd=0));g['calls']+=1
        g['settled_micro_usd']+=r['actual'] or 0;g['exposure_micro_usd']+=r['reserved'] if r['actual'] is None else r['actual']
    core.save(HERE/'result.json',dict(registration=sha(OUT/'registration.json'),models=models,cost=ledger_read.totals(OUT/'budget.sqlite3'),by_planner=groups))

if __name__=='__main__':
    with browser.lock(OUT/'run.lock'):
        reg=register();generate();score(reg)
