"""Export anonymous source AND historical observations, with separate rewritten hashes.

No upload. SQLite snapshots retain amounts/policy but pseudonymize request IDs.
Absolute experiment paths become paths relative to the bundle root. Original
frozen manifests remain historical evidence; the bundle has its own hash map.
"""
from __future__ import annotations
import argparse
import hashlib
from functools import lru_cache
import json
import os
import re
import sqlite3
import subprocess
import tempfile
import zipfile
from pathlib import Path

from test.export_review_snapshot import ALLOWED_FILES, ALLOWED_ROOTS, EXTENSIONS

ROOT = Path(__file__).resolve().parents[1]
TEXT = EXTENSIONS | {'.csv', '.svg', '.yaml', '.yml', '.mjs'}
RAW_PREFIXES = ('todomvc-', 'webbench-dna', 'webapp1k-dna', 'name-sensitivity', 'interface-blind', 'behavior-feedback', 'library-')
RAW_NAMES = {'live', 'followup', 'linked-plan-posthoc', 'scale-study', 'random-plans', 'failure-figure', 'review-20261112'}
NOV14_NAMES = {'library-repair-resume-20261114', 'library-repair-full-20261114',
               'library-repair-entrypoint-20261114',
               'library-toggle-control-20261114', 'prefix-history-audit-20261114',
               'prefix-factorial-20261114', 'prefix-factorial-v2-20261114', 'review-20261114'}
NOV15_NAMES = {'history-replay-20261115', 'interaction-transfer-sources-20261115',
               'finite-schema-audit-20261115', 'container-replay-20261115-uid', 'container-network-probe-20261115',
               'interaction-transfer-calibration-20261115', 'interaction-transfer-build-20261115',
               'interaction-transfer-run-20261115', 'interaction-transfer-controls-20261115', 'review-20261115',
               'interaction-union-20261115', 'development-feedback-20261115', 'container-replay-20261115',
               'history-tasks-only-20261115', 'linked-control', 'compact-pair'}
SKIP_PARTS = {'node_modules', '.git', '__pycache__', '.pytest_cache', 'playwright-output', 'test-results', 'playwright-report'}
AUTHOR_NAMES = ('lxler', 'llxler')
HOME_IDENTITY = re.compile(rb'/home/(?!anonymous)[A-Za-z_][A-Za-z0-9_.-]*')
SECRET = re.compile(rb'(?:sk-or-v1-|sk-proj-)[A-Za-z0-9_-]{20,}')


@lru_cache(maxsize=4096)
def scrub(text):
    for root in (str(ROOT), '/home/lxler/work/gui_test'):
        text = text.replace(root + '/', '').replace(root, '.')
    text = re.sub(r'/home/[A-Za-z_][A-Za-z0-9_.-]*', '/home/anonymous', text)
    text = re.sub(r'(https?://openrouter\.ai/workspaces/)[^/\s\"\')]+', r'\1anonymous', text)
    text = text.replace('github.com/llxler/', 'example.invalid/anonymous/')
    for name in AUTHOR_NAMES:
        if name != 'anonymous':
            text = re.sub(r'\b' + re.escape(name) + r'\b', 'anonymous', text, flags=re.I)
    return text


def has_identity(content):
    names = [name.encode().lower() for name in AUTHOR_NAMES if name != 'anonymous']
    lower = content.lower()
    return bool(HOME_IDENTITY.search(content)) or any(name in lower for name in names)


@lru_cache(maxsize=8192)
def pseudonym(value):
    return hashlib.sha256(('anonymous-replay-v1:' + value).encode()).hexdigest()[:32]


def transform(value, call_ids):
    if isinstance(value, dict):
        out = {}
        for key, child in value.items():
            if key in ('id', 'call_id') and isinstance(child, str) and child in call_ids:
                child = pseudonym(child)
            elif key in ('id', 'generation_id') and isinstance(child, str) and child.startswith('gen-'):
                child = 'gen-anonymous-' + pseudonym(child)
            out[scrub(key)] = transform(child, call_ids)
        return out
    if isinstance(value, list):
        return [transform(child, call_ids) for child in value]
    return scrub(value) if isinstance(value, str) else value


