"""Extract the local replay bundle and recompute selected tables without API access."""
from __future__ import annotations

import hashlib
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CHECKS = (
    ('test.replay_scale_table', 'test/results/scale-table-replay.json'),
    ('test.replay_primary_tables', 'test/results/primary-replay.json'),
    ('test.review_metrics', 'test/results/review-metrics.json'),
    ('test.interface_blind.analyze', 'test/results/interface-blind.json'),
    ('test.behavior_feedback_analyze', 'test/results/behavior-feedback.json'),
    ('test.repair_breakdown', 'test/results/repair-breakdown.json'),
    ('test.paired_intervals', 'test/results/paired-intervals.json'),
)


def normalize(value, root):
    if isinstance(value, dict):
        return {k: normalize(v, root) for k, v in value.items()}
    if isinstance(value, list):
        return [normalize(v, root) for v in value]
    if isinstance(value, str):
        return value.replace(str(root) + '/', '')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, default=ROOT / 'artifacts/anonymous-replay.zip')
    parser.add_argument('--report', type=Path, default=ROOT / 'test/results/replay-validation.json')
    parser.add_argument('--expanded', action='store_true')
    args = parser.parse_args()
    path = args.archive
    result = {'archive_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
              'published': False, 'checks': [], 'scope': 'Hash verification; three primary accuracy tables plus five sample/seed/frontier extensions from raw records; five further summary recomputations. External row checks reuse observations across tables; distinct file-path count reported separately. Not a replay of every historical browser test or every paper table.'}
    with tempfile.TemporaryDirectory(prefix='gui-dna-anonymous-replay-') as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                if Path(name).is_absolute() or '..' in Path(name).parts:
                    raise ValueError('Unsafe archive path')
            archive.extractall(root)
        manifest = json.loads((root / 'REPLAY-MANIFEST.json').read_text())
        for name, entry in manifest.items():
            assert hashlib.sha256((root / name).read_bytes()).hexdigest() == entry['exported_sha256'], name
        result['hashes_verified'] = len(manifest)
        env = {k: v for k, v in os.environ.items() if not any(s in k.upper() for s in ('API_KEY', 'TOKEN', 'SECRET'))}
        env['PYTHONPATH'] = os.pathsep.join((str(root / 'src'), str(root)))
        proof = subprocess.run([sys.executable, '-c', 'import gui_dna, test.interface_blind.core as c; print(gui_dna.__file__); print(c.ROOT)'],
                               cwd=root, env=env, check=True, capture_output=True, text=True)
        assert all(line.startswith(str(root)) for line in proof.stdout.splitlines()), proof.stdout
        checks = CHECKS + ((('test.replay_new_tables', 'test/results/new-tables-replay.json'),) if args.expanded else ())
        for module, output in checks:
            expected = json.loads((root / output).read_text())
            done = subprocess.run([sys.executable, '-m', module], cwd=root, env=env,
                                  capture_output=True, text=True, timeout=240)
            check = {'module': module, 'output': output, 'exit_code': done.returncode}
            if done.returncode:
                check.update(identical=False, error=done.stderr[-2400:].replace(str(root), '<replay-root>'))
            else:
                observed = json.loads((root / output).read_text())
                check['identical'] = normalize(expected, root) == normalize(observed, root)
            result['checks'].append(check)
            print(module, check['identical'], flush=True)
    result['all_passed'] = all(c['identical'] for c in result['checks'])
    result['expanded'] = args.expanded
    if args.expanded:
        result['scope'] += ' Also four new cohorts (904 distinct candidates) and their stored fixed-control scores; no additional browser reruns.'
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    if not result['all_passed']:
        raise SystemExit(f'Replay validation failed; inspect {args.report}')


if __name__ == '__main__':
    main()
