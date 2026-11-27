"""Independently validate every truncated first reply left without a functional verdict."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from decimal import Decimal
import hashlib
from pathlib import Path
from unittest.mock import patch

import httpx
from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from . import run

OUT = ROOT/'artifacts/webgen-html-confirmation-20261127'
RESULT = run.HERE/'functional-confirmation.json'
CAP = .50


def register():
    original = read(run.RESULT)
    assert original['cost']['calls'] == 0 and len(original['rows']) == 16
    assert all(r['status'] == 'missing' and r['verdict'] is None for r in original['rows'])
    assert original['candidates'] == sha(run.PAGES)
    sources = [Path(__file__), run.HERE/'CONFIRMATION.md', run.PAGES, run.RESULT, Path(run.__file__),
               Path(run.first.api.__file__), Path(run.evaluator.__file__), run.gen.SRC]
    sums = {str(p.relative_to(ROOT)):sha(p) for p in sources}
    reg = OUT/'registration.json'
    if not reg.exists():
        assert datetime.now(timezone.utc) < run.first.run.END
        prior = sum(round(ledger_read.totals(ROOT/'artifacts'/(name+'-20261127')/'budget.sqlite3')['exposure_usd']*1e6)
                    for name in run.report.LEDGERS.values() if name != 'webgen-html-confirmation')
        assert prior + round(CAP*1e6) <= 8_000_000
        balance = check_credits(CAP)
        assert balance['sufficient']
        response = httpx.get('https://openrouter.ai/api/v1/models/'+original['model']+'/endpoints',timeout=20)
        response.raise_for_status()
        allowed = [e for e in response.json()['data']['endpoints'] if e.get('status') == 0
                   and 0 < e['context_length'] <= 262144 and Decimal(e['pricing']['prompt']) <= Decimal('.00000015')
                   and Decimal(e['pricing']['completion']) <= Decimal('.0000006')
                   and not any(Decimal(e['pricing'].get(k) or 0) for k in ('request','image'))]
        assert allowed
        core.save(reg, dict(utc=now(),deadline=run.first.run.END.isoformat(),sources=sums,balance=balance,
                            cap=CAP,previous_exposure_usd=prior/1e6,model=original['model'],
                            price_routes=[e['provider_name'] for e in allowed]))
    assert read(reg)['sources'] == sums
    return reg


def evaluate():
    import duckdb
    reg = register()
    if RESULT.exists():
        return
    model = read(reg)['model']
    records = read(run.PAGES)['records']
    source = read(run.RESULT)
    ledger = Ledger(OUT/'budget.sqlite3',CAP,CAP)
    data = dict(duckdb.sql('select id, ui_instruct from read_parquet(?)',params=[str(run.gen.SRC)]).fetchall())
    def grade(row):
        batch, site, index = row['batch'],row['site'],row['check']
        saved = records[batch]
        assert saved['site'] == site and saved['evaluated_attempt'] == 0
        trial = saved['attempts'][0]
        path = ROOT/trial['html']
        assert sha(path) == trial['sha256']
        if not calibration['qualified']:
            return row | dict(reason='Independent calibration failed', source=None)
        dest = OUT/'checks'/batch/str(index)
        task = {k:data[site][index][k] for k in ('task','expected_result')}
        verdict = run.evaluator.browser_job(lambda eng:run.evaluator.journey(ledger,model,path.read_text(),False,task,dest,eng))
        return row | dict(status=verdict['status'],verdict=verdict['verdict'],reason=verdict.get('reason'),source=sha(dest/'judgment.json'))
    jobs = sorted(source['rows'], key=lambda r: hashlib.sha256(f"{r['site']}/{r['check']}".encode()).digest())
    with patch.multiple(run.first.api, OUT=OUT, END=run.first.run.END), patch.object(run.first, 'OUT', OUT), patch.dict(run.first.api.PRICES, {model:(.15,.6)}):
        calibration = run.first.calibrate(ledger,model)
        with ThreadPoolExecutor(max_workers=2) as workers:
            rows = list(workers.map(grade,jobs))
    core.save(RESULT,dict(registration=sha(reg),candidates=sha(run.PAGES),earlier_judgments=sha(run.RESULT),model=model,
                          calibration=calibration,rows=rows,cost=ledger_read.totals(OUT/'budget.sqlite3'),
                          previous_exposure_usd=read(reg)['previous_exposure_usd'],price_routes=read(reg)['price_routes']))


if __name__ == '__main__':
    with browser.lock(OUT/'run.lock'):
        evaluate()