def walk_files(root):
    for directory, folders, files in os.walk(root, followlinks=False):
        folders[:] = [name for name in folders if name not in SKIP_PARTS and not (Path(directory) / name).is_symlink()]
        for name in files:
            path = Path(directory) / name
            if not path.is_symlink():
                yield path


def candidate_source_files(stage, allow_shared_artifacts=False):
    """Preserve every generated source file, even with an uncommon extension."""
    result = set()
    for manifest in stage.rglob('source-manifest.json'):
        if any(part in SKIP_PARTS for part in manifest.parts):
            continue
        value = json.loads(manifest.read_text())
        for name in value.get('files_sha256', {}):
            path = manifest.parent / name
            if not path.resolve().is_relative_to(stage.resolve()) or path.is_symlink():
                raise ValueError('Unsafe candidate source path')
            if not path.is_file():
                raise ValueError(f'Missing saved candidate source: {path}')
            result.add(path)
    for filename in ('replay-inputs.json', 'format-replay-inputs.json', 'inputs.json', 'scoring-inputs.json'):
        index = stage / filename
        if not index.exists():
            continue
        for job in json.loads(index.read_text()).get('jobs', {}).values():
            page = ROOT / job['page']
            if page.is_symlink():
                raise ValueError('Unsafe replay page path')
            if page.resolve().is_relative_to(stage.resolve()):
                result.update(walk_files(page))
            elif allow_shared_artifacts and page.resolve().is_relative_to((ROOT / 'artifacts').resolve()):
                mapping = job.get('files_sha256', job.get('files'))
                if not isinstance(mapping, dict) or not mapping:
                    raise ValueError('Shared source requires an explicit frozen file map')
                for name, expected_sha in mapping.items():
                    source = page / name
                    if source.is_symlink() or not source.resolve().is_relative_to(page.resolve()):
                        raise ValueError('Unsafe shared source path')
                    if hashlib.sha256(source.read_bytes()).hexdigest() != expected_sha:
                        raise ValueError('Shared source differs from frozen manifest')
                    result.add(source)
            else:
                raise ValueError('Unsafe replay page path')
    return result


def selected_files(expanded=False, library_repair=False, nov14=False, nov15=False):
    names = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT).decode().split('\0')
    chosen = {ROOT / n for n in names if n and (n in ALLOWED_FILES or (Path(n).parts[0] in ALLOWED_ROOTS and Path(n).suffix in TEXT))}
    prefixes = RAW_PREFIXES + (('webbench-expand', 'heldout-composition') if expanded else ())
    for stage in (ROOT / 'artifacts').iterdir():
        if stage.name in NOV15_NAMES and not nov15:
            continue
        if stage.name in NOV14_NAMES and not nov14:
            continue
        if not stage.is_dir() or not (stage.name in RAW_NAMES or stage.name.startswith(prefixes) or (nov14 and stage.name in NOV14_NAMES) or (nov15 and stage.name in NOV15_NAMES)):
            continue
        if stage.name.startswith('library-repair-') and not library_repair:
            continue
        for path in walk_files(stage):
            if path.suffix in TEXT | {'.sqlite3', '.png', '.jpg'}:
                chosen.add(path)
        if expanded and (stage.name.startswith(('webbench-expand', 'heldout-composition', 'library-repair-')) or (nov14 and stage.name in NOV14_NAMES) or (nov15 and stage.name in NOV15_NAMES)):
            chosen.update(candidate_source_files(stage, allow_shared_artifacts=nov15 and stage.name in NOV15_NAMES))
        if nov15 and stage.name in ('container-replay-20261115', 'container-replay-20261115-uid'):
            chosen.update(walk_files(stage / 'inputs/pages'))
            dockerfile = stage / 'context/Dockerfile'
            if dockerfile.exists(): chosen.add(dockerfile)
    if (ROOT / 'artifacts/budget.sqlite3').exists():
        chosen.add(ROOT / 'artifacts/budget.sqlite3')
    if nov15:
        # Only the probe ledger is needed for the original-study cost subtotal;
        # its large unrelated npm checkout is not part of this addition.
        chosen.add(ROOT / 'artifacts/benchmark-probe/budget.sqlite3')
    # List-16 reconstructs atoms from this standalone historical library.
    for name in ('library-live.json', 'library-offline.json', 'library-learning-history.json'):
        path = ROOT / 'artifacts' / name
        if path.exists():
            chosen.add(path)
    projects = ('dom1', 'form', 'calculator', 'table', 'bom') if expanded else ('dom1', 'form')
    for project in projects:
        folder = ROOT / 'artifacts/web-bench/projects' / project
        chosen.update(p for p in walk_files(folder) if p.suffix in TEXT)
    license_path = ROOT / 'artifacts/web-bench/LICENSE'
    if license_path.exists():
        chosen.add(license_path)
    generated_reports = {'replay-bundle.json', 'replay-validation.json', 'replay-bundle-expanded.json', 'replay-validation-expanded.json',
                         'replay-bundle-20261113.json', 'replay-validation-20261113.json',
                         'replay-bundle-20261113-final.json', 'replay-validation-20261113-final.json',
                         'replay-bundle-20261114.json', 'replay-validation-20261114.json',
                         'replay-bundle-20261115.json', 'replay-validation-20261115.json'}
    return sorted(p for p in chosen if p.is_file() and not p.is_symlink() and p.name not in generated_reports
                  and not (p.parent.name.startswith('review-') and p.name == 'HANDOFF.md')
                  and not (p.parent.name.startswith('review-') and p.name.startswith('credits'))
                  and not (p.parent.name == 'paper-preview' and p.parent.parent.name.startswith('review-')))


