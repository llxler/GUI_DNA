"""Independently rate one hash-selected check per site on newly evaluated pages."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import hashlib
from pathlib import Path
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,now,read,sha
from ..functional_pilot.judge_controls import run as old
from ..component_contracts.typed_inputs import score_visibility as latest
from . import evaluate as flash

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/webgen-holdout-second-20261127'
RESULT=HERE/'secondary.json'
score=latest.scoring
API=score.first.api
ENGINE=score.first.evaluator
CAP=1.60


def schedule():
    import duckdb
    final=read(latest.run.CANDIDATES)
    pages={k:dict(final[k]) for k in ('development','holdout')}
    pages['holdout']['deepseek-flash']=read(flash.run.CANDIDATES)['rows']
    sites={s for group in pages.values() for by_site in group.values() for s in by_site}
    data=duckdb.sql('select id,ui_instruct from read_parquet(?)',params=[str(flash.run.gen.SRC)]).fetchall()
    checks={s:[{k:c[k] for k in ('task','expected_result')} for c in cs] for s,cs in data if s in sites}
    subset={s:min(range(len(cs)),key=lambda i:hashlib.sha256(f'webgen-rater-v1:{s}:{i}'.encode()).digest()) for s,cs in checks.items()}
    prior=read(old.HERE/'result.json')['subset']
    assert all(subset[s]==i for s,i in prior.items())
    jobs=[]
    for batch,models in pages.items():
        for t,by_site in models.items():
            arms=('direct','human','self') if batch=='holdout' else ('self',) if t in ('gemma','qwen9') else ()
            for site,records in by_site.items():
                for arm in arms:jobs.append((batch,t,site,subset[site],arm,records[arm]))
    jobs.sort(key=lambda item:hashlib.sha256(str(item[:5]).encode()).digest())
    assert len(jobs)==39
    return jobs,subset,checks


def evaluate():
    jobs,subset,checks=schedule()
    registration=OUT/'scheduled.json'
    paths=(Path(__file__),HERE/'SECOND_JUDGE.md',latest.run.CANDIDATES,flash.run.CANDIDATES,old.HERE/'result.json',Path(ENGINE.__file__))
    hashes={str(p.relative_to(ROOT)):sha(p) for p in paths}
    if not registration.exists():core.save(registration,dict(utc=now(),sources=hashes,subset=subset,ids=[list(j[:5]) for j in jobs]))
    assert read(registration)['sources']==hashes and read(registration)['subset']==subset
    score.wait_for(latest.RESULT)
    layers=(score.first.OUT,score.second.OUT,score.OUT,latest.previous.previous.OUT,latest.previous.OUT,flash.OUT,latest.OUT)
    spent=sum(Decimal(str(ledger_read.totals(d/'budget.sqlite3')['exposure_usd'])) for d in layers)
    cap=min(CAP,float(Decimal(str(score.first.CAP))-spent))
    reg=OUT/'registration.json'
    if not reg.exists():
        balance=check_credits(cap);assert cap>0 and balance['sufficient']
        core.save(reg,dict(utc=now(),cap=cap,balance=balance,schedule=sha(registration),sources=hashes,
                           primary=[sha(latest.RESULT),sha(flash.RESULT)],deadline=flash.run.comp.END.isoformat()))
    assert read(reg)['cap']==cap and read(reg)['schedule']==sha(registration)
    if RESULT.exists():return
    ledger=Ledger(OUT/'budget.sqlite3',cap,cap)
    def judge(html,sdk,task,dest):
        path=dest/'judgment.json'
        if path.exists():return read(path)
        return ENGINE.browser_job(lambda eng:ENGINE.journey(ledger,old.SECOND,html,sdk,task,dest,eng))
    control={}
    for name,action in [('working',"document.querySelector('output').innerText='Amber Ready'"),('inert','void(0)')]:
        html=f'<html><body><h1>Switch check</h1><button onclick="{action}">Activate</button><output>Standby</output></body></html>'
        control[name]=judge(html,False,ENGINE.TEST,OUT/'calibration'/name)
    qualified=control['working']['verdict']=='YES' and control['inert']['verdict']=='NO'
    if qualified:
        html="""<html><body><button onclick="document.querySelector('output').textContent='Amber Ready'">Activate</button><output>Standby</output><button>Enable lamp</button><p>Lamp dark</p></body></html>"""
        control['partial']=judge(html,False,dict(task='Activate the status and enable the lamp using both buttons.',
                      expected_result='Both independent outcomes occur: the status reads Amber Ready and the lamp reads Lamp green.'),OUT/'partial')
    primary={(r['batch'],r['model'],r['site'],r['check'],r['arm']):r for f in (latest.RESULT,flash.RESULT) for r in read(f)['rows']}
    def one(job):
        batch,t,site,index,arm,page=job
        p=primary[batch,t,site,index,arm]
        row=dict(batch=batch,model=t,site=site,check=index,arm=arm,primary=p['verdict'],primary_status=p['status'],
                 page_status=page['status'],page=page.get('sha256'))
        if page['status']!='valid' or not qualified:
            return row|dict(status=page['status'] if page['status']!='valid' else 'uncalibrated',verdict=None)
        path=ROOT/page['file'];assert sha(path)==page['sha256']
        dest=OUT/'second'/batch/t/site/arm
        res=judge(path.read_text(),arm=='human',checks[site][index],dest)
        return row|dict(status=res['status'],verdict=res['verdict'],receipt=sha(dest/'judgment.json'),reason=res.get('reason'))
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows=list(pool.map(one,jobs))
    core.save(RESULT,dict(registration=sha(reg),scheduled=sha(registration),subset=subset,model=old.SECOND,
                          calibration=control,qualified=qualified,rows=rows,cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__=='__main__':
    with browser.lock(OUT/'run.lock'),patch.multiple(API,OUT=OUT,END=flash.run.comp.END,PRICES=API.PRICES|{old.SECOND:(.90,1.20)}):
        evaluate()
