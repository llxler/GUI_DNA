"""Score only newly sealed sites; inherit every byte-identical comparison and judge."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
from pathlib import Path
import time
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, read, now, sha
from .. import evaluate as first
from . import run

OUT = ROOT/'artifacts/webgen-body-judge-20261127'


def score():
    import duckdb
    source=run.HERE/'candidates.json'
    old_source=run.prior.HERE/'candidates.json'
    old_judgments=run.prior.HERE/'judgments.json'
    while not (source.exists() and old_judgments.exists()):
        if datetime.now(timezone.utc)>=run.prior.END:raise RuntimeError('Previous evaluation incomplete at deadline')
        time.sleep(4)
    original=read(old_judgments);after=read(source);before=read(old_source)
    assert original['candidates']==sha(old_source) and after['previous']==sha(old_source) and after['seal']==sha(run.OUT/'seal.json')
    for t,h in read(run.OUT/'seal.json')['libraries'].items():assert h==sha(run.OUT/'build'/t/'library.json')
    earlier=ledger_read.totals(first.OUT/'budget.sqlite3')
    assert earlier==original['cost']
    cap=float(Decimal(str(first.CAP))-Decimal(str(earlier['exposure_usd'])))
    assert cap>0
    reg=OUT/'registration.json'
    sources={str(p.relative_to(ROOT)):sha(p) for p in (Path(__file__),run.HERE/'PROTOCOL.md',source,old_source,old_judgments,Path(first.evaluator.__file__))}
    if not reg.exists():
        balance=check_credits(cap);assert balance['sufficient']
        core.save(reg,dict(utc=now(),deadline=run.prior.END.isoformat(),balance=balance,cap=cap,sources=sources))
    assert read(reg)['sources']==sources and read(reg)['cap']==cap
    ledger=Ledger(OUT/'budget.sqlite3',cap,cap)
    primary=original['route']['primary']
    data=duckdb.sql('select id,ui_instruct from read_parquet(?)',params=[str(run.gen.SRC)]).fetchall()
    tests={(s,i):{k:r[k] for k in ('task','expected_result')} for s,cs in data for i,r in enumerate(cs)}
    def one(r):
        batch,t,s,i,arm=(r[k] for k in ('batch','model','site','check','arm'))
        old=before[batch][t][s][arm];new=after[batch][t][s][arm]
        if new==old or old.get('sha256') and old.get('sha256')==new.get('sha256'):
            return r|{'reused':True}
        dest=OUT/'checks'/batch/t/s/str(i)/arm;reason=source_hash=verdict=None
        if new['status']=='valid' and primary['qualified']:
            fname=ROOT/new['file'];assert sha(fname)==new['sha256']
            def judge(eng):return first.evaluator.journey(ledger,primary['model'],fname.read_text(),arm=='human',tests[s,i],dest,eng)
            result=read(dest/'judgment.json') if (dest/'judgment.json').exists() else first.evaluator.browser_job(judge)
            status,verdict,reason=result['status'],result['verdict'],result.get('reason')
            source_hash=sha(dest/'judgment.json')
        else:
            status={'valid':'missing','invalid':'start_failed'}.get(new['status'],new['status'])
        return r|dict(status=status,verdict=verdict,reason=reason,source=source_hash,reused=False)
    with ThreadPoolExecutor(max_workers=5) as pool:
        rows=list(pool.map(one,original['rows']))
    core.save(run.HERE/'judgments.json',dict(registration=sha(reg),candidates=sha(source),original_judgments=sha(old_judgments),
                route=original['route'],rows=rows,cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__=='__main__':
    with browser.lock(OUT/'run.lock'),patch.multiple(first.api,OUT=OUT,END=run.prior.END):
        score()
