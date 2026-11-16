"""Freeze a bounded configuration search, then evaluate separate project queues."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import subprocess

from test.history_replay import run as history
from test.history_replay.run import ROOT, read, dump, sha, digest, now, source_files
from test.webbench_expand.core import PROJECTS, BUILDERS, UPSTREAM, compile_plan
from test.interface_blind.core import write_files, slug
from test.library_repair.core import source_folder, source_output
from .population import select

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/schema-search-20261116'


def prepare():
    assert not OUT.exists()
    history.OUT = OUT
    rows, jobs, libraries, sources = [], {}, [], []
    endpoints = {'current': ['task-20'], 'history': ['init', *[f'task-{i}' for i in range(1,21)]]}
    for project in PROJECTS:
        history.prepare_harness('expansion', project)
        write_files(OUT / 'blank' / project, {'index.html': '<!doctype html><title>blank</title>'})
        for builder in BUILDERS:
            if project == 'calculator' and builder == 'openai/gpt-5': continue
            package_path = ROOT / 'artifacts/webbench-expand-build/libraries' / project / slug(builder) / 'package.json'
            package = read(package_path)
            source = source_folder(project,builder,'openai/gpt-oss-120b','plan',20)
            anchors = [e['plan'] for e in package['examples']] + [source_output(source)]
            population = select(package['plan_schema'], anchors)
            library = project + '/' + slug(builder)
            pool_path = OUT / 'populations' / library / 'pool.json'; dump(pool_path, population)
            libraries.append({'project': project, 'builder': builder, 'pool': str(pool_path.relative_to(ROOT)),
                'package': str(package_path.relative_to(ROOT)), 'population_size': len(population['pool']),
                'selected_count': len(population['selected']), 'anchor_source': str(source.relative_to(ROOT))})
            for key in population['selected']:
                plan = population['pool'][key]['plan']; page = None; error = None
                try:
                    files = compile_plan(package, plan)
                    page = OUT / 'pages' / project / digest(files)
                    if not page.exists(): write_files(page, files)
                except (ValueError, KeyError, TypeError, TimeoutError, subprocess.TimeoutExpired) as issue:
                    error = f'{type(issue).__name__}: {issue}'[:2000]
                for endpoint, specs in endpoints.items():
                    score_key = digest([project, source_files(page), specs]) if page else None
                    rows.append({'project': project, 'builder': builder, 'plan_key': key, 'endpoint': endpoint,
                        'score_key': score_key, 'compile_error': error})
                    if score_key:
                        jobs[score_key] = {'project': project, 'harness': '157-' + project, 'runtime': '157',
                            'page': str(page.relative_to(ROOT)), 'files': source_files(page), 'specs': specs, 'all_tests': False}
            sources += [package_path, pool_path, source / 'record.json', *source.glob('output-*.json')]
    dump(OUT / 'inputs.json', {'rows': rows, 'jobs': jobs, 'libraries': libraries})
    sources += [OUT / 'inputs.json', HERE / 'run.py', HERE / 'population.py', HERE / '__init__.py', HERE / 'PROTOCOL.md']
    sources += [ROOT / p for p in ('test/history_replay/run.py', 'test/todomvc_dna/evaluate.py', 'test/library_repair/core.py',
        'test/webbench_expand/core.py', 'test/webbench_expand/schema.py', 'test/interface_blind/core.py',
        'test/interface_blind/compile.cjs', 'test/webbench_expand/runtime-lock.json')]
    sources += [p for p in (OUT / 'harness').rglob('*') if p.is_file() and 'node_modules' not in p.parts]
    sources += [p for p in (OUT / 'blank').rglob('*') if p.is_file()]
    for project in PROJECTS:
        sources += [p for p in (UPSTREAM / 'projects' / project / 'src').rglob('*') if p.is_file()]
    sources += [history.RUNTIME['157'].parent / 'package-lock.json', history.RUNTIME['157'] / '@playwright/test/package.json']
    sources += [history.RUNTIME['157'] / '@web-bench/test-util' / n for n in ('index.js','css.js')]
    dump(OUT / 'snapshot.json', {'frozen_utc': now(), 'sha256': {str(p.relative_to(ROOT)): sha(p) for p in sources}})
    print('Frozen', len(rows), 'comparisons;', len(jobs), 'unique sources/test sets', flush=True)


def verify():
    for path, expected in read(OUT / 'snapshot.json')['sha256'].items(): assert sha(ROOT / path) == expected, path
    inputs = read(OUT / 'inputs.json')
    for job in inputs['jobs'].values(): assert source_files(ROOT / job['page']) == job['files']
    return inputs


def evaluate(project):
    inputs = verify(); history.OUT = OUT
    assert datetime.now(timezone.utc) < datetime.fromisoformat('2026-11-16T07:00:00+00:00')
    if project == 'bom':
        assert (ROOT / 'artifacts/matched-feedback-20261116/evaluation-complete.json').exists(), 'Serialize all BOM experiments'
    assert not (OUT / f'grading-started-{project}.json').exists()
    for label, specs, page, expected in [
        ('current', ['task-20'], UPSTREAM / 'projects' / project / 'src', True),
        ('history', ['init', *[f'task-{i}' for i in range(1,21)]], UPSTREAM / 'projects' / project / 'src', True),
        ('blank', ['task-20'], OUT / 'blank' / project, False)]:
        job = {'project': project, 'harness': '157-' + project, 'runtime': '157', 'page': str(page.relative_to(ROOT)),
            'files': source_files(page), 'specs': specs, 'all_tests': False}
        result = history.grade(project + '/' + label, job, True)
        assert result['all_passed'] == expected
    dump(OUT / f'grading-started-{project}.json', {'started_utc': now(), 'inputs_sha256': sha(OUT / 'inputs.json')})
    selected = [(key,job) for key,job in inputs['jobs'].items() if job['project'] == project]
    def one(item):
        assert datetime.now(timezone.utc) < datetime.fromisoformat('2026-11-16T07:00:00+00:00')
        return history.grade(*item)
    with ThreadPoolExecutor(max_workers=1 if project == 'bom' else 3) as pool:
        for i,_ in enumerate(pool.map(one, selected), 1):
            if i % 16 == 0 or i == len(selected): print(project, i, '/', len(selected), flush=True)
    dump(OUT / f'evaluation-complete-{project}.json', {'finished_utc': now(), 'inputs_sha256': sha(OUT / 'inputs.json')})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=['prepare','evaluate'])
    parser.add_argument('--project', choices=PROJECTS); args = parser.parse_args()
    if args.action == 'prepare': prepare()
    else:
        assert args.project
        evaluate(args.project)
