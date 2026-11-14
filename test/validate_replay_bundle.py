"""Extract the local replay bundle and recompute selected tables without API access."""
from __future__ import annotations

import hashlib
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig
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
    parser.add_argument('--library-repair', action='store_true')
    parser.add_argument('--nov14', action='store_true')
    parser.add_argument('--browser-smoke', action='store_true', help='Replay five saved table pages with fresh npm dependencies')
    parser.add_argument('--browser-artifacts', type=Path, help='New directory retaining browser reports and runtime provenance')
    args = parser.parse_args()
    if args.library_repair and not args.expanded:
        raise ValueError('--library-repair requires --expanded')
    if args.nov14 and not args.library_repair:
        raise ValueError('--nov14 requires --library-repair and --expanded')
    if args.browser_smoke and (not args.library_repair or args.browser_artifacts is None):
        raise ValueError('--browser-smoke requires --library-repair and --browser-artifacts')
    if args.browser_smoke and args.browser_artifacts.exists():
        raise ValueError('Browser artifact directory already exists; preserve it and choose a new directory')
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
        if args.library_repair:
            checks += (('test.replay_library_repair', 'test/results/library-repair-replay.json'),)
        if args.nov14:
            checks += (('test.replay_nov14', 'test/results/nov14-replay.json'),)
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
        if args.browser_smoke:
            libs = ROOT / '.browser-deps/usr/lib' / (sysconfig.get_config_var('MULTIARCH') or 'x86_64-linux-gnu')
            if libs.exists():
                env['LD_LIBRARY_PATH'] = str(libs) + os.pathsep + env.get('LD_LIBRARY_PATH', '')
            done = subprocess.run([sys.executable, '-m', 'test.replay_browser_smoke'], cwd=root, env=env,
                                  capture_output=True, text=True, timeout=600)
            output = root / 'artifacts/anonymous-browser-smoke'
            if output.exists():
                shutil.copytree(output, args.browser_artifacts, ignore=shutil.ignore_patterns('node_modules'))
            if done.returncode:
                result['browser_smoke'] = {'all_passed': False, 'exit_code': done.returncode,
                                           'error': done.stderr[-2400:].replace(str(root), '<replay-root>')}
            else:
                result['browser_smoke'] = json.loads((output / 'result.json').read_text())
            result['browser_smoke']['artifacts'] = str(args.browser_artifacts)
            result['browser_smoke']['shared_system_library_fallback'] = libs.exists()
            print('browser_smoke', result['browser_smoke']['all_passed'], flush=True)
    result['all_passed'] = all(c['identical'] for c in result['checks'])
    if args.browser_smoke:
        result['all_passed'] = result['all_passed'] and result['browser_smoke']['all_passed']
    result['expanded'] = args.expanded
    result['library_repair'] = args.library_repair
    result['nov14'] = args.nov14
    if args.expanded:
        result['scope'] += ' Also four new cohorts (904 distinct candidates) and their stored fixed-control scores; no additional browser reruns.'
    if args.library_repair:
        result['scope'] += ' Also strict and secondary repair replay tables reconstructed from stored raw reports; no new browser calls.'
    if args.nov14:
        result['scope'] += ' Also November 14 full-library continuation, conditional toggles, prefix calibration and corrected factorial, reconstructed from raw reports and dated ledgers.'
    if args.browser_smoke:
        result['scope'] += ' Separate five-page table/task-20 browser smoke check uses a fresh extraction and npm install on the same host.'
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    if not result['all_passed']:
        raise SystemExit(f'Replay validation failed; inspect {args.report}')


if __name__ == '__main__':
    main()
