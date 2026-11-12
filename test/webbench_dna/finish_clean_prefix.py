"""Finish only Qwen task 16, replaying its settled truncated first response."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from gui_dna.budget import Ledger
from test.ledger_read import calls
from test.rerun_failed import affected
from test.review_stage import freeze, provider_for
from . import clean_prefix as control, domain, run
from .library import library
from .review_evaluate import grade_record

ROOT = domain.ROOT
SOURCE = ROOT / 'artifacts/webbench-dna-clean-2'
OUT = ROOT / 'artifacts/webbench-dna-clean-3'
RELATIVE = Path('qwen__qwen3-coder-30b-a3b-instruct/free_clean/task-16')


def prepare():
    target = OUT / 'continuation.json'
    if target.exists():
        return
    assert affected(SOURCE, 'webbench') == [(SOURCE / 'runs' / RELATIVE, affected(SOURCE, 'webbench')[0][1])]
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SOURCE / 'runs', OUT / 'runs')
    archived = OUT / 'discarded-transport/1' / RELATIVE
    archived.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(OUT / 'runs' / RELATIVE), str(archived))
    # Preserve the first model response; retry only the interrupted repair call.
    restored = OUT / 'runs' / RELATIVE
    restored.mkdir(parents=True)
    shutil.copytree(archived / 'call-1', restored / 'call-1')
    value = {'source': str(SOURCE), 'archived': str(RELATIVE),
             'reason': '2026-11-12 authorized continuation; unchanged repair context, no provider/parameter change.',
             'replayed_call_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (restored / 'call-1').iterdir()},
             'copied_record_sha256': {str(p.relative_to(OUT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                      for p in (OUT / 'runs').rglob('record.json')}}
    target.write_text(json.dumps(value, indent=2) + '\n')


def main():
    prepare()
    cfg = json.loads((SOURCE / 'review-manifest.json').read_text())['config']
    cfg.update(budget_usd=.25, stop_new_requests_usd=.20)
    files = ['test/webbench_dna/finish_clean_prefix.py', 'test/webbench_dna/clean_prefix.py',
             'test/webbench_dna/run.py', 'test/webbench_dna/domain.py', 'test/webbench_dna/library.py',
             'test/provider_ext.py']
    freeze(OUT, cfg, files, {'source': str(SOURCE), 'candidate': str(RELATIVE), 'same_first_response': True,
                            'daily_authorization': '$20 on 2026-11-12; this stage cap $0.25'})
    ledgers = [ROOT / 'artifacts/webbench-dna-clean/budget.sqlite3', SOURCE / 'budget.sqlite3']
    provider = provider_for(cfg, Ledger(OUT / 'budget.sqlite3', .25, .20), ledgers)
    control.OUT = OUT
    task = next(t for t in domain.tasks() if t['id'] == 'task-16')
    control.run_model('free_clean', control.MODELS[0], [task], library(), provider)
    path = OUT / 'runs' / RELATIVE / 'record.json'
    grade_record(path)

    class Combined:
        def summary(self):
            rows = [row for ledger in [*ledgers, OUT / 'budget.sqlite3'] for row in calls(ledger)]
            return {'calls': rows, 'actual_usd': sum(r['actual'] or 0 for r in rows) / 1e6,
                    'unsettled_calls': sum(r['actual'] is None for r in rows)}
    control.summarise(Combined(), domain.tasks())


if __name__ == '__main__':
    main()
