"""Reconstruct review-stage accuracy/control tables from retained observations."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT / path).read_text())


def slug(value):
    return value.replace('/', '__')


def baseline(suite, model, method):
    summary = read(f'test/{suite}_dna/results/summary.json')
    row = next(m for m in summary['models'] if m['model'] == model)
    stage = 'todomvc-dna-5' if suite == 'todomvc' else 'webbench-dna-6'
    outcomes = []
    for task in row['rows']:
        folder = Path('artifacts') / stage / 'runs' / slug(model) / method / task['task']
        if suite == 'todomvc':
            folder /= f's{task["sample"]}'
        passed = bool(read(folder / 'hidden.json')['final']['all_passed'])
        assert passed == task[method]['final_all']
        outcomes.append(passed)
    return {'n': len(outcomes), 'passed': sum(outcomes)}


def name_and_body_tables():
    naming = read('test/results/name-sensitivity.json')
    stage = Path(naming['accounting']['ledgers'][0]).parent
    names = []
    for suite, models in naming['suites'].items():
        for model, values in models.items():
            metrics = baseline(suite, model, 'dna')
            assert all(values['original'][k] == v for k, v in metrics.items())
            names.append({'suite': suite, 'model': model, 'condition': 'original', **metrics})
            for condition in ('neutral', 'nodesc', 'neutral_nodesc', 'shuffle'):
                folder = ROOT / stage / 'runs' / suite / condition / slug(model)
                passed = n = rejected = transport = 0
                for record_path in sorted(folder.rglob('record.json')):
                    record = read(record_path)
                    if any('ProviderError' in (a.get('compile_error') or '') for a in record['attempts']):
                        transport += 1
                        continue
                    score = read(record_path.with_name('hidden.json'))
                    n += 1
                    passed += bool(score['all_passed'])
                    rejected += sum(bool(a.get('compile_error')) for a in record['attempts'])
                metrics = {'n': n, 'passed': passed, 'rejections': rejected, 'transport_failures': transport}
                assert all(values[condition][k] == v for k, v in metrics.items())
                names.append({'suite': suite, 'model': model, 'condition': condition, **metrics})
    bodies = read('test/results/blind-library.json')
    stage = Path(bodies['accounting']['ledgers'][0]).parent
    body_rows = []
    for builder, info in bodies['builders'].items():
        for model, values in info['models'].items():
            for method in ('dna', 'free_lib'):
                folder = ROOT / stage / 'runs' / slug(builder) / slug(model) / method
                n = first = final = rejected = transport = 0
                for record_path in sorted(folder.rglob('record.json')):
                    record = read(record_path)
                    if any('ProviderError' in (a.get('compile_error') or '') for a in record['attempts']):
                        transport += 1
                        continue
                    score = read(record_path.with_name('hidden.json'))
                    n += 1
                    first += bool(score['first']['all_passed'])
                    final += bool(score['final']['all_passed'])
                    rejected += sum(bool(a.get('compile_error')) for a in record['attempts'])
                metrics = {'n': n, 'first': first, 'final': final, 'rejections': rejected, 'transport_failures': transport}
                assert all(values[method][k] == v for k, v in metrics.items())
                body_rows.append({'builder': builder, 'model': model, 'method': method, **metrics})
            for method in ('free', 'dna', 'free_lib'):
                assert baseline('todomvc', model, method)['passed'] == values['main_' + method]
    return {'naming': names, 'body_construction': body_rows,
            'scope': 'Accuracy/denominator and rejection columns from candidate records plus retained hidden scores, keeping original transport exclusions. Reference-choice agreement, all per-condition costs and adequacy-search prose are outside this check; no browser reexecution.'}


def browser_outcome(path):
    data = read(path)
    assert not [e for e in data.get('errors', []) if 'maximum allowed failures' not in e.get('message', '')]
    statuses = []
    pending = list(data.get('suites', []))
    while pending:
        suite = pending.pop()
        pending += suite.get('suites', [])
        for spec in suite.get('specs', []):
            for test in spec.get('tests', []):
                runs = [r['status'] for r in test.get('results', [])]
                statuses.append(bool(runs) and all(s == 'passed' for s in runs))
    return bool(statuses) and all(statuses)


def interface_controls():
    examples = read('test/results/interface-blind-controls.json')
    for row in examples['rows']:
        folder = Path('artifacts/interface-blind-controls') / row['project'] / slug(row['builder']) / f'example-{row["example"]}' / row['task']
        assert row['all_passed'] == read(folder / 'hidden.json')['all_passed'] == browser_outcome(folder / 'report.json')
    for group in examples['groups']:
        selected = [r for r in examples['rows'] if all(r[k] == group[k] for k in ('project', 'builder', 'example'))]
        assert group['n'] == len(selected) and group['passed'] == sum(r['all_passed'] for r in selected)
    fixed = read('test/results/interface-blind-final-plan.json')
    for row in fixed['rows']:
        folder = Path('artifacts/interface-blind-final-plan-replay') / row['project'] / slug(row['builder']) / slug(row['model']) / row['task']
        original = Path('artifacts/interface-blind-final-2/runs') / row['project'] / slug(row['builder']) / slug(row['model']) / 'plan' / row['task']
        assert row['constant'] == read(folder / 'hidden.json')['all_passed'] == browser_outcome(folder / 'report.json')
        assert row['per_task'] == read(original / 'hidden.json')['final']['all_passed']
    for group in fixed['groups']:
        selected = [r for r in fixed['rows'] if all(r[k] == group[k] for k in ('project', 'builder', 'model'))]
        metrics = {'n': len(selected), 'constant': sum(r['constant'] for r in selected),
                   'per_task': sum(r['per_task'] for r in selected),
                   'per_task_won': sum(r['per_task'] and not r['constant'] for r in selected),
                   'per_task_lost': sum(r['constant'] and not r['per_task'] for r in selected)}
        assert all(group[k] == v for k, v in metrics.items())
    return {'raw_control_reports': len(examples['rows']) + len(fixed['rows']),
            'examples': examples['groups'], 'fixed_final': fixed['groups'],
            'scope': 'Original current-task fixed controls, distinct from the new full-history endpoint. Reconstructed from raw Playwright reports, without fresh browser execution or recompilation.'}


def format_relaxations():
    rows = []
    targets = ['deepseek/deepseek-v4-pro-0813', 'qwen/qwen3-coder-30b-a3b-instruct', 'google/gemma-3-12b-it']
    strict = read('test/todomvc_dna/results/summary-strict-compiler.json')
    for model in targets:
        model_summary = next((r['arms']['dna'] for r in strict['models'] if r['model'] == model), None)
        records = list((ROOT / 'artifacts/todomvc-dna/runs' / slug(model) / 'dna').rglob('record.live.json'))
        passed = rejected = 0
        for path in records:
            record = read(path)
            score = read(path.with_name('hidden.live.json'))
            passed += bool(score['final']['all_passed'])
            rejected += sum(bool(a.get('compile_error')) for a in record['attempts'])
        if model_summary is not None:
            assert (len(records), passed, rejected) == (model_summary['n'], model_summary['final_all'], model_summary['compile_errors'])
        # Compare the same original 16 responses, not the later five-sample cohort.
        relaxed_passed = sum(bool(read(p.with_name('hidden.json'))['final']['all_passed']) for p in records)
        rows.append({'suite': 'todomvc', 'model': model, 'n': len(records),
                     'strict_passed': passed, 'strict_rejections': rejected, 'relaxed_passed': relaxed_passed,
                     'strict_summary_available': model_summary is not None})
    duo = {}
    for stage, summary_name in [('webapp1k-dna', 'summary'), ('webapp1k-dna-replay', 'summary-replay')]:
        expected = next(r for r in read(f'test/webapp1k_dna/results/{summary_name}.json')['models'] if r['model'] == 'qwen/qwen3-coder')['arms']['dna']
        passed = rejected = n = 0
        for path in sorted((ROOT / 'artifacts' / stage / 'runs/qwen__qwen3-coder/dna').rglob('record.json')):
            record = read(path)
            n += 1
            for attempt in record['attempts']:
                verdict = attempt.get('verdict')
                if verdict:
                    raw = read(path.parent / f'jest-{attempt["attempt"]}.json')
                    actual = raw['numTotalTests'] == raw['numPassedTests'] and raw['numTotalTests'] >= 4
                    assert verdict['all_passed'] == actual
            last = record['attempts'][-1] if record['attempts'] else {}
            passed += bool(last.get('verdict') and last['verdict']['all_passed'])
            rejected += sum(bool(a.get('compile_error')) for a in record['attempts'])
        assert (n, passed, rejected) == (expected['n'], expected['final_pass'], expected['compile_errors'])
        duo[stage] = {'n': n, 'passed': passed, 'rejections': rejected}
    return {'todomvc': rows, 'webapp1k_qwen': duo,
            'scope': 'Strict live backups and relaxed saved observations; Qwen Duo verdicts also reconciled with raw Jest reports. Not a new compiler or browser/Jest run; original posthoc status retained.'}


def reconstruct():
    return {'all_passed': True, 'name_and_body': name_and_body_tables(),
            'interface_controls': interface_controls(), 'format_relaxations': format_relaxations()}


if __name__ == '__main__':
    result = reconstruct()
    (ROOT / 'test/results/review-tables-replay.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Naming/body, original interface controls, and compiler-relaxation table sources match.')
