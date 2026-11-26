"""Score the final prepared sites using the original shared judgment budget."""
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
import time
from unittest.mock import patch

from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from .. import evaluate as original, generate as gen, judge_api as api
from ..native_plans import evaluate as scorer
from ..mounted_components import evaluate as mounted
from . import run


OUT = ROOT / 'artifacts/webgen-function-judge-20261126pm'

def register():
    files = [Path(__file__), run.HERE/'PROTOCOL.md', run.HERE/'candidates.json',
             run.previous.HERE/'candidates.json', run.previous.HERE/'judgments.json',
             Path(scorer.__file__), Path(api.__file__), Path(original.__file__)]
    sums = {str(f.relative_to(ROOT)): sha(f) for f in files}
    charged = [ledger_read.totals(folder/'budget.sqlite3')['exposure_usd']
               for folder in (original.OUT, mounted.PREVIOUS_OUT, mounted.OUT)]
    cap = float(Decimal(str(api.CAP)) - sum(Decimal(str(x)) for x in charged))
    dest = OUT/'registration.json'
    if not dest.exists():
        balance = check_credits(cap)
        assert cap > 0 and balance['sufficient']
        core.save(dest, dict(utc=now(), deadline=gen.END.isoformat(), cap=cap, sources=sums,
                             balance=balance, prior_exposures=charged))
    assert read(dest)['sources'] == sums and read(dest)['cap'] == cap
    return read(dest)

if __name__ == '__main__':
    with browser.lock(OUT/'run.lock'):
        while not (run.previous.HERE/'judgments.json').exists() or not (run.HERE/'candidates.json').exists():
            if datetime.now(timezone.utc) >= gen.END:
                raise RuntimeError('Previous evaluation or candidates missing at deadline')
            time.sleep(6)
        prev = SimpleNamespace(HERE=run.previous.HERE, SRC=gen.SRC, OUT=gen.OUT, END=gen.END)
        with patch.multiple(scorer, HERE=run.HERE, OUT=OUT, register=register, run=run, gen=prev):
            scorer.score()
