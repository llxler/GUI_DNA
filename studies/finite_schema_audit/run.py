"""Freeze a complete finite schema population, then score its necessary condition."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import itertools
from pathlib import Path

from test.history_replay.run import ROOT, now, read, dump, sha, digest, source_files
from test.webbench_expand.generate import output_files
from test.webbench_expand.schema import validate
from test.webbench_expand import evaluate_pinned as evaluator
from test.interface_blind.core import write_files

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/finite-schema-audit-20261115'
PACKAGE = ROOT / 'artifacts/webbench-expand-build/libraries/calculator/openai__gpt-5/package.json'


def population(schema):
    assert schema['type'] == 'object' and not schema['required'] and schema['additionalProperties'] is False
    keys, domains = list(schema['properties']), []
    for child in schema['properties'].values():
        values = [False, True] if child['type'] == 'boolean' else child['enum']
        assert child['type'] in ('string', 'boolean') and None not in values
        domains.append([None, *values])
    return [{k: v for k, v in zip(keys, values) if v is not None} for values in itertools.product(*domains)]


def prepare():
    assert not OUT.exists(), 'Preserve existing stage'
    package = read(PACKAGE)
    plans = population(package['plan_schema'])
    assert len(plans) == 1215 and len({digest(p) for p in plans}) == 1215
    evaluator.HARNESS = OUT / 'harness'
    evaluator.prepare()
    rows, jobs = [], {}
    for i, plan in enumerate(plans):
        validate(package['plan_schema'], plan)
        files = output_files('plan', package, plan)
        key = digest(files)
        page = OUT / 'pages' / key
        if key not in jobs:
            write_files(page, files)
            jobs[key] = {'project': 'calculator', 'page': str(page.relative_to(ROOT)), 'files': source_files(page)}
        rows.append({'index': i, 'plan': plan, 'score_key': key})
    dump(OUT / 'inputs.json', {'package': str(PACKAGE.relative_to(ROOT)), 'rows': rows, 'jobs': jobs,
                             'scope': 'Complete semantic configuration population; one frozen calculator/GPT-5 library and init necessary condition only.'})
    blank = OUT / 'blank'
    blank.mkdir(); (blank / 'index.html').write_text('<!doctype html><title>blank</title>')
    dependencies = [HERE / n for n in ('run.py', '__init__.py', 'PROTOCOL.md')]
    dependencies += [ROOT / 'test' / n for n in ('history_replay/run.py', 'webbench_expand/core.py', 'webbench_expand/schema.py',
        'webbench_expand/generate.py', 'webbench_expand/evaluate_pinned.py', 'interface_blind/core.py', 'todomvc_dna/evaluate.py')]
    dependencies += [PACKAGE, OUT / 'inputs.json', blank / 'index.html', ROOT / 'test/webbench_expand/runtime-lock.json']
    dependencies += [p for p in (OUT / 'harness/calculator').rglob('*') if p.is_file() and 'node_modules' not in p.parts]
    dependencies += [p for p in (ROOT / 'artifacts/web-bench/projects/calculator/src').rglob('*') if p.is_file()]
    dump(OUT / 'snapshot.json', {'frozen_utc': now(), 'sha256': {str(p.relative_to(ROOT)): sha(p) for p in dependencies}})
    print('Frozen', len(rows), 'configurations;', len(jobs), 'distinct complete sources', flush=True)


def verify():
    for path, value in read(OUT / 'snapshot.json')['sha256'].items():
        assert sha(ROOT / path) == value, path
    inputs = read(OUT / 'inputs.json')
    for job in inputs['jobs'].values():
        assert source_files(ROOT / job['page']) == job['files']
    return inputs


def evaluate():
    inputs = verify()
    evaluator.HARNESS = OUT / 'harness'
    assert not (OUT / 'grading-started.json').exists(), 'Do not overwrite observations'
    dump(OUT / 'grading-started.json', {'started_utc': now(), 'inputs_sha256': digest(inputs)})
    calibration = {}
    for name, page, expected in [('reference', ROOT / 'artifacts/web-bench/projects/calculator/src', True),
                                 ('blank', OUT / 'blank', False)]:
        value = evaluator.grade('calculator', page, 'init', OUT / 'calibration' / name / 'report.json')
        calibration[name] = value
        dump(OUT / 'calibration' / name / 'score.json', value)
        assert value['all_passed'] == expected, name
    dump(OUT / 'calibration.json', calibration)
    def one(item):
        key, job = item
        value = evaluator.grade('calculator', ROOT / job['page'], 'init', OUT / 'scores' / key / 'report.json')
        dump(OUT / 'scores' / key / 'score.json', value)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i, _ in enumerate(pool.map(one, inputs['jobs'].items()), 1):
            if i % 16 == 0 or i == len(inputs['jobs']): print(i, '/', len(inputs['jobs']), flush=True)
    dump(OUT / 'evaluation-complete.json', {'finished_utc': now(), 'inputs_sha256': digest(inputs)})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=['prepare', 'evaluate'])
    globals()[parser.parse_args().action]()
