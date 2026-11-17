"""Independent harness location with unchanged pinned official assertions."""
import hashlib
from pathlib import Path

from test.webbench_expand import evaluate_pinned as pinned
from test.webbench_expand.core import UPSTREAM, PROJECTS, dump
from test.behavior_feedback import feedback_message
from .core import OUT, PUBLIC_TASKS, TEST_TASKS, BUILDERS, MODELS, source_folder, source_output, read

HARNESS = OUT / 'harness'


def prepare():
    pinned.HARNESS = HARNESS
    return pinned.prepare()


def grade(project, folder, task, report):
    pinned.HARNESS = HARNESS
    return pinned.grade(project, folder, task, report)


def public_feedback(report, task):
    result = []
    def walk(suite):
        for spec in suite.get('specs', []):
            assert Path(spec['file']).name == f'{task}.spec.js', 'Unexpected file in development feedback'
            for test in spec.get('tests', []):
                runs = test.get('results', [])
                result.append({'title': spec['title'], 'status': runs[-1]['status'] if runs else 'not_run',
                               'errors': [feedback_message(e.get('message', '')) for r in runs for e in r.get('errors', [])]})
        for child in suite.get('suites', []):
            walk(child)
    walk(report)
    assert result
    return result


def prepare_inputs():
    assert not (OUT / 'review-manifest.json').exists(), 'Input boundary is already frozen'
    manifest = prepare()
    inputs, source_hashes = {}, {}
    for project in PROJECTS:
        inputs[project] = {}
        for builder in BUILDERS:
            public = {}
            for k in PUBLIC_TASKS:
                folder = source_folder(project, builder, MODELS[0], 'plan', k)
                record = read(folder / 'record.json')
                version = record['versions'][-1]
                report = folder / version / 'official-report.json'
                expected_sha = read(folder / 'hidden.json')['final']['report_sha256']
                assert hashlib.sha256(report.read_bytes()).hexdigest() == expected_sha
                public[f'task-{k}'] = {'plan': source_output(folder), 'feedback': public_feedback(read(report), f'task-{k}')}
                source_hashes[str(report.relative_to(OUT.parents[1]))] = expected_sha
            inputs[project][builder] = public
    dump(OUT / 'public-inputs.json', inputs)
    dump(OUT / 'input-provenance.json', {'official_runtime': manifest, 'public_reports_sha256': source_hashes,
                                        'public_tasks': PUBLIC_TASKS, 'test_tasks': TEST_TASKS})


def calibrate():
    prepare()
    rows = []
    for project in PROJECTS:
        for k in sorted(set(PUBLIC_TASKS) | set(TEST_TASKS)):
            target = OUT / 'calibration' / project / f'task-{k}'
            score = target / 'score.json'
            if not score.exists():
                dump(score, grade(project, UPSTREAM / 'projects' / project / 'src', f'task-{k}', target / 'report.json'))
            value = read(score)
            rows.append({'project': project, 'task': k, **value})
            print('reference', project, k, value['all_passed'], flush=True)
    dump(OUT / 'calibration-complete.json', {'rows': rows, 'all_passed': all(r['all_passed'] for r in rows)})
    assert all(r['all_passed'] for r in rows), 'Reference discrepancy; do not start API calls'


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('phase', choices=['prepare', 'calibrate'])
    args = p.parse_args()
    (prepare_inputs if args.phase == 'prepare' else calibrate)()
