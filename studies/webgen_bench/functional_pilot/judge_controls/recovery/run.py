"""Complete the preselected independent rater cohort without rerating settled answers."""
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import time
from unittest.mock import patch

import httpx
from gui_dna.budget import Ledger, BudgetStop
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from ... import evaluate as ev, generate as gen, judge_api as api
from ...function_binding import run as final
from .. import run as controls

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/webgen-second-rater-recovery-20261126pm'
CAP=2.
LAST=0.
BACKOFF=0.
SECOND=controls.SECOND


def register():
    dest=OUT/'registration.json'
    files=[Path(__file__),HERE/'PROTOCOL.md',controls.HERE/'result.json',controls.native.HERE/'candidates.json',
           final.HERE/'judgments.json',Path(ev.__file__),Path(api.__file__)]
    hashes={str(f.relative_to(ROOT)):sha(f) for f in files}
    if not dest.exists():
        b=check_credits(CAP);assert b['sufficient']
        route=httpx.get('https://openrouter.ai/api/v1/models/'+SECOND+'/endpoints',timeout=25)
        route.raise_for_status()
        endpoints=[v for v in route.json()['data']['endpoints'] if v['provider_name']=='Parasail' and v.get('status')==0]
        assert len(endpoints)==1
        e=endpoints[0]
        assert e['context_length']<=128000 and Decimal(e['pricing']['prompt'])<=Decimal('.0000008') and Decimal(e['pricing']['completion'])<=Decimal('.000001')
        assert not any(Decimal(str(e['pricing'].get(k) or 0)) for k in ('request','image'))
        core.save(dest,dict(utc=now(),cap=CAP,deadline=gen.END.isoformat(),balance=b,endpoint=e,sources=hashes))
    assert read(dest)['sources']==hashes


def send(ledger,model,folder,messages):
    global LAST,BACKOFF
    assert model==SECOND
    body=dict(model=model,messages=api.image_message(messages),seed=42,max_tokens=1000,temperature=1,
              provider=dict(only=['Parasail'],allow_fallbacks=False,max_price=dict(prompt=.8,completion=1,request=0)))
    checksum=hashlib.sha256(json.dumps(body,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    for i in (1,2):
        dest=folder/str(i);req=dest/'request.json';done=dest/'settled.json'
        if req.exists():
            assert read(req)['body_sha256']==checksum
            if done.exists():
                response=dest/'response.json';assert sha(response)==read(done)['sha256']
                val=read(response)['choices'][0]['message'].get('content')
                if val:return val
            continue
        if datetime.now(timezone.utc)+timedelta(seconds=95)>=gen.END:raise api.Undelivered('Deadline')
        delay=max(0,LAST+4.5-time.monotonic(),BACKOFF-time.monotonic())
        if delay:time.sleep(delay)
        bound=Decimal('.1034')
        try:ticket=ledger.reserve(bound,'judge/second/'+str(dest.relative_to(OUT)),model)
        except BudgetStop as exc:raise api.Undelivered('Reservation declined') from exc
        core.save(req,dict(id=ticket,model=model,body_sha256=checksum,reserved_usd=float(bound),messages=messages))
        start=LAST=time.monotonic()
        try:
            result=httpx.post('https://openrouter.ai/api/v1/chat/completions',json=body,
                  headers={'Authorization':'Bearer '+os.environ['OPENROUTER_API_KEY']},timeout=httpx.Timeout(70,connect=15))
            result.raise_for_status();r=result.json();usage=r['usage']
            if usage.get('cost') is None:raise ValueError('Missing cost')
            core.save(dest/'response.json',r)
        except (httpx.HTTPError,KeyError,ValueError,TypeError) as exc:
            status=exc.response.status_code if isinstance(exc,httpx.HTTPStatusError) else None
            cause=f'HTTP {status}' if status else type(exc).__name__
            ledger.uncertain(ticket,cause);core.save(dest/'error.json',dict(reason=cause))
            if status==429:BACKOFF=time.monotonic()+45
            if status in (401,402,403,404):raise api.Undelivered(cause) from None
            continue
        ledger.settle(ticket,usage['cost'],time.monotonic()-start,r.get('id'),usage)
        core.save(done,dict(sha256=sha(dest/'response.json')))
        if msg:=r['choices'][0]['message'].get('content'):return msg
    raise api.Undelivered('No usable second-rater response after two transmissions')


def run():
    import duckdb
    while not (final.HERE/'judgments.json').exists() or not (controls.HERE/'result.json').exists():
        if datetime.now(timezone.utc)>=gen.END:raise RuntimeError('Primary or controls did not finish')
        time.sleep(6)
    register()
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    old=read(controls.HERE/'result.json')
    assert old['controls']['qualified']
    candidates=read(controls.native.HERE/'candidates.json')
    checks=dict(duckdb.sql('select id, ui_instruct from read_parquet(?)',params=[str(gen.SRC)]).fetchall())
    order=sorted(old['second'],key=lambda r:hashlib.sha256(json.dumps([r['model'],r['arm'],r['site']],separators=(',',':')).encode()).digest())
    rows=[]
    with patch.object(api,'send',send):
        for item in order:
            t,s,i,a=(item[k] for k in ('model','site','check','arm'))
            cand=candidates['rows'][t][s][a]
            if cand['status']!='valid' or item['status']=='judged':
                rows.append(item|{'reused':True});continue
            assert cand['sha256']==sha(ROOT/cand['file']) and old['subset'][s]==i
            dest=OUT/'checks'/s/str(i)/t/a
            task={k:checks[s][i][k] for k in ('task','expected_result')}
            verdict=ev.browser_job(lambda eng:ev.journey(ledger,SECOND,(ROOT/cand['file']).read_text(),a=='human',task,dest,eng))
            rows.append(item|dict(reused=False,status=verdict['status'],verdict=verdict['verdict'],receipt=sha(dest/'judgment.json')))
    core.save(HERE/'result.json',old|dict(second=rows,previous=sha(controls.HERE/'result.json'),
                                         registration=sha(OUT/'registration.json'),cost=ledger_read.totals(OUT/'budget.sqlite3')))

if __name__=='__main__':
    with browser.lock(OUT/'run.lock'):run()
