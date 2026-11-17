"""Recompute the two external primary tables from saved per-candidate hidden scores.

No generation, browser, or writable ledger is opened. Historical transport
classifications are preserved; Gemma is excluded from the Web-Bench primary
cohort exactly as in the paper, rather than changing old observations.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGES = {'todomvc': 'todomvc-dna-5', 'webbench': 'webbench-dna-6'}


def replay(suite, stage, summary='summary', checked_paths=None):
    expected = json.loads((ROOT / f'test/{suite}_dna/results/{summary}.json').read_text())
    rows_checked, models = 0, []
    for model in expected['models']:
        groups = {method: [] for method in expected['arms']}
        for row in model['rows']:
            for method in expected['arms']:
                observed = row.get(method)
                if observed is None:
                    continue
                folder = ROOT / 'artifacts' / stage / 'runs' / model['model'].replace('/', '__') / method / row['task']
                if suite == 'todomvc':
                    folder /= f's{row["sample"]}'
                if checked_paths is not None:
                    checked_paths.add(folder.relative_to(ROOT).as_posix())
                record = json.loads((folder / 'record.json').read_text())
                hidden = json.loads((folder / 'hidden.json').read_text())
                actual = {'first_all': hidden['first']['all_passed'], 'final_all': hidden['final']['all_passed'],
                          'first_passed': hidden['first']['passed'], 'final_passed': hidden['final']['passed'],
                          'total': hidden['final']['total'], 'calls': len(record['attempts']) if method != 'rule' else 0,
                          'compile_errors': sum(bool(a.get('compile_error')) for a in record['attempts'])}
                assert all(observed[key] == value for key, value in actual.items()), str(folder)
                groups[method].append(actual)
                rows_checked += 1
        counts = {}
        for method, values in groups.items():
            counts[method] = {'n': len(values), 'first_all': sum(r['first_all'] for r in values),
                             'final_all': sum(r['final_all'] for r in values)}
            assert all(model['arms'][method][k] == v for k, v in counts[method].items())
        models.append({'model': model['model'], 'counts': counts})
    cohort = [m for m in models if not (suite == 'webbench' and m['model'] == 'google/gemma-3-12b-it')]
    primary = {method: {key: sum(m['counts'][method][key] for m in cohort)
                       for key in ('n', 'first_all', 'final_all')}
               for method in expected['arms'] if method != 'rule'}
    rule = cohort[0]['counts'].get('rule')
    assert all(m['counts'].get('rule') == rule for m in cohort)
    return {'suite': suite, 'stage': stage, 'summary': summary, 'raw_candidates_checked': rows_checked, 'models': models,
            'primary_models': [m['model'] for m in cohort], 'primary': primary,
            'rule_not_repeated_across_models': rule, 'all_match': True}


def main():
    extensions = [('todomvc', 'todomvc-dna-5', 'summary-samples5'),
                  ('webbench', 'webbench-dna-seed1', 'summary-seed1'),
                  ('webbench', 'webbench-dna-seed2', 'summary-seed2'),
                  ('webbench', 'webbench-dna-frontier', 'summary-frontier'),
                  ('webbench', 'webbench-dna-frontier-lib', 'summary-frontier-lib')]
    checked_paths = set()
    results = {'suites': [replay(suite, stage, checked_paths=checked_paths) for suite, stage in STAGES.items()],
               'extensions': [replay(*spec, checked_paths=checked_paths) for spec in extensions],
               'unique_record_paths_checked': len(checked_paths),
               'scope': 'Candidate-level first/final scores, calls and compile-error counts checked against saved raw records; primary pass counts independently summed. No new browser evaluation and no change to historical missing-data policy.'}
    results['raw_candidates_checked'] = sum(v['raw_candidates_checked'] for v in results['suites'] + results['extensions'])
    (ROOT / 'test/results/primary-replay.json').write_text(json.dumps(results, indent=2) + '\n')
    for value in results['suites'] + results['extensions']:
        print(value['suite'], value['summary'], value['raw_candidates_checked'], 'raw candidates match', value['primary'])


if __name__ == '__main__':
    main()
