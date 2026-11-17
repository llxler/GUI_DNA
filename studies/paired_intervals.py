"""Paired differences with cluster-bootstrap intervals for the external suites (TodoMVC, Web-Bench dom1).

Zero API.  Reads test/todomvc_dna/results/summary.json and test/webbench_dna/results/summary.json, writes
test/results/paired-intervals.{json,md}.

    uv run python -m test.paired_intervals

The statistic mirrors experiments/scale_study/analyze.py::paired_interval: for each (model, task[, sample]) pair the
difference GUI-DNA minus baseline in task passes (0/1), expressed in percentage points; clusters (TodoMVC: feature
family = task id; Web-Bench: task id) are resampled with replacement 10,000 times and the mean difference of each
resample gives the 95% interval.  Pooled rows additionally report the interval when models are the clusters.
"""
from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITES = {
    'todomvc': {'summary': ROOT / 'test/todomvc_dna/results/summary.json', 'cluster': 'task', 'label': 'TodoMVC (official Playwright tests)'},
    'webbench': {'summary': ROOT / 'test/webbench_dna/results/summary.json', 'cluster': 'task', 'label': 'Web-Bench dom1 (official tests)'},
}
BASELINES = ['free', 'free_lib', 'dna_unchecked', 'rule']
NAMES = {'free': 'Free', 'free_lib': 'Free+Lib', 'dna_unchecked': 'Plan-', 'rule': 'Rule', 'dna': 'GUI-DNA'}
SEED, SAMPLES = 20261108, 10_000


def paired_interval(pairs, seed=SEED, samples=SAMPLES):
    """Resample clusters with replacement; 2.5/97.5 percentiles of the resampled mean difference (points)."""
    by_cluster = defaultdict(list)
    for cluster, difference in pairs:
        by_cluster[cluster].append(difference)
    if not pairs:
        return None
    clusters = sorted(by_cluster)
    rng = random.Random(seed)
    values = []
    for _ in range(samples):
        rows = [d for c in rng.choices(clusters, k=len(clusters)) for d in by_cluster[c]]
        values.append(sum(rows) / len(rows))
    values.sort()
    return [round(values[int(.025 * samples)], 1), round(values[min(samples - 1, int(.975 * samples))], 1)]


def contrast(pairs):
    diffs = [d for _, d in pairs]
    return {'n': len(pairs), 'diff': round(sum(diffs) / len(diffs), 1) if diffs else None, 'ci95': paired_interval(pairs),
            'wins': sum(d > 0 for d in diffs), 'losses': sum(d < 0 for d in diffs), 'ties': sum(d == 0 for d in diffs)}


def rows_for(summary, model_entry, baseline, version):
    """(task cluster, model cluster, difference in points) for every row that has both arms."""
    key = f'{version}_all'
    out = []
    for row in model_entry['rows']:
        a, b = row.get('dna'), row.get(baseline)
        if not a or not b:
            continue
        out.append((row['task'], model_entry['model'], 100 * (int(a[key]) - int(b[key]))))
    return out


def analyse(name, spec):
    summary = json.loads(spec['summary'].read_text())
    result = {'suite': name, 'label': spec['label'], 'date_utc': summary['date_utc'], 'models': [], 'pooled': {}}
    for entry in summary['models']:
        m = {'model': entry['model'], 'contrasts': {}}
        for baseline in BASELINES:
            if baseline not in entry['arms']:
                continue
            for version in ('final', 'first'):
                pairs = [(t, d) for t, _, d in rows_for(summary, entry, baseline, version)]
                if pairs:
                    m['contrasts'][f'{baseline}:{version}'] = contrast(pairs)
        result['models'].append(m)
    for baseline in BASELINES:
        for version in ('final', 'first'):
            triples = [x for e in summary['models'] if baseline in e['arms'] for x in rows_for(summary, e, baseline, version)]
            if not triples:
                continue
            by_task = contrast([(t, d) for t, _, d in triples])
            by_model = contrast([(mo, d) for _, mo, d in triples])
            by_task['ci95_model_clusters'] = by_model['ci95']
            by_task['models'] = len({mo for _, mo, _ in triples})
            result['pooled'][f'{baseline}:{version}'] = by_task
    return result


def markdown(results):
    lines = ['# 配对差与聚类 bootstrap 区间（GUI-DNA − 基线，单位：百分点）', '',
             '零 API，`uv run python -m test.paired_intervals`。统计口径与第三轮 `paired_interval()` 相同：按簇（TodoMVC 为功能族 = 任务 id；'
             'Web-Bench 为任务 id）有放回重抽 10,000 次，取重抽均值的 2.5% / 97.5% 分位。合计行另给「以模型为簇」的区间。']
    for r in results:
        lines += ['', f"## {r['label']}（summary 生成于 {r['date_utc']}）", '',
                  '| 范围 | 对比 | 版本 | n 对 | 差值 | 95% 区间（任务簇） | 95% 区间（模型簇） | 胜/负/平 |', '|---|---|---|---:|---:|---:|---:|---:|']
        for key, c in r['pooled'].items():
            baseline, version = key.split(':')
            lines.append(f"| 合计（{c['models']} 模型） | vs {NAMES[baseline]} | {version} | {c['n']} | {c['diff']:+.1f} | {c['ci95']} | {c['ci95_model_clusters']} | {c['wins']}/{c['losses']}/{c['ties']} |")
        for m in r['models']:
            for key, c in m['contrasts'].items():
                baseline, version = key.split(':')
                if version == 'first' and c['diff'] == m['contrasts'].get(f'{baseline}:final', {}).get('diff') and c['ci95'] == m['contrasts'].get(f'{baseline}:final', {}).get('ci95'):
                    continue   # identical to the final row; keep the table short
                lines.append(f"| {m['model']} | vs {NAMES[baseline]} | {version} | {c['n']} | {c['diff']:+.1f} | {c['ci95']} | — | {c['wins']}/{c['losses']}/{c['ties']} |")
    return '\n'.join(lines) + '\n'


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--todomvc', type=Path, default=SUITES['todomvc']['summary'], help='alternative TodoMVC summary.json (e.g. the 5-sample stage)')
    parser.add_argument('--webbench', type=Path, default=SUITES['webbench']['summary'])
    parser.add_argument('--label', default='', help='suffix for the output files, e.g. samples5 -> paired-intervals-samples5.{json,md}')
    args = parser.parse_args()
    SUITES['todomvc']['summary'], SUITES['webbench']['summary'] = args.todomvc, args.webbench
    results = [analyse(name, spec) for name, spec in SUITES.items() if spec['summary'].exists()]
    out = ROOT / 'test/results'
    out.mkdir(exist_ok=True)
    suffix = f'-{args.label}' if args.label else ''
    (out / f'paired-intervals{suffix}.json').write_text(json.dumps(results, ensure_ascii=False, indent=1))
    (out / f'paired-intervals{suffix}.md').write_text(markdown(results))
    for r in results:
        print(r['label'])
        for key, c in r['pooled'].items():
            print(f"  pooled {key:22} n={c['n']:3} diff={c['diff']:+6.1f} ci(task)={c['ci95']} ci(model)={c['ci95_model_clusters']} w/l/t={c['wins']}/{c['losses']}/{c['ties']}")


if __name__ == '__main__':
    main()
