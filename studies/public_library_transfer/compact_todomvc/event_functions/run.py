"""Build and verify model-written small TodoMVC event functions."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import os
import re
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.public_library_transfer.compact_todomvc import run as weak
from studies.public_library_transfer.self_refinement.todomvc.event_modules import modules
from studies.public_library_transfer.self_refinement.todomvc.event_modules.feedback import run as feedback
from studies.study_io import ROOT,now,read,sha
from studies.webbench.self_build_modules import run as base

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/small-events-20261125'
CAP=.40
TAGS=tuple(weak.SMALL)+('gemma',)
MISSING=weak.recovery.TRANSPORT


def register():
    path=OUT/'registration.json'
    if path.exists():
        r=read(path)
        assert all(sha(ROOT/f)==h for f,h in r['sources'].items())
        return r
    files=[Path(__file__),HERE/'PROTOCOL.md',Path(modules.__file__),modules.HERE/'function.cjs',
           Path(feedback.__file__),feedback.HERE/'probes.cjs',weak.OUT/'registration.json',
           weak.suite.SOURCE/'targets.json',weak.suite.SOURCE/'build-inputs.json',weak.OUT/'llama3/seal.json']
    balance=check_credits(CAP)
    assert balance['sufficient']
    core.save(path,dict(utc=now(),deadline=weak.compact.END.isoformat(),balance=balance,cap=CAP,
        models={t:weak.MODELS[t] for t in TAGS},sources={str(f.relative_to(ROOT)):sha(f) for f in files}))
    return read(path)


def template(project,tag,stage):
    if tag not in weak.SMALL:return weak.recovery.template(project,tag,stage)
    original=read(weak.OUT/tag/'a/build/first/transmission-1/request.json')['body']
    return {k:v for k,v in original.items() if k not in ('messages','max_tokens')}


def create_library(ledger,tag,rep,pub):
    folder=OUT/tag/rep
    if (folder/'library.json').exists():return read(folder/'library.json')
    config=dict.fromkeys(modules.OPTIONS,True)
    features=list(pub['spec'])
    def source(name,phase,messages):
        dest=folder/'calls'/name/phase
        try:
            raw=base.request(ledger,('todomvc',tag,rep),dest,messages,'build',1700)
            return 'returned',modules.extract(name,raw)
        except MISSING:return 'missing',None
    def initial(name):
        return name,source(name,'first',modules.messages(name,pub))
    with ThreadPoolExecutor(max_workers=2) as pool:states=dict(pool.map(initial,modules.CONTRACTS))
    funcs={k:v[1] for k,v in states.items()}
    def probe(fs,conf):return feedback.evaluate_public(modules.assemble(fs,conf),features)
    initial_checks=probe(funcs,config)
    checks=initial_checks
    decisions={}
    for name in modules.CONTRACTS:
        failing={k:v for k,v in initial_checks.items() if not v['passed'] and name in v['owners']}
        if funcs[name] and not failing:continue
        messages=modules.messages(name,pub)+[dict(role='user',content=json.dumps(dict(source=funcs[name],
            observations=feedback.diagnostic(failing),instruction='Return the full corrected function, preserving name and arity.')))]
        status,fn=source(name,'repair',messages)
        if fn:
            trial={**funcs,name:fn}
            after=probe(trial,config)
            outcome=feedback.classify(checks,after,True)
            if not funcs[name] and feedback.passes(checks)<=feedback.passes(after):outcome='accepted'
            if outcome=='accepted':funcs,checks=trial,after
        else:outcome=status
        decisions[name]=outcome
    menu={}
    for key in config:
        alternate=probe(funcs,{**config,key:False})
        lost=sorted(feedback.passes(checks)-feedback.passes(alternate))
        if lost:menu[key]=lost
    status='valid' if all(funcs.values()) and menu and feedback.passes(checks) else (
        'missing' if any(v[0]=='missing' and not funcs[k] for k,v in states.items()) else 'build_failed')
    lib=dict(status=status,functions=funcs,options=menu,repairs=decisions,public_passes=sorted(feedback.passes(checks)),
             checks=checks,initial_checks=initial_checks)
    core.save(folder/'library.json',lib)
    return lib


def generate(tag):
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    targets,briefs=weak.suite.inputs()
    folder=OUT/tag
    if (folder/'seal.json').exists():return
    rows={}
    libs={}
    with patch.multiple(base,OUT=OUT,END=weak.compact.END,template=template):
        if tag=='llama3':
            original=read(weak.OUT/tag/'seal.json')
            for task,arms in original['rows'].items():
                for arm,v in arms.items():
                    if arm not in ('direct','human','gpt5-library') or v['status']!='missing':continue
                    old=weak.OUT/tag/task/arm/'call/transmission-1/request.json'
                    msg=read(old)['body']['messages']
                    try:
                        text=base.request(ledger,('todomvc',tag,'a'),folder/'restore'/task/arm,msg,'plan',8192)
                        value=base.parse_json(text)
                        t=next(x for x in weak.domain.tasks() if x['id']==task)
                        if arm=='direct':
                            code=value['source']
                            if not isinstance(code,str) or not code.strip():raise ValueError('Empty code')
                        elif arm=='human':code=weak.domain.compile_plan(value,t['features'],weak.library.library())
                        else:
                            lib=read(weak.GPT)
                            code=weak.generic.compile_plan(value,t['features'],lib,weak.tables_of(lib))
                        path=folder/'restore'/task/arm/'files.json'
                        core.save(path,{'candidate.js':code})
                        row=dict(status='valid',file=str(path.relative_to(ROOT)),files_sha256=sha(path))
                    except MISSING as exc:row=dict(status='missing',reason=str(exc))
                    except base.ERRORS as exc:row=dict(status='invalid',reason=str(exc)[:300])
                    rows.setdefault(task,{})[arm]=row
        for rep in ('a','b'):
            lib=create_library(ledger,tag,rep,briefs['todomvc'])
            libs[rep]=lib['status']
            for n in weak.recovery.todo.TASKS:
                dest=folder/rep/n
                def store(name,settings):
                    path=dest/name/'files.json'
                    code=modules.assemble(lib['functions'],settings)
                    core.save(path,{'candidate.js':code})
                    return dict(status='valid',file=str(path.relative_to(ROOT)),files_sha256=sha(path))
                arms=rows.setdefault(n,{})
                if lib['status']!='valid':
                    arms[rep]=arms['fixed-'+rep]=dict(status=lib['status'])
                    continue
                config=dict.fromkeys(modules.OPTIONS,True)
                arms['fixed-'+rep]=store('fixed',config)
                keys=list(lib['options'])
                msg=core.messages('Choose which optional event families to enable. Return only a JSON array of exact enabled option names, including [] or all as needed.',
                                  dict(requirement=targets[n]['public'],options=keys))
                try:
                    raw=base.request(ledger,('todomvc',tag,rep),dest/'call',msg,'plan',2000)
                    found=re.fullmatch(r'\s*(?:```(?:json)?\s*)?(\[[^\[\]]*\])\s*(?:```)?\s*',raw,re.S|re.I)
                    selected=json.loads(found[1]) if found else None
                    if not isinstance(selected,list) or not all(isinstance(s,str) and s in keys for s in selected): raise ValueError('Invalid enabled list')
                    arms[rep]=store('planned',{**config,**{k:k in selected for k in keys}})
                except MISSING as exc:arms[rep]=dict(status='missing',reason=str(exc))
                except base.ERRORS as exc:arms[rep]=dict(status='invalid',reason=str(exc)[:300])
    core.save(folder/'seal.json',dict(rows=rows,libraries={k:dict(status=v) for k,v in libs.items()},registration=sha(OUT/'registration.json')))
    print(tag,libs,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('register','generate','score','publish'))
    args=parser.parse_args()
    reg=register()
    if args.action=='generate':
        with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(generate,TAGS))
    elif args.action=='score':
        with patch.multiple(weak,OUT=OUT,MODELS=reg['models']):weak.score()
    elif args.action=='publish':
        core.save(HERE/'result.json',dict(registration=sha(OUT/'registration.json'),cost=ledger_read.totals(OUT/'budget.sqlite3'),
            models={weak.MODELS[t]:read(OUT/t/'result.json') for t in TAGS}))
