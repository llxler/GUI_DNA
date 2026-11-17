"""Retry the single transport-incomplete builder; never select by hidden score."""
from __future__ import annotations
import json
import shutil
from pathlib import Path

from gui_dna.budget import Ledger
from test.interface_blind.core import ROOT, BUILDERS, PROJECTS, config, digest, dump, slug
from test.interface_blind.run import BUILD_OUT, build_one, frozen_inputs
from test.long_request_provider import LongRequestOpenRouter

OUT = ROOT / 'artifacts/interface-blind-build-2'


def main():
    if not (OUT / 'continuation.json').exists():
        OUT.mkdir(parents=True, exist_ok=True)
        shutil.copytree(BUILD_OUT / 'libraries', OUT / 'libraries')
        archived = []
        for p in (OUT / 'libraries').glob('*/*/record.json'):
            record = json.loads(p.read_text())
            if record['status'] == 'transport_incomplete':
                relative = p.parent.relative_to(OUT / 'libraries')
                dest = OUT / 'discarded-transport/1' / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(p.parent), str(dest))
                archived.append(str(relative))
        dump(OUT / 'continuation.json', {'source': str(BUILD_OUT), 'archived': archived,
            'change': 'HTTP read timeout 300 to 900 seconds; request body unchanged; no hidden scores available.'})
    cfg = config(True)
    cfg.update(budget_usd=1.5, stop_new_requests_usd=1.4)
    frozen_inputs(OUT, cfg, {'phase': 'builder-transport-continuation', 'source': str(BUILD_OUT),
        'read_timeout_seconds': 900, 'generation_parameters_unchanged': True, 'daily_cap_allocation_usd': 16.25},
        [Path(__file__).resolve(), ROOT / 'test/long_request_provider.py', BUILD_OUT / 'review-manifest.json'])
    client = LongRequestOpenRouter(cfg, Ledger(OUT / 'budget.sqlite3', 1.5, 1.4))
    records = [build_one(client, OUT, project, builder) for project in PROJECTS for builder in BUILDERS]
    dump(OUT / 'build-complete.json', {'records': records, 'sha256': digest(records), 'hidden_feedback': False,
                                      'extra_ledgers': [str(BUILD_OUT / 'budget.sqlite3')]})


if __name__ == '__main__':
    main()
