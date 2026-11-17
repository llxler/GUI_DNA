"""Continue the identical frontier cohort in a new, smaller budget ledger."""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from test.ledger_read import totals
from .core import ROOT, PROJECTS, BUILDERS, digest, dump, slug
from .run import frozen_inputs, provider
from .frontier import BUILD, MODEL, TASKS, settings
from . import generate

SOURCE = ROOT / 'artifacts/webbench-expand-frontier'
OUT = ROOT / 'artifacts/webbench-expand-frontier-2'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args()
    assert totals(SOURCE / 'budget.sqlite3')['stop_usd'] == 0
    assert not (SOURCE / 'grading-started.json').exists() and not (OUT / 'grading-started.json').exists()
    receipt = OUT / 'continuation.json'
    if not receipt.exists():
        copied = []
        for path in sorted((SOURCE / 'runs').rglob('record.json')):
            relative = path.parent.relative_to(SOURCE / 'runs')
            shutil.copytree(path.parent, OUT / 'runs' / relative)
            record = json.loads(path.read_text())
            copied.append({'path': str(relative), 'record_sha256': digest(record), 'status': record['status']})
        dump(receipt, {'source': str(SOURCE.relative_to(ROOT)), 'copied': copied,
            'policy': 'Copy every saved candidate, including all complete failures and incomplete prefixes. Resume missing attempts only. Unchanged models/providers/messages/limits; old ledger remains closed with all reservations.'})
    generate.OUT = OUT
    cfg = settings()
    cfg.update(budget_usd=2, stop_new_requests_usd=1.8)
    packages = {}
    extras = [Path(__file__).resolve(), Path(__file__).with_name('frontier.py'), Path(generate.__file__),
        Path(__file__).with_name('resume.py'), Path(__file__).with_name('free_build.cjs'),
        Path(__file__).with_name('FRONTIER.md'), Path(__file__).with_name('PRELOAD.md'),
        SOURCE / 'review-manifest.json', receipt, BUILD / 'build-complete.json']
    for project in PROJECTS:
        for builder in BUILDERS:
            folder = BUILD / 'libraries' / project / slug(builder)
            package = json.loads((folder / 'package.json').read_text())
            assert digest(package) == json.loads((folder / 'record.json').read_text())['package_sha256']
            packages[project, builder] = package
            extras.extend([folder / 'package.json', folder / 'record.json'])
    frozen_inputs(OUT, cfg, {'phase': 'frontier-budget-continuation', 'original_protocol': str(SOURCE.relative_to(ROOT)),
        'change': 'Only budget ledger and concurrency; every valid attempt and feedback retained. Same60-candidate cohort, no extra samples.',
        'budget': 'Closed old frontier exposure3.984886 plus newcap2; daily worstcase16.979706 <20.',
        'tasks': list(TASKS), 'model': MODEL}, extras)
    client = provider(cfg, OUT)
    jobs = [(project, builder, MODEL, method, f'task-{task}', packages[project, builder])
            for project in PROJECTS for task in TASKS for builder in BUILDERS for method in ('free_lib', 'plan')]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        records = list(pool.map(lambda job: generate.candidate(client, *job, resume=True), jobs))
    if any(r['status'] != 'complete' for r in records):
        raise ValueError('Missing frontier transports remain; rerun unchanged continuation')
    dump(OUT / 'generation-complete.json', {'candidates': len(records), 'records_sha256': digest(records), 'transport_incomplete': 0})


if __name__ == '__main__':
    main()
