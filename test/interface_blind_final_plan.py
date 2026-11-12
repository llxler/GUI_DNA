"""Post-hoc zero-API diagnostic: reuse each frozen task-20 plan on every prefix.

This is not a new model run or a best-of-plan selection. It checks the extra
value of per-task decisions when the library already sees the whole sequence.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from test.interface_blind.core import ROOT, BUILDERS, PROJECTS, digest, dump, slug
from test.interface_blind.evaluate import grade, prepare

BASE = ROOT / 'artifacts/interface-blind-final-2'
OUT = ROOT / 'artifacts/interface-blind-final-plan-replay'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args()
    assert (BASE / 'generation-complete.json').exists()
    models = json.loads((BASE / 'review-manifest.json').read_text())['config']['models']
    jobs, sources = [], []
    for project in PROJECTS:
        for builder in BUILDERS:
            for model in models:
                source = BASE / 'runs' / project / slug(builder) / slug(model) / 'plan/task-20'
                record = json.loads((source / 'record.json').read_text())
                assert record['status'] == 'complete' and record['versions']
                page = source / record['versions'][-1]
                manifest = json.loads((page / 'source-manifest.json').read_text())
                assert all(hashlib.sha256((page / n).read_bytes()).hexdigest() == sha for n, sha in manifest['files_sha256'].items())
                sources.append({'project': project, 'builder': builder, 'model': model,
                                'page': str(page.relative_to(ROOT)), 'files_sha256': manifest['files_sha256']})
                for k in range(1, 21):
                    jobs.append((project, builder, model, page, f'task-{k}'))
    protocol = {'scope': 'Post-hoc diagnostic designed after primary scores; no changes to primary candidates, libraries or generation.',
                'selection': 'Always the final executed plan from task 20, irrespective of its score; reuse unchanged on all 20 prefixes. One model decision, not zero model construction.',
                'sources': sources, 'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    target = OUT / 'protocol.json'
    if target.exists():
        assert json.loads(target.read_text()) == protocol
    else:
        dump(target, protocol)
    prepare()

    def one(job):
        project, builder, model, page, task = job
        folder = OUT / project / slug(builder) / slug(model) / task
        score = folder / 'hidden.json'
        if not score.exists():
            dump(score, grade(project, page, task, folder / 'report.json'))
        original = json.loads((BASE / 'runs' / project / slug(builder) / slug(model) / 'plan' / task / 'hidden.json').read_text())
        return {'project': project, 'builder': builder, 'model': model, 'task': task,
                'constant': bool(json.loads(score.read_text())['all_passed']),
                'per_task': bool(original['final']['all_passed'])}

    rows = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for i, row in enumerate(pool.map(one, jobs), 1):
            rows.append(row)
            if i % 10 == 0:
                print(f'fixed final-plan replay {i}/160', flush=True)
    groups = []
    for source in sources:
        selected = [r for r in rows if all(r[k] == source[k] for k in ('project', 'builder', 'model'))]
        groups.append({k: source[k] for k in ('project', 'builder', 'model')} | {
            'n': len(selected), 'constant': sum(r['constant'] for r in selected),
            'per_task': sum(r['per_task'] for r in selected),
            'per_task_won': sum(r['per_task'] and not r['constant'] for r in selected),
            'per_task_lost': sum(r['constant'] and not r['per_task'] for r in selected)})
    result = {'protocol': protocol['scope'] + ' ' + protocol['selection'], 'groups': groups, 'rows': rows}
    dump(ROOT / 'test/results/interface-blind-final-plan.json', result)
    dump(OUT / 'complete.json', {'scores': len(rows), 'rows_sha256': digest(rows)})
    print(json.dumps(groups, indent=2))


if __name__ == '__main__':
    main()
