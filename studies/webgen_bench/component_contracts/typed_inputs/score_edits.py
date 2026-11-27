"""Evaluate sealed local edits using only the unused portion of the registered judge budget."""
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,now,read,sha
from . import evaluate as scoring,local_edits as edit

OUT=ROOT/'artifacts/webgen-edits-judge-20261127'
RESULT=edit.HERE/'edit-judgments.json'


def score():
    import duckdb
    for f in (scoring.RESULT,edit.CANDIDATES):
        scoring.wait_for(f)
    sources=[Path(__file__),scoring.RESULT,edit.CANDIDATES,edit.replay.CANDIDATES,
             Path(scoring.__file__),edit.HERE/'LOCAL_EDITS.md']
    reg=OUT/'registration.json'
    hashes={str(p.relative_to(ROOT)):sha(p) for p in sources}
    used=sum(Decimal(str(ledger_read.totals(d/'budget.sqlite3')['exposure_usd']))
             for d in (scoring.first.OUT,scoring.second.OUT,scoring.OUT))
    cap=float(Decimal(str(scoring.first.CAP))-used)
    if not reg.exists():
        balance=check_credits(cap);assert balance['sufficient']
        core.save(reg,dict(utc=now(),cap=cap,balance=balance,sources=hashes,deadline=edit.replay.COMP.END.isoformat()))
    assert read(reg)['sources']==hashes and read(reg)['cap']==cap
    if RESULT.exists():return
    previous=read(scoring.RESULT);before=read(edit.replay.CANDIDATES);after=read(edit.CANDIDATES)
    assert previous['candidates']==sha(edit.replay.CANDIDATES) and after['previous']==sha(edit.replay.CANDIDATES)
    seal=edit.OUT/'seal.json'
    assert after['seal']==sha(seal) and all(read(seal)[k]==after[k] for k in ('development','holdout'))
    for t,h in read(seal)['libraries'].items():assert h==sha(edit.OUT/'build'/t/'library.json')
    data=duckdb.sql('select id,ui_instruct from read_parquet(?)',params=[str(edit.typed.GEN.SRC)]).fetchall()
    tests={(s,i):{k:v[k] for k in ('task','expected_result')} for s,checks in data for i,v in enumerate(checks)}
    assert previous['route']['primary']['qualified']
    ledger=Ledger(OUT/'budget.sqlite3',cap,cap)
    with patch.object(scoring,'OUT',OUT):
        rows=scoring.grade(previous['rows'],before,after,tests,'local-edits',previous['route']['primary']['model'],ledger)
    core.save(RESULT,dict(registration=sha(reg),candidates=sha(edit.CANDIDATES),original_judgments=sha(scoring.RESULT),
                          route=previous['route'],rows=rows,cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__=='__main__':
    with browser.lock(OUT/'run.lock'),patch.multiple(scoring.first.api,OUT=OUT,END=edit.replay.COMP.END):
        score()
