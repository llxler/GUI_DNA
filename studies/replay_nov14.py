"""Independently reconstruct November 14 tables from stored browser reports and ledgers."""
from collections import defaultdict, Counter
import json
from pathlib import Path
import random

from test.ledger_read import totals
from test.replay_library_repair import report_passed
from test.prefix_history_audit.analyze import cases_by_file
from test.library_toggle_control.run import variant, boolean_paths

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT / path).read_text())


def reconstruct(stage, output, *, history=False):
    stage = Path(stage)
    inputs = read(stage / ('scoring-inputs.json' if history else 'inputs.json'))
    expected = read(output)
    scores = {}
    for key, job in inputs['jobs'].items():
        report = read(stage / 'scores' / key / 'report.json')
        if history:
            cases = cases_by_file(report)
            passed = set(cases) == set(job['specs']) and all(c['passed'] for values in cases.values() for c in values)
        else:
            passed = report_passed(report)
        assert passed == read(stage / 'scores' / key / 'score.json')['all_passed']
        scores[key] = passed
    rows = [{**r, 'passed': scores[r['score_key']] if r['score_key'] else False} for r in inputs['rows']]
    assert rows == expected['rows'], output
    return inputs, expected, rows, scores


def main():
    full_inputs, full, full_rows, full_scores = reconstruct('artifacts/library-repair-full-20261114', 'test/results/library-repair-full.json')
    fields = ('format', 'kind', 'cohort', 'condition', 'method', 'project', 'builder')
    for group in full['aggregates'] + full['groups']:
        selected = [r for r in full_rows if all(r[k] == group[k] for k in fields if k in group)]
        metrics = {'n': len(selected), 'passed': sum(r['passed'] for r in selected),
            'baseline': sum(r['baseline']['passed'] for r in selected),
            'wins': sum(r['passed'] and not r['baseline']['passed'] for r in selected),
            'losses': sum(r['baseline']['passed'] and not r['passed'] for r in selected),
            'compile_failures': sum(r['score_key'] is None for r in selected)}
        assert all(group[k] == v for k, v in metrics.items())
    for row in full_rows:
        baseline = read(row['baseline']['source'])
        if row['kind'] != 'fixed':
            baseline = baseline['final']
        assert baseline['all_passed'] == row['baseline']['passed']
    assert totals(ROOT / full['stages']['generation'] / 'budget.sqlite3') == full['cost']

    entry = read('test/results/library-repair-entrypoint.json')
    entry_inputs = read('artifacts/library-repair-entrypoint-20261114/inputs.json')
    entry_results, entry_files = {}, {}
    for key, job in entry_inputs['jobs'].items():
        entry_results[key] = report_passed(read(Path('artifacts/library-repair-entrypoint-20261114/scores') / key / 'report.json'))
        page = ROOT / job['page']
        entry_files[key] = {p.relative_to(page).as_posix(): p.read_text() for p in page.rglob('*') if p.is_file()}
    assert [{**r, 'passed': entry_results[r['score_key']]} for r in entry_inputs['rows']] == entry['rows']
    entry_by_name = {r['name']: entry_files[r['score_key']] for r in entry['rows']}
    assert {k: v for k, v in entry_by_name['original'].items() if k != 'index.js'} == entry_by_name['original_remove_entry']
    for condition in ('review', 'feedback'):
        before, after = entry_by_name[condition], entry_by_name[condition + '_restore_placeholder']
        assert set(after) - set(before) == {'index.js'} and all(after[k] == v for k, v in before.items())

    toggle_inputs, toggle, toggle_rows, toggle_scores = reconstruct('artifacts/library-toggle-control-20261114', 'test/results/library-toggle-control.json')
    for lib in toggle_inputs['libraries']:
        paths = boolean_paths(lib['anchor'])
        population = 2 ** len(paths)
        expected_masks = list(range(population)) if population <= 32 else sorted(random.Random(lib['seed']).sample(range(population), 32))
        assert expected_masks == lib['masks'] and population == lib['population']
        subset = [r for r in toggle_rows if (r['project'], r['builder']) == (lib['project'], lib['builder'])]
        assert len(subset) == len(expected_masks) * 5
        for row in subset:
            assert read(row['plan']) == variant(lib['anchor'], paths, row['mask'])
            assert read(row['anchor_baseline']['source'])['all_passed'] == row['anchor_baseline']['passed']
        summary = next(r for r in toggle['libraries'] if (r['project'], r['builder']) == (lib['project'], lib['builder']))
        by_mask = defaultdict(list)
        for row in subset:
            by_mask[row['mask']].append(row['passed'])
        metrics = {'comparisons': len(subset), 'passed': sum(r['passed'] for r in subset),
            'mean_tasks_passed': sum(r['passed'] for r in subset) / len(expected_masks),
            'best_sample_tasks': max(sum(v) for v in by_mask.values()),
            'anchor_tasks_passed': sum(next(r['anchor_baseline']['passed'] for r in subset if r['task'] == k) for k in (4, 8, 12, 16, 20)),
            'compile_failures': len({r['mask'] for r in subset if r['score_key'] is None})}
        assert all(summary[k] == v for k, v in metrics.items())
    for group in toggle['groups']:
        selected = [r for r in toggle_rows if all(r[k] == group[k] for k in ('project', 'builder', 'task'))]
        assert len(selected) == group['n'] and sum(r['passed'] for r in selected) == group['passed']
        assert bool(group['witness']) == any(r['passed'] for r in selected)
    historical = read('test/results/webbench-expand-witnesses.json')
    old_pairs = {(r['project'], r['builder'], int(t.removeprefix('task-')))
                 for r in historical['libraries'] for t in r['witness_tasks']}
    witnessed = {(r['project'], r['builder'], r['task']) for r in toggle_rows if r['passed']}
    assert len(old_pairs) == toggle['historical_witness_pairs']
    assert len(old_pairs | witnessed) == toggle['union_witness_pairs']
    assert {(r['project'], r['builder'], r['task']) for r in toggle['new_witnesses']} == witnessed - old_pairs

    prefix = read('test/results/prefix-history-audit.json')
    seen = set()
    for row in prefix['rows']:
        observed = cases_by_file(read(row['report']))[row['spec']]
        assert observed == row['tests'] and all(c['passed'] for c in observed) == row['passed']
        seen.add((row['prefix'], row['spec']))
    assert seen == {(k, name) for k in range(20) for name in ['init', *[f'task-{i}' for i in range(1, k + 1)]]}
    assert sum(r['passed'] for r in prefix['rows']) == prefix['passed_pairs']
    assert sum(c['passed'] for r in prefix['rows'] for c in r['tests']) == prefix['passed_tests']

    factorial_inputs, factorial, factorial_rows, factorial_scores = reconstruct('artifacts/prefix-factorial-v2-20261114', 'test/results/prefix-factorial.json', history=True)
    fields = ('model', 'prefix', 'method', 'label', 'scope')
    for group in factorial['aggregates'] + factorial['groups']:
        selected = [r for r in factorial_rows if all(r[k] == group[k] for k in fields if k in group)]
        assert len(selected) == group['n'] and sum(r['passed'] for r in selected) == group['passed']
    assert totals(ROOT / 'artifacts/prefix-factorial-v2-20261114/budget.sqlite3') == factorial['cost']
    assert totals(ROOT / 'artifacts/prefix-factorial-20261114/budget.sqlite3') == factorial['abandoned_protocol_cost']
    abandoned_stage = ROOT / 'artifacts/prefix-factorial-20261114'
    abandoned_statuses = Counter(json.loads(p.read_text())['status'] for p in (abandoned_stage / 'runs').rglob('record.json'))
    assert abandoned_statuses['complete'] == 55 and factorial['abandoned_protocol_cost']['calls'] == 120
    assert not (abandoned_stage / 'grading-started.json').exists()
    earlier_failures = Counter()
    final_index = {(r['model'], r['prefix'], r['method'], r['task'], r['scope']): r
                   for r in factorial_rows if r['label'] == 'final'}
    for key, current in final_index.items():
        if key[-1] != 'current' or not current['passed']:
            continue
        history = final_index[(*key[:-1], 'history')]
        if history['passed']:
            continue
        report = read(Path('artifacts/prefix-factorial-v2-20261114/scores') / history['score_key'] / 'report.json')
        for filename, cases in cases_by_file(report).items():
            for case in cases:
                if any(s in ('failed', 'timedOut') for s in case['statuses']):
                    earlier_failures[current['method'], filename, case['title']] += 1
    failure_groups = [{'method': k[0], 'file': k[1], 'title': k[2], 'n': v}
                      for k, v in sorted(earlier_failures.items())]
    from test.authorized_costs import summarize
    daily = summarize('20261114')
    assert daily == read('test/results/review-20261114-costs.json')
    result = {'all_passed': True,
        'full_repair': {'comparisons': len(full_rows), 'raw_reports': len(full_scores), 'aggregates': full['aggregates']},
        'entrypoint_intervention': {'pages': len(entry['rows']), 'raw_reports': len(entry_results), 'rows': entry['rows']},
        'toggle_control': {'comparisons': len(toggle_rows), 'raw_reports': len(toggle_scores), 'groups': toggle['groups']},
        'prefix_calibration': {'pairs': len(seen), 'passed_pairs': prefix['passed_pairs'], 'passed_tests': prefix['passed_tests']},
        'prefix_factorial': {'comparisons': len(factorial_rows), 'raw_reports': len(factorial_scores),
                            'aggregates': factorial['aggregates'], 'earlier_failure_groups': failure_groups},
        'abandoned_protocol': {'record_statuses': dict(abandoned_statuses),
                               'calls': factorial['abandoned_protocol_cost']['calls'], 'hidden_grading_marker': False},
        'daily_cost': daily,
        'scope': 'Recompute from saved reports and ledgers; no new API or browser calls. Anonymous copies use exported manifest hashes.'}
    (ROOT / 'test/results/nov14-replay.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: ({x: y for x, y in v.items() if x not in ('aggregates', 'groups')} if isinstance(v, dict) else v) for k, v in result.items()}, indent=2))


if __name__ == '__main__':
    main()
