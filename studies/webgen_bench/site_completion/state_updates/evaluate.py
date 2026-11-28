"""Replay the enabled and inert versions on every operation of three registered sites."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from .. import evaluate as primary
from . import build

OUT=ROOT/'artifacts/webgen-native-state-judge-20261128'
RESULT=build.HERE/'judgments.json'
CAP=4.30


def score():
    import duckdb
    candidates=read(build.CANDIDATES)
    assert candidates['seal']==sha(build.OUT/'seal.json')
    assert candidates['main_candidates']==sha(build.main.CANDIDATES)
    assert candidates['rows']==read(build.OUT/'seal.json')['rows']
    calibration=read(primary.OUT/'calibration.json')
    assert calibration['qualified']
    sources=[Path(__file__),build.HERE/'PROTOCOL.md',build.CANDIDATES,primary.OUT/'calibration.json',
             primary.OUT/'registration.json',Path(primary.evaluator.__file__),Path(primary.api.__file__),build.main.gen.SRC]
    hashes={str(f.relative_to(ROOT)):sha(f) for f in sources}
    reg=OUT/'registration.json'
    if not reg.exists():
        balance=check_credits(CAP)
        assert balance['sufficient'] and datetime.now(timezone.utc)<build.main.END
        core.save(reg,dict(sources=hashes,model=calibration['model'],utc=now(),deadline=build.main.END.isoformat(),cap=CAP,balance=balance))
    assert read(reg)['sources']==hashes
    if RESULT.exists():
        return
    ops=duckdb.sql('select id, ui_instruct from read_parquet(?) where id in (select unnest(?))',
                   params=[str(build.main.gen.SRC),list(build.SITES)]).fetchall()
    cases={(s,i):{k:c[k] for k in ('task','expected_result')} for s,tests in ops for i,c in enumerate(tests)}
    jobs=[(site,i,arm) for site,i in cases for arm in ('active','inert')]
    jobs.sort(key=lambda j:hashlib.sha256('/'.join(map(str,j)).encode()).digest())
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    def grade(job):
        site,i,arm=job
        page=candidates['rows'][site][arm]
        record=dict(site=site,check=i,arm=arm,verdict=None)
        if page['status']!='valid':
            return record|dict(status='start_failed' if page['status']=='invalid' else page['status'])
        file=ROOT/page['file']
        assert sha(file)==page['sha256']
        dest=OUT/'checks'/site/str(i)/arm
        val=primary.evaluator.browser_job(lambda eng:primary.evaluator.journey(ledger,calibration['model'],
                                file.read_text(),True,cases[site,i],dest,eng))
        return record|dict(status=val['status'],verdict=val['verdict'],reason=val.get('reason'),source=sha(dest/'judgment.json'))
    with patch.multiple(primary.api,OUT=OUT,END=build.main.END),patch.dict(primary.api.PRICES,{primary.api.ALTERNATE:(.15,.6)}),ThreadPoolExecutor(max_workers=2) as pool:
        rows=list(pool.map(grade,jobs))
    core.save(RESULT,dict(candidates=sha(build.CANDIDATES),registration=sha(reg),calibration=sha(primary.OUT/'calibration.json'),
                          judge=calibration['model'],rows=rows,cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__=='__main__':
    with browser.lock(OUT/'run.lock'):
        score()
