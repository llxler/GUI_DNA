"""Exhaust all seven interaction switches for one fixed-style table task.

Posthoc and zero API. This enumerates a conditional slice, not the full schema.
"""
import argparse
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from itertools import product
import hashlib

from .core import ROOT, HERE, read, dump, digest, source_folder, source_output, original_package, compile_plan
from .run import now, verify_frozen
from .evaluator import prepare as prepare_harness, grade
from test.interface_blind.core import write_files

OUT = ROOT / 'artifacts/library-repair-space-20261113'


def prepare():
    verify_frozen()
    assert not (OUT / 'grading-started.json').exists()
    source = source_folder('table', 'openai/gpt-5', 'openai/gpt-oss-120b', 'plan', 20)
    base = source_output(source)
    package = original_package('table', 'openai/gpt-5')
    switches = list(base['interactions'])
    assert len(switches) == 7 and all(type(v) is bool for v in base['interactions'].values())
    assert set(switches) == set(package['plan_schema']['properties']['interactions']['properties'])
    assert all(v['type'] == 'boolean' for v in package['plan_schema']['properties']['interactions']['properties'].values())
    previous = read(ROOT / 'test/results/library-repair-mechanism.json')
    reuse = {r['files_sha256']: r for r in previous['rows'] if r['name'] in ('original', 'original_plus_stop')}
    rows, jobs = [], {}
    anchor = 'e.preventDefault();\n      const pos = grid.getCellCoords(cell);'
    inserted = 'e.preventDefault();\n      e.stopPropagation();\n      const pos = grid.getCellCoords(cell);'
    for bits in product((False, True), repeat=7):
        plan = deepcopy(base)
        plan['interactions'] = dict(zip(switches, bits))
        original = compile_plan(package, plan)
        assert original['index.js'].count(anchor) == 1
        repaired = {**original, 'index.js': original['index.js'].replace(anchor, inserted)}
        for condition, files in (('original', original), ('stop_only', repaired)):
            sha = digest(files)
            page = OUT / 'pages' / sha
            write_files(page, files)
            row = {'condition': condition, 'bits': ''.join('1' if b else '0' for b in bits),
                   'plan': plan, 'files_sha256': sha, 'page': str(page.relative_to(ROOT))}
            if sha in reuse:
                row['report'] = reuse[sha]['report']
                row['score'] = str((ROOT / row['report']).with_name('score.json').relative_to(ROOT))
                row['reused'] = True
            else:
                row['report'] = str((OUT / 'scores' / sha / 'report.json').relative_to(ROOT))
                row['score'] = str((OUT / 'scores' / sha / 'score.json').relative_to(ROOT))
                row['reused'] = False
                jobs[sha] = row
            rows.append(row)
    assert len(rows) == 256
    value = {'frozen_utc': now(), 'posthoc': True, 'project': 'table', 'task': 'task-20',
        'builder': 'openai/gpt-5', 'source': str(source.relative_to(ROOT)), 'package_sha256': digest(package),
        'switches': switches, 'fixed_fields': {k: v for k, v in base.items() if k != 'interactions'},
        'selection': 'After observing the menu propagation defect, enumerate all 2^7 boolean switch assignments. '
                     'Hold all four style fields at the saved final-plan values. Apply one fixed source-line intervention, no other repair.',
        'scope': 'Exhaustive only for this fixed-style slice and task; not full-schema impossibility, all-task correctness, or independent 128-task evidence.',
        'reuse': 'Only the two exact all-enabled pages already scored in the four-page mechanism intervention; retain those outcomes without reruns.',
        'rows': rows, 'jobs': jobs,
        'script_sha256': hashlib.sha256((HERE / 'finite_space.py').read_bytes()).hexdigest()}
    target = OUT / 'inputs.json'
    if target.exists():
        saved = read(target)
        value['frozen_utc'] = saved['frozen_utc']
        assert value == saved
    else:
        dump(target, value)
    print('Frozen', len(rows), 'conditional configurations;', len(jobs), 'new browser checks')


def verify():
    verify_frozen()
    value = read(OUT / 'inputs.json')
    assert hashlib.sha256((HERE / 'finite_space.py').read_bytes()).hexdigest() == value['script_sha256']
    assert digest(original_package('table', 'openai/gpt-5')) == value['package_sha256']
    for row in value['rows']:
        page = ROOT / row['page']
        assert digest({p.relative_to(page).as_posix(): p.read_text() for p in page.rglob('*') if p.is_file()}) == row['files_sha256']
    return value


def evaluate():
    value = verify()
    prepare_harness()
    target = OUT / 'grading-started.json'
    if not target.exists():
        dump(target, {'started_utc': now(), 'inputs_sha256': digest(value)})
    assert read(target)['inputs_sha256'] == digest(value)
    assert value['frozen_utc'] <= read(target)['started_utc']
    def one(row):
        score = ROOT / row['score']
        if not score.exists():
            dump(score, grade('table', ROOT / row['page'], 'task-20', ROOT / row['report']))
    with ThreadPoolExecutor(max_workers=6) as pool:
        for i, _ in enumerate(pool.map(one, value['jobs'].values()), 1):
            if i % 20 == 0 or i == len(value['jobs']):
                print('conditional table search', i, '/', len(value['jobs']), flush=True)
    dump(OUT / 'evaluation-complete.json', {'inputs_sha256': digest(value), 'finished_utc': now()})


def analyze():
    value = verify()
    assert read(OUT / 'evaluation-complete.json')['inputs_sha256'] == digest(value)
    rows = []
    for row in value['rows']:
        score = read(ROOT / row['score'])
        assert hashlib.sha256((ROOT / row['report']).read_bytes()).hexdigest() == score['report_sha256']
        rows.append({**row, 'passed': bool(score['all_passed'])})
    groups = [{'condition': c, 'n': sum(r['condition'] == c for r in rows),
               'passed': sum(r['passed'] for r in rows if r['condition'] == c),
               'passing_bits': [r['bits'] for r in rows if r['condition'] == c and r['passed']]}
              for c in ('original', 'stop_only')]
    result = {k: value[k] for k in ('posthoc', 'project', 'task', 'builder', 'source', 'switches', 'fixed_fields', 'selection', 'scope', 'reuse')}
    result.update(groups=groups, rows=rows, new_browser_scores=len(value['jobs']), reused_scores=len(rows)-len(value['jobs']))
    dump(ROOT / 'test/results/library-repair-space.json', result)
    print(groups)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['prepare', 'evaluate', 'analyze'])
    phase = parser.parse_args().phase
    {'prepare': prepare, 'evaluate': evaluate, 'analyze': analyze}[phase]()
