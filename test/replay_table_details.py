"""Read-only reconstruction of previously uncovered cost and appendix columns."""
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path
from test.ledger_read import calls as ledger_calls

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT / path).read_text())


def original_costs():
    # Explicit original-study ledger set: later reviews never enter this table.
    groups = [
        ('Pilot round 1', ['budget.sqlite3'], ['generate', 'library', 'connectivity-probe'], '0.42'),
        ('Pilot round 2', ['budget.sqlite3'], ['v2', 'compact', 'linked'], '1.15'),
        ('List-16', ['budget.sqlite3'], ['scale'], '0.83'),
        ('WebApp1K-Duo', ['benchmark-probe/budget.sqlite3', 'webapp1k-dna/budget.sqlite3', 'webapp1k-dna-replay/budget.sqlite3'], None, '0.10'),
        ('TodoMVC original', [f'{name}/budget.sqlite3' for name in ['todomvc-dna', 'todomvc-dna-2', 'todomvc-dna-3', 'todomvc-dna-4']], None, '0.92'),
        ('TodoMVC samples 3-5', ['todomvc-dna-5/budget.sqlite3'], None, '0.67'),
        ('Web-Bench original', [f'{name}/budget.sqlite3' for name in ['webbench-dna', *[f'webbench-dna-{k}' for k in range(2, 7)]]], None, '4.08'),
        ('Web-Bench seeds 2-3', ['webbench-dna-seed1/budget.sqlite3', 'webbench-dna-seed2/budget.sqlite3'], None, '3.95'),
        ('Web-Bench GPT-5 original', ['webbench-dna-frontier/budget.sqlite3'], None, '2.22'),
    ]
    rows = []
    for name, ledgers, prefixes, display in groups:
        settled = reserved = calls = 0
        for ledger in ledgers:
            for row in ledger_calls(ROOT / 'artifacts' / ledger):
                if prefixes is not None and row['purpose'].split(':')[0] not in prefixes:
                    continue
                calls += 1
                settled += row['actual'] or 0
                reserved += row['reserved'] if row['actual'] is None else 0
        rendered = f'{Decimal(settled) / 1000000:.2f}'
        assert rendered == display, (name, rendered, display)
        rows.append({'study': name, 'ledgers': ['artifacts/' + p for p in ledgers], 'purpose_prefixes': prefixes,
                     'calls': calls, 'settled_microusd': settled, 'unconfirmed_reserve_microusd': reserved,
                     'displayed_usd': rendered})
    total = sum(r['settled_microusd'] for r in rows)
    assert f'{Decimal(total) / 1000000:.2f}' == '14.36'
    quartet = sum(r['actual'] or 0 for r in ledger_calls(ROOT / 'artifacts/webapp1k-dna-quartet/budget.sqlite3'))
    assert f'{Decimal(quartet) / 1000000:.2f}' == '0.31'
    return {'rows': rows, 'total_microusd': total, 'displayed_total_usd': '14.36',
            'separate_exploratory_quartet_microusd': quartet,
            'scope': 'Explicit original-study subtotal, including transport costs. Later review stages excluded; unsettled reservations retained separately. This is not the present all-experiment grand total.'}


def expansion_details():
    summary = read('test/results/webbench-expand.json')
    libraries = []
    for lib in summary['libraries']:
        folder = Path('artifacts/webbench-expand-build/libraries') / lib['project'] / lib['builder'].replace('/', '__')
        package, record = read(folder / 'package.json'), read(folder / 'record.json')
        metrics = {'files': len(package['files']), 'source_bytes': sum(len(s.encode()) for s in package['files'].values()),
                   'compiler_bytes': len(package['compiler'].encode()), 'attempts': len(record['attempts'])}
        assert all(lib[k] == v for k, v in metrics.items())
        libraries.append({'project': lib['project'], 'builder': lib['builder'], **metrics})
    sensitivity = []
    stage = Path(summary['stages']['run'])
    for group in summary['groups']:
        selected = [k for k in range(1, 21) if group['project'] != 'bom' or k not in (7, 14, 19)]
        pairs = []
        for k in selected:
            folder = stage / 'runs' / group['project'] / group['builder'].replace('/', '__') / group['model'].replace('/', '__')
            pair = [read(folder / method / f'task-{k}' / 'hidden.json')['final']['all_passed'] for method in ('free_lib', 'plan')]
            pairs.append(pair)
        metrics = {'n': len(pairs), 'free_lib': sum(c for c, _ in pairs), 'plan': sum(p for _, p in pairs),
                   'plan_wins_vs_free_lib': sum(p and not c for c, p in pairs),
                   'plan_losses_vs_free_lib': sum(c and not p for c, p in pairs)}
        assert all(group['predefined_sensitivity'][k] == v for k, v in metrics.items())
        sensitivity.append({k: group[k] for k in ('project', 'builder', 'model')} | metrics)
    return {'libraries': libraries, 'sensitivity': sensitivity,
            'scope': 'Source-size/attempt columns and the displayed prespecified sensitivity aggregates, reconstructed from packages, records and saved hidden observations.'}


