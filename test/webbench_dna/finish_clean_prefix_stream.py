"""Repeat the transport-incomplete repair using SSE, with unchanged model messages."""
from __future__ import annotations
import json
from pathlib import Path

from gui_dna.budget import Ledger
from test.ledger_read import calls
from test.review_stage import freeze
from test.streaming_provider import StreamingOpenRouter
from . import finish_clean_prefix as prior, clean_prefix as control, domain
from .library import library
from .review_evaluate import grade_record


def main():
    prior.SOURCE = domain.ROOT / 'artifacts/webbench-dna-clean-3'
    prior.OUT = domain.ROOT / 'artifacts/webbench-dna-clean-4'
    prior.prepare()
    out = prior.OUT
    cfg = json.loads((prior.SOURCE / 'review-manifest.json').read_text())['config']
    cfg.update(budget_usd=.25, stop_new_requests_usd=.20)
    freeze(out, cfg, ['test/webbench_dna/finish_clean_prefix_stream.py', 'test/webbench_dna/finish_clean_prefix.py',
        'test/webbench_dna/clean_prefix.py', 'test/webbench_dna/run.py', 'test/webbench_dna/domain.py',
        'test/webbench_dna/library.py', 'test/streaming_provider.py', 'test/provider_ext.py'],
        {'source': str(prior.SOURCE), 'candidate': str(prior.RELATIVE), 'sampling_unchanged': True,
         'transport_change': 'stream=true; retain raw SSE; require terminal billed usage; replay first response.',
         'daily_cap_allocation_usd': 16.5})
    earlier = [domain.ROOT / f'artifacts/{name}/budget.sqlite3' for name in
               ['webbench-dna-clean', 'webbench-dna-clean-2', 'webbench-dna-clean-3']]
    old_calls = [c for ledger in earlier for c in calls(ledger)]
    current = Ledger(out / 'budget.sqlite3', .25, .20)

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
