"""Score the two sealed named-input variants under one remaining evaluator allowance."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import time
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from .. import evaluate as first
from ..function_bodies import evaluate as second
from . import fragment_replay as replay, run

OUT = ROOT / 'artifacts/webgen-typed-judge-20261127'
RESULT = run.HERE/'replay-judgments.json'


def wait_for(path):
    while not path.exists():
        if datetime.now(timezone.utc) >= run.components.END:
            raise TimeoutError(f'Seal unavailable at deadline: {path}')
        time.sleep(3)


def grade(previous_rows, before, after, tests, stage, model, ledger):
    def one(row):
        batch, tag, site, index, arm = (row[k] for k in ('batch','model','site','check','arm'))
        old, new = (pages[batch][tag][site][arm] for pages in (before,after))
        if old == new or old.get('sha256') and old['sha256'] == new.get('sha256'):
            return row | {'reused':True}
        dest = OUT/stage/batch/tag/site/str(index)/arm
        status = {'invalid':'start_failed'}.get(new['status'],new['status'])
        verdict = reason = source = None
        if status == 'valid':
            path = ROOT/new['file']
            assert sha(path) == new['sha256']
            def journey(engine):
                return first.evaluator.journey(ledger,model,path.read_text(),arm=='human',tests[site,index],dest,engine)
            record = dest/'judgment.json'
            value = read(record) if record.exists() else first.evaluator.browser_job(journey)
            status, verdict, reason = value['status'], value['verdict'], value.get('reason')
            source = sha(record)
        return row | dict(status=status,verdict=verdict,reason=reason,source=source,reused=False)
    with ThreadPoolExecutor(max_workers=5) as pool:
        return list(pool.map(one,previous_rows))


def evaluate():
    import duckdb
    initial = run.bodies.HERE/'judgments.json'
    variants = [('typed',run.HERE/'candidates.json',run.OUT,run.HERE/'judgments.json'),
                ('fragments',replay.CANDIDATES,replay.OUT,RESULT)]
    for path in (initial,replay.CANDIDATES):
        wait_for(path)
    prior = read(initial)
    before_path = run.bodies.HERE/'candidates.json'
    assert prior['candidates'] == sha(before_path)
    source_files = [Path(__file__),run.HERE/'FRAGMENT_REPLAY.md',initial,before_path,*[v[1] for v in variants]]
    sources = {str(p.relative_to(ROOT)):sha(p) for p in source_files}
    spent = sum(Decimal(str(ledger_read.totals(d/'budget.sqlite3')['exposure_usd'])) for d in (first.OUT,second.OUT))
    cap = float(Decimal(str(first.CAP))-spent)
    reg = OUT/'registration.json'
    if not reg.exists():
        balance = check_credits(cap)
        assert balance['sufficient']
        core.save(reg, dict(utc=now(),balance=balance,cap=cap,sources=sources,deadline=run.components.END.isoformat()))
    assert read(reg)['sources'] == sources and read(reg)['cap'] == cap
    ledger = Ledger(OUT/'budget.sqlite3',cap,cap)
    data = duckdb.sql('select id,ui_instruct from read_parquet(?)',params=[str(run.GEN.SRC)]).fetchall()
    tests = {(site,i):{k:v[k] for k in ('task','expected_result')} for site,checks in data for i,v in enumerate(checks)}
    assert prior['route']['primary']['qualified']
    prev_j = initial
    for stage,source,folder,dest in variants:
        before,after = read(before_path),read(source)
        assert after['previous']==sha(before_path) and after['seal']==sha(folder/'seal.json')
        for tag,h in read(folder/'seal.json')['libraries'].items():
            assert sha(folder/'build'/tag/'library.json') == h
        if not dest.exists():
            rows = grade(prior['rows'],before,after,tests,stage,prior['route']['primary']['model'],ledger)
            core.save(dest,dict(registration=sha(reg),candidates=sha(source),original_judgments=sha(prev_j),
                                route=prior['route'],rows=rows,cumulative_stage_cost=ledger_read.totals(OUT/'budget.sqlite3')))
        prior = read(dest)
        assert prior['candidates'] == sha(source) and prior['original_judgments'] == sha(prev_j)
        before_path,prev_j = source,dest


if __name__=='__main__':
    with browser.lock(OUT/'run.lock'),patch.multiple(first.api,OUT=OUT,END=run.components.END):
        evaluate()
