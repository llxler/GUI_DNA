"""Calibrate before requests and freeze source, public split, inputs and controls."""
from concurrent.futures import ThreadPoolExecutor
import argparse
from .core import *
from .browser import grade
from studies import browser_jobs


def prepare():
    assert not OUT.exists(), 'Never overwrite a stage'
    browser_jobs.OUT = OUT
    for project in PROJECTS:
        browser_jobs.prepare_harness('expansion', project)
    controls = []
    for project in PROJECTS:
        for builder in BUILDERS:
            package = read(package_path(project, builder))
            assert messages(project, 'plan', package)[1] == messages(project, 'free_lib', package)[1]
            for i, example in enumerate(package['examples']):
                folder = OUT / 'controls' / project / slug(builder) / str(i)
                files = validate_files(output_files('plan', package, example['plan']))
                write_files(folder, files)
                dump(folder / 'source-manifest.json', {'files_sha256': {n: __import__('hashlib').sha256(v.encode()).hexdigest() for n, v in files.items()}})
                controls.append({'project': project, 'builder': builder, 'example': i, 'folder': str(folder.relative_to(ROOT)), 'plan': example['plan']})
        write_files(OUT / 'blank' / project, {'index.html': '<!doctype html><title>blank</title>'})
    dump(OUT / 'inputs.json', {'jobs': jobs(), 'controls': controls, 'public': PUBLIC,
        'withheld': [f'task-{i}' for i in range(1, 21) if f'task-{i}' not in PUBLIC]})
    calibration = []
    def one(project):
        reference = UPSTREAM / 'projects' / project / 'src'
        for label, specs in [('public', PUBLIC), ('current', ['task-20'])]:
            result = grade(project, reference, specs, project + '/' + label, True)
            calibration.append({'project': project, 'label': label, 'all_passed': result['all_passed'], 'expected': True})
        for label, specs in [('blank-init', ['init'])]:
            result = grade(project, OUT / 'blank' / project, specs, project + '/' + label, True)
            calibration.append({'project': project, 'label': label, 'all_passed': result['all_passed'], 'expected': False})
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(one, PROJECTS))
    dump(OUT / 'calibration.json', sorted(calibration, key=lambda x: (x['project'],x['label'])))
    assert all(r['all_passed'] == r['expected'] for r in calibration)
    paths = [p for p in HERE.iterdir() if p.suffix in ('.py', '.md') and p.name not in ('analyze.py','README.md')]
    deps = ['studies/study_io.py', 'studies/browser_jobs.py', 'test/todomvc_dna/evaluate.py', 'test/webbench_expand/core.py',
        'test/webbench_expand/schema.py', 'test/webbench_expand/generate.py', 'test/webbench_expand/free_build.cjs',
        'test/interface_blind/core.py', 'test/interface_blind/compile.cjs', 'test/provider_ext.py',
        'test/streaming_provider_v2.py', 'src/gui_dna/provider.py', 'src/gui_dna/budget.py',
        'test/ledger_read.py', 'test/review_stage.py', 'test/webbench_expand/run.py', 'test/webbench_expand/resume.py',
        'pyproject.toml', 'uv.lock', 'test/webbench_expand/runtime-lock.json']
    paths += [ROOT / p for p in deps]
    paths += [p for p in (OUT / 'harness').rglob('*') if p.is_file() and 'node_modules' not in p.parts]
    paths += [p for p in (OUT / 'controls').rglob('*') if p.is_file()]
    paths += [p for p in (OUT / 'calibration').rglob('*') if p.is_file() and p.suffix in ('.json','.txt')]
    paths += [OUT / 'inputs.json', OUT / 'calibration.json']
    for project in PROJECTS:
        paths += [UPSTREAM / 'projects' / project / 'tasks.jsonl']
        paths += [p for p in (UPSTREAM / 'projects' / project / 'src').rglob('*') if p.is_file()]
        paths += [package_path(project, b) for b in BUILDERS]
    paths += [browser_jobs.RUNTIME['157'] / '@playwright/test/package.json', browser_jobs.RUNTIME['157'].parent / 'package-lock.json']
    paths += [browser_jobs.RUNTIME['157'] / '@web-bench/test-util' / n for n in ('index.js','css.js')]
    dump(OUT / 'snapshot.json', {'frozen_utc': now(), 'sha256': {str(p.relative_to(ROOT)): sha(p) for p in paths},
        'config': configuration(), 'scope': 'Exploratory matched feedback; no new library construction or independent sources.'})
    print('Calibrated and frozen', len(jobs()), 'candidates and', len(controls), 'controls', flush=True)


if __name__ == '__main__':
    prepare()
