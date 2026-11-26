"""Complete previously undelivered Web-Bench requests without replacing any returned candidate."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
import os
from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.public_library_transfer.compact_todomvc import run as todo
from studies.study_io import ROOT,now,read,sha
from studies.webbench.compact_planning import run as compact
from studies.webbench.compact_planning.visible_decoding import run as visible
from studies.webbench.self_build_modules import run as base
from studies.webbench.self_build_modules.score import controls
from studies.webbench.typed_components import run as typed

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/web-transport-completion-20261125'
CAP=1
ARMS=('direct','human','gpt5-library')
PROJECTS=('table','svg-chart','form')


def register():
    path=OUT/'registration.json'
    if path.exists():
        reg=read(path)
        assert all(sha(ROOT/f)==h for f,h in reg['sources'].items())
        return reg
    completed={}
    for mod in (compact,visible,todo):
        report=read(mod.HERE/'result.json')
        totals=ledger_read.totals(mod.OUT/'budget.sqlite3')
        assert totals==report['cost']
        completed[mod.OUT.name]=totals['exposure_usd']
    maximum=sum(completed.values())+typed.CAP+.35+.40+CAP
    assert maximum<10
    balance=check_credits(CAP)
    assert balance['sufficient']
    files=[HERE/'PROTOCOL.md',Path(__file__),Path(base.__file__),Path(browser.__file__),Path(base.original.__file__)]
    jobs=[]
    for p in PROJECTS:
        for t in typed.ALL_TAGS:
            model,src,observations=controls(p,t)
            old=base.old_root(p,t)
            for arm in ARMS:
                for n,r in sorted(observations[arm].items()):
                    if r['status']!='missing': continue
                    dest=old/t/p/arm/str(n)/'call'
                    f=dest/'request.json'
                    assert f.exists() and not (dest/'response.json').exists()
                    body=read(f)['body']
                    original_prompt=old/'inputs'/p/arm/f'{n}.json'
                    assert body['messages']==read(original_prompt) and body['model']==model
                    files.extend([f,original_prompt,src,old/'inputs'/p/'public.json',old/'inputs'/p/'browser.json'])
                    if arm!='direct':files.append(old/'inputs'/p/(arm+'.json'))
                    jobs.append(dict(project=p,tag=t,task=n,arm=arm,request=str(f.relative_to(ROOT))))
    assert len(jobs)==42
    core.save(path,dict(utc=now(),deadline=compact.END.isoformat(),cap=CAP,balance=balance,closed_exposure=completed,
                        combined_bound=maximum,jobs=jobs,sources={str(f.relative_to(ROOT)):sha(f) for f in files}))
    return read(path)


def one(job,ledger):
    p,t,a,n=(job[k] for k in ('project','tag','arm','task'))
    root=OUT/p/t/a/str(n)
    result=root/'result.json'
    if result.exists():return read(result)
    old=base.old_root(p,t)/'inputs'/p
    body=read(ROOT/job['request'])['body']
    # Original settings are identical across targets and arms for each registered project and model.
    assert {**base.template(p,t,'plan'),'messages':body['messages'],'max_tokens':body['max_tokens']}==body
    try:
        raw=base.request(ledger,(p,t,'a'),root/'call',body['messages'],'plan',body['max_tokens'])
        value=base.parse_json(raw)
        if a=='direct':
            if set(value)!={'files'} or not isinstance(value['files'],dict):raise ValueError('Expected one files object')
            extra=core.files_map([dict(path=k,content=v) for k,v in value['files'].items()])
        else:
            compiler=base.original.table_compile if p=='table' else base.original.chart_compile
            extra=compiler(read(old/(a+'.json')),value)
        page=root/'page'
        files=core.emit(p,base.original.validate_files(read(old/'public.json')['starter']|extra),page)
        state=dict(status='valid',page=str(page.relative_to(ROOT)),files=files)
    except typed.MISSING as exc:state=dict(status='missing',reason=str(exc))
    except base.ERRORS as exc:state=dict(status='invalid',reason=str(exc)[:350])
    record=dict(**job,**state)
    core.save(result,record)
    return record


def main(action):
    reg=register()
    seal=OUT/'seal.json'
    if action=='generate':
        if seal.exists():return
        ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
        with patch.multiple(base,OUT=OUT,END=compact.END),ThreadPoolExecutor(max_workers=4) as pool:
            rows=list(pool.map(lambda j:one(j,ledger),reg['jobs']))
        core.save(seal,dict(registration=sha(OUT/'registration.json'),rows=rows))
    if action=='score':
        assert read(seal)['registration']==sha(OUT/'registration.json')
        for k in tuple(os.environ):
            if k.endswith(('_API_KEY','_AUTH_TOKEN','_ACCESS_TOKEN')):os.environ.pop(k)
        browser.OUT=OUT
        protocols={p:browser.verify_contract(p) for p in PROJECTS}
        scored=browser.evaluate(read(seal)['rows'],OUT,protocols,3)
        rows=[{k:v for k,v in r.items() if k in ('project','tag','task','arm','request','status','passed','reason','report_sha256')} for r in scored]
        for r in rows:
            if r['status']=='invalid':r['passed']=False
        core.save(HERE/'result.json',dict(registration=sha(OUT/'registration.json'),seal_sha256=sha(seal),
                  cost=ledger_read.totals(OUT/'budget.sqlite3'),rows=rows))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('register','generate','score'))
    main(parser.parse_args().action)
