"""Freeze, score and verify within-response table compiler comparisons without API calls."""
import argparse
from hashlib import sha256
from pathlib import Path

from gui_dna.provider import parse_json
from studies.interface_blind.core import validate_files, write_files
from studies.study_io import ROOT, cases_by_file, digest, dump, now, read, sha, source_files
from studies.table_library_sources import core
from studies.webbench_expand.core import compile_plan, validate_package
from studies.webbench_expand.generate import messages_for, output_files
from .adapter import bind_starter, score_pages

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/library-refinement-table-20261123'
REPORT = ROOT / 'studies/results/library-refinement-table-20261123.json'
PREVIOUS = ROOT / 'studies/results/table-library-sources-20261123.json'
ARCHIVE = ROOT / 'artifacts/webbench-expand-run/runs/table'
COHORTS = ('primary_20261123', 'independent_archive')
VARIANTS = ('original', 'starter_bound')


def rel(p):
    return str(p.relative_to(ROOT))


def freeze_page(files):
    manifest = {name: sha256(content.encode()).hexdigest() for name, content in files.items()}
    key = digest(manifest)
    folder = OUT / 'pages' / key
    if not folder.exists():
        write_files(folder, files)
    assert source_files(folder) == manifest
    return key


def first(cohort, task, arm, package, evidence):
    primary = cohort == COHORTS[0]
    if primary:
        folder = core.OUT / 'candidates' / arm / task / 'first'
        call = folder / 'call'
        expected = core.messages(arm, task, package)
    else:
        label, method = ('openai__gpt-5', 'plan') if arm == 'ai' else ('no_library', 'free')
        folder = ARCHIVE / label / core.MODEL.replace('/', '__') / method / task
        call = folder / 'call-0'
        expected = messages_for('table', task, method, package)
        assert read(folder / 'messages.json') == expected
        evidence[rel(folder / 'messages.json')] = sha(folder / 'messages.json')
    request = call / 'request.json'
    evidence[rel(request)] = sha(request)
    if not request.exists():
        raise ValueError(f'No frozen request at {call}')
    body = read(request)['body']
    assert body['model'] == core.MODEL and body['messages'] == expected
    assert (body['max_tokens'], body['seed'], body['temperature']) == ((8192, 20261123, .6) if primary else (12000, 20261112, .6))
    receipts = list(call.rglob('response.json'))
    if not receipts:
        return None, folder
    assert len(receipts) == 1, call
    response = receipts[0]
    response_request = response.parent / 'request.json'
    assert read(response_request)['body'] == body
    for path in (response_request, response):
        evidence[rel(path)] = sha(path)
    payload = read(response)
    assert payload['model'] == core.MODEL
    raw = payload['choices'][0]['message']['content']
    if not primary:
        output = folder / 'output-0.json'
        assert read(output)['text'] == raw
        evidence[rel(output)] = sha(output)
    return raw, folder


def candidate_files(cohort, task, arm, packages, evidence):
    package = packages['original'] if arm == 'ai' else None
    raw, source = first(cohort, task, arm, package, evidence)
    if raw is None:
        return {'received': False, 'pages': {}}
    pages = {}
    for name in (VARIANTS if arm == 'ai' else ('no_library',)):
        try:
            plan = parse_json(raw)
            if cohort == COHORTS[0]:
                files = core.render(arm, packages.get(name), plan)
            elif arm == 'ai':
                files = compile_plan(packages[name], plan)
            else:
                files = validate_files(output_files('free', None, plan))
            if 'index.html' not in files:
                raise ValueError('Missing index.html')
        except (ValueError, KeyError, TypeError):
            pages[name] = None
            continue
        pages[name] = freeze_page(files)
    source_page = source / ('page' if cohort == COHORTS[0] else 'version-0')
    original = pages['original' if arm == 'ai' else 'no_library']
    assert (original is not None) == source_page.exists(), (cohort, task, arm)
    if original:
        assert original == digest(source_files(source_page)), (cohort, task, arm)
    if arm == 'ai':
        assert bool(pages['original']) == bool(pages['starter_bound']), (cohort, task)
    return {'received': True, 'pages': pages}


