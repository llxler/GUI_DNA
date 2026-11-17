"""Recompute extension tables from observations, including rewritten replay bundles.

This deliberately does not assert original source/report hashes after anonymous
rewriting. The bundle validator checks its independent exported-file manifest.
No model calls, browser runs, or mutable ledger construction.
"""
from __future__ import annotations
import json
from pathlib import Path
from test.ledger_read import totals

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return json.loads((ROOT / name).read_text())


def slug(value):
    return value.replace('/', '__')


def key(row):
    return tuple(row[k] for k in ('project', 'builder', 'model', 'method', 'task'))


def cohort(stage, expected_rows):
    actual, sources = {}, []
    for path in sorted((ROOT / stage / 'runs').rglob('record.json')):
        record = json.loads(path.read_text())
        assert record['status'] == 'complete'
        hidden = json.loads(path.with_name('hidden.json').read_text())
        row = {name: record[name] for name in ('project', 'builder', 'model', 'method', 'task')}
        row.update(first=bool(hidden['first']['all_passed']), final=bool(hidden['final']['all_passed']))
        assert key(row) not in actual
        actual[key(row)] = row
        sources.append(str(path.relative_to(ROOT)))
    assert len(actual) == len(expected_rows)
    for expected in expected_rows:
        observed = actual[key(expected)]
        assert all(expected[name] == observed[name] for name in observed)
    return actual, sources


def method_totals(rows):
    return {method: {'n': sum(r['method'] == method for r in rows),
                     'first': sum(r['first'] for r in rows if r['method'] == method),
                     'final': sum(r['final'] for r in rows if r['method'] == method)}
            for method in sorted({r['method'] for r in rows})}


def verify_groups(groups, actual, control, interface, has_free):
    checked = []
    for g in groups:
        project, builder, model = (g[name] for name in ('project', 'builder', 'model'))
        tasks = sorted({r['task'] for r in actual.values() if r['project'] == project and r['model'] == model and r['builder'] == builder})
        assert len(tasks) == g['n']
        pairs = []
        for task in tasks:
            item = {method: actual[project, builder, model, method, task]['final'] for method in ('free_lib', 'plan')}
            if has_free:
                item['free'] = actual[project, None, model, 'free', task]['final']
            controls = [f'dev-{i}' for i in range(5)] + ['delta'] if interface == 'heldout' else ['example-0', 'example-1']
            for name in controls:
                item[name] = control[project, builder, name, None, task]
            item['fixed_final'] = control[project, builder, 'fixed-final', model, task]
            pairs.append(item)
        counts = {name: sum(r[name] for r in pairs) for name in pairs[0]}
        assert all(g[name] == value for name, value in counts.items())
        for against in ('free_lib', 'fixed_final', 'delta', 'example-0', 'example-1'):
            if against not in pairs[0]:
                continue
            wins = sum(r['plan'] and not r[against] for r in pairs)
            losses = sum(r[against] and not r['plan'] for r in pairs)
            if 'vs_' + against in g:
                assert g['vs_' + against] == {'wins': wins, 'losses': losses, 'ties': len(pairs) - wins - losses}
            if against == 'free_lib' and 'plan_wins_vs_code' in g:
                assert (g['plan_wins_vs_code'], g['plan_losses_vs_code']) == (wins, losses)
        checked.append({'project': project, 'builder': builder, 'model': model, 'n': len(pairs), **counts})
    return checked


