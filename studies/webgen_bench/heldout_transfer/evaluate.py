"""Run the 21 official operations on the sealed Flash pages under the same judge."""
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from ..component_contracts.typed_inputs import score_dom as earlier
from . import generate as run

scoring=earlier.scoring
OUT=ROOT/'artifacts/webgen-flash-judge-20261127'
RESULT=run.HERE/'judgments.json'


def score():
    import duckdb
    for path in (earlier.RESULT,run.CANDIDATES):
        scoring.wait_for(path)
    sources=[Path(__file__),Path(scoring.__file__),earlier.RESULT,run.HERE/'PROTOCOL.md',run.CANDIDATES,run.gen.SRC]
    hashes={str(p.relative_to(ROOT)):sha(p) for p in sources}
    layers=(scoring.first.OUT,scoring.second.OUT,scoring.OUT,earlier.previous.OUT,earlier.OUT)
    previous=sum(Decimal(str(ledger_read.totals(p/'budget.sqlite3')['exposure_usd'])) for p in layers)
    cap=float(Decimal(str(scoring.first.CAP))-previous)
    reg=OUT/'registration.json'
    if not reg.exists():
        balance=check_credits(cap);assert balance['sufficient']
        core.save(reg,dict(utc=now(),cap=cap,balance=balance,sources=hashes,deadline=run.comp.END.isoformat()))
    assert read(reg)['sources']==hashes and read(reg)['cap']==cap
    if RESULT.exists():return
    prior=read(earlier.RESULT)
    assert prior['route']['primary']['qualified']
    candidates=read(run.CANDIDATES);assert candidates['seal']==sha(run.OUT/'seal.json')
    rows=candidates['rows'];assert rows==read(run.OUT/'seal.json')['rows']
    data=duckdb.sql('select id,ui_instruct from read_parquet(?)',params=[str(run.gen.SRC)]).fetchall()
    tests={(s,i):{k:v[k] for k in ('task','expected_result')} for s,cs in data if s in rows for i,v in enumerate(cs)}
    after={'holdout':{run.TAG:rows}}
    before={'holdout':{run.TAG:{s:{a:{'status':'unscheduled'} for a in arms} for s,arms in rows.items()}}}
    scheduled=[dict(batch='holdout',model=run.TAG,site=s,check=i,arm=arm) for s,i in tests for arm in rows[s]]
    ledger=Ledger(OUT/'budget.sqlite3',cap,cap)
    with patch.object(scoring,'OUT',OUT):
        judgments=scoring.grade(scheduled,before,after,tests,'heldout',prior['route']['primary']['model'],ledger)
    core.save(RESULT,dict(registration=sha(reg),candidates=sha(run.CANDIDATES),route=prior['route'],rows=judgments,
                          cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__=='__main__':
    with browser.lock(OUT/'run.lock'),patch.multiple(scoring.first.api,OUT=OUT,END=run.comp.END):
        score()
