"""Complete transport-missing candidates in a new ledger, before hidden scoring."""
from __future__ import annotations
import argparse
import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from gui_dna.budget import Ledger
from test.interface_blind.core import ROOT, PROJECTS, BUILDERS, digest, dump, requirements, slug
from test.interface_blind.run import frozen_inputs
from test.interface_blind_run_helpers import candidate
from test.streaming_provider import StreamingOpenRouter


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'artifacts/interface-blind-preloaded')
    parser.add_argument('--out', type=Path, default=ROOT / 'artifacts/interface-blind-final')
    parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--archive-transport', action='store_true', help='Archive only this stage\'s remaining transport failures and retry with the same frozen inputs and cap')
    args = parser.parse_args()
    source, out = args.source.resolve(), args.out.resolve()
    if not (source / 'generation-complete.json').exists():
        raise ValueError('Source generation must finish first')
    if (source / 'grading-started.json').exists() or (out / 'grading-started.json').exists():
        raise ValueError('Transport completion must precede hidden scoring')
    old = json.loads((source / 'review-manifest.json').read_text())
    if args.archive_transport:
        numbers = [int(p.name) for p in (out / 'discarded-transport').glob('[0-9]*')]
        batch = out / 'discarded-transport' / str(max(numbers, default=0) + 1)
        moved = []
        for path in (out / 'runs').rglob('record.json'):
            if json.loads(path.read_text())['status'] != 'transport_incomplete':
                continue
            relative = path.parent.relative_to(out / 'runs')
            destination = batch / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path.parent), str(destination))
            moved.append(str(relative))
        if moved:
            dump(batch / 'archive.json', {'reason': 'Transport failures only; complete model outputs, including behavioral failures, retained.', 'candidates': moved})
            barrier = out / 'generation-complete.json'
            if barrier.exists():
                shutil.move(str(barrier), str(batch / 'generation-complete.json'))
        print(f'archived {len(moved)} transport-incomplete candidates', flush=True)
    if not (out / 'continuation.json').exists():
        copied, archived = [], []
        for path in (source / 'runs').rglob('record.json'):
            record = json.loads(path.read_text())
            relative = path.parent.relative_to(source / 'runs')
            if record['status'] == 'complete':
                destination = out / 'runs' / relative
                copied.append(str(relative))
            else:
                destination = out / 'discarded-transport/1' / relative
                archived.append(str(relative))
            shutil.copytree(path.parent, destination)
        dump(out / 'continuation.json', {'source': str(source), 'copied_complete': copied, 'archived': archived,
            'policy': 'Retry every transport-incomplete candidate with unchanged initial inputs, seed, output cap, provider and repair budget. Preserve all prior attempts. No hidden results available.'})
    cfg = old['config']
    # Close the old ledger through its supported tightening-only constructor.
    Ledger(source / 'budget.sqlite3', cfg['budget_usd'], 0)
    cfg = {**cfg, 'budget_usd': 2.0, 'stop_new_requests_usd': 1.8}
    build = ROOT / 'artifacts/interface-blind-build-2'
    packages = {}
    extras = [Path(__file__).resolve(), ROOT / 'test/interface_blind_run_helpers.py', ROOT / 'test/streaming_provider.py',
              source / 'review-manifest.json', source / 'generation-complete.json', out / 'continuation.json']
    for project in PROJECTS:
        for builder in BUILDERS:
            path = build / 'libraries' / project / slug(builder)
            package = json.loads((path / 'package.json').read_text())
            assert digest(package) == json.loads((path / 'record.json').read_text())['package_sha256']
            packages[project, builder] = package
            extras.append(path / 'package.json')
    frozen_inputs(out, cfg, {'phase': 'transport-completion', 'source': str(source),
                            'methods': ['free', 'free_lib', 'plan'], 'preloaded_library': True,
                            'request_parameters_unchanged': True, 'daily_authorization_usd': 20}, extras)
    client = StreamingOpenRouter(cfg, Ledger(out / 'budget.sqlite3', 2.0, 1.8))
    jobs = []
    for project in PROJECTS:
        for task in requirements(project)[1:]:
            for model in cfg['models']:
                jobs.append((project, None, model, 'free', task['id'], None))
                for builder in BUILDERS:
                    for method in ('free_lib', 'plan'):
                        jobs.append((project, builder, model, method, task['id'], packages[project, builder]))
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        records = list(pool.map(lambda job: candidate(client, out, *job), jobs))
    dump(out / 'generation-complete.json', {'candidates': len(records), 'records_sha256': digest(records),
                                           'transport_incomplete': sum(r['status'] != 'complete' for r in records)})


if __name__ == '__main__':
    main()
