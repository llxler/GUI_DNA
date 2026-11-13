"""Transparent secondary replay after exact extraction of one JSON fence."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import re
import subprocess

from gui_dna.provider import parse_json
from test.interface_blind.core import write_files
from test.webbench_expand.generate import output_files
from .core import (ROOT, HERE, OUT, PROJECTS, BUILDERS, CONDITIONS, read, dump,
                   digest, original_package, repaired_package, source_output)
from .run import library_folder, verify_frozen, now
from .evaluator import prepare, grade
from .analyze import summary


def extract_single_fence(text):
    blocks = re.findall(r'^```(?:json)?[ \t]*\r?\n(.*?)^```[ \t]*$', text, re.M | re.S)
    if len(blocks) != 1:
        raise ValueError('Expected exactly one JSON fence')
    return blocks[0]


def prepare_inputs():
    verify_frozen()
    assert not (OUT / 'grading-started.json').exists(), 'Freeze diagnostic before any new candidate grading'
    inputs = read(OUT / 'replay-inputs.json')
    assert inputs['generation_sha256'] == digest(read(OUT / 'generation-complete.json'))
    packages, libraries = {}, []
    for project in PROJECTS:
        for builder in BUILDERS:
            for condition in CONDITIONS:
                folder = library_folder(project, builder, condition)
                primary = read(folder / 'package.json')
                record = read(folder / 'record.json')
                package = primary
                item = {'project': project, 'builder': builder, 'condition': condition,
                        'primary_deployed': record['deployed'], 'extracted': False, 'error': None}
                if record['deployed'] == 'original_fallback':
                    try:
                        block = extract_single_fence(read(folder / 'output.json')['text'])
                        package = repaired_package(original_package(project, builder), parse_json(block))
                        item.update(extracted=True, extracted_text_sha256=hashlib.sha256(block.encode()).hexdigest())
                    except (ValueError, KeyError, TypeError, AssertionError, TimeoutError, subprocess.TimeoutExpired) as error:
                        item['error'] = str(error)[:2000]
                packages[project, builder, condition] = package
                item['package_sha256'] = digest(package)
                libraries.append(item)
                dump(folder / 'format-diagnostic-package.json', package)
    jobs, rows = {}, []
    for original_row in inputs['rows']:
        row = {k: v for k, v in original_row.items() if k not in ('score_key', 'files_sha256', 'compile_error', 'unchanged_files')}
        package = packages[row['project'], row['builder'], row['condition']]
        try:
            parsed = source_output(ROOT / row['source'])
            if parsed is None:
                raise ValueError('No executable original output')
            files = output_files(row['method'], package, parsed)
            oldfiles = output_files(row['method'], original_package(row['project'], row['builder']), parsed)
            sha = digest(files)
            page = OUT / 'pages' / row['project'] / sha
            if page.exists():
                assert {p.relative_to(page).as_posix(): p.read_text() for p in page.rglob('*') if p.is_file()} == files
            else:
                write_files(page, files)
            key = f'{row["project"]}/task-{row["task"]}/{sha}'
            jobs[key] = {'project': row['project'], 'task': row['task'], 'page': str(page.relative_to(ROOT)), 'files_sha256': sha}
            row.update(score_key=key, files_sha256=sha, unchanged_files=files == oldfiles)
        except (ValueError, KeyError, TypeError, TimeoutError, subprocess.TimeoutExpired) as error:
            row.update(score_key=None, compile_error=str(error)[:2000], unchanged_files=False)
        rows.append(row)
    value = {'primary_inputs_sha256': digest(inputs), 'libraries': libraries, 'rows': rows, 'jobs': jobs}
    target = OUT / 'format-replay-inputs.json'
    if target.exists():
        assert read(target) == value
    else:
        dump(target, value)
    manifest = OUT / 'format-replay-manifest.json'
    files = [HERE / 'FORMAT_DIAGNOSTIC.md', HERE / 'format_replay.py', target]
    frozen = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    if manifest.exists():
        assert read(manifest)['sha256'] == frozen
    else:
        dump(manifest, {'frozen_utc': now(), 'sha256': frozen, 'posthoc': True, 'before_candidate_grading': True})
    snapshot_path = OUT / 'pre-scoring-snapshot.json'
    snapshot_files = [p for p in (OUT / 'libraries').rglob('*') if p.is_file()]
    snapshot_files += [OUT / name for name in ('generation-complete.json', 'replay-inputs.json', 'format-replay-inputs.json', 'format-replay-manifest.json')]
    snapshot = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(snapshot_files)}
    if snapshot_path.exists():
        assert read(snapshot_path)['sha256'] == snapshot
    else:
        dump(snapshot_path, {'frozen_utc': now(), 'sha256': snapshot})
    print('Format diagnostic prepared:', sum(r['extracted'] for r in libraries), 'extracted libraries;', len(jobs), 'score keys')


def verify():
    verify_frozen()
    manifest = read(OUT / 'format-replay-manifest.json')
    for path, sha in manifest['sha256'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == sha, path
    assert manifest['frozen_utc'] <= read(OUT / 'grading-started.json')['started_utc']
    snapshot = read(OUT / 'pre-scoring-snapshot.json')
    assert snapshot['frozen_utc'] <= read(OUT / 'grading-started.json')['started_utc']
    for path, sha in snapshot['sha256'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == sha, path
    return read(OUT / 'format-replay-inputs.json')


def evaluate():
    inputs = verify()
    prepare()
    def one(item):
        key, job = item
        folder = OUT / 'scores' / key
        if not (folder / 'score.json').exists():
            dump(folder / 'score.json', grade(job['project'], ROOT / job['page'], f'task-{job["task"]}', folder / 'report.json'))
    for project in PROJECTS:
        jobs = [(k, j) for k, j in inputs['jobs'].items() if j['project'] == project]
        with ThreadPoolExecutor(max_workers=1 if project == 'bom' else 6) as pool:
            for i, _ in enumerate(pool.map(one, jobs), 1):
                if i % 10 == 0 or i == len(jobs):
                    print('format diagnostic', project, i, '/', len(jobs), flush=True)
    dump(OUT / 'format-evaluation-complete.json', {'inputs_sha256': digest(inputs), 'finished_utc': now()})


def analyze():
    inputs = verify()
    assert read(OUT / 'format-evaluation-complete.json')['inputs_sha256'] == digest(inputs)
    scores = {}
    for key, job in inputs['jobs'].items():
        folder = OUT / 'scores' / key
        score = read(folder / 'score.json')
        assert hashlib.sha256((folder / 'report.json').read_bytes()).hexdigest() == score['report_sha256']
        page = ROOT / job['page']
        assert digest({p.relative_to(page).as_posix(): p.read_text() for p in page.rglob('*') if p.is_file()}) == job['files_sha256']
        scores[key] = score
    rows = [{**r, 'passed': bool(scores[r['score_key']]['all_passed']) if r['score_key'] else False,
             'cohort': 'strong' if r['model'] == 'openai/gpt-5' else 'main'} for r in inputs['rows']]
    aggregates, groups = [], []
    for kind in ('candidate', 'fixed', 'development'):
        for cohort in ('main', 'strong'):
            for condition in CONDITIONS:
                for method in ('plan', 'free_lib') if kind == 'candidate' else ('plan',):
                    selected = [r for r in rows if (r['kind'], r['cohort'], r['condition'], r['method']) == (kind, cohort, condition, method)]
                    if not selected:
                        continue
                    metadata = {'kind': kind, 'cohort': cohort, 'condition': condition, 'method': method}
                    aggregates.append({**metadata, **summary(selected)})
                    for project in PROJECTS:
                        for builder in BUILDERS:
                            group = [r for r in selected if (r['project'], r['builder']) == (project, builder)]
                            groups.append({**metadata, 'project': project, 'builder': builder, **summary(group)})
    unchanged = [r for r in rows if r['unchanged_files']]
    result = {'scope': 'Post-generation, pre-scoring exact single-JSON-fence extraction; secondary diagnostic, never replaces strict primary results.',
              'aggregates': aggregates, 'groups': groups, 'libraries': inputs['libraries'], 'rows': rows,
              'unique_browser_scores': len(scores), 'unchanged_comparisons': len(unchanged),
              'unchanged_score_mismatches': [r for r in unchanged if r['passed'] != r['baseline']['passed']]}
    dump(ROOT / 'test/results/library-repair-format.json', result)
    print(json_summary(result))


def json_summary(result):
    import json
    return json.dumps({k: v for k, v in result.items() if k not in ('rows', 'groups', 'unchanged_score_mismatches')}, indent=2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['prepare', 'evaluate', 'analyze'])
    phase = parser.parse_args().phase
    {'prepare': prepare_inputs, 'evaluate': evaluate, 'analyze': analyze}[phase]()
