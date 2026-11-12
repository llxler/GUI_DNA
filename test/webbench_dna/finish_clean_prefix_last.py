"""Repeat the transport-incomplete repair using SSE, with unchanged model messages."""
from __future__ import annotations
import json
import shutil
from pathlib import Path

from gui_dna.budget import Ledger
from test.ledger_read import calls
from test.review_stage import freeze
from test.streaming_provider import StreamingOpenRouter
from . import finish_clean_prefix as prior, clean_prefix as control, domain
from .library import library
from .review_evaluate import grade_record


def main():
    prior.SOURCE = domain.ROOT / 'artifacts/webbench-dna-clean-4'
    prior.OUT = domain.ROOT / 'artifacts/webbench-dna-clean-5'
    prior.prepare()
    restored = prior.OUT / 'runs' / prior.RELATIVE / 'call-2'
    if not restored.exists():
        shutil.copytree(prior.SOURCE / 'runs' / prior.RELATIVE / 'call-2', restored)
    out = prior.OUT
    cfg = json.loads((prior.SOURCE / 'review-manifest.json').read_text())['config']
    cfg.update(budget_usd=.10, stop_new_requests_usd=.09)
    freeze(out, cfg, ['test/webbench_dna/finish_clean_prefix_last.py', 'test/webbench_dna/finish_clean_prefix.py',
        'test/webbench_dna/clean_prefix.py', 'test/webbench_dna/run.py', 'test/webbench_dna/domain.py',
        'test/webbench_dna/library.py', 'test/streaming_provider.py', 'test/provider_ext.py'],
        {'source': str(prior.SOURCE), 'candidate': str(prior.RELATIVE), 'sampling_unchanged': True,
         'transport_change': 'Replay first TWO settled truncated responses; retry only final interrupted repair, same SSE and sampling parameters.',
         'stage_cap_usd': .10})
    earlier = [domain.ROOT / f'artifacts/{name}/budget.sqlite3' for name in
               ['webbench-dna-clean', 'webbench-dna-clean-2', 'webbench-dna-clean-3', 'webbench-dna-clean-4']]
    old_calls = [c for ledger in earlier for c in calls(ledger)]
    current = Ledger(out / 'budget.sqlite3', .10, .09)

    class Replay:
        def __getattr__(self, name):
            return getattr(current, name)
        def summary(self):
            value = current.summary()
            return {**value, 'calls': [*value['calls'], *old_calls]}

    provider = StreamingOpenRouter(cfg, Replay())
    control.OUT = out
    task = next(t for t in domain.tasks() if t['id'] == 'task-16')
    control.run_model('free_clean', control.MODELS[0], [task], library(), provider)
    grade_record(out / 'runs' / prior.RELATIVE / 'record.json')

    class Combined:
        def summary(self):
            rows = [*old_calls, *calls(out / 'budget.sqlite3')]
            return {'calls': rows, 'actual_usd': sum(c['actual'] or 0 for c in rows)/1e6,
                    'unsettled_calls': sum(c['actual'] is None for c in rows)}
    control.summarise(Combined(), domain.tasks())


if __name__ == '__main__':
    main()
