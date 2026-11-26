"""Complete only still-undelivered Llama requests after a provider cooldown."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import threading
import time
from unittest.mock import patch
from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import core
from studies.study_io import ROOT,now,read,sha
from studies.webbench.typed_components import run as typed
from studies.webbench.self_build_modules import run as base
from studies.webbench.transport_completion import run as restore
from . import run as events

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/todo-delivery-20261125'
CAP=.65
TAG='llama3'
MODEL=events.weak.SMALL[TAG]
LOCK=threading.Lock()
RESULT=HERE/'delivery-result.json'


def register():
    path=OUT/'registration.json'
    if path.exists():
        r=read(path)
        assert all(sha(ROOT/f)==h for f,h in r['sources'].items())
        return r
    old=events.weak.OUT/TAG/'result.json'
    interim=events.OUT/TAG/'result.json'
    files=[Path(__file__),HERE/'delivery.md',Path(events.__file__),old,interim]
    jobs=[]
    for r in read(old)['rows']:
        if r['arm'] not in ('direct','human','gpt5-library') or r['passed'] is not None:continue
        got=next(i for i in read(interim)['rows'] if (i['arm'],i['task'])==(r['arm'],r['task']))
        if got['passed'] is not None:continue
        path0=events.weak.OUT/TAG/r['task']/r['arm']/'call/transmission-1/request.json'
        files.append(path0)
        jobs.append(dict(task=r['task'],arm=r['arm'],request=str(path0.relative_to(ROOT))))
    balance=check_credits(CAP)
    bound=restore.register()['combined_bound']+1+1.25+CAP
    assert balance['sufficient'] and bound<=10 and len(jobs)==2
    last=max(f.stat().st_mtime for f in (events.OUT/TAG).rglob('error.json'))
    core.save(path,dict(utc=now(),cap=CAP,combined_bound=bound,balance=balance,
        deadline=events.weak.compact.END.isoformat(),earliest_utc=datetime.fromtimestamp(last+900,timezone.utc).isoformat(),
        jobs=jobs,sources={str(f.relative_to(ROOT)):sha(f) for f in files}))
    return read(path)


def generate(reg):
    root=OUT/TAG
    seal=root/'seal.json'
    if seal.exists():return
    start=datetime.fromisoformat(reg['earliest_utc']).timestamp()
    while time.time()<start:time.sleep(min(3,start-time.time()))
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    previous_root=events.OUT/TAG
    original_request=base.request
    send=base.httpx.post
    def post(*args,**kwargs):
        response=send(*args,**kwargs)
        if response.status_code==429:
            core.save(OUT/'closed-llama3.json',dict(reason='HTTP 429',retry_after=response.headers.get('retry-after'),utc=now()))
        return response
    def request(ledger,case,folder,messages,stage,limit):
        rel=folder.relative_to(root)
        for f in sorted((previous_root/rel).glob('transmission-*/settled.json')):
            resp=f.with_name('response.json')
            prior=read(f.with_name('request.json'))['body']
            if prior['messages']==messages and prior['max_tokens']==limit and prior['model']==MODEL and sha(resp)==read(f)['response_sha256']:
                answer=read(resp)['choices'][0]
                if answer['finish_reason']!='error':return answer['message']['content'] or ''
        with LOCK:
            if (OUT/'closed-llama3.json').exists():raise base.original.Unavailable('closed route')
            time.sleep(3)
            return original_request(ledger,case,folder,messages,stage,limit)
    rows={}
    weak=events.weak
    libs={}
    with patch.multiple(base,OUT=OUT,END=weak.compact.END,template=events.template,request=request),patch.object(base.httpx,'post',post):
        for j in reg['jobs']:
            task,arm=j['task'],j['arm']
            try:
                msg=read(ROOT/j['request'])['body']['messages']
                value=base.parse_json(request(ledger,('todomvc',TAG,'a'),root/'fill'/task/arm,msg,'plan',8192))
                t=next(x for x in weak.domain.tasks() if x['id']==task)
                if arm=='direct':
                    code=value['source']
                    if not isinstance(code,str) or not code.strip():raise ValueError('Missing code')
                elif arm=='human':code=weak.domain.compile_plan(value,t['features'],weak.library.library())
                else:
                    lib=read(weak.GPT)
                    code=weak.generic.compile_plan(value,t['features'],lib,weak.tables_of(lib))
                path=root/'fill'/task/arm/'files.json'
                core.save(path,{'candidate.js':code})
                row=dict(status='valid',file=str(path.relative_to(ROOT)),files_sha256=sha(path))
            except events.MISSING as exc:row=dict(status='missing',reason=str(exc))
            except base.ERRORS as exc:row=dict(status='invalid',reason=str(exc)[:240])
            rows.setdefault(task,{})[arm]=row
        if not (OUT/'closed-llama3.json').exists():
            # Delegate the exact registered event-function generation; controls above are the only ones still absent.
            # Use an alternate tag alias with the same template and model to avoid replaying old control requests.
            alias='llama-recovery'
            def settings(project,tag,stage):return events.template(project,TAG,stage)
            def delegated(ledger,case,folder,messages,stage,limit):
                return request(ledger,('todomvc',TAG,case[2]),root/folder.relative_to(OUT/alias),messages,stage,limit)
            with patch.object(events,'OUT',OUT),patch.object(base,'template',settings),patch.object(base,'request',delegated):
                events.generate(alias)
            extra=read(OUT/alias/'seal.json')
            libs=extra['libraries']
            for task,arms in extra['rows'].items():rows.setdefault(task,{}).update(arms)
        else:libs={rep:dict(status='missing') for rep in ('a','b')}
    core.save(seal,dict(registration=sha(OUT/'registration.json'),rows=rows,libraries=libs))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('register','generate','score','publish'))
    args=parser.parse_args()
    reg=register()
    if args.action=='generate':generate(reg)
    elif args.action=='score':
        with patch.multiple(events.weak,OUT=OUT,MODELS={TAG:MODEL}):events.weak.score()
    elif args.action=='publish':
        core.save(RESULT,dict(registration_sha256=sha(OUT/'registration.json'),model=MODEL,results=read(OUT/TAG/'result.json'),cost=ledger_read.totals(OUT/'budget.sqlite3'),route=read(OUT/'closed-llama3.json') if (OUT/'closed-llama3.json').exists() else None))
