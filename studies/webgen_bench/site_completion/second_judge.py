"""Independently evaluate both Flash arms on one deterministic operation per site."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from unittest.mock import patch

import httpx
from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,now,read,sha
from ..component_contracts import evaluate as controls
from . import evaluate as main

OUT=ROOT/'artifacts/webgen-independent-flash-20261128'
RESULT=main.gen.HERE/'second-judge.json'
MODEL='openai/gpt-4o-mini'
CAP=1.


def score():
    import duckdb
    candidates=read(main.gen.CANDIDATES)
    assert candidates['seal']==sha(main.gen.OUT/'seal.json')
    pages=candidates['rows']['deepseek-flash']
    raw=duckdb.sql('select id,ui_instruct from read_parquet(?) where id in (select unnest(?))',
                   params=[str(main.gen.gen.SRC),list(pages)]).fetchall()
    subset={s:min(range(len(items)),key=lambda i:hashlib.sha256(f'webgen-human-audit-v1:{s}:{i}'.encode()).digest()) for s,items in raw}
    tasks={s:{k:items[subset[s]][k] for k in ('task','expected_result')} for s,items in raw}
    reg=OUT/'registration.json'
    hashes={str(p.relative_to(ROOT)):sha(p) for p in (Path(__file__),main.gen.HERE/'SECOND_JUDGE.md',
            main.gen.CANDIDATES,main.gen.gen.SRC,Path(main.evaluator.__file__),Path(main.api.__file__))}
    if not reg.exists():
        finalized=sum(ledger_read.totals(ROOT/'artifacts'/(name+'-20261128')/'budget.sqlite3')['exposure_usd'] for name in
                      ('webgen-site-completion','webgen-native-state','webgen-grounded-actions','webgen-grounded-actions-judge'))
        assert finalized+11.5+4.30+1.30+.20+.20+CAP<=20
        balance=check_credits(CAP)
        assert balance['sufficient'] and datetime.now(timezone.utc)<main.gen.END
        r=httpx.get('https://openrouter.ai/api/v1/models/'+MODEL+'/endpoints',timeout=15)
        r.raise_for_status()
        available=[e['provider_name'] for e in r.json()['data']['endpoints'] if e.get('status')==0 and 0<e['context_length']<=262144
                   and Decimal(e['pricing']['prompt'])<=Decimal('.00000015') and Decimal(e['pricing']['completion'])<=Decimal('.0000006')
                   and not any(Decimal(e['pricing'].get(k) or 0) for k in ('image','request'))]
        assert available
        core.save(reg,dict(utc=now(),deadline=main.gen.END.isoformat(),sources=hashes,cap=CAP,balance=balance,model=MODEL,subset=subset,routes=available))
    assert read(reg)['sources']==hashes and read(reg)['subset']==subset
    if RESULT.exists():
        return
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    jobs=sorted(((s,a) for s in subset for a in ('human','direct')),key=lambda j:hashlib.sha256('/'.join(j).encode()).digest())
    def grade(job):
        s,a=job
        base=dict(site=s,check=subset[s],arm=a,verdict=None)
        candidate=pages[s][a]
        if not calibration['qualified'] or candidate['status']!='valid':
            return base|dict(status='missing',reason='Judge calibration failed' if not calibration['qualified'] else candidate['status'])
        file=ROOT/candidate['file']
        assert sha(file)==candidate['sha256']
        dest=OUT/'checks'/s/a
        val=main.evaluator.browser_job(lambda e:main.evaluator.journey(ledger,MODEL,file.read_text(),a=='human',tasks[s],dest,e))
        return base|dict(status=val['status'],verdict=val['verdict'],reason=val.get('reason'),source=sha(dest/'judgment.json'))
    with patch.multiple(main.api,OUT=OUT,END=main.gen.END),patch.dict(main.api.PRICES,{MODEL:(.15,.6)}),patch.object(controls,'OUT',OUT):
        calibration=controls.calibrate(ledger,MODEL)
        with ThreadPoolExecutor(max_workers=2) as pool:
            rows=list(pool.map(grade,jobs))
    core.save(RESULT,dict(candidates=sha(main.gen.CANDIDATES),registration=sha(reg),subset=subset,model=MODEL,
                          calibration=calibration,rows=rows,cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__=='__main__':
    with browser.lock(OUT/'run.lock'):
        score()
