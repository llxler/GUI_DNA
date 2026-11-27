"""Pace the original preselected 72B second judgments, preserving all earlier verdicts."""
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
import time
from unittest.mock import patch

import httpx
from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,now,read,sha
from ..functional_pilot.judge_controls.recovery import run as transport
from . import second_judge as original

HERE=original.HERE
OUT=ROOT/'artifacts/webgen-paced-second-20261127'
RESULT=HERE/'secondary-completion.json'
END=original.flash.run.comp.END
API=original.API


def finish():
    source=read(original.RESULT);assert source['qualified']
    jobs,subset,checks=original.schedule()
    old={(r['batch'],r['model'],r['site'],r['check'],r['arm']):r for r in source['rows']}
    destinations=[list(j[:5]) for j in jobs if j[5]['status']=='valid' and old[j[:5]]['status']!='judged']
    sc=original.score
    layers=(sc.first.OUT,sc.second.OUT,sc.OUT,original.latest.previous.previous.OUT,original.latest.previous.OUT,
            original.flash.OUT,original.latest.OUT,original.OUT)
    spent=sum(Decimal(str(ledger_read.totals(p/'budget.sqlite3')['exposure_usd'])) for p in layers)
    cap=float(Decimal(str(sc.first.CAP))-spent)
    reg=OUT/'registration.json'
    sources=[Path(__file__),HERE/'RATER_RECOVERY.md',original.RESULT,Path(transport.__file__),original.latest.run.CANDIDATES,original.flash.run.CANDIDATES]
    hashes={str(p.relative_to(ROOT)):sha(p) for p in sources}
    if not reg.exists():
        balance=check_credits(cap);assert cap>0 and balance['sufficient']
        response=httpx.get('https://openrouter.ai/api/v1/models/'+source['model']+'/endpoints',timeout=25)
        response.raise_for_status()
        endpoints=[e for e in response.json()['data']['endpoints'] if e['provider_name']=='Parasail' and e.get('status')==0]
        route=next((e for e in endpoints if e['context_length']<=128000 and Decimal(e['pricing']['prompt'])<=Decimal('.0000008')
                    and Decimal(e['pricing']['completion'])<=Decimal('.000001') and
                    not any(Decimal(str(e['pricing'].get(k) or 0)) for k in ('request','image'))),None)
        core.save(reg,dict(utc=now(),deadline=END.isoformat(),balance=balance,cap=cap,sources=hashes,endpoint=route,cases=destinations))
    rec=read(reg)
    assert rec['sources']==hashes and rec['cap']==cap and rec['cases']==destinations
    if RESULT.exists():return
    ledger=Ledger(OUT/'budget.sqlite3',cap,cap)
    def paced(*args):
        time.sleep(max(0,transport.LAST+10-time.monotonic()))
        return transport.send(*args)
    def judge(html,sdk,task,dest):
        f=dest/'judgment.json'
        if f.exists():return read(f)
        return original.ENGINE.browser_job(lambda eng:original.ENGINE.journey(ledger,source['model'],html,sdk,task,dest,eng))
    calibrations={}
    with patch.multiple(transport,OUT=OUT),patch.object(transport.gen,'END',END),patch.object(API,'send',paced):
        if rec['endpoint']:
            for name,action in [('working',"document.querySelector('output').innerText='Amber Ready'"),('inert','void(0)')]:
                html=f'<html><body><h1>Switch check</h1><button onclick="{action}">Activate</button><output>Standby</output></body></html>'
                calibrations[name]=judge(html,False,original.ENGINE.TEST,OUT/'calibration'/name)
        allowed=(calibrations.get('working',{}).get('verdict')=='YES' and calibrations.get('inert',{}).get('verdict')=='NO')
        rows=[]
        for batch,t,site,index,arm,page in jobs:
            row=old[batch,t,site,index,arm]
            if row['status']=='judged' or page['status']!='valid' or not allowed:
                rows.append(row|{'reused':True});continue
            dest=OUT/'checks'/batch/t/site/arm
            path=ROOT/page['file'];assert page['sha256']==row['page']==sha(path)
            answer=judge(path.read_text(),arm=='human',checks[site][index],dest)
            rows.append(row|dict(status=answer['status'],verdict=answer['verdict'],receipt=sha(dest/'judgment.json'),
                                 reason=answer.get('reason'),reused=False))
    core.save(RESULT,source|dict(previous=sha(original.RESULT),registration=sha(reg),rows=rows,
                                 endpoint_qualified=allowed,endpoint_controls=calibrations,cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__=='__main__':
    with browser.lock(OUT/'run.lock'):finish()
