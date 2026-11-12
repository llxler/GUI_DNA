"""Formal interface-blind comparison with a preloaded-library unrestricted baseline.

Public-only pilots are retained; no candidate hidden scores informed this change.
"""
from __future__ import annotations

import argparse
import json
import shutil
from concurrent.futures import ThreadPoolExecutor
import hashlib
import subprocess
from gui_dna.budget import BudgetStop
from gui_dna.provider import ProviderError, parse_json
from pathlib import Path
from gui_dna.budget import Ledger

from test.interface_blind.core import (ROOT, PROJECTS, BUILDERS, SEED, config, digest, dump, requirements, slug,
    compile_plan, planner_messages, public_check, write_files)
from test.interface_blind.run import BUILD_OUT, RUN_OUT, frozen_inputs, provider
from test.streaming_provider import StreamingOpenRouter

from test.interface_blind_run_helpers import candidate

MODELS = ('openai/gpt-oss-120b', 'mistralai/mistral-small-3.2-24b-instruct')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=12)
    parser.add_argument('--out', type=Path, default=ROOT / 'artifacts/interface-blind-preloaded')
    parser.add_argument('--build-out', type=Path, default=ROOT / 'artifacts/interface-blind-build-2')
    args = parser.parse_args()
    out = args.out.resolve()
    if (out / 'grading-started.json').exists():
        raise ValueError('Hidden grading started; no further generation in this stage')
    build_out = args.build_out.resolve()
    barrier = build_out / 'build-complete.json'
    if not barrier.exists():
        raise ValueError('All library attempts must finish first')
    source = ROOT / 'artifacts/interface-blind-run-2'
    if not (out / 'continuation.json').exists():
        from test.ledger_read import totals
        if totals(source / 'budget.sqlite3')['stop_usd'] != 0:
            raise ValueError('Prior generation must be closed before continuation')
        copied = []
        for path in (source / 'runs').rglob('record.json'):
            record = json.loads(path.read_text())
            if record['method'] in ('free', 'plan') and record['status'] == 'complete':
                relative = path.parent.relative_to(source / 'runs')
                shutil.copytree(path.parent, out / 'runs' / relative)
                copied.append(str(relative))
        dump(out / 'continuation.json', {'source': str(source), 'copied_complete_free_and_plan': copied,
            'method_change': 'Preload the same frozen file map for free_lib. Regenerate ALL free_lib candidates, regardless of public success. No hidden scores seen.',
            'other_incomplete': 'All incomplete outputs remain archived in source; generate fresh in this stage.'})
    cfg = config(False)
    cfg.update(budget_usd=3.0, stop_new_requests_usd=2.8)
    cfg['provider_order']['mistralai/mistral-small-3.2-24b-instruct'] = ['Parasail']
    cfg['models'] = list(MODELS)
    cfg['model_price_caps']['openai/gpt-oss-120b'] = {'prompt': .2, 'completion': .7}
    cfg['reasoning_effort']['openai/gpt-oss-120b'] = 'low'
    extras = [Path(__file__).resolve(), ROOT / 'test/streaming_provider.py', source / 'review-manifest.json', ROOT / 'test/interface_blind_run_helpers.py', out / 'continuation.json', barrier]
    packages = {}
    for project in PROJECTS:
        for builder in BUILDERS:
            folder = build_out / 'libraries' / project / slug(builder)
            record = json.loads((folder / 'record.json').read_text())
            extras.append(folder / 'record.json')
            if record['status'] == 'frozen':
                package = json.loads((folder / 'package.json').read_text())
                assert digest(package) == record['package_sha256']
                packages[project, builder] = package
                extras.append(folder / 'package.json')
    protocol = {'projects': PROJECTS, 'builders': BUILDERS, 'planners': MODELS,
        'cohort_change_before_first_planner_call': 'Qwen JSON-compatible SiliconFlow endpoint again failed the historical task-16 repair. Replace Qwen by GPT-OSS-120B for the entire new study; no hidden library scores seen.',
        'input': 'Public tasks.jsonl only; no human schema, reference, tests, or shell.',
        'feedback': 'JSON/compiler/load errors only; max 2 repairs; same 12000-token cap.',
        'selection': 'All first public-valid builder outputs, unchanged.',
        'generation': '20 cumulative tasks from scratch, one seed; free reused across builders; free_lib inherits library files and may override any.',
        'phase': 'generate', 'method_change': 'Preloaded frozen files for unrestricted free_lib; return new/modified files only. The plan and free protocols are unchanged. No hidden scores seen.', 'transport': 'SSE streaming, terminal usage.cost required; same sampling and JSON parameters.',
        'daily_authorization': '$20; both pilot planner ledgers closed at stop=0. New planner cap $3, public-feedback cap $3 reserved separately.'}
    frozen_inputs(out, cfg, protocol, extras)
    client = StreamingOpenRouter(cfg, Ledger(out / 'budget.sqlite3', cfg['budget_usd'], cfg['stop_new_requests_usd']))
    jobs = []
    for project in PROJECTS:
        for task in requirements(project)[1:]:
            for model in MODELS:
                jobs.append((project, None, model, 'free', task['id'], None))
                for builder in BUILDERS:
                    if (project, builder) in packages:
                        for method in ('free_lib', 'plan'):
                            jobs.append((project, builder, model, method, task['id'], packages[project, builder]))
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        records = list(pool.map(lambda j: candidate(client, out, *j), jobs))
    dump(out / 'generation-complete.json', {'candidates': len(records), 'records_sha256': digest(records),
                                           'transport_incomplete': sum(r['status'] != 'complete' for r in records)})


if __name__ == '__main__':
    main()
