"""Judge only pages changed by pre-rendering the two child fragments."""
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from . import dom_inputs as run, score_edits as previous

OUT = ROOT/'artifacts/webgen-dom-judge-20261127'
RESULT = run.HERE/'dom-judgments.json'
scoring = previous.scoring


def score():
    import duckdb
    for path in (previous.RESULT,run.CANDIDATES):
        scoring.wait_for(path)
    prior = read(previous.RESULT)
    before = read(run.prior.CANDIDATES)
    after = read(run.CANDIDATES)
    seal = run.OUT/'seal.json'
    assert prior['candidates'] == sha(run.prior.CANDIDATES) and after['previous'] == sha(run.prior.CANDIDATES)
    assert sha(seal) == after['seal'] and all(read(seal)[k] == after[k] for k in ('development','holdout'))
    assert read(seal)['libraries'][run.MODEL] == sha(run.OUT/'build'/run.MODEL/'library.json')
    used = sum(Decimal(str(ledger_read.totals(d/'budget.sqlite3')['exposure_usd']))
               for d in (scoring.first.OUT,scoring.second.OUT,scoring.OUT,previous.OUT))
    cap = float(Decimal(str(scoring.first.CAP))-used)
    reg = OUT/'registration.json'
    files = [Path(__file__),Path(scoring.__file__),previous.RESULT,run.CANDIDATES,run.prior.CANDIDATES,run.HERE/'DOM_INPUTS.md']
    hashes = {str(p.relative_to(ROOT)):sha(p) for p in files}
    if not reg.exists():
        balance = check_credits(cap)
        assert balance['sufficient']
        core.save(reg,dict(utc=now(),cap=cap,balance=balance,sources=hashes,deadline=run.comp.END.isoformat()))
    assert read(reg)['sources'] == hashes and read(reg)['cap'] == cap
    if RESULT.exists():return
    ledger = Ledger(OUT/'budget.sqlite3',cap,cap)
    data = duckdb.sql('select id,ui_instruct from read_parquet(?)',params=[str(run.typed.GEN.SRC)]).fetchall()
    tests = {(s,i):{k:v[k] for k in ('task','expected_result')} for s,checks in data for i,v in enumerate(checks)}
    assert prior['route']['primary']['qualified']
    with patch.object(scoring,'OUT',OUT):
        rows = scoring.grade(prior['rows'],before,after,tests,'dom-inputs',prior['route']['primary']['model'],ledger)
    core.save(RESULT,dict(registration=sha(reg),candidates=sha(run.CANDIDATES),original_judgments=sha(previous.RESULT),
                          route=prior['route'],rows=rows,cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__ == '__main__':
    with browser.lock(OUT/'run.lock'),patch.multiple(scoring.first.api,OUT=OUT,END=run.comp.END):
        score()
