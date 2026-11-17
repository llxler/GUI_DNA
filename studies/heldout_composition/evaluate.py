"""Hidden scoring only after both cohorts are complete and snapshotted."""
from __future__ import annotations
import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from test.interface_blind.core import ROOT, dump, digest
from .domain import heldout
from .fixtures import cases
from .browser import evaluate


def snapshot(stage):
    barrier = stage / 'generation-complete.json'
    assert json.loads(barrier.read_text())['transport_incomplete'] == 0
    target = stage / 'candidate-files-sha256.json'
    if target.exists():
        value = json.loads(target.read_text())
        assert value['generation_sha256'] == hashlib.sha256(barrier.read_bytes()).hexdigest()
        for name, sha in value['files'].items():
            assert hashlib.sha256((stage / name).read_bytes()).hexdigest() == sha
    else:
        assert not (stage / 'grading-started.json').exists()
        value = {'generation_sha256': hashlib.sha256(barrier.read_bytes()).hexdigest(),
                 'files': {str(p.relative_to(stage)): hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in sorted((stage / 'runs').rglob('*')) if p.is_file()}}
        dump(target, value)
    return value


def one(path):
    record = json.loads(path.read_text())
    assert record['status'] == 'complete'
    target = path.with_name('hidden.json')
    if target.exists():
        return
    task = next(t for t in heldout(record['project']) if t['id'] == record['task'])
    test_cases = cases(record['project'], task['policy'])
    versions = record['versions']
    if not versions:
        first = final = {'all_passed': False, 'reason': 'library unavailable' if record.get('unavailable_library') else 'no executable version'}
    else:
        def grade(version):
            folder = path.parent / version
            source = json.loads((folder / 'source-manifest.json').read_text())
            assert all(hashlib.sha256((folder / n).read_bytes()).hexdigest() == h for n, h in source['files_sha256'].items())
            outcome = evaluate(folder, record['project'], test_cases)
            dump(folder / 'hidden-report.json', outcome)
            return {'all_passed': outcome['all_passed'], 'cases_passed': outcome['cases_passed'], 'cases_total': outcome['cases_total'],
                    'report_sha256': hashlib.sha256((folder / 'hidden-report.json').read_bytes()).hexdigest(),
                    'output_sha256': source['output_sha256']}
        first = grade(versions[0])
        final = first if versions[0] == versions[-1] else grade(versions[-1])
    dump(target, {'first': first, 'final': final, 'cases_sha256': digest(test_cases)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--main-stage', type=Path, default=ROOT / 'artifacts/heldout-composition-run')
    parser.add_argument('--strong-stage', type=Path, default=ROOT / 'artifacts/heldout-composition-strong')
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    stages = [args.main_stage.resolve(), args.strong_stage.resolve()]
    for stage, expected in zip(stages, (220, 24)):
        barrier = json.loads((stage / 'generation-complete.json').read_text())
        assert barrier['candidates'] == expected and barrier['transport_incomplete'] == 0
        paths = sorted((stage / 'runs').rglob('record.json'))
        actual = {str(path.parent.relative_to(stage)): digest(json.loads(path.read_text())) for path in paths}
        assert len(paths) == expected and actual == barrier['records_by_path_sha256']
        manifest = json.loads((stage / 'review-manifest.json').read_text())
        for name, sha in manifest['sha256'].items():
            assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha, name
    for stage in stages:
        saved = snapshot(stage)
        dump(stage / 'grading-started.json', {'snapshot_sha256': digest(saved),
                                             'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                             'workers': args.workers, 'barrier': 'Both cohorts completed before hidden scoring'})
    for stage in stages:
        paths = sorted((stage / 'runs').rglob('record.json'))
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for i, _ in enumerate(pool.map(one, paths), 1):
                if i % 10 == 0 or i == len(paths):
                    print(stage.name, i, '/', len(paths), flush=True)
        dump(stage / 'grading-complete.json', {'records': len(paths)})


if __name__ == '__main__':
    main()
