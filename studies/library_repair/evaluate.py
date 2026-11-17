"""Replay immutable old outputs with each frozen revised library."""
from concurrent.futures import ThreadPoolExecutor
import argparse
import hashlib
import subprocess

from test.webbench_expand.generate import output_files
from test.interface_blind.core import write_files
from .core import (ROOT, OUT, MAIN, STRONG, PROJECTS, BUILDERS, MODELS, CONDITIONS,
                   PUBLIC_TASKS, TEST_TASKS, read, dump, digest, slug, source_folder,
                   source_output, original_package)
from .run import library_folder, verify_frozen, now
from .evaluator import prepare, grade


def saved_files(folder):
    record = read(folder / 'record.json')
    if not record['versions']:
        return None
    page = folder / record['versions'][-1]
    manifest = read(page / 'source-manifest.json')
    files = {n: (page / n).read_text() for n in manifest['files_sha256']}
    assert all(hashlib.sha256(v.encode()).hexdigest() == manifest['files_sha256'][n] for n, v in files.items())
    return files


def baseline_score(project, builder, model, method, task, kind):
    if kind == 'fixed':
        if model == 'openai/gpt-5':
            path = STRONG / 'fixed-final' / project / slug(builder) / f'task-{task}' / 'hidden.json'
        else:
            path = ROOT / 'artifacts/webbench-expand-controls/scores' / project / slug(builder) / 'final-plan' / slug(model) / f'task-{task}' / 'hidden.json'
        value = read(path)
    else:
        path = source_folder(project, builder, model, method, task) / 'hidden.json'
        value = read(path)['final']
    return {'passed': bool(value['all_passed']), 'source': str(path.relative_to(ROOT))}


def materialize():
    verify_frozen()
    barrier = read(OUT / 'generation-complete.json')
    records = [read(library_folder(p, b, c) / 'record.json') for p in PROJECTS for b in BUILDERS for c in CONDITIONS]
    assert digest(records) == barrier['records_sha256']
    assert all(r['status'] == 'complete' and r['valid_responses'] == 1 for r in records)
    jobs, rows = {}, []
    def add(project, builder, condition, model, method, task, kind):
        source = source_folder(project, builder, model, method, 20 if kind == 'fixed' else task)
        parsed = source_output(source)
        original_files = saved_files(source)
        package = read(library_folder(project, builder, condition) / 'package.json')
        record = read(library_folder(project, builder, condition) / 'record.json')
        assert digest(package) == record['package_sha256']
        row = {'project': project, 'builder': builder, 'condition': condition, 'model': model,
               'method': method, 'task': task, 'kind': kind, 'source': str(source.relative_to(ROOT)),
               'deployed': record['deployed'], 'baseline': baseline_score(project, builder, model, method, task, kind)}
        try:
            if parsed is None:
                raise ValueError('No executable original output')
            assert output_files(method, original_package(project, builder), parsed) == original_files, 'Original replay differs'
            files = output_files(method, package, parsed)
            row['unchanged_files'] = files == original_files
            sha = digest(files)
            page = OUT / 'pages' / project / sha
            if not page.exists():
                write_files(page, files)
            else:
                assert {p.relative_to(page).as_posix(): p.read_text() for p in page.rglob('*') if p.is_file()} == files
            key = f'{project}/task-{task}/{sha}'
            jobs[key] = {'project': project, 'task': task, 'page': str(page.relative_to(ROOT)), 'files_sha256': sha}
            row.update(score_key=key, files_sha256=sha)
        except (ValueError, KeyError, TypeError, TimeoutError, subprocess.TimeoutExpired) as error:
            row.update(score_key=None, compile_error=str(error)[:2000], unchanged_files=False)
        rows.append(row)

    for project in PROJECTS:
        for builder in BUILDERS:
            for condition in CONDITIONS:
                for model in MODELS:
                    for task in TEST_TASKS:
                        for method in ('plan', 'free_lib'):
                            add(project, builder, condition, model, method, task, 'candidate')
                        add(project, builder, condition, model, 'plan', task, 'fixed')
                for task in PUBLIC_TASKS:
                    add(project, builder, condition, MODELS[0], 'plan', task, 'development')
    assert len(rows) == 600
    value = {'generation_sha256': digest(barrier), 'rows': rows, 'jobs': jobs}
    path = OUT / 'replay-inputs.json'
    if path.exists():
        assert read(path) == value
    else:
        dump(path, value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=6)
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    value = materialize()
    if args.prepare_only:
        print('Prepared', len(value['rows']), 'comparisons;', len(value['jobs']), 'unique browser checks')
        return
    prepare()
    barrier = OUT / 'grading-started.json'
    if not barrier.exists():
        dump(barrier, {'started_utc': now(), 'inputs_sha256': digest(value)})
    assert read(barrier)['inputs_sha256'] == digest(value)
    def one(item):
        key, job = item
        folder = OUT / 'scores' / key
        target = folder / 'score.json'
        if not target.exists():
            dump(target, grade(job['project'], ROOT / job['page'], f'task-{job["task"]}', folder / 'report.json'))
        score = read(target)
        report = folder / 'report.json'
        assert hashlib.sha256(report.read_bytes()).hexdigest() == score['report_sha256']
        return key
    for project in PROJECTS:
        selected = [(k, j) for k, j in value['jobs'].items() if j['project'] == project]
        with ThreadPoolExecutor(max_workers=1 if project == 'bom' else min(6, args.workers)) as pool:
            for i, key in enumerate(pool.map(one, selected), 1):
                if i % 10 == 0 or i == len(selected):
                    print(project, i, '/', len(selected), flush=True)
    dump(OUT / 'evaluation-complete.json', {'comparisons': len(value['rows']), 'unique_scores': len(value['jobs']),
         'inputs_sha256': digest(value), 'finished_utc': now()})


if __name__ == '__main__':
    main()