def main():
    official = read('test/results/webbench-expand.json')
    strong = read('test/results/webbench-expand-frontier.json')
    synthetic = read('test/results/heldout-composition.json')
    controls, control_paths = {}, []
    raw = read('artifacts/webbench-expand-controls/results.json')['rows']
    for row in raw:
        path = (Path('artifacts/webbench-expand-controls/scores') / row['project'] / slug(row['builder']) /
                row['control'] / (slug(row['model']) if row['model'] else 'none') / row['task'] / 'hidden.json')
        passed = read(path)['all_passed']
        assert passed == row['passed']
        name = 'fixed-final' if row['control'] == 'final-plan' else row['control']
        controls[row['project'], row['builder'], name, row['model'], row['task']] = passed
        control_paths.append(str(path))
    for row in strong['fixed_control_rows']:
        path = Path('artifacts/webbench-expand-frontier-2/fixed-final') / row['project'] / slug(row['builder']) / row['task'] / 'hidden.json'
        passed = read(path)['all_passed']
        assert passed == row['fixed_final']
        controls[row['project'], row['builder'], 'fixed-final', strong['model'], row['task']] = passed
        control_paths.append(str(path))
    syn_control = {}
    for row in synthetic['fixed_control_rows']:
        passed = read(row['report_path'])['all_passed']
        assert passed == row['passed']
        syn_control[row['project'], row['builder'], row['control'], row['model'], row['task']] = passed
        control_paths.append(row['report_path'])
    selected = [('webbench_expand', official['stages']['run'], official, controls, 'official', True),
                ('webbench_gpt5_medium', 'artifacts/webbench-expand-frontier-2', strong, controls, 'official', False),
                ('heldout_main', synthetic['stages']['main'], synthetic['cohorts']['main'], syn_control, 'heldout', True),
                ('heldout_gpt5_medium', synthetic['stages']['strong'], synthetic['cohorts']['strong'], syn_control, 'heldout', False)]
    candidates, tables = [], []
    for name, stage, summary, control, interface, has_free in selected:
        actual, paths = cohort(stage, summary['rows'])
        counts = method_totals(list(actual.values()))
        if 'method_totals' in summary:
            assert counts == summary['method_totals']
        source_groups = [dict(g, model=g.get('model', summary.get('model'))) for g in summary['groups']]
        groups = verify_groups(source_groups, actual, control, interface, has_free)
        tables.append({'name': name, 'candidates': len(actual), 'method_totals': counts, 'groups': groups})
        candidates.extend(paths)
    ledgers = {str(Path(official['stages'][name]) / 'budget.sqlite3'): value for name, value in official['costs'].items()}
    ledgers.update({str(Path(name) / 'budget.sqlite3'): value for name, value in strong['costs_by_stage'].items()})
    for costs in synthetic['costs'].values():
        ledgers.update(costs)
    costs = {}
    for name, expected in sorted(ledgers.items()):
        actual = totals(ROOT / name)
        assert actual == expected, name
        costs[name] = actual
    assert len(candidates) == len(set(candidates)) == 904
    assert len(control_paths) == len(set(control_paths)) == 874
    witness_summary = read('test/results/webbench-expand-witnesses.json')
    seen = set()
    for row in witness_summary['witnesses']:
        identity = tuple(row[k] for k in ('project', 'builder', 'task'))
        assert identity not in seen and row['observations']
        seen.add(identity)
        for observation in row['observations']:
            score = read(observation['score_path'])
            if observation['kind'].endswith(('/first', '/final')):
                score = score[observation['kind'].rsplit('/', 1)[-1]]
            assert score['all_passed']
    assert len(seen) == witness_summary['with_observed_witness'] == 53
    for library in witness_summary['libraries']:
        tasks = {task for project, builder, task in seen if (project, builder) == (library['project'], library['builder'])}
        assert tasks == set(library['witness_tasks'])
        assert len(tasks) == library['with_observed_witness']
    result = {'all_passed': True, 'distinct_candidate_records': len(candidates), 'fixed_control_scores': len(control_paths),
              'tables': tables, 'ledger_checks': costs, 'observed_witness_pairs': len(seen),
              'scope': 'Four extension cohorts and stored fixed controls independently recomputed from records/scores. No source-byte audit after anonymization and no new browser scoring; the bundle manifest verifies exported files.'}
    (ROOT / 'test/results/new-tables-replay.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('tables', 'ledger_checks')}, indent=2))


if __name__ == '__main__':
    main()
