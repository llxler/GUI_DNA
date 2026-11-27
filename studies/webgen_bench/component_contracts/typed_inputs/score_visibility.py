"""Score the sealed native-control follow-up after accounting for the Flash transfer."""
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,now,read,sha
from ...heldout_transfer import evaluate as flash
from . import native_visibility as run, score_dom as previous

scoring=previous.scoring
OUT=ROOT/'artifacts/webgen-visibility-judge-20261127'
RESULT=run.HERE/'visibility-judgments.json'


def score():
    import duckdb
    for f in (flash.RESULT,previous.RESULT,run.CANDIDATES):scoring.wait_for(f)
    sources=[Path(__file__),Path(scoring.__file__),run.HERE/'NATIVE_VISIBILITY.md',flash.RESULT,previous.RESULT,run.CANDIDATES,run.dom.CANDIDATES]
    hashes={str(p.relative_to(ROOT)):sha(p) for p in sources}
    ledgers=(scoring.first.OUT,scoring.second.OUT,scoring.OUT,previous.previous.OUT,previous.OUT,flash.OUT)
    used=sum(Decimal(str(ledger_read.totals(d/'budget.sqlite3')['exposure_usd'])) for d in ledgers)
    cap=float(Decimal(str(scoring.first.CAP))-used)
    reg=OUT/'registration.json'
    if not reg.exists():
        balance=check_credits(cap);assert balance['sufficient']
        core.save(reg,dict(utc=now(),cap=cap,balance=balance,sources=hashes,deadline=run.dom.comp.END.isoformat()))
    assert read(reg)['sources']==hashes and read(reg)['cap']==cap
    if RESULT.exists():return
    before,after,prior=read(run.dom.CANDIDATES),read(run.CANDIDATES),read(previous.RESULT)
    assert prior['candidates']==sha(run.dom.CANDIDATES) and after['previous']==sha(run.dom.CANDIDATES)
    seal=run.OUT/'seal.json'
    assert after['seal']==sha(seal) and all(read(seal)[k]==after[k] for k in ('development','holdout'))
    assert read(seal)['libraries'][run.TAG]==sha(run.OUT/'build'/run.TAG/'library.json')
    data=duckdb.sql('select id,ui_instruct from read_parquet(?)',params=[str(run.dom.typed.GEN.SRC)]).fetchall()
    tests={(s,i):{k:v[k] for k in ('task','expected_result')} for s,cs in data for i,v in enumerate(cs)}
    assert prior['route']['primary']['qualified']
    ledger=Ledger(OUT/'budget.sqlite3',cap,cap)
    with patch.object(scoring,'OUT',OUT):
        rows=scoring.grade(prior['rows'],before,after,tests,'native-visibility',prior['route']['primary']['model'],ledger)
    core.save(RESULT,dict(registration=sha(reg),candidates=sha(run.CANDIDATES),original_judgments=sha(previous.RESULT),
                          route=prior['route'],rows=rows,cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__=='__main__':
    with browser.lock(OUT/'run.lock'),patch.multiple(scoring.first.api,OUT=OUT,END=run.dom.comp.END):
        score()
