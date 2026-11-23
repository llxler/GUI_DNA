"""Reconstruct the chart comparison from saved requests, responses, and official reports."""
from collections import Counter
from decimal import Decimal
import sys

from gui_dna.provider import parse_json
from studies.interface_blind.core import compile_plan
from studies.ledger_read import calls, totals
from studies.study_io import ROOT, cases_by_file, digest, dump, read, sha, source_files
from studies.svg_chart_sources.run import files_under

from .run import ARMS, MODEL, OLD, OUT, SEED, SOURCE, TARGETS, check_freeze

OUTPUT = ROOT / 'studies/results/svg-chart-interfaces-20261123.json'
PRIMARY = ('direct', 'reference_typed', 'ai')


def audit_score(arm, n):
    folder = OUT / 'scores' / arm / f'task-{n}'
    state = read(folder / 'score.json')
    assert state['report_sha256'] == sha(folder / 'report.json')
    raw = read(folder / 'report.json')
    cases = cases_by_file(raw)
    assert set(cases) == {f'task-{n}'} and cases[f'task-{n}']
    assert all('maximum allowed failures' in err.get('message', '') for err in raw.get('errors', []))
    passed = all(c['passed'] for c in cases[f'task-{n}'])
    assert passed == state['passed']
    return state


def counts(cells, names, target_set):
    targets = [n for n in target_set if all(cells[a][str(n)]['passed'] is not None for a in names)]
    return {'tasks': targets, 'denominator': len(targets),
            'passed': {a: sum(cells[a][str(n)]['passed'] for n in targets) for a in names}}


