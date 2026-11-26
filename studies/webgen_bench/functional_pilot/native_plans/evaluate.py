"""Grade the second sealed deployment; reuse byte-identical pages and the calibrated rater."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from decimal import Decimal
import hashlib
from pathlib import Path
import sys
import time

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,now,read,sha
from .. import evaluate as first, generate as gen, judge_api as api
from . import run

OUT=ROOT/'artifacts/webgen-native-judge-20261126pm'
HERE=run.HERE
def register():
    f=OUT/'registration.json'
    files=[Path(__file__),HERE/'PROTOCOL.md',HERE/'candidates.json',gen.HERE/'candidates.json',gen.HERE/'judgments.json',Path(first.__file__),Path(api.__file__),first.OUT/'calibration.json']
    sums={str(p.relative_to(ROOT)):sha(p) for p in files}
    used=ledger_read.totals(first.OUT/'budget.sqlite3')
    assert used==read(gen.HERE/'judgments.json')['cost']
    remaining=float(Decimal(str(api.CAP))-Decimal(str(used['exposure_usd'])))
    if not f.exists():
        b=check_credits(remaining);assert b['sufficient'] and remaining>0
        core.save(f,dict(utc=now(),balance=b,cap=remaining,original_exposure=used['exposure_usd'],deadline=gen.END.isoformat(),sources=sums))
    assert read(f)['sources']==sums and read(f)['cap']==remaining
    return read(f)

def score():
    import duckdb
    while not (gen.HERE/'judgments.json').exists() or not (HERE/'candidates.json').exists():
        if datetime.now(timezone.utc)>=gen.END:raise RuntimeError('Previous batch still running at deadline')
        time.sleep(6)
    reg=register()
    original=read(gen.HERE/'judgments.json')
    oldpages=read(gen.HERE/'candidates.json')['rows']
    newpages=read(HERE/'candidates.json')['rows']
    old={(r['model'],r['site'],r['check'],r['arm']):r for r in original['rows']}
    ledger=Ledger(OUT/'budget.sqlite3',reg['cap'],reg['cap'])
    api.OUT=OUT
    model=original['route']['model'];cal=original['calibration']
    assert cal['qualified']
    for f,h in read(run.OUT/'seal.json')['libraries'].items():assert sha(run.OUT/'build'/f/'library.json')==h
    test=duckdb.sql('select id,ui_instruct from read_parquet(?)',params=[str(gen.SRC)]).fetchall()
    by_id={(s,i):dict(task=c['task'],expected_result=c['expected_result']) for s,checks in test if s in read(gen.OUT/'generation-input.json') for i,c in enumerate(checks)}
    assert len(by_id)==43
    def evaluate(key):
        tag,site,index,arm=key
        previous=old[key];row=newpages[tag][site][arm]
        orig=oldpages[tag][site][arm]
        dest=OUT/'checks'/tag/site/str(index)/arm
        if row==orig or (row['status']==orig['status']=='valid' and row['sha256']==orig['sha256']):
            if previous['status']!='missing' or row['status']!='valid':
                return previous|{'reused':True}
        if row['status']=='valid':
            page=ROOT/row['file'];assert sha(page)==row['sha256']
            fn=lambda eng:first.journey(ledger,model,page.read_text(),arm=='human',by_id[site,index],dest,eng)
            value=read(dest/'judgment.json') if (dest/'judgment.json').exists() else first.browser_job(fn)
            extras=dict(status=value['status'],verdict=value['verdict'],reason=value['reason'],source=sha(dest/'judgment.json'))
        elif row['status']=='invalid':extras=dict(status='start_failed',verdict=None)
        else:extras=dict(status=row['status'],verdict=None)
        return dict(model=tag,site=site,check=index,arm=arm,reused=False,**extras)
    jobs=sorted(old,key=lambda k:hashlib.sha256(('/'.join(map(str,k))).encode()).digest())
    with ThreadPoolExecutor(max_workers=5) as pool:rows=list(pool.map(evaluate,jobs))
    core.save(HERE/'judgments.json',dict(registration=sha(OUT/'registration.json'),candidates=sha(HERE/'candidates.json'),route=original['route'],
            calibration=cal,original_judgments=sha(gen.HERE/'judgments.json'),cost=ledger_read.totals(OUT/'budget.sqlite3'),rows=rows))

if __name__=='__main__':
    with browser.lock(OUT/'evaluation.lock'):score()