def archive_inputs():
    runtime = ROOT / 'artifacts/webbench-expand-runtime-157'
    paths = [HERE / f for f in ('PROTOCOL.md', 'adapter.py', 'bind_starter.js', 'run.py')]
    paths += [core.AI, PREVIOUS, Path(core.__file__), ROOT / 'studies/browser_jobs.py',
              ROOT / 'studies/study_io.py', ROOT / 'studies/webbench_expand/core.py',
              ROOT / 'studies/webbench_expand/generate.py', ROOT / 'studies/webbench_expand/schema.py',
              ROOT / 'studies/interface_blind/core.py', ROOT / 'studies/interface_blind/compile.cjs',
              ROOT / 'src/gui_dna/provider.py', runtime / 'package-lock.json']
    paths += list((core.SOURCE / 'src-init').glob('*')) + list((runtime / 'test-util').glob('*'))
    paths += [f for f in (core.SOURCE / 'test').rglob('*') if f.is_file()]
    return {rel(p): sha(p) for p in paths}


def freeze():
    path = OUT / 'freeze.json'
    if path.exists():
        return verified_freeze()
    if (OUT / 'scores').exists():
        raise RuntimeError('A new freeze cannot follow scores')
    original = read(core.AI)
    packages = {'original': original, 'starter_bound': bind_starter(original)}
    evidence = archive_inputs()
    for name, pkg in packages.items():
        pkg_path = OUT / f'{name}-package.json'
        dump(pkg_path, pkg)
        evidence[rel(pkg_path)] = sha(pkg_path)
        problems = validate_package(pkg, OUT / 'public-validation' / name)
        if problems:
            raise ValueError(problems)
    cohorts = {cohort: {task: {arm: candidate_files(cohort, task, arm, packages, evidence)
                                for arm in ('ai', 'direct')} for task in core.TASKS} for cohort in COHORTS}
    fixed = {name: freeze_page(core.render('ai', pkg, pkg['examples'][1]['plan'])) for name, pkg in packages.items()}
    manifest = {'study': 'library-refinement-table-20261123', 'inputs_sha256': evidence,
                'cohorts': cohorts, 'fixed_example2_pages': fixed, 'sealed_utc': now()}
    dump(path, manifest)
    return manifest


def verified_freeze():
    manifest = read(OUT / 'freeze.json')
    for p, expected in manifest['inputs_sha256'].items():
        assert sha(ROOT / p) == expected, p
    return manifest


def grade_jobs(manifest):
    jobs = {}
    def add(key, task):
        if key is None:
            return
        folder = OUT / 'pages' / key
        assert digest(source_files(folder)) == key
        job = f'{task}-{key}'
        jobs[job] = (job, task, folder)
    for cohort in manifest['cohorts'].values():
        for task, record in cohort.items():
            for arm in record.values():
                for key in arm['pages'].values():
                    add(key, task)
    for task in core.TASKS:
        for key in manifest['fixed_example2_pages'].values():
            add(key, task)
    return list(jobs.values())


def evaluate(workers):
    manifest = verified_freeze()
    scores = score_pages(OUT, grade_jobs(manifest), workers)
    path = OUT / 'scores-complete.json'
    hashes = {'freeze_sha256': sha(OUT / 'freeze.json'), 'unique_scores': scores}
    if path.exists():
        assert hashes == read(path)
    else:
        dump(path, hashes)


def summary(rows, name):
    present = [r[name] for r in rows.values() if r[name] is not None]
    return {'planned': len(rows), 'received': len(present), 'valid': sum(r['valid'] for r in present),
            'passed': sum(r['passed'] for r in present)}


def paired(rows):
    groups = {'gained': [], 'lost': [], 'both_pass': [], 'both_fail': [], 'unknown': []}
    for task, row in rows.items():
        old, new = row['original'], row['starter_bound']
        if old is None or new is None:
            group = 'unknown'
        else:
            group = {(True, True): 'both_pass', (False, True): 'gained', (True, False): 'lost',
                     (False, False): 'both_fail'}[(old['passed'], new['passed'])]
        groups[group].append(task)
    return groups


