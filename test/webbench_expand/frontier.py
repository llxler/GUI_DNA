"""Separately budgeted GPT-5 medium-reasoning matched-library pilot."""
from __future__ import annotations
import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from .core import ROOT, PROJECTS, BUILDERS, config, digest, dump, slug
from .run import frozen_inputs, provider
from . import generate

OUT = ROOT / 'artifacts/webbench-expand-frontier'
BUILD = ROOT / 'artifacts/webbench-expand-build'
TASKS = (4, 8, 12, 16, 20)
MODEL = 'openai/gpt-5'


def settings():
    cfg = config(False)
    cfg.update(models=[MODEL], budget_usd=4.5, stop_new_requests_usd=4.3)
    cfg['reasoning_effort'] = {MODEL: 'medium'}
    cfg['provider_order'] = {MODEL: ['OpenAI']}
    return cfg


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--resume-transport', action='store_true')
    args = parser.parse_args()
    assert not (OUT / 'grading-started.json').exists()
    generate.OUT = OUT  # Process-local destination; frozen base source is unchanged.
    packages = {}
    extras = [BUILD / 'build-complete.json', Path(__file__).resolve(),
        Path(__file__).with_name('FRONTIER.md'), Path(generate.__file__),
        Path(__file__).with_name('PRELOAD.md'), Path(__file__).with_name('resume.py'),
        Path(__file__).with_name('free_build.cjs'), ROOT / 'artifacts/webbench-expand-run/review-manifest.json']
    for project in PROJECTS:
        for builder in BUILDERS:
            folder = BUILD / 'libraries' / project / slug(builder)
            record = json.loads((folder / 'record.json').read_text())
            assert record['status'] == 'frozen'
            package = json.loads((folder / 'package.json').read_text())
            assert digest(package) == record['package_sha256']
            packages[project, builder] = package
            extras.extend([folder / 'record.json', folder / 'package.json'])
    cfg = settings()
    frozen_inputs(OUT, cfg, {'scope': 'P4b normal-reasoning pilot, separate from 600-candidate primary cohort; one model, no multi-seed claim.',
        'model': MODEL, 'reasoning': 'medium', 'provider': 'OpenAI', 'tasks': list(TASKS),
        'selection': 'Every fourth task chosen before any candidate hidden score; no library or prompt changes.',
        'methods': ['free_lib', 'plan'], 'user_inputs': 'Exactly the same as the primary matched-library cohort.',
        'limits': '12000 output tokens including reasoning, at most2 public format/load repairs, no behavioral feedback.',
        'controls': 'Reuse both builder examples on these five tasks, and reuse this planner task20 last executable page unchanged on the five tasks.',
        'budget': 'Newcap4.5; combined daily worstcase15.49482 <20.'}, extras)
    client = provider(cfg, OUT)
    jobs = [(project, builder, MODEL, method, f'task-{task}', packages[project, builder])
            for project in PROJECTS for task in TASKS for builder in BUILDERS for method in ('free_lib', 'plan')]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        records = list(pool.map(lambda job: generate.candidate(client, *job, resume=args.resume_transport), jobs))
    if any(r['status'] != 'complete' for r in records):
        raise ValueError('Incomplete frontier transports remain; resume before grading')
    dump(OUT / 'generation-complete.json', {'candidates': len(records), 'records_sha256': digest(records), 'transport_incomplete': 0})


if __name__ == '__main__':
    main()
