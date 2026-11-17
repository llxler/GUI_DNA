"""Continue the review control in a new ledger after shared-provider rate limits.

Keep all prior candidates; archive transport failures and interrupted candidates.
The Mistral model ID is unchanged, but new requests explicitly route to Mistral.
This provider change is recorded and is a limitation of the cross-stage comparison.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from gui_dna.budget import Ledger
from test.ledger_read import ReadOnlyLedger, calls
from test.rerun_failed import affected
from test.review_stage import freeze, provider_for
from . import clean_prefix as control, domain, run
from .library import library


def prepare(source, out):
    target = out / 'continuation.json'
    if target.exists():
        if json.loads(target.read_text())['source'] != str(source):
            raise ValueError('continuation source changed')
        return
    if out.exists() and any(out.iterdir()):
        raise ValueError('new continuation directory must be empty')
    out.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source / 'runs', out / 'runs')
    moves = affected(out, 'webbench')
    for folder in (out / 'runs').glob('*/*/task-*'):
        if not (folder / 'record.json').exists():
            moves.append((folder, 'interrupted before a complete record was written'))
    archived = []
    for folder, reason in moves:
        if not folder.exists():
            continue
        rel = folder.relative_to(out / 'runs')
        destination = out / 'discarded-transport/continuation' / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(folder), str(destination))
        archived.append({'path': str(rel), 'reason': reason})
    records = {str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in (out / 'runs').rglob('record.json')}
    target.write_text(json.dumps({'source': str(source), 'archived': archived, 'copied_record_hashes': records,
                                 'reason': 'Mistral DeepInfra shared pool repeatedly returned HTTP 429'}, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=domain.ROOT / 'artifacts/webbench-dna-clean')
    parser.add_argument('--out', type=Path, default=domain.ROOT / 'artifacts/webbench-dna-clean-2')
    parser.add_argument('--no-generate', action='store_true')
    parser.add_argument('--threads', type=int, default=6)
    args = parser.parse_args()
    source, out = args.source.resolve(), args.out.resolve()
    prepare(source, out)
    control.OUT = out
    config = json.loads((source / 'review-manifest.json').read_text())['config']
    config.update(budget_usd=.85, stop_new_requests_usd=.8,
                  provider_order={'mistralai/mistral-small-3.2-24b-instruct': ['Mistral']})
    freeze(out, config, ['test/webbench_dna/continue_clean_prefix.py', 'test/webbench_dna/clean_prefix.py',
                        'test/webbench_dna/domain.py', 'test/webbench_dna/run.py', 'test/webbench_dna/library.py'],
           {'source_manifest_sha256': hashlib.sha256((source / 'review-manifest.json').read_bytes()).hexdigest(),
            'source': str(source), 'arms': control.ARMS,
            'change': 'New Mistral requests route to official Mistral; copied outputs retain original provider.'})
    ledger = ReadOnlyLedger(out / 'budget.sqlite3') if args.no_generate else Ledger(out / 'budget.sqlite3', .85, .8)
    tasks, lib = domain.tasks(), library()
    if not args.no_generate:
        provider = provider_for(config, ledger, [source / 'budget.sqlite3'])
        jobs = [(m, a) for a in control.ARMS for m in control.MODELS]
        with ThreadPoolExecutor(max_workers=args.threads) as pool:
            for pair, _ in zip(jobs, pool.map(lambda pair: control.run_model(pair[1], pair[0], tasks, lib, provider), jobs)):
                print(*pair, 'generation complete', flush=True)

    class CombinedReadLedger:
        def summary(self):
            rows = calls(source / 'budget.sqlite3') + calls(out / 'budget.sqlite3')
            return {'calls': rows, 'actual_usd': sum(c['actual'] or 0 for c in rows) / 1e6,
                    'unsettled_calls': sum(c['actual'] is None for c in rows)}

    # Grade serially: the unchanged Web-Bench runner owns one shared output directory.
    for model in control.MODELS:
        for arm in control.ARMS:
            for task in tasks:
                folder = out / 'runs' / run.slug(model) / arm / task['id']
                path = folder / 'record.json'
                if path.exists():
                    run.grade_record(json.loads(path.read_text()), folder, task, False)
    control.summarise(CombinedReadLedger(), tasks)


if __name__ == '__main__':
    main()
