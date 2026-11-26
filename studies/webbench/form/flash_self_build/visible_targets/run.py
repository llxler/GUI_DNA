"""Replay the five questionnaire deployment arms, changing just the reasoning switch."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,read,sha,now
from studies.webbench.compact_planning import run as compact
from studies.webbench.table.event_modules import source_recovery
from studies.webbench.typed_components import run as typed
from ..transport_completion import run as transport

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/flash-visible-targets-20261125'
CAP=1.30
RESULT=HERE/'result.json'
ARMS=('direct','human','gpt5-library','file-a','file-b')
TAG='deepseek-flash'
OLD=compact.base.old_root('form',TAG)
PREP=transport.previous.OUT
PREVIOUS=HERE.parent/'transport_completion/result.json'


def register():
    path=OUT/'registration.json'
    if path.exists():
        reg=read(path)
        assert all(sha(ROOT/p)==h for p,h in reg['sources'].items())
        return reg
    bound=source_recovery.register()['combined_bound']+CAP
    balance=check_credits(CAP)
    assert bound<10 and balance['sufficient']
    files=[Path(__file__),HERE/'PROTOCOL.md',PREVIOUS,OLD/'inputs/form/browser.json',OLD/'inputs/form/public.json',
           Path(compact.base.original.__file__),Path(compact.base.__file__),source_recovery.OUT/'registration.json']
    jobs=[]
    for arm in ARMS:
        is_self=arm.startswith('file-')
        pkg=PREP/arm/'form/build/package.json' if is_self else OLD/'inputs/form'/(arm+'.json')
        if arm!='direct':files.append(pkg)
        for n in range(1,21):
            orig=(PREP/arm/'form/self' if is_self else OLD/TAG/'form'/arm)/str(n)/'call/request.json'
            body=read(orig)['body']
            assert body['model']==compact.base.template('form',TAG,'plan')['model'] and 'reasoning' not in body and body['max_tokens']==8192
            files.append(orig)
            jobs.append(dict(task=n,arm=arm,request=str(orig.relative_to(ROOT)),package=None if arm=='direct' else str(pkg.relative_to(ROOT))))
    core.save(path,dict(utc=now(),deadline=compact.END.isoformat(),balance=balance,cap=CAP,combined_bound=bound,
                         jobs=jobs,sources={str(p.relative_to(ROOT)):sha(p) for p in files}))
    return read(path)


def produce(job,ledger):
    n,arm=job['task'],job['arm']
    folder=OUT/arm/str(n)
    dest=folder/'result.json'
    if dest.exists():return read(dest)
    body=read(ROOT/job['request'])['body']
    template=compact.base.template('form',TAG,'plan')
    assert dict(template, messages=body['messages'],max_tokens=8192)==dict(body,reasoning={'enabled':False})
    try:
        raw=compact.base.request(ledger,('form',TAG,'a'),folder/'call',body['messages'],'plan',8192)
        plan=compact.base.original.parse_json(raw)
        page=folder/'page'
        if arm.startswith('file-'):
            core.materialize('form',read(ROOT/job['package']),plan,page)
        else:
            if arm=='direct':
                if set(plan)!={'files'} or not isinstance(plan['files'],dict):raise ValueError('Expected one files object')
                part=core.files_map([dict(path=k,content=v) for k,v in plan['files'].items()])
            else:part=compact.base.original.chart_compile(read(ROOT/job['package']),plan)
            starter=read(OLD/'inputs/form/public.json')['starter']
            core.emit('form',compact.base.original.validate_files(starter|part),page)
        row=dict(status='valid',page=str(page.relative_to(ROOT)),files=browser.tree(page))
    except typed.MISSING as exc:row=dict(status='missing',reason=str(exc))
    except compact.base.ERRORS as exc:row=dict(status='invalid',reason=str(exc)[:300])
    val=dict(project='form',**job,**row)
    core.save(dest,val)
    return val


def main(action):
    reg=register()
    if action=='generate':
        if (OUT/'seal.json').exists():return
        ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
        orig=compact.base.template
        def settings(p,t,s):return dict(orig(p,t,s),reasoning={'enabled':False})
        with patch.multiple(compact.base,OUT=OUT,END=compact.END,template=settings),ThreadPoolExecutor(max_workers=6) as pool:
            rows=list(pool.map(lambda j:produce(j,ledger),reg['jobs']))
        core.save(OUT/'seal.json',dict(registration=sha(OUT/'registration.json'),rows=rows))
    if action=='score':
        for k in tuple(os.environ):
            if k.endswith(('_API_KEY','_AUTH_TOKEN','_ACCESS_TOKEN')):os.environ.pop(k)
        browser.OUT=OUT
        seal=read(OUT/'seal.json')
        assert seal['registration']==sha(OUT/'registration.json')
        protocol=browser.verify_contract('form')
        assert protocol==read(OLD/'inputs/form/browser.json')
        scored=browser.evaluate(seal['rows'],OUT,{'form':protocol},3)
        rows=[{k:v for k,v in r.items() if k in ('task','arm','status','passed','report_sha256','reason')} for r in scored]
        for r in rows:
            if r['status']=='invalid':r['passed']=False
        core.save(RESULT,dict(registration=seal['registration'],seal_sha256=sha(OUT/'seal.json'),previous=sha(PREVIOUS),
                             rows=rows,cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('register','generate','score'))
    main(parser.parse_args().action)
