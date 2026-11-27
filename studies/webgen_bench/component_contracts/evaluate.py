"""Grade sealed sites under the original alternate judge, keeping the two cohorts separate."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import time
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from studies.webgen_bench.functional_pilot import evaluate as evaluator, judge_api as api
from . import run

OUT=ROOT/'artifacts/webgen-contract-judge-20261127'
CAP=5.75
OLD=run.previous.HERE/'judgments.json'


def calibrate(ledger,model):
    results={}
    for name,action in [('working',"document.querySelector('output').innerText='Amber Ready'"),('inert','void(0)')]:
        html=f'<html><body><h1>Switch check</h1><button onclick="{action}">Activate</button><output>Standby</output></body></html>'
        dest=OUT/'calibration'/model.split('/')[-1]/name
        results[name]=evaluator.browser_job(lambda eng:evaluator.journey(ledger,model,html,False,evaluator.TEST,dest,eng))
    return dict(model=model,results=results,qualified=results['working']['verdict']=='YES' and results['inert']['verdict']=='NO')


def register():
    dest=OUT/'registration.json'
    sources=[Path(__file__),run.HERE/'PROTOCOL.md',Path(evaluator.__file__),Path(api.__file__),run.OLD,OLD,run.gen.SRC]
    hashes={str(p.relative_to(ROOT)):sha(p) for p in sources}
    if not dest.exists():
        bal=check_credits(CAP);assert bal['sufficient']
        core.save(dest,dict(utc=now(),deadline=run.END.isoformat(),cap=CAP,balance=bal,sources=hashes))
    assert read(dest)['sources']==hashes
    return dest


def score():
    import duckdb
    reg=register()
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    previous=read(OLD)
    model=previous['route']['model']
    assert model==api.ALTERNATE and previous['calibration']['qualified']
    route=OUT/'route.json'
    if not route.exists():
        try:
            api.send(ledger,api.EXACT,OUT/'official-route',[dict(role='user',content='Reply OK')])
            exact=calibrate(ledger,api.EXACT)
        except api.Undelivered as exc:
            exact=dict(model=api.EXACT,reason=str(exc),qualified=False)
        core.save(route,dict(official=exact,primary=calibrate(ledger,model)))
    cal=read(route)
    while not (run.HERE/'candidates.json').exists():
        if datetime.now(timezone.utc)>=run.END:raise RuntimeError('Candidate seal unavailable at deadline')
        time.sleep(3)
    candidates=read(run.HERE/'candidates.json');seal=read(run.OUT/'seal.json')
    assert candidates['seal']==sha(run.OUT/'seal.json')
    for t,h in seal['libraries'].items():assert sha(run.OUT/'build'/t/'library.json')==h
    assert all(candidates[batch]==seal[batch] for batch in ('development','holdout'))
    oldpages=read(run.OLD)['rows']
    receipts={(r['model'],r['site'],r['check'],r['arm']):r for r in previous['rows']}
    data=duckdb.sql('select id,ui_instruct from read_parquet(?)',params=[str(run.gen.SRC)]).fetchall()
    def one(job):
        batch,tag,site,index,arm,check=job
        row=candidates[batch][tag][site][arm]
        old=oldpages.get(tag,{}).get(site,{}).get(arm)
        if batch=='development' and old is not None and (row==old or row.get('sha256') and row.get('sha256')==old.get('sha256')):
            return receipts[tag,site,index,arm]|{'batch':batch,'reused':True}
        dest=OUT/'checks'/batch/tag/site/str(index)/arm
        reason=source=verdict=None
        if row['status']=='valid' and cal['primary']['qualified']:
            file=ROOT/row['file'];assert sha(file)==row['sha256']
            if not (dest/'judgment.json').exists():
                v=evaluator.browser_job(lambda eng:evaluator.journey(ledger,model,file.read_text(),arm=='human',check,dest,eng))
            else:v=read(dest/'judgment.json')
            status,verdict,reason,source=v['status'],v['verdict'],v.get('reason'),sha(dest/'judgment.json')
        elif row['status']=='invalid':status='start_failed'
        elif row['status']=='valid':status='missing';reason='Calibration failed'
        else:status=row['status']
        return dict(batch=batch,model=tag,site=site,check=index,arm=arm,status=status,verdict=verdict,reason=reason,source=source,reused=False)
    jobs=[]
    for batch in ('development','holdout'):
        for tag,sites in candidates[batch].items():
            for site,checks in data:
                if site in sites:
                    for i,c in enumerate(checks):
                        for arm in sites[site]:jobs.append((batch,tag,site,i,arm,{k:c[k] for k in ('task','expected_result')}))
    jobs.sort(key=lambda x:hashlib.sha256('/'.join(map(str,x[:5])).encode()).digest())
    with ThreadPoolExecutor(max_workers=5) as pool:
        rows=list(pool.map(one,jobs))
    core.save(run.HERE/'judgments.json',dict(registration=sha(reg),candidates=sha(run.HERE/'candidates.json'),
              original_judgments=sha(OLD),route=cal,rows=rows,cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__=='__main__':
    with browser.lock(OUT/'evaluation.lock'),patch.multiple(api,OUT=OUT,END=run.END):
        score()
