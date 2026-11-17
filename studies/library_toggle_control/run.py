"""Freeze and score prespecified conditional configuration controls without API calls."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import argparse
import hashlib
import random
import shutil
import subprocess
from pathlib import Path

from test.library_repair.core import (ROOT, PROJECTS, BUILDERS, TEST_TASKS, read, dump, digest,
    original_package, source_folder, source_output, slug)
from test.library_repair.run import now, verify_frozen
from test.library_repair.evaluate import baseline_score
from test.library_repair.available import verify as verify_previous
from test.webbench_expand.generate import output_files
from test.webbench_expand.schema import validate
from test.webbench_expand import evaluate_pinned as evaluator
from test.interface_blind.core import write_files

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/library-toggle-control-20261114'
PREVIOUS = ROOT / 'artifacts/library-repair-available-20261113'


def boolean_paths(value, prefix=()):
    if type(value) is bool:
        return [prefix]
    if isinstance(value, dict):
        return [p for k, v in sorted(value.items()) for p in boolean_paths(v, (*prefix, k))]
    if isinstance(value, list):
        return [p for k, v in enumerate(value) for p in boolean_paths(v, (*prefix, k))]
    return []


def variant(anchor, paths, mask):
    result = deepcopy(anchor)
    for bit, path in enumerate(paths):
        parent = result
        for key in path[:-1]:
            parent = parent[key]
        parent[path[-1]] = bool(mask & (1 << bit))
    return result


def prepare():
    verify_frozen()
    verify_previous()
    assert not (OUT / 'inputs.json').exists(), 'Do not replace frozen configurations'
    libraries, rows, jobs = [], [], {}
    sources = [HERE / 'run.py', HERE / 'PROTOCOL.md', ROOT / 'test/webbench_expand/evaluate_pinned.py']
    for pi, project in enumerate(PROJECTS):
        for bi, builder in enumerate(BUILDERS):
            package = original_package(project, builder)
            source = source_folder(project, builder, 'openai/gpt-oss-120b', 'plan', 20)
            anchor = source_output(source)
            paths = boolean_paths(anchor)
            population = 2 ** len(paths)
            seed = 20261114 + pi * 2 + bi
            masks = list(range(population)) if population <= 32 else sorted(random.Random(seed).sample(range(population), 32))
            name = project + '/' + slug(builder)
            libraries.append({'project': project, 'builder': builder, 'source': str(source.relative_to(ROOT)),
                'anchor': anchor, 'boolean_paths': paths, 'population': population, 'sampled': len(masks),
                'exhaustive_slice': population <= 32, 'seed': seed, 'masks': masks,
                'package_sha256': digest(package)})
            for mask in masks:
                plan = variant(anchor, paths, mask)
                validate(package['plan_schema'], plan)
                plan_path = OUT / 'plans' / name / f'{mask}.json'
                dump(plan_path, plan)
                error, files = None, None
                try:
                    files = output_files('plan', package, plan)
                except (ValueError, KeyError, TypeError, TimeoutError, subprocess.TimeoutExpired) as issue:
                    error = str(issue)[:2000]
                for task in TEST_TASKS:
                    row = {'project': project, 'builder': builder, 'mask': mask, 'task': task,
                           'plan': str(plan_path.relative_to(ROOT)), 'compile_error': error,
                           'anchor_baseline': baseline_score(project, builder, 'openai/gpt-oss-120b', 'plan', task, 'fixed')}
                    if files is not None:
                        sha = digest(files)
                        page = OUT / 'pages' / project / sha
                        if not page.exists():
                            write_files(page, files)
                        key = f'{project}/task-{task}/{sha}'
                        jobs[key] = {'project': project, 'task': task, 'page': str(page.relative_to(ROOT)), 'files_sha256': sha}
                        row['score_key'] = key
                    else:
                        row['score_key'] = None
                    rows.append(row)
            sources += list(source.glob('output-*.json')) + [source / 'record.json']
            sources.append(ROOT / 'artifacts/webbench-expand-build/libraries' / project / slug(builder) / 'package.json')
    assert len(rows) == 645 and sum(x['sampled'] for x in libraries) == 129
    dump(OUT / 'inputs.json', {'libraries': libraries, 'rows': rows, 'jobs': jobs})
    sources += [OUT / 'inputs.json', *sorted((OUT / 'plans').rglob('*.json'))]
    dump(OUT / 'snapshot.json', {'frozen_utc': now(), 'sha256': {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}})
    print('Frozen', len(rows), 'comparisons;', len(jobs), 'distinct page/task scores', flush=True)


def verify():
    verify_frozen()
    for name, sha in read(OUT / 'snapshot.json')['sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha, name
    inputs = read(OUT / 'inputs.json')
    for job in inputs['jobs'].values():
        page = ROOT / job['page']
        assert digest({p.relative_to(page).as_posix(): p.read_text() for p in page.rglob('*') if p.is_file()}) == job['files_sha256']
    return inputs


def evaluate(project):
    inputs = verify()
    evaluator.HARNESS = OUT / 'harness'
    evaluator.prepare()
    previous = read(PREVIOUS / 'inputs.json')
    start = OUT / f'grading-started-{project}.json'
    if not start.exists():
        dump(start, {'started_utc': now(), 'inputs_sha256': digest(inputs)})
    assert read(start)['inputs_sha256'] == digest(inputs)
    assert read(OUT / 'snapshot.json')['frozen_utc'] <= read(start)['started_utc']
    selected = [(k, j) for k, j in inputs['jobs'].items() if j['project'] == project]
    def one(item):
        key, job = item
        folder = OUT / 'scores' / key
        if (folder / 'score.json').exists():
            return
        if key in previous['jobs']:
            source = PREVIOUS / 'scores' / key
            score = read(source / 'score.json')
            assert hashlib.sha256((source / 'report.json').read_bytes()).hexdigest() == score['report_sha256']
            old_page = ROOT / previous['jobs'][key]['page']
            assert digest({p.relative_to(old_page).as_posix(): p.read_text() for p in old_page.rglob('*') if p.is_file()}) == job['files_sha256']
            folder.mkdir(parents=True, exist_ok=True)
            for name in ('score.json', 'report.json'):
                shutil.copy2(source / name, folder / name)
            dump(folder / 'reused.json', {'source': str(source.relative_to(ROOT)), 'report_sha256': score['report_sha256']})
        else:
            dump(folder / 'score.json', evaluator.grade(project, ROOT / job['page'], f'task-{job["task"]}', folder / 'report.json'))
    with ThreadPoolExecutor(max_workers=1 if project == 'bom' else 6) as pool:
        for i, _ in enumerate(pool.map(one, selected), 1):
            if i % 10 == 0 or i == len(selected):
                print(project, i, '/', len(selected), flush=True)
    dump(OUT / f'evaluation-complete-{project}.json', {'finished_utc': now(), 'inputs_sha256': digest(inputs)})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['prepare', 'evaluate'])
    parser.add_argument('--project', choices=PROJECTS)
    args = parser.parse_args()
    if args.phase == 'prepare':
        prepare()
    else:
        assert args.project
        evaluate(args.project)