def sanitize_ledger(source, target):
    with sqlite3.connect(f'file:{source}?mode=ro', uri=True) as original, sqlite3.connect(target) as dest:
        original.backup(dest)
        dest.row_factory = sqlite3.Row
        rows = [dict(r) for r in dest.execute('SELECT * FROM calls')]
        for row in rows:
            values = {k: scrub(v) if isinstance(v, str) else v for k, v in row.items()}
            values['id'] = pseudonym(row['id'])
            if values.get('generation_id'):
                values['generation_id'] = 'gen-anonymous-' + pseudonym(row['generation_id'])
            fields = list(values)
            dest.execute('UPDATE calls SET ' + ','.join(f'{key}=?' for key in fields) + ' WHERE id=?',
                         [values[key] for key in fields] + [row['id']])
        dest.commit()
        dest.execute('VACUUM')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'artifacts/anonymous-replay.zip')
    parser.add_argument('--report', type=Path, default=ROOT / 'test/results/replay-bundle.json')
    parser.add_argument('--expanded', action='store_true', help='Include the three-project and heldout-composition extensions')
    parser.add_argument('--library-repair', action='store_true', help='Include the completed availability diagnostic and interrupted generation (requires --expanded)')
    parser.add_argument('--nov14', action='store_true', help='Include completed repair continuation, Boolean controls and matched-prefix factorial')
    parser.add_argument('--nov15', action='store_true', help='Include historical full-prefix replay and development-only interaction transfer')
    args = parser.parse_args()
    args.out = args.out.resolve()
    args.report = args.report.resolve()
    for stage in ('interface-blind-final-2', 'behavior-feedback'):
        if not (ROOT / 'artifacts' / stage / 'generation-complete.json').exists():
            raise ValueError(f'{stage}: finish generation before snapshotting')
        for record in (ROOT / 'artifacts' / stage / 'runs').rglob('record.json'):
            if not record.with_name('hidden.json').exists():
                raise ValueError(f'{stage}: finish hidden scoring before snapshotting')
    if args.expanded:
        for name in ('webbench-expand-run', 'heldout-composition-run'):
            if not (ROOT / 'artifacts' / name / 'offline-complete.json').exists():
                raise ValueError(f'{name}: finish the full offline pipeline before expanded export')
        if not (ROOT / 'test/results/new-tables-replay.json').exists():
            raise ValueError('Run test.replay_new_tables before expanded export')
    if args.library_repair:
        if not args.expanded:
            raise ValueError('--library-repair requires --expanded for its original source cohorts')
        if not (ROOT / 'artifacts/library-repair-available-20261113/evaluation-complete.json').exists():
            raise ValueError('Complete the separate availability diagnostic before exporting')
        space = ROOT / 'artifacts/library-repair-space-20261113'
        if space.exists() and not (space / 'evaluation-complete.json').exists():
            raise ValueError('Finish the conditional space evaluation before exporting')
        if not (ROOT / 'test/results/library-repair-replay.json').exists():
            raise ValueError('Run test.replay_library_repair before exporting')
    if args.nov14:
        if not args.library_repair:
            raise ValueError('--nov14 requires --library-repair and --expanded')
        for name in ('library-repair-full-20261114', 'prefix-factorial-v2-20261114'):
            if not (ROOT / 'artifacts' / name / 'evaluation-complete.json').exists():
                raise ValueError(f'{name}: complete scoring before export')
        for project in ('calculator', 'table', 'bom'):
            if not (ROOT / 'artifacts/library-toggle-control-20261114' / f'evaluation-complete-{project}.json').exists():
                raise ValueError('Complete all Boolean control projects before export')
        if not (ROOT / 'test/results/nov14-replay.json').exists():
            raise ValueError('Run test.replay_nov14 before export')
        if not (ROOT / 'artifacts/library-repair-entrypoint-20261114/evaluation-complete.json').exists():
            raise ValueError('The frozen entrypoint intervention must be complete')
        daily = json.loads((ROOT / 'test/results/review-20261114-costs.json').read_text())
        if any(stage['stop_usd'] != 0 for stage in daily['stages'].values()):
            raise ValueError('Close all November 14 generation stages before export')
    if args.nov15:
        if not args.nov14:
            raise ValueError('--nov15 requires --nov14, --library-repair and --expanded')
        for name in ('history-replay-20261115', 'interaction-transfer-run-20261115',
                     'interaction-union-20261115', 'development-feedback-20261115'):
            if not (ROOT / 'artifacts' / name / 'evaluation-complete.json').exists():
                raise ValueError(f'{name}: complete scoring before export')
        if not (ROOT / 'test/results/nov15-replay.json').exists():
            raise ValueError('Run test.replay_nov15 before export')
        daily = json.loads((ROOT / 'test/results/review-20261115-costs.json').read_text())
        from test.authorized_costs import summarize as authorized_costs
        if daily != authorized_costs('20261115'):
            raise ValueError('Refresh November 15 cost snapshot before export')
        if any(stage['stop_usd'] != 0 for stage in daily['stages'].values()):
            raise ValueError('Close November 15 paid stages before export')
        container = ROOT / 'artifacts/container-replay-20261115'
        if container.exists() and not (ROOT / 'test/results/container-replay.json').exists():
            raise ValueError('Analyze the completed container observations before export')
        if container.exists():
            observed = json.loads((ROOT / 'test/results/container-replay.json').read_text())
            stage_name = observed.get('stage', 'artifacts/container-replay-20261115')
            allowed = {'artifacts/container-replay-20261115', 'artifacts/container-replay-20261115-uid'}
            if stage_name not in allowed or not (ROOT / stage_name / 'outputs/complete.json').exists():
                raise ValueError('Complete the explicitly identified container stage before export')
            if stage_name.endswith('-uid'):
                recovery = json.loads((ROOT / stage_name / 'recovery.json').read_text())
                assert recovery['parent'] == 'artifacts/container-replay-20261115' and recovery['original_pages_scored'] == 0
                assert not list((container / 'outputs').iterdir()), 'Original infrastructure failure must precede all page observations'
                assert (ROOT / stage_name / 'inputs/inputs.json').read_bytes() == (container / 'inputs/inputs.json').read_bytes()
        task_history = ROOT / 'artifacts/history-tasks-only-20261115'
        if task_history.exists() and not (task_history / 'evaluation-complete.json').exists():
            raise ValueError('Complete the separately frozen task-file history diagnostic before export')
        if task_history.exists() and not (ROOT / 'test/results/history-tasks-only.json').exists():
            raise ValueError('Analyze task-file history evidence before export')
        finite_schema = ROOT / 'artifacts/finite-schema-audit-20261115'
        if finite_schema.exists() and not (finite_schema / 'evaluation-complete.json').exists():
            raise ValueError('Complete the finite-schema audit before export')
        if finite_schema.exists() and not (ROOT / 'test/results/finite-schema-audit.json').exists():
            raise ValueError('Analyze the finite-schema audit before export')
    paths = selected_files(args.expanded, args.library_repair, args.nov14, args.nov15)
    source_paths = set()
    if args.expanded:
        for stage in (ROOT / 'artifacts').iterdir():
            if stage.is_dir() and (stage.name.startswith(('webbench-expand', 'heldout-composition') + (('library-repair-',) if args.library_repair else ())) or (args.nov14 and stage.name in NOV14_NAMES) or (args.nov15 and stage.name in NOV15_NAMES)):
                source_paths.update(candidate_source_files(stage, allow_shared_artifacts=args.nov15 and stage.name in NOV15_NAMES))
    call_ids = set()
    for path in paths:
        if path.suffix == '.sqlite3':
            with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as db:
                call_ids.update(r[0] for r in db.execute('SELECT id FROM calls'))
    manifest = {}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp, zipfile.ZipFile(args.out, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for i, path in enumerate(paths):
            name = path.relative_to(ROOT).as_posix()
            original = path.read_bytes()
            if path.suffix == '.sqlite3':
                target = Path(temp) / f'{i}.sqlite3'
                sanitize_ledger(path, target)
                content = target.read_bytes()
            elif path.suffix == '.json':
                try:
                    content = (json.dumps(transform(json.loads(original), call_ids), ensure_ascii=False, indent=2) + '\n').encode()
                except json.JSONDecodeError:
                    content = scrub(original.decode()).encode()
            elif path.suffix == '.jsonl':
                lines = []
                for line in original.decode().splitlines():
                    try:
                        lines.append(json.dumps(transform(json.loads(line), call_ids), ensure_ascii=False))
                    except json.JSONDecodeError:
                        lines.append(scrub(line))
                content = ('\n'.join(lines) + '\n').encode()
            elif path.suffix in TEXT or path.name == 'LICENSE' or path in source_paths:
                content = scrub(original.decode()).encode()
            else:
                content = original
            if SECRET.search(content) or has_identity(content):
                raise ValueError(f'Potential identity/credential remains in {name}; archive not publishable')
            archive.writestr(name, content)
            manifest[name] = {'original_sha256': hashlib.sha256(original).hexdigest(),
                              'exported_sha256': hashlib.sha256(content).hexdigest(), 'bytes': len(content)}
            if i and i % 2000 == 0:
                print(f'exported {i}/{len(paths)} files', flush=True)
        metadata = {'commit': '7b31ca2b786eef120dd49ce63dd03d0c0006046d',
                    'scope': ('dom1, form, calculator, table, bom' if args.expanded else 'dom1 and form only') + '; files retain upstream license notices'}
        generated = {'artifacts/web-bench/REPLAY-UPSTREAM.json': json.dumps(metadata, indent=2) + '\n'}
        generated['REPLAY.md'] = '''# Anonymous observations bundle

This local file has NOT been published. It contains source, saved candidate files,
model responses/SSE events, scores, and sanitized SQLite ledger snapshots.
Run commands from the extracted root. Absolute project paths were rewritten to
relative paths. Request/generation IDs were pseudonymized; amounts, reserved
exposure and policy were preserved. Original frozen manifests refer to original
bytes: REPLAY-MANIFEST.json maps original and exported hashes. Do not claim the
old source hashes validate these rewritten files or use this copy to resume paid
experiments. Credentials and Git history are absent. External dependencies still
require installation; the two new Web-Bench projects retain their license notices.

Zero-API table checks (after installing the Python dependencies):
  python -m test.replay_primary_tables
  python -m test.replay_scale_table
  python -m test.review_metrics
  python -m test.interface_blind.analyze
  python -m test.behavior_feedback_analyze
  python -m test.repair_breakdown
  python -m test.paired_intervals

Browser scoring additionally requires Chromium and the npm dependencies from
test/webbench_dna/harness. Historical stages may need their separately documented
upstream benchmark installations. The accompanying validation report states
which tables were actually reproduced; this archive alone does not certify every
paper table, every historical browser score, or anonymous online availability.
'''
        if args.expanded:
            generated['REPLAY.md'] += '''
This expanded snapshot additionally includes three official Web-Bench projects,
their pinned Playwright 1.57 runtime lockfiles, and the separately labeled
synthetic heldout-composition diagnostic. Recompute their four cohorts and fixed
controls with:
  python -m test.replay_new_tables
This reads stored outcomes and does not rerun every browser trajectory. Original
generation audits bind original bytes and are not applicable to rewritten files;
verify REPLAY-MANIFEST.json instead. Browser replay requires separate dependency
installation. The synthetic tasks are not official Web-Bench results.
'''
        if args.library_repair:
            generated['REPLAY.md'] += '''
The November 13 snapshot also includes the implementation-only library revision,
strict-format results and separate exact-JSON-fence diagnostic. Reconstruct their
old baselines and new stored raw browser reports with:
  python -m test.replay_library_repair
Only the three libraries with complete responses in both conditions are included
in this posthoc availability subset; the planned six-library study remains
incomplete. Its 90 original planner outputs are replayed, not newly generated.
Development feedback and all-target requirement access prevent a transfer claim.
The final snapshot additionally includes all 128 Boolean interaction settings at
one fixed style, before and after one source-line intervention on table/task-20.
This is a conditional slice, not an impossibility proof for the whole schema.
An optional five-page browser smoke replay can run within a fresh extraction:
  python -m test.replay_browser_smoke
It installs the pinned npm dependencies from the local npm cache and requires
the matching cached Chromium and system libraries. It checks four mechanism
pages and the official reference on table/task-20; it does not certify the full
browser history or a different operating system. The outer validator exposes
this as --browser-smoke --browser-artifacts <new-directory> and preserves reports.
'''
        if args.nov14:
            generated['REPLAY.md'] += '''
The November 14 snapshot additionally includes the disclosed six-response
continuation, six conditional Boolean slices, all-history reference-prefix
calibration, and the corrected matched-prefix factorial. Recompute these with:
  python -m test.replay_nov14
The initial malformed-contract factorial is retained as an abandoned development
stage, including every paid response; it was never hidden-scored or pooled with
the corrected experiment. Boolean sampling fixes non-Boolean anchor structure
and is not uniform over the entire schema. Historical byte hashes are remapped
by this export: use REPLAY-MANIFEST.json on the anonymous copy. API fees include
abandoned development calls; no generation should be resumed from this bundle.
'''
        if args.nov15:
            generated['REPLAY.md'] += '''
The November 15 snapshot adds same-page full-history Web-Bench checks and a
separate two-application interaction-transfer diagnostic grounded in public
specifications. Recompute the stored reports, controls and dated costs with:
  python -m test.replay_nov15
The initial legacy-rule/positive-reference labeling error and its pre-candidate
correction are retained. The new synthetic trajectories are not official
TodoMVC, js-framework-benchmark or Web-Bench scores. This reconstruction does
not rerun all browser trajectories or establish cross-machine reproducibility.
The exploratory Boolean-union control and construction-scale no-library public
feedback baseline remain separate from the originally frozen comparisons.
The posthoc task-file history diagnostic retains the original initialization-
plus-history endpoint and separately completes previously censored task files.
This snapshot also carries read-only reconstructions of the two historical pilot
tables, explicit original-study cost subtotal, and additional appendix columns.
The posthoc finite-schema audit enumerates all 1,215 semantic configurations of
one calculator library, including omitted optional fields, and tests its official
initial-file necessary condition. It is not an impossibility claim about other
libraries or about the original current-task endpoint.
If included, container observations use an isolated userspace and browser image,
but share the host kernel; the Docker image itself is not included in this zip.
'''
        for name, text in generated.items():
            content = text.encode()
            archive.writestr(name, content)
            manifest[name] = {'original_sha256': None, 'exported_sha256': hashlib.sha256(content).hexdigest(), 'bytes': len(content)}
        archive.writestr('REPLAY-MANIFEST.json', json.dumps(manifest, indent=2) + '\n')
    result = {'file': str(args.out.relative_to(ROOT)), 'files': len(manifest), 'bytes': args.out.stat().st_size,
              'sha256': hashlib.sha256(args.out.read_bytes()).hexdigest(), 'published': False,
              'original_hashes_remapped': True, 'sqlite_ledgers': sum(p.suffix == '.sqlite3' for p in paths)}
    result['expanded'] = args.expanded
    result['library_repair'] = args.library_repair
    result['nov14'] = args.nov14
    result['nov15'] = args.nov15
    output = args.report
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
