"""Evaluate the fixed configurations specified before any new model calls."""
from __future__ import annotations
import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from .core import ROOT, PROJECTS, BUILDERS, PLANNERS, slug, dump, digest, compile_plan, write_files
from .evaluate_pinned import prepare, grade

BUILD = ROOT / 'artifacts/webbench-expand-build'
BASE = ROOT / 'artifacts/webbench-expand-run'
OUT = ROOT / 'artifacts/webbench-expand-controls'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=6)
    args = parser.parse_args()
    barrier = json.loads((BASE / 'generation-complete.json').read_text())
    assert barrier['transport_incomplete'] == 0
    protocol = {'selection': 'Both documentation examples, separately; each planner task-20 last executable page, regardless of scores. Fixed before calls in frozen README and generation manifest.',
                'generation_sha256': digest(barrier), 'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'evaluator_sha256': hashlib.sha256(Path(__file__).with_name('evaluate_pinned.py').read_bytes()).hexdigest(),
                'evaluation_protocol_sha256': hashlib.sha256(Path(__file__).with_name('EVALUATION.md').read_bytes()).hexdigest(),
                'not_claimed': 'Not a uniform random baseline, reachable upper bound, or heldout-composition test.'}
    target = OUT / 'protocol.json'
    if target.exists():
        assert json.loads(target.read_text()) == protocol
    else:
        dump(target, protocol)
    prepare()
    jobs, sources = [], []
    for project in PROJECTS:
        for builder in BUILDERS:
            library = BUILD / 'libraries' / project / slug(builder)
            record = json.loads((library / 'record.json').read_text())
            if record['status'] != 'frozen':
                sources.append({'project': project, 'builder': builder, 'unavailable': record['status']})
                continue
            package = json.loads((library / 'package.json').read_text())
            assert digest(package) == record['package_sha256']
            options = []
            for index, example in enumerate(package['examples']):
                files = compile_plan(package, example['plan'])
                page = OUT / 'pages' / project / slug(builder) / f'example-{index}'
                write_files(page, files)
                options.append((f'example-{index}', None, page))
            for model in PLANNERS:
                source = BASE / 'runs' / project / slug(builder) / slug(model) / 'plan/task-20'
                result = json.loads((source / 'record.json').read_text())
                assert result['status'] == 'complete'
                page = source / result['versions'][-1] if result['versions'] else None
                if page:
                    manifest = json.loads((page / 'source-manifest.json').read_text())
                    assert all(hashlib.sha256((page / name).read_bytes()).hexdigest() == sha for name, sha in manifest['files_sha256'].items())
                options.append(('final-plan', model, page))
            for control, model, page in options:
                sources.append({'project': project, 'builder': builder, 'control': control, 'model': model,
                                'page': str(page.relative_to(ROOT)) if page else None})
                jobs.extend((project, builder, control, model, page, f'task-{k}') for k in range(1, 21))
    dump(OUT / 'sources.json', sources)

    def one(job):
        project, builder, control, model, page, task = job
        folder = OUT / 'scores' / project / slug(builder) / control / (slug(model) if model else 'none') / task
        score = folder / 'hidden.json'
        if not score.exists():
            value = grade(project, page, task, folder / 'report.json') if page else {'all_passed': False, 'reason': 'No executable final plan'}
            dump(score, value)
        return {'project': project, 'builder': builder, 'control': control, 'model': model, 'task': task,
                'passed': bool(json.loads(score.read_text())['all_passed'])}

    rows = []
    for project in PROJECTS:
        selected = [job for job in jobs if job[0] == project]
        with ThreadPoolExecutor(max_workers=1 if project == 'bom' else args.workers) as pool:
            for i, row in enumerate(pool.map(one, selected), 1):
                rows.append(row)
                if i % 20 == 0:
                    print(f'fixed controls {project} {i}/{len(selected)}', flush=True)
    dump(OUT / 'results.json', {'protocol': protocol, 'sources': sources, 'rows': rows})
    dump(OUT / 'complete.json', {'scores': len(rows), 'rows_sha256': digest(rows)})


if __name__ == '__main__':
    main()
