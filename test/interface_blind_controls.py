"""Zero-API controls: reuse both builder documentation plans on every task."""
from __future__ import annotations
import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from test.interface_blind.core import ROOT, PROJECTS, BUILDERS, compile_plan, digest, dump, slug, write_files
from test.interface_blind.evaluate import grade, prepare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--build', type=Path, default=ROOT / 'artifacts/interface-blind-build-2')
    parser.add_argument('--stage', type=Path, default=ROOT / 'artifacts/interface-blind-final-2')
    args = parser.parse_args()
    if not (args.stage / 'generation-complete.json').exists():
        raise ValueError('Do not run hidden controls before all planning is complete')
    prepare()
    out = ROOT / 'artifacts/interface-blind-controls'
    jobs = []
    for project in PROJECTS:
        for builder in BUILDERS:
            path = args.build / 'libraries' / project / slug(builder) / 'package.json'
            if not path.exists():
                continue
            package = json.loads(path.read_text())
            for i, example in enumerate(package['examples']):
                folder = out / project / slug(builder) / f'example-{i}'
                files = compile_plan(package, example['plan'])
                write_files(folder / 'page', files)
                dump(folder / 'control.json', {'project': project, 'builder': builder, 'example': i,
                    'plan': example['plan'], 'package_sha256': digest(package), 'files_sha256': digest(files),
                    'protocol': 'The same builder documentation plan is used unchanged for all 20 tasks; no task information or model calls.'})
                for k in range(1, 21):
                    jobs.append((project, builder, i, folder, f'task-{k}'))

    def one(job):
        project, builder, example, folder, task = job
        target = folder / task / 'hidden.json'
        if not target.exists():
            dump(target, grade(project, folder / 'page', task, folder / task / 'report.json'))
        return {'project': project, 'builder': builder, 'example': example, 'task': task,
                'all_passed': json.loads(target.read_text())['all_passed']}

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = []
        for i, row in enumerate(pool.map(one, jobs), 1):
            rows.append(row)
            if i % 10 == 0:
                print(f'constant-plan controls {i}/{len(jobs)}', flush=True)
    result = {'protocol': 'Two frozen builder examples, each reused unchanged across all task prefixes; no task-conditioned decisions.', 'rows': rows}
    result['groups'] = [{'project': p, 'builder': b, 'example': i,
                         'passed': sum(r['all_passed'] for r in rows if (r['project'], r['builder'], r['example']) == (p, b, i)),
                         'n': sum((r['project'], r['builder'], r['example']) == (p, b, i) for r in rows)}
                        for p in PROJECTS for b in BUILDERS for i in (0, 1)]
    dump(ROOT / 'test/results/interface-blind-controls.json', result)
    print(json.dumps(result['groups'], indent=2))


if __name__ == '__main__':
    main()
