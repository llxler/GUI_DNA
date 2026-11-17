"""Replace the entire failing-provider cohort before any candidate hidden scoring."""
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
from test.streaming_provider_v2 import StreamingOpenRouter
from test.ledger_read import totals

SOURCE = ROOT / 'artifacts/interface-blind-final'
OUT = ROOT / 'artifacts/interface-blind-final-2'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=6)
    parser.add_argument('--archive-transport', action='store_true')
    args = parser.parse_args()
    if (SOURCE / 'grading-started.json').exists() or (OUT / 'grading-started.json').exists():
        raise ValueError('Provider change must precede hidden scoring')
    if totals(SOURCE / 'budget.sqlite3')['stop_usd'] != 0:
        raise ValueError('Prior provider stage must be closed first')
    if args.archive_transport:
        numbers = [int(p.name) for p in (OUT / 'discarded-transport').glob('[0-9]*')]
        batch = OUT / 'discarded-transport' / str(max(numbers, default=0) + 1)
        moved = []
        for path in list((OUT / 'runs').rglob('record.json')):
            if json.loads(path.read_text())['status'] != 'transport_incomplete':
                continue
            relative = path.parent.relative_to(OUT / 'runs')
            destination = batch / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path.parent), str(destination))
            moved.append(str(relative))
        if moved:
            dump(batch / 'archive.json', {'candidates': moved, 'policy': 'Only incomplete transports; unchanged inputs and provider; all complete model failures retained.'})
            barrier = OUT / 'generation-complete.json'
            if barrier.exists():
                shutil.move(str(barrier), str(batch / 'generation-complete.json'))
    if not (OUT / 'continuation.json').exists():
        copied = []
        for path in SOURCE.glob('runs/**/record.json'):
            record = json.loads(path.read_text())
            if record['model'] != 'openai/gpt-oss-120b' or record['status'] != 'complete':
                continue
            relative = path.parent.relative_to(SOURCE / 'runs')
            shutil.copytree(path.parent, OUT / 'runs' / relative)
            copied.append(str(relative))
        dump(OUT / 'continuation.json', {'source': str(SOURCE), 'copied_complete_gpt_oss': copied,
            'policy': 'Regenerate the ENTIRE Mistral cohort, including all complete passes/failures from public checks, through DeepInfra FP8. Parasail streams repeatedly terminate with provider error; endpoint catalog reports 0% recent uptime. No candidate hidden scores seen. Original source records and ledgers retained.'})
    cfg = json.loads((SOURCE / 'review-manifest.json').read_text())['config']
    cfg.update(budget_usd=2, stop_new_requests_usd=1.8)
    cfg['provider_order']['mistralai/mistral-small-3.2-24b-instruct'] = ['DeepInfra']
    build = ROOT / 'artifacts/interface-blind-build-2'
    extras = [Path(__file__).resolve(), ROOT / 'test/interface_blind_run_helpers.py', ROOT / 'test/streaming_provider_v2.py',
              SOURCE / 'review-manifest.json', OUT / 'continuation.json', ROOT / 'artifacts/review-20261112/mistral-routing-status.json']
    packages = {}
    for project in PROJECTS:
        for builder in BUILDERS:
            folder = build / 'libraries' / project / slug(builder)
            package = json.loads((folder / 'package.json').read_text())
            assert digest(package) == json.loads((folder / 'record.json').read_text())['package_sha256']
            packages[project, builder] = package
            extras.append(folder / 'package.json')
    frozen_inputs(OUT, cfg, {'phase': 'whole-provider-cohort-replacement', 'source': str(SOURCE),
        'preloaded_library': True, 'methods': ['free', 'free_lib', 'plan'], 'daily_authorization_usd': 20,
        'change': 'All Mistral candidates use DeepInfra FP8; original Parasail BF16 cohort retained as incomplete pilot. Same model ID, messages, seed, temperature, output cap and repair budget. GPT-OSS completed records reused without selection by public success.'}, extras)
    client = StreamingOpenRouter(cfg, Ledger(OUT / 'budget.sqlite3', 2, 1.8))
    jobs = []
    for project in PROJECTS:
        for task in requirements(project)[1:]:
            for model in cfg['models']:
                jobs.append((project, None, model, 'free', task['id'], None))
                for builder in BUILDERS:
                    for method in ('free_lib', 'plan'):
                        jobs.append((project, builder, model, method, task['id'], packages[project, builder]))
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        records = list(pool.map(lambda job: candidate(client, OUT, *job), jobs))
    dump(OUT / 'generation-complete.json', {'candidates': len(records), 'records_sha256': digest(records),
        'transport_incomplete': sum(r['status'] != 'complete' for r in records)})


if __name__ == '__main__':
    main()
