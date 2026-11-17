"""Zero-API matched-availability diagnostic; never completes the interrupted six-library study."""
import argparse
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import subprocess

from gui_dna.provider import parse_json
from test.interface_blind.core import write_files
from test.webbench_expand.generate import output_files
from test.ledger_read import totals, calls
from .core import (ROOT, HERE, OUT as SOURCE, PROJECTS, BUILDERS, MODELS, CONDITIONS, PUBLIC_TASKS,
                   TEST_TASKS, read, dump, digest, source_folder, source_output, original_package,
                   repaired_package, messages_for)
from .run import library_folder, verify_frozen, now
from .evaluate import saved_files, baseline_score
from .format_replay import extract_single_fence
from .evaluator import prepare as prepare_harness, grade
from .analyze import summary

OUT = ROOT / 'artifacts/library-repair-available-20261113'


def prepare():
    verify_frozen()
    assert (SOURCE / 'generation-stopped.json').exists()
    assert totals(SOURCE / 'budget.sqlite3')['stop_usd'] == 0
    assert not (SOURCE / 'grading-started.json').exists()
    assert not (OUT / 'grading-started.json').exists()
    selected, missing, libraries, packages = [], [], [], {}
    public = read(SOURCE / 'public-inputs.json')
    settled = {c['id'] for c in calls(SOURCE / 'budget.sqlite3') if c['actual'] is not None}
    snapshot_files = {HERE / name for name in ('available.py', 'AVAILABLE_PROTOCOL.md', 'format_replay.py', 'FORMAT_DIAGNOSTIC.md', 'analyze.py')}
    snapshot_files.update(SOURCE / name for name in ('review-manifest.json', 'generation-stopped.json', 'public-inputs.json', 'input-provenance.json', 'calibration-complete.json', 'network-continuation.json'))
    for project in PROJECTS:
        for builder in BUILDERS:
            records = [read(library_folder(project, builder, c) / 'record.json') for c in CONDITIONS]
            if any(r['status'] != 'complete' for r in records):
                missing.append({'project': project, 'builder': builder, 'records': records})
                continue
            selected.append({'project': project, 'builder': builder})
            original = original_package(project, builder)
            for condition, record in zip(CONDITIONS, records):
                folder = library_folder(project, builder, condition)
                snapshot_files.update(p for p in folder.rglob('*') if p.is_file())
                messages = messages_for(project, builder, condition, public[project][builder])
                assert read(folder / 'messages.json') == messages
                responses = []
                for request_path in (folder / 'call').rglob('request.json'):
                    request = read(request_path)
                    assert request['body']['messages'] == messages
                    if request['call_id'] in settled:
                        response = read(request_path.with_name('response.json'))
                        assert response['choices'][0]['message']['content'] == read(folder / 'output.json')['text']
                        responses.append(response)
                assert len(responses) == record['valid_responses'] == 1
                primary = read(folder / 'package.json')
                assert digest(primary) == record['package_sha256']
                assert all(primary[k] == original[k] for k in original if k not in ('files', 'compiler'))
                normalized, extracted, error = primary, False, None
                if record['deployed'] == 'original_fallback':
                    try:
                        block = extract_single_fence(read(folder / 'output.json')['text'])
                        normalized = repaired_package(original, parse_json(block))
                        extracted = True
                    except (ValueError, KeyError, TypeError, AssertionError, TimeoutError, subprocess.TimeoutExpired) as issue:
                        error = str(issue)[:2000]
                for form, package in (('strict', primary), ('single_fence', normalized)):
                    packages[project, builder, condition, form] = package
                response = responses[0]
                libraries.append({**record, 'single_fence_extracted': extracted, 'single_fence_error': error,
                                  'normalized_sha256': digest(normalized), 'response_usage': response['usage'],
                                  'provider': response.get('provider'), 'finish_reason': response['choices'][0]['finish_reason']})
    assert len(selected) == 3 and len(libraries) == 6, 'Do not silently change this available cohort'
    rows, jobs, original_cache, compile_cache = [], {}, {}, {}
    def add(project, builder, condition, form, model, method, task, kind):
        folder = source_folder(project, builder, model, method, 20 if kind == 'fixed' else task)
        source = str(folder.relative_to(ROOT))
        original = original_package(project, builder)
        if source not in original_cache:
            parsed, oldfiles = source_output(folder), saved_files(folder)
            assert parsed is None or output_files(method, original, parsed) == oldfiles
            original_cache[source] = (parsed, oldfiles)
        parsed, oldfiles = original_cache[source]
        row = {'format': form, 'project': project, 'builder': builder, 'condition': condition, 'model': model,
               'method': method, 'task': task, 'kind': kind, 'source': source,
               'cohort': 'strong' if model == 'openai/gpt-5' else 'main',
               'baseline': baseline_score(project, builder, model, method, task, kind)}
        cache_key = (source, condition, form)
        try:
            if parsed is None:
                raise ValueError('No executable original output')
            if cache_key not in compile_cache:
                compile_cache[cache_key] = output_files(method, packages[project, builder, condition, form], parsed)
            files = compile_cache[cache_key]
            sha = digest(files)
            page = OUT / 'pages' / project / sha
            if page.exists():
                assert {p.relative_to(page).as_posix(): p.read_text() for p in page.rglob('*') if p.is_file()} == files
            else:
                write_files(page, files)
            key = f'{project}/task-{task}/{sha}'
            jobs[key] = {'project': project, 'task': task, 'page': str(page.relative_to(ROOT)), 'files_sha256': sha}
            row.update(score_key=key, files_sha256=sha, unchanged_files=files == oldfiles)
        except (ValueError, KeyError, TypeError, TimeoutError, subprocess.TimeoutExpired) as error:
            row.update(score_key=None, compile_error=str(error)[:2000], unchanged_files=False)
        rows.append(row)
    for pair in selected:
        project, builder = pair['project'], pair['builder']
        for condition in CONDITIONS:
            for form in ('strict', 'single_fence'):
                for model in MODELS:
                    for task in TEST_TASKS:
                        for method in ('plan', 'free_lib'):
                            add(project, builder, condition, form, model, method, task, 'candidate')
                        add(project, builder, condition, form, model, 'plan', task, 'fixed')
                for task in PUBLIC_TASKS:
                    add(project, builder, condition, form, MODELS[0], 'plan', task, 'development')
    assert len(rows) == 600
    value = {'selected_pairs': selected, 'missing_pairs': missing, 'libraries': libraries,
             'rows': rows, 'jobs': jobs, 'cost': totals(SOURCE / 'budget.sqlite3')}
    target = OUT / 'inputs.json'
    if target.exists():
        assert read(target) == value
    else:
        dump(target, value)
    snapshot_files.add(target)
    snapshot = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(snapshot_files)}
    manifest = OUT / 'snapshot.json'
    if manifest.exists():
        assert read(manifest)['sha256'] == snapshot
    else:
        dump(manifest, {'frozen_utc': now(), 'sha256': snapshot})
    print('Prepared', len(rows), 'comparisons;', len(jobs), 'unique browser checks;', len(selected), 'matched libraries')


