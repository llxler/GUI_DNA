"""Recompute paused List-16 accuracy/contrasts from saved evaluations, without a ledger.

This never invokes the frozen analyzer's main() (which opens a writable Ledger),
changes its outputs, runs a browser, or resumes generation. Cost/token columns
are outside this check. Original and anonymized observations both work.
"""
from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path

from experiments.scale_study.analyze import paired_interval
from experiments.scale_study.domain import METHODS

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(Path(path).read_text())


def main():
    stage = ROOT / 'artifacts/scale-study'
    data, expected = read(stage / 'results.json'), read(stage / 'analysis.json')
    config = read(ROOT / 'configs/scale-study.json')
    groups = defaultdict(dict)
    checked = 0
    for row in data['runs']:
        folder = ROOT / row['directory']
        raw = read(folder / 'result.json')
        assert all(row[k] == v for k, v in raw.items()), folder
        if row['status'] == 'generated':
            first = read(folder / 'first_hidden/evaluation.json')
            last = first if row['versions'][0]['code_sha256'] == row['versions'][-1]['code_sha256'] else read(folder / 'hidden/evaluation.json')
            assert row['first_hidden'] == first and row['hidden'] == last, folder
            checked += 1
        key = row['model'], row['task_id'], row['repetition']
        assert row['method'] not in groups[key]
        groups[key][row['method']] = row
    complete = {k: v for k, v in groups.items() if set(v) == set(METHODS) and all(r['status'] == 'generated' for r in v.values())}
    assert len(complete) == expected['complete_groups']
    summaries, contrasts = [], []
    for model in config['models']:
        selected = [g for k, g in complete.items() if k[0] == model]
        for method in METHODS:
            rows = [g[method] for g in selected]
            result = {'model': model, 'method': method, 'n': len(rows),
                      'first_passed': sum(r['first_hidden']['behavior_passed'] for r in rows),
                      'passed': sum(r['hidden']['behavior_passed'] for r in rows),
                      'state_passed': sum(r['hidden']['state_passed'] for r in rows),
                      'runnable': sum(r['hidden']['runnable'] for r in rows),
                      'base_passed': sum(r['hidden']['base_passed'] for r in rows),
                      'base_total': sum(r['hidden']['base_total'] for r in rows)}
            old = next(r for r in expected['summary'] if r['model'] == model and r['method'] == method)
            assert all(old[k] == v for k, v in result.items()), result
            summaries.append(result)
        for baseline in ('linked_js', 'dna', 'plan_unchecked'):
            for metric in ('first_hidden', 'hidden'):
                pairs = [(g['plan_checked']['family'], int(g['plan_checked'][metric]['behavior_passed']) - int(g[baseline][metric]['behavior_passed'])) for g in selected]
                values = [d for _, d in pairs]
                result = {'model': model, 'baseline': baseline, 'metric': metric, 'n': len(pairs),
                          'wins': values.count(1), 'losses': values.count(-1), 'ties': values.count(0),
                          'delta': sum(values) / len(values) if values else None,
                          'family_cluster_ci95': paired_interval(pairs, config['bootstrap_seed'], config['bootstrap_samples'])}
                assert result in expected['contrasts'], result
                contrasts.append(result)
    result = {'raw_evaluated_candidates_checked': checked, 'record_metadata_checked': len(data['runs']),
              'complete_groups': len(complete), 'summary': summaries, 'contrasts': contrasts, 'all_match': True,
              'scope': 'Saved List-16 evaluations, accuracy and paired intervals; no writable ledger, browser rerun, cost/token recomputation, or resumed generation.'}
    (ROOT / 'test/results/scale-table-replay.json').write_text(json.dumps(result, indent=2) + '\n')
    print(checked, 'saved evaluated candidates;', len(complete), 'complete groups; accuracy and contrasts match')


if __name__ == '__main__':
    main()