def reconstruct():
    check_freeze()
    generated = read(OUT / 'generation-complete.json')
    scores = read(OUT / 'results.json')
    assert scores['generated_sha256'] == sha(OUT / 'generation-complete.json')
    matrix = {(a, n) for a in ARMS for n in TARGETS}
    for rows in [generated['rows'], scores['rows']]:
        assert {(r['arm'], r['task']) for r in rows} == matrix and len(rows) == len(matrix)
    outcomes = {(r['arm'], r['task']): r['passed'] for r in scores['rows']}
    cells = {a: {} for a in ARMS}
    ledger = calls(OUT / 'budget.sqlite3')
    bills = {a: Counter() for a in ARMS}
    requests = set()
    starter = files_under(SOURCE / 'src-init')
    assets = {'assets/' + k: v for k, v in files_under(SOURCE / 'assets').items()}
    packages = {a: read(OUT / 'packages' / (a + '.json')) for a in ARMS if a != 'direct'}
    assert packages['reference_typed']['files'] == packages['reference_prose']['files']
    assert packages['reference_typed']['compiler'] == packages['reference_prose']['compiler']
    for r in generated['rows']:
        a, n = r['arm'], r['task']
        path = OUT / 'runs' / a / f'task-{n}'
        assert read(path / 'record.json') == r
        entry = {'passed': None if not r['response'] else False, 'materialized': bool(r.get('files')),
                 'source': str(path.relative_to(ROOT))}
        call = path / 'call'
        if (call / 'request.json').exists():
            req = read(call / 'request.json')
            assert req['body']['messages'] == read(OUT / 'prompts' / a / f'task-{n}.json')
            assert req['body']['model'] == MODEL and req['body']['seed'] == SEED
            assert req['call_id'] not in requests
            requests.add(req['call_id'])
            charge, = [c for c in ledger if c['id'] == req['call_id']]
            assert charge['purpose'] == f'{a}:task-{n}'
            bills[a]['requests'] += 1
            bills[a]['unsettled'] += charge['actual'] is None
            bills[a]['settled_microusd'] += charge['actual'] or 0
            bills[a]['exposure_microusd'] += charge['actual'] if charge['actual'] is not None else charge['reserved']
        if r['response']:
            payload = read(call / 'response.json')
            usage = payload['usage']
            for k in ('prompt_tokens', 'completion_tokens'):
                bills[a][k] += usage[k]
            assert abs(Decimal(str(usage['cost'])) * 1_000_000 - charge['actual']) <= 1
            entry['response_sha256'] = sha(call / 'response.json')
            if r.get('files'):
                parsed = parse_json(payload['choices'][0]['message']['content'])
                files = compile_plan(packages[a], parsed) if a != 'direct' else parsed['files']
                expected = starter | files | assets
                assert set(expected) == set(r['files'])
                page = path / 'page'
                assert all((page / name).read_bytes() == content.encode() for name, content in expected.items())
                assert source_files(page) == r['files']
                verified = audit_score(a, n)
                entry.update({'passed': verified['passed'], 'report_sha256': verified['report_sha256'],
                              'page_digest': digest(r['files'])})
            else:
                assert r.get('error')
        if r.get('error'):
            entry['error'] = r['error']
        assert entry['passed'] == outcomes[a, n]
        cells[a][str(n)] = entry
    assert requests == {c['id'] for c in ledger}
    controls = {'starter': {}, 'fixed-renderers': {}}
    for row in scores['controls']:
        a, n = row['arm'], row['task']
        assert source_files(OUT / 'controls' / a) == read(OUT / 'freeze.json')['controls'][a]
        controls[a][str(n)] = audit_score(a, n)
        assert controls[a][str(n)]['passed'] == row['passed']
    assert all(len(x) == len(TARGETS) for x in controls.values())
    calibration = read(OUT / 'calibration.json')
    for a, n, passed in calibration:
        assert audit_score('calibration-' + a, n)['passed'] == passed
    informative = [n for a, n, passed in calibration if a == 'blank' and not passed]
    assert informative == list(TARGETS[1:])
    materialization = {}
    for arm in ARMS:
        entries = list(cells[arm].values())
        materialization[arm] = {
            'planned': len(entries), 'observed': sum(e['passed'] is not None for e in entries),
            'materialized': sum(e['materialized'] for e in entries), 'passed': sum(e['passed'] is True for e in entries)}
    comparison = counts(cells, ('reference_prose', 'reference_typed'), TARGETS)
    changes = {}
    for t in comparison['tasks']:
        a = cells['reference_prose'][str(t)]['passed']
        b = cells['reference_typed'][str(t)]['passed']
        key = ('pass' if a else 'fail') + '_to_' + ('pass' if b else 'fail')
        changes.setdefault(key, []).append(t)
    historical = [r for r in calls(OLD / 'budget.sqlite3') if r['purpose'] == 'library:svg-chart']
    history_usd = sum(r['actual'] for r in historical) / 1e6
    return {'project': 'svg-chart', 'generator': MODEL, 'builder': 'openai/gpt-5', 'seed': SEED,
            'targets': list(TARGETS), 'calibration': calibration, 'arms': list(ARMS), 'cells': cells,
            'main': counts(cells, PRIMARY, TARGETS), 'blank_discriminating': counts(cells, PRIMARY, informative),
            'documentation_pair': comparison, 'documentation_transitions': changes, 'materialization': materialization,
            'documentation_pair_blank_discriminating': counts(cells, ('reference_prose', 'reference_typed'), informative),
            'controls': controls, 'billing': {a: dict(b) for a, b in bills.items()}, 'ledger': totals(OUT / 'budget.sqlite3'),
            'historical_ai_library_usd': history_usd, 'historical_ai_library_calls': len(historical),
            'freeze_sha256': sha(OUT / 'freeze.json'), 'generation_sha256': scores['generated_sha256'],
            'score_summary_sha256': sha(OUT / 'results.json')}


if __name__ == '__main__':
    report = reconstruct()
    if sys.argv[1:] == ['--write']:
        if OUTPUT.exists():
            assert read(OUTPUT) == report, 'Existing report differs from the frozen records'
        dump(OUTPUT, report)
    elif sys.argv[1:]:
        raise SystemExit('Use --write to create the derived result')
    else:
        assert report == read(OUTPUT)
    print({k: report[k] for k in ('main', 'blank_discriminating', 'documentation_pair', 'ledger')})
