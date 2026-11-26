"""Evaluate newly admitted Self pages on the registered native-plan cohort."""
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import time

from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from .. import evaluate as original, generate as gen, judge_api as api
from ..native_plans import evaluate as previous
from . import run

OUT = ROOT / 'artifacts/webgen-mounted-judge-20261126pm'

def register():
    previous_source = run.native.HERE / 'judgments.json'
    sources = [Path(__file__), run.HERE / 'PROTOCOL.md', run.HERE / 'candidates.json',
               run.native.HERE / 'candidates.json', previous_source, Path(previous.__file__),
               Path(original.__file__), Path(api.__file__)]
    sums = {str(p.relative_to(ROOT)): sha(p) for p in sources}
    costs = [ledger_read.totals(p / 'budget.sqlite3')['exposure_usd']
             for p in (original.OUT, PREVIOUS_OUT)]
    remaining = float(Decimal(str(api.CAP)) - sum(Decimal(str(x)) for x in costs))
    f = OUT / 'registration.json'
    if not f.exists():
        balance = check_credits(remaining)
        assert remaining > 0 and balance['sufficient']
        core.save(f, dict(utc=now(), balance=balance, cap=remaining, deadline=gen.END.isoformat(),
                          prior_exposures=costs, sources=sums))
    assert read(f)['sources'] == sums
    return read(f)

PREVIOUS_OUT = previous.OUT
if __name__ == '__main__':
    with browser.lock(OUT / 'run.lock'):
        while not (run.native.HERE / 'judgments.json').exists() or not (run.HERE / 'candidates.json').exists():
            if datetime.now(timezone.utc) >= gen.END:raise RuntimeError('Candidate or previous judgment missing at deadline')
            time.sleep(6)
        stage = SimpleNamespace(HERE=run.native.HERE, SRC=gen.SRC, OUT=gen.OUT, END=gen.END)
        with patch.multiple(previous, HERE=run.HERE, OUT=OUT, register=register, run=run, gen=stage):
            previous.score()
