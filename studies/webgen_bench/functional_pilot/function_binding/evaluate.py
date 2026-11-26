"""Grade the public output-binding correction against identical comparisons."""
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
from ..component_functions import evaluate as previous
from . import run

OUT = ROOT / 'artifacts/webgen-binding-judge-20261126pm'

def register():
    sources = [Path(__file__), run.HERE/'PROTOCOL.md', run.HERE/'candidates.json',
               run.parent.HERE/'candidates.json', run.parent.HERE/'judgments.json',
               Path(scorer.__file__), Path(original.__file__), Path(api.__file__)]
    sums = {str(p.relative_to(ROOT)): sha(p) for p in sources}
    folders = [original.OUT, previous.mounted.PREVIOUS_OUT, previous.mounted.OUT, previous.OUT]
    charges = [ledger_read.totals(p/'budget.sqlite3')['exposure_usd'] for p in folders]
    cap = float(Decimal(str(api.CAP)) - sum(Decimal(str(c)) for c in charges))
    dest = OUT/'registration.json'
    if not dest.exists():
        balance = check_credits(cap)
        assert cap > 0 and balance['sufficient']
        core.save(dest, dict(utc=now(), deadline=gen.END.isoformat(), cap=cap, sources=sums,
                             balance=balance, previous_exposures=charges))
    assert read(dest)['sources'] == sums and read(dest)['cap'] == cap
    return read(dest)

if __name__ == '__main__':
    with browser.lock(OUT/'run.lock'):
        while not (run.parent.HERE/'judgments.json').exists() or not (run.HERE/'candidates.json').exists():
            if datetime.now(timezone.utc) >= gen.END:raise RuntimeError('Previous phase incomplete at deadline')
            time.sleep(6)
        parent = SimpleNamespace(HERE=run.parent.HERE, SRC=gen.SRC, OUT=gen.OUT, END=gen.END)
        with patch.multiple(scorer, HERE=run.HERE, OUT=OUT, register=register, run=run, gen=parent):
            scorer.score()