def report():
    frozen = verified_freeze()
    scores = read(OUT / 'scores-complete.json')
    assert scores['freeze_sha256'] == sha(OUT / 'freeze.json')
    checked = {}
    for job, task, folder in grade_jobs(frozen):
        item = scores['unique_scores'][job]
        source = OUT / 'scores' / job / 'report.json'
        assert item['report_sha256'] == sha(source)
        cases = cases_by_file(read(source))
        assert set(cases) == {task} and cases[task]
        assert item['passed'] == all(case['passed'] for case in cases[task])
        checked[job] = item
    assert set(checked) == set(scores['unique_scores'])
    def outcome(key, task, received=True):
        if not received:
            return None
        if key is None:
            return {'valid': False, 'passed': False}
        return {'valid': True, 'page_sha256': key, **checked[f'{task}-{key}']}
    cohorts = {}
    previous = read(PREVIOUS)
    for name, records in frozen['cohorts'].items():
        targets = {}
        for task, arms in records.items():
            targets[task] = {variant: outcome(arms[arm]['pages'].get(variant), task, arms[arm]['received'])
                             for arm, names in [('ai', VARIANTS), ('direct', ['no_library'])] for variant in names}
            if name == COHORTS[0]:
                for variant, arm in [('original', 'ai'), ('no_library', 'direct')]:
                    item, prior = targets[task][variant], previous['targets'][task][arm]['first']
                    assert prior['response'] and (item['valid'], item['passed']) == (prior['valid'], prior['passed'])
        cohorts[name] = {'methods': {v: summary(targets, v) for v in (*VARIANTS, 'no_library')},
                         'paired_tasks': paired(targets), 'targets': targets}
    fixed = {task: {v: outcome(key, task) for v, key in frozen['fixed_example2_pages'].items()} for task in core.TASKS}
    fixed_comparison = {'methods': {v: summary(fixed, v) for v in VARIANTS}, 'paired_tasks': paired(fixed), 'targets': fixed}
    assert fixed_comparison['methods']['original']['passed'] == previous['fixed_page_controls']['ai_example2']['passed']
    return {'study': frozen['study'], 'project': 'table', 'post_hoc': True, 'model_calls': 0, 'additional_api_cost_usd': 0,
            'library_builder': 'openai/gpt-5', 'planner': core.MODEL,
            'intervention': 'Rebind generated boot scripts to public src-init/index.html and append public src-init/index.css. Same original GPT-5 package, schema, examples, behavior code and sampled plans.',
            'unit': 'One official current-task file per target, all twenty target positions in each named cohort.',
            'decision_rule': 'Strict paired increase in both cohorts with all twenty responses received.',
            'confirmed_within_archived_plans': all(not c['paired_tasks']['unknown'] and len(c['paired_tasks']['gained']) > len(c['paired_tasks']['lost']) for c in cohorts.values()),
            'cohorts': cohorts, 'fixed_documentation_example_2': fixed_comparison,
            'limitations': 'Same AI-built library and benchmark targets across cohorts. Includes knowledge of prior deficiencies and historical scores. The new shell binding is deterministic; this does not validate an improved AI builder prompt.',
            'runtime': previous['evaluation_runtime'], 'protocol_sha256': sha(HERE / 'PROTOCOL.md'),
            'package_file_sha256': {v: sha(OUT / f'{v}-package.json') for v in VARIANTS},
            'freeze_sha256': sha(OUT / 'freeze.json'), 'sealed_utc': frozen['sealed_utc'],
            'unique_official_reports': len(checked), 'scores_complete_sha256': sha(OUT / 'scores-complete.json')}


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('action', choices=('freeze', 'score', 'report', 'check'))
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    if args.action == 'freeze':
        manifest = freeze()
        print('Frozen unique target/page jobs:', len(grade_jobs(manifest)))
    elif args.action == 'score':
        if args.workers <= 0:
            parser.error('--workers must be positive')
        evaluate(args.workers)
    else:
        result = report()
        if args.action == 'check' or REPORT.exists():
            assert result == read(REPORT)
        else:
            dump(REPORT, result)
        print({k: v['methods'] for k, v in result['cohorts'].items()})
        print('Fixed example:', result['fixed_documentation_example_2']['methods'])


if __name__ == '__main__':
    main()
