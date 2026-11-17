"""Independently reconstruct repair tables from saved reports, including anonymous copies."""
import json
from itertools import product
from pathlib import Path
from test.ledger_read import totals

ROOT = Path(__file__).resolve().parents[1]
STAGE = Path('artifacts/library-repair-available-20261113')


def read(path):
    return json.loads((ROOT / path).read_text())


def report_passed(report):
    statuses = []
    def walk(suite):
        for spec in suite.get('specs', []):
            for test in spec.get('tests', []):
                runs = test.get('results', [])
                statuses.append(bool(runs) and all(r['status'] == 'passed' for r in runs))
        for child in suite.get('suites', []):
            walk(child)
    walk(report)
    assert statuses, 'No listed tests'
    return all(statuses)


def main():
    scores, sources, tables = {}, set(), []
    inputs = read(STAGE / 'inputs.json')
    expected = read('test/results/library-repair-available.json')
    for kind in ('strict', 'single_fence'):
        actual = []
        for row in inputs['rows']:
            if row['format'] != kind:
                continue
            before = read(row['baseline']['source'])
            if row['kind'] != 'fixed':
                before = before['final']
            assert bool(before['all_passed']) == row['baseline']['passed']
            key = row['score_key']
            if key is not None and key not in scores:
                folder = STAGE / 'scores' / key
                score = read(folder / 'score.json')
                observed = report_passed(read(folder / 'report.json'))
                assert observed == bool(score['all_passed'])
                scores[key] = observed
            passed = scores[key] if key else False
            actual.append({**row, 'passed': passed, 'cohort': 'strong' if row['model'] == 'openai/gpt-5' else 'main'})
            if row['kind'] == 'candidate':
                sources.add(row['source'])
        assert actual == [r for r in expected['rows'] if r['format'] == kind]
        expected_groups = [g for g in expected['aggregates'] if g['format'] == kind]
        for group in expected_groups:
            selected = [r for r in actual if all(r[k] == group[k] for k in ('kind', 'cohort', 'condition', 'method'))]
            metrics = {'n': len(selected), 'baseline': sum(r['baseline']['passed'] for r in selected),
                       'passed': sum(r['passed'] for r in selected),
                       'wins': sum(r['passed'] and not r['baseline']['passed'] for r in selected),
                       'losses': sum(r['baseline']['passed'] and not r['passed'] for r in selected),
                       'compile_failures': sum(r['score_key'] is None for r in selected)}
            assert all(group[k] == v for k, v in metrics.items())
        tables.append({'diagnostic': kind, 'comparisons': len(actual), 'aggregates': expected_groups})
    cost = totals(ROOT / expected['stages']['generation'] / 'budget.sqlite3')
    assert cost == expected['cost']
    mechanism = read('test/results/library-repair-mechanism.json')
    mechanism_rows = []
    for row in mechanism['rows']:
        observed = report_passed(read(row['report']))
        assert observed == row['all_passed']
        mechanism_rows.append({'name': row['name'], 'passed': observed})
    space = read('test/results/library-repair-space.json')
    conditional_rows, space_counts = [], []
    for row in space['rows']:
        observed = report_passed(read(row['report']))
        assert observed == row['passed'] == read(row['score'])['all_passed']
        assert {k: v for k, v in row['plan'].items() if k != 'interactions'} == space['fixed_fields']
        assert all(type(v) is bool for v in row['plan']['interactions'].values())
        conditional_rows.append(row)
    for group in space['groups']:
        selected = [r for r in conditional_rows if r['condition'] == group['condition']]
        observed_bits = {tuple(r['plan']['interactions'][name] for name in space['switches']) for r in selected}
        assert len(selected) == group['n'] == 128 and observed_bits == set(product((False, True), repeat=7))
        assert sum(r['passed'] for r in selected) == group['passed']
        space_counts.append({'condition': group['condition'], 'n': len(selected), 'passed': group['passed']})
    result = {'all_passed': True, 'original_candidates': len(sources), 'unique_raw_reports': len(scores),
              'mechanism_raw_reports': len(mechanism_rows), 'mechanism': mechanism_rows,
              'conditional_space': space_counts, 'conditional_new_reports': space['new_browser_scores'],
              'conditional_reused_reports': space['reused_scores'],
              'tables': tables, 'cost': cost,
              'scope': 'Three complete library pairs only; planned six-library study remains incomplete. '
                       'Stored original baselines and new raw Playwright reports independently reconstructed; '
                       'strict and secondary formatting results remain separate. The complete fixed-style Boolean slice and line intervention are checked separately. No new API or browser calls. '
                       'Anonymous exported bytes use the bundle manifest, not original source hashes.'}
    (ROOT / 'test/results/library-repair-replay.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'tables'}, indent=2))


if __name__ == '__main__':
    main()
