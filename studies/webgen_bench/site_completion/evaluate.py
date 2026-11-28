"""Score the sealed panel in a fixed interleaved order with fresh browser sessions."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
from pathlib import Path
import time
from unittest.mock import patch

import httpx

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from ..functional_pilot import evaluate as evaluator, judge_api as api
from . import generate as gen

OUT = ROOT/'artifacts/webgen-site-completion-judge-20261128'
RESULT = gen.HERE/'judgments.json'
CAP = 11.50
ARMS = ('direct','human','gpt5-library','self')


def register():
    path = OUT/'registration.json'
    paths = [Path(__file__), gen.HERE/'PROTOCOL.md', Path(gen.__file__), gen.gen.SRC,
             Path(evaluator.__file__), Path(api.__file__), Path(evaluator.v.__file__),
             evaluator.v.UI, evaluator.v.UTILS, evaluator.v.OPERATOR, evaluator.v.PROMPTS]
    hashes = {str(f.relative_to(ROOT)):sha(f) for f in paths}
    if not path.exists():
        balance = check_credits(CAP)
        assert balance['sufficient'] and datetime.now(timezone.utc) < gen.END
        routes = httpx.get('https://openrouter.ai/api/v1/models/'+api.ALTERNATE+'/endpoints',timeout=20)
        routes.raise_for_status()
        available = [e for e in routes.json()['data']['endpoints'] if e.get('status') == 0
                     and 0 < e['context_length'] <= 262144 and Decimal(e['pricing']['prompt']) <= Decimal('.00000015')
                     and Decimal(e['pricing']['completion']) <= Decimal('.0000006')
                     and not any(Decimal(e['pricing'].get(k) or 0) for k in ('request','image'))]
        assert available, 'No alternate route within the registered price and size limits'
        core.save(path, dict(sources=hashes, utc=now(), cap=CAP, deadline=gen.END.isoformat(),
                             balance=balance, alternate_price_routes=[e['provider_name'] for e in available]))
    assert read(path)['sources'] == hashes
    return path


def score():
    import duckdb
    registration = register()
    if RESULT.exists():
        assert read(RESULT)['registration'] == sha(registration)
        return
    ledger = Ledger(OUT/'budget.sqlite3', CAP, CAP)
    with patch.multiple(api, OUT=OUT, END=gen.END), patch.object(evaluator,'OUT',OUT), patch.dict(api.PRICES,{api.ALTERNATE:(.15,.6)}):
        calibration = evaluator.calibrate(ledger)
        while not gen.CANDIDATES.exists():
            if datetime.now(timezone.utc) >= gen.END:
                raise TimeoutError('No candidates sealed before deadline')
            time.sleep(5)
        candidates = read(gen.CANDIDATES)
        sealed = read(gen.OUT/'seal.json')
        assert sha(gen.OUT/'seal.json') == candidates['seal'] and candidates['rows'] == sealed['rows']
        pages = sealed['rows']
        sites = sorted(read(gen.OUT/'registration.json')['sites'])
        assert all(sorted(group) == sites for group in pages.values())
        data = duckdb.sql('select id, ui_instruct from read_parquet(?) where id in (select unnest(?))',
                          params=[str(gen.gen.SRC),sites]).fetchall()
        checks = {(site,i):{k:c[k] for k in ('task','expected_result')}
                  for site,ops in data for i,c in enumerate(ops)}
        jobs = [(t,s,i,a) for s,i in checks for t in pages for a in ARMS]
        jobs.sort(key=lambda x:hashlib.sha256('/'.join(map(str,x)).encode()).digest())
        core.save(OUT/'schedule.json',dict(seal=candidates['seal'],jobs=[list(j) for j in jobs]))
        def grade(job):
            tag, site, i, arm = job
            page = pages[tag][site][arm]
            result = dict(model=tag,site=site,check=i,arm=arm,verdict=None)
            if page['status'] == 'invalid':
                return result | {'status':'start_failed'}
            if page['status'] != 'valid':
                return result | {'status':page['status'], 'reason':page.get('reason')}
            if not calibration['qualified']:
                return result | dict(status='missing',reason='Judge calibration failed')
            path = ROOT/page['file']
            assert sha(path) == page['sha256']
            dest = OUT/'checks'/tag/site/str(i)/arm
            if (dest/'judgment.json').exists():
                value = read(dest/'judgment.json')
            else:
                value = evaluator.browser_job(lambda engine:evaluator.journey(
                    ledger,calibration['model'],path.read_text(),arm=='human',checks[site,i],dest,engine))
            return result | dict(status=value['status'],verdict=value['verdict'],reason=value.get('reason'),source=sha(dest/'judgment.json'))
        with ThreadPoolExecutor(max_workers=5) as pool:
            rows = list(pool.map(grade,jobs))
    core.save(RESULT,dict(candidates=sha(gen.CANDIDATES),registration=sha(registration),schedule=sha(OUT/'schedule.json'),
                          route=read(OUT/'route.json'),calibration=calibration,rows=rows,cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__ == '__main__':
    with browser.lock(OUT/'run.lock'):
        score()