def verify():
    verify_frozen()
    snapshot = read(OUT / 'snapshot.json')
    for path, sha in snapshot['sha256'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == sha, path
    return read(OUT / 'inputs.json')


def evaluate():
    inputs = verify()
    prepare_harness()
    target = OUT / 'grading-started.json'
    if not target.exists():
        dump(target, {'started_utc': now(), 'inputs_sha256': digest(inputs)})
    assert read(target)['inputs_sha256'] == digest(inputs)
    assert read(OUT / 'snapshot.json')['frozen_utc'] <= read(target)['started_utc']
    def one(item):
        key, job = item
        folder = OUT / 'scores' / key
        if not (folder / 'score.json').exists():
            dump(folder / 'score.json', grade(job['project'], ROOT / job['page'], f'task-{job["task"]}', folder / 'report.json'))
    for project in PROJECTS:
        selected = [(k, j) for k, j in inputs['jobs'].items() if j['project'] == project]
        if not selected:
            continue
        with ThreadPoolExecutor(max_workers=1 if project == 'bom' else 6) as pool:
            for i, _ in enumerate(pool.map(one, selected), 1):
                if i % 10 == 0 or i == len(selected):
                    print(project, i, '/', len(selected), flush=True)
    dump(OUT / 'evaluation-complete.json', {'inputs_sha256': digest(inputs), 'finished_utc': now()})


def analyze():
    inputs = verify()
    assert read(OUT / 'evaluation-complete.json')['inputs_sha256'] == digest(inputs)
    scores = {}
    for key, job in inputs['jobs'].items():
        folder = OUT / 'scores' / key
        score = read(folder / 'score.json')
        assert hashlib.sha256((folder / 'report.json').read_bytes()).hexdigest() == score['report_sha256']
        page = ROOT / job['page']
        assert digest({p.relative_to(page).as_posix(): p.read_text() for p in page.rglob('*') if p.is_file()}) == job['files_sha256']
        scores[key] = score
    rows = [{**r, 'passed': bool(scores[r['score_key']]['all_passed']) if r['score_key'] else False} for r in inputs['rows']]
    grouped, aggregates = defaultdict(list), []
    fields = ('format', 'kind', 'cohort', 'condition', 'method')
    for row in rows:
        grouped[tuple(row[k] for k in fields)].append(row)
    groups = []
    for key, selected in sorted(grouped.items()):
        meta = dict(zip(fields, key))
        aggregates.append({**meta, **summary(selected)})
        for pair in inputs['selected_pairs']:
            subset = [r for r in selected if all(r[k] == v for k, v in pair.items())]
            groups.append({**meta, **pair, **summary(subset)})
    unchanged = [r for r in rows if r['unchanged_files']]
    result = {'scope': 'Posthoc matched-availability subset: three libraries, two projects, six complete responses out of twelve planned. '
              'The six-library experiment remains incomplete. Fixed old outputs replayed; no new planner generation. '
              'Strict and single-fence results separate; no unseen-behavior or semantic-equivalence claim.',
              'stages': {'generation': str(SOURCE.relative_to(ROOT)), 'evaluation': str(OUT.relative_to(ROOT))},
              'selected_pairs': inputs['selected_pairs'], 'missing_pairs': inputs['missing_pairs'],
              'libraries': inputs['libraries'], 'aggregates': aggregates, 'groups': groups, 'rows': rows,
              'cost': inputs['cost'], 'audit': {'comparisons': len(rows), 'unique_browser_scores': len(scores),
                'original_candidates': len({r['source'] for r in rows if r['kind'] == 'candidate'}),
                'completed_responses': len(inputs['libraries']), 'planned_responses': 12,
                'snapshot_files': len(read(OUT / 'snapshot.json')['sha256']),
                'unchanged_comparisons': len(unchanged),
                'unchanged_score_mismatches': [r for r in unchanged if r['passed'] != r['baseline']['passed']]}}
    dump(ROOT / 'test/results/library-repair-available.json', result)
    for group in aggregates:
        print(group)
    print('cost', result['cost'], 'audit', {k: v for k, v in result['audit'].items() if k != 'unchanged_score_mismatches'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['prepare', 'evaluate', 'analyze'])
    phase = parser.parse_args().phase
    {'prepare': prepare, 'evaluate': evaluate, 'analyze': analyze}[phase]()