def heldout_usage():
    expected = read('test/results/heldout-composition.json')['usage']
    usage = Counter()
    adopted = 0
    for phase, name, subdir in [('build', 'heldout-composition-build', 'libraries'),
                                ('main', 'heldout-composition-run', 'runs'),
                                ('strong', 'heldout-composition-strong', 'runs')]:
        for path in sorted((ROOT / 'artifacts' / name / subdir).rglob('record.json')):
            record = json.loads(path.read_text())
            if record.get('unavailable_library'):
                continue
            prefix = 'build' if phase == 'build' else phase + '/' + record['method']
            for attempt in record['attempts']:
                index = attempt['attempt']
                responses = [json.loads(p.read_text()) for p in (path.parent / f'call-{index}').rglob('response.json')]
                responses = [r for r in responses if r.get('choices') and r['choices'][0].get('finish_reason') not in (None, 'error') and r.get('usage', {}).get('cost') is not None]
                assert len(responses) == 1
                response = responses[0]
                assert response['choices'][0]['message']['content'] == json.loads((path.parent / f'output-{index}.json').read_text())['text']
                adopted += 1
                for field in ('prompt_tokens', 'completion_tokens', 'cost'):
                    usage[prefix + '/' + field] += response['usage'].get(field, 0)
                usage[prefix + '/reasoning_tokens'] += response['usage'].get('completion_tokens_details', {}).get('reasoning_tokens', 0)
    assert set(usage) == set(expected)
    assert all(abs(value - expected[k]) < 1e-8 for k, value in usage.items())
    return {'adopted_responses': adopted, 'usage': dict(usage),
            'scope': 'Adopted response tokens and reported costs, including reasoning. Unknown transport reservations remain in separate ledgers and are not treated as zero-priced completed outputs.'}


def primary_costs_and_sequence():
    ledger = {r['id']: r for r in ledger_calls(ROOT / 'artifacts/budget.sqlite3')}
    records = read('artifacts/scale-study/results.json')['runs']
    scale = []
    for expected in read('artifacts/scale-study/analysis.json')['summary']:
        selected = [r for r in records if all(r[k] == expected[k] for k in ('model', 'method'))]
        requests = [p for r in selected for p in (ROOT / r['directory']).rglob('request.json')]
        ids = {read(p)['call_id'] for p in requests}
        assert ids.issubset(ledger)
        calls = [ledger[k] for k in sorted(ids)]
        usages = {}
        for path in requests:
            identifier = read(path)['call_id']
            response = path.with_name('response.json')
            if response.exists():
                usages[identifier] = read(response).get('usage', {})
            else:
                assert ledger[identifier]['actual'] is None, 'A settled request lacks its saved response'
                usages[identifier] = {}
        metrics = {'known_usd': sum(c['actual'] or 0 for c in calls) / 1e6,
                   'unknown_reserve_usd': sum(c['reserved'] for c in calls if c['actual'] is None) / 1e6,
                   'input_tokens': sum(u.get('prompt_tokens', 0) for u in usages.values()),
                   'output_tokens': sum(u.get('completion_tokens', 0) for u in usages.values())}
        assert all(expected[k] == v for k, v in metrics.items())
        scale.append({k: expected[k] for k in ('model', 'method')} | metrics)
    ledgers = ['webbench-dna'] + [f'webbench-dna-{k}' for k in range(2, 7)]
    calls = [r for stage in ledgers for r in ledger_calls(ROOT / 'artifacts' / stage / 'budget.sqlite3')]
    assert len({c['id'] for c in calls}) == len(calls)
    webbench = []
    for model in read('test/webbench_dna/results/summary.json')['models']:
        assert [r['task'] for r in model['rows']] == [f'task-{k}' for k in range(1, 21)]
        for method in ('free', 'dna'):
            score = failures = attempts = rejections = 0
            stopped = False
            for task in model['rows']:
                folder = Path('artifacts/webbench-dna-6/runs') / model['model'].replace('/', '__') / method / task['task']
                passed = read(folder / 'hidden.json')['final']['all_passed']
                record = read(folder / 'record.json')
                attempts += len(record['attempts'])
                rejections += sum(bool(a.get('compile_error')) for a in record['attempts'])
                if not stopped:
                    if passed:
                        score += 1
                        failures = 0
                    else:
                        failures += 1
                        stopped = failures == 2
            metrics = {'sequential_final': score, 'calls': attempts, 'compile_errors': rejections,
                       'cost_usd': sum(c['actual'] or 0 for c in calls
                                      if c['purpose'].startswith(f'webbench:{model["model"]}:{method}:')) / 1e6}
            assert all(model['arms'][method][k] == v for k, v in metrics.items())
            webbench.append({'model': model['model'], 'method': method, **metrics})
    return {'list16': scale, 'webbench': webbench, 'webbench_cost_stages': ledgers,
            'scope': 'List-16 cost/tokens cover all attempted records, not only complete groups. Original Web-Bench costs include historical transport calls; sequential score stops at two consecutive current-file failures and is not the same-page full-history endpoint. No writable Ledger or new execution.'}


def reconstruct():
    return {'original_costs': original_costs(), 'expansion_details': expansion_details(), 'heldout_usage': heldout_usage(),
            'primary_costs_and_sequence': primary_costs_and_sequence(),
            'all_passed': True, 'scope': 'Read-only appendix-source reconstruction. Does not launch browsers, resume generation, modify ledgers, or compare every LaTeX cell.'}


if __name__ == '__main__':
    result = reconstruct()
    (ROOT / 'test/results/table-details-replay.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Original $14.36 subtotal, scale tokens/costs, Web-Bench sequential/cost columns, expansion details and heldout usage match.')
