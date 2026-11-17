"""Audit matched-prefix outputs, raw reports and accounting; report both endpoints."""
from collections import defaultdict
import hashlib

from .run import OUT, ROOT, MODELS, PREFIXES, METHODS, read, dump, digest, slug, messages_for, library, domain
from .score import verify_scoring
from test.prefix_history_audit.analyze import cases_by_file
from test.ledger_read import totals, calls


def main():
    inputs = verify_scoring()
    assert read(OUT / 'evaluation-complete.json')['inputs_sha256'] == digest(inputs)
    scores = {}
    for key, job in inputs['jobs'].items():
        folder = OUT / 'scores' / key
        score = read(folder / 'score.json')
        assert hashlib.sha256((folder / 'report.json').read_bytes()).hexdigest() == score['report_sha256']
        cases = cases_by_file(read(folder / 'report.json'))
        assert cases == score['tests']
        passed = set(cases) == set(job['specs']) and all(c['passed'] for values in cases.values() for c in values)
        assert passed == score['all_passed']
        scores[key] = passed
    rows = [{**r, 'passed': bool(scores[r['score_key']]) if r['score_key'] else False} for r in inputs['rows']]
    grouped = defaultdict(list)
    fields = ('model', 'prefix', 'method', 'label', 'scope')
    for row in rows:
        grouped[tuple(row[k] for k in fields)].append(row)
    groups = [{**dict(zip(fields, key)), 'n': len(values), 'passed': sum(r['passed'] for r in values),
               'no_executable': sum(r['score_key'] is None for r in values)} for key, values in sorted(grouped.items())]
    aggregate_fields = ('prefix', 'method', 'label', 'scope')
    grouped = defaultdict(list)
    for row in rows:
        grouped[tuple(row[k] for k in aggregate_fields)].append(row)
    aggregates = [{**dict(zip(aggregate_fields, key)), 'n': len(values), 'passed': sum(r['passed'] for r in values)}
                  for key, values in sorted(grouped.items())]
    index = {(r['model'], r['prefix'], r['method'], r['task'], r['label'], r['scope']): r for r in rows}
    contrasts = []
    for label in ('first', 'final'):
        for scope in ('current', 'history'):
            for prefix in PREFIXES:
                pairs = [(index[m, prefix, 'plan', t['id'], label, scope], index[m, prefix, 'free_lib', t['id'], label, scope])
                         for m in MODELS for t in domain.tasks()]
                contrasts.append({'contrast': 'plan_vs_code', 'prefix': prefix, 'label': label, 'scope': scope,
                    'n': len(pairs), 'wins': sum(a['passed'] and not b['passed'] for a, b in pairs),
                    'losses': sum(b['passed'] and not a['passed'] for a, b in pairs)})
            for method in METHODS:
                pairs = [(index[m, 'reference', method, t['id'], label, scope], index[m, 'self', method, t['id'], label, scope])
                         for m in MODELS for t in domain.tasks()]
                contrasts.append({'contrast': 'reference_vs_self', 'method': method, 'label': label, 'scope': scope,
                    'n': len(pairs), 'wins': sum(a['passed'] and not b['passed'] for a, b in pairs),
                    'losses': sum(b['passed'] and not a['passed'] for a, b in pairs)})
    divergences = []
    for model in MODELS:
        for prefix in PREFIXES:
            for method in METHODS:
                for task in domain.tasks():
                    a = index[model, prefix, method, task['id'], 'final', 'current']
                    b = index[model, prefix, method, task['id'], 'final', 'history']
                    if a['passed'] != b['passed']:
                        divergences.append({'model': model, 'prefix': prefix, 'method': method, 'task': task['id'],
                                            'current': a['passed'], 'history': b['passed']})
    ledger_calls = calls(OUT / 'budget.sqlite3')
    settled = {c['id']: c for c in ledger_calls if c['actual'] is not None}
    responses, sequences = [], []
    lib = library()
    for model in MODELS:
        for prefix in PREFIXES:
            for method in METHODS:
                previous = (OUT / 'prefixes/task-1/index.html').read_text()
                for task in domain.tasks():
                    folder = OUT / 'runs' / slug(model) / prefix / method / task['id']
                    record = read(folder / 'record.json')
                    start = (OUT / 'prefixes' / task['id'] / 'index.html').read_text() if prefix == 'reference' else previous
                    messages = messages_for(task, method, start, lib)
                    assert messages == read(folder / 'messages.json') and digest(messages) == record['initial_messages_sha256']
                    for i, attempt in enumerate(record['attempts']):
                        saved = []
                        for req in (folder / f'call-{i}').rglob('request.json'):
                            request = read(req)
                            assert request['body']['messages'] == messages and request['body']['model'] == model
                            if request['call_id'] in settled:
                                response = read(req.with_name('response.json'))
                                assert response['choices'][0]['message']['content'] == read(folder / attempt['output'])['text']
                                saved.append(response)
                        assert len(saved) == 1
                        responses.append({'model': model, 'prefix': prefix, 'method': method, 'task': task['id'], 'attempt': i,
                            'provider': saved[0].get('provider'), 'usage': saved[0]['usage'],
                            'finish_reason': saved[0]['choices'][0]['finish_reason']})
                        if attempt['feedback']:
                            messages += [{'role': 'assistant', 'content': read(folder / attempt['output'])['text']},
                                         {'role': 'user', 'content': attempt['feedback']}]
                    if record['versions']:
                        previous = (folder / record['versions'][-1] / 'index.html').read_text()
                    if prefix == 'reference':
                        other = OUT / 'runs' / slug(model) / prefix / ('plan' if method == 'free_lib' else 'free_lib') / task['id']
                        assert read(other / 'messages.json')[1] == read(folder / 'messages.json')[1]
                values = [index[model, prefix, method, t['id'], 'final', 'current']['passed'] for t in domain.tasks()]
                from test.webbench_dna.run import sequential_score
                sequences.append({'model': model, 'prefix': prefix, 'method': method, 'current_task_passes': values,
                                  'sequential_score': sequential_score(values)})
    result = {'scope': 'Exploratory corrected-contract factorial: two models, one dependent dom1 sequence, one seed. '
        'Shared cumulative requirements, library source and output-token cap; reference user content is identical across output methods. '
        'Self-prefix pages are compiled HTML for both methods. No pure causal attribution to inherited errors or cross-project claim.',
        'stages': {'generation': str(OUT.relative_to(ROOT))}, 'groups': groups, 'aggregates': aggregates,
        'contrasts': contrasts, 'endpoint_divergences': divergences, 'sequences': sequences, 'rows': rows,
        'responses': responses, 'cost': totals(OUT / 'budget.sqlite3'),
        'abandoned_protocol_cost': totals(ROOT / 'artifacts/prefix-factorial-20261114/budget.sqlite3'),
        'audit': {'candidates': 160, 'comparisons': len(rows), 'unique_raw_reports': len(scores),
            'complete_responses': len(responses), 'reference_user_pairs': 40,
            'generation_before_hidden_grading': True, 'reference_calibration_pairs': 210,
            'reference_calibration_assertions': 909, 'first_contract_abandoned_before_grading': True}}
    dump(ROOT / 'test/results/prefix-factorial.json', result)
    for group in groups:
        if group['label'] == 'final':
            print(group)
    print('cost', result['cost'], 'audit', result['audit'])


if __name__ == '__main__':
    main()
