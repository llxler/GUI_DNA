"""Web-Bench dom1 across seeds: per model and method pass counts per seed, and paired differences pooled over seeds.

    uv run python -m test.webbench_dna.seeds

Zero API.  Reads the first-seed summary (test/webbench_dna/results/summary.json, seed 20261102) and the summaries of the
additional seed stages (artifacts/webbench-dna-seed*/summary.json; a stage may hold several arms per model and not every
model has every arm).  For each (model, method) it lists final full-task passes per seed; for the contrasts GUI-DNA vs
Free and GUI-DNA vs Free+Lib it pools every (model, task, seed) pair that has both arms in that seed and gives the
cluster-bootstrap interval with tasks as clusters (same statistic as test/paired_intervals.py).  Writes
test/webbench_dna/results/seeds.{json,md}.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from test.paired_intervals import contrast

ROOT = Path(__file__).resolve().parents[2]
FIRST = ROOT / 'test/webbench_dna/results/summary.json'
STAGES = sorted(ROOT.glob('artifacts/webbench-dna-seed*/summary.json'))
NAMES = {'free': 'Free', 'free_lib': 'Free+Lib', 'dna': 'GUI-DNA', 'dna_unchecked': 'Plan-', 'rule': 'Rule'}
SHORT = {'qwen/qwen3-coder-30b-a3b-instruct': 'Qwen3-Coder-30B', 'mistralai/mistral-small-3.2-24b-instruct': 'Mistral-Small-3.2',
         'google/gemma-3-12b-it': 'Gemma-3-12B', 'deepseek/deepseek-v4-flash': 'DeepSeek-V4-Flash', 'openai/gpt-oss-120b': 'GPT-OSS-120B',
         'google/gemini-2.5-flash': 'Gemini-2.5-Flash', 'openai/gpt-5-mini': 'GPT-5-mini', 'anthropic/claude-haiku-4.5': 'Claude-Haiku-4.5'}


def load(path):
    s = json.loads(path.read_text())
    manifest = path.parent / 'manifest.json'
    if not manifest.exists():   # the copy under test/webbench_dna/results/ comes from the stage-5 directory
        manifest = ROOT / 'artifacts/webbench-dna-5/manifest.json'
    seed = json.loads(manifest.read_text())['config']['seed'] if manifest.exists() else 20261102
    cells = {}   # (model, arm, task) -> final_all
    for entry in s['models']:
        for row in entry['rows']:
            for arm in s['arms']:
                if row.get(arm):
                    cells[(entry['model'], arm, row['task'])] = bool(row[arm]['final_all'])
    return seed, cells


def main():
    stages = [load(FIRST)] + [load(p) for p in STAGES]
    seeds = [seed for seed, _ in stages]
    models = [m for m in SHORT if any((m, 'dna', 'task-1') in cells for _, cells in stages)]
    arms = ['free', 'free_lib', 'dna']
    table = defaultdict(dict)   # (model, arm) -> {seed: passes}
    for seed, cells in stages:
        for model in models:
            for arm in arms:
                rows = [v for (m, a, t), v in cells.items() if m == model and a == arm]
                if rows:
                    table[(model, arm)][seed] = sum(rows)
    contrasts = {}
    for baseline in ['free', 'free_lib']:
        pairs, per_seed = [], defaultdict(list)
        for seed, cells in stages:
            for (m, a, t), v in cells.items():
                if a == 'dna' and (m, baseline, t) in cells:
                    d = 100 * (int(v) - int(cells[(m, baseline, t)]))
                    pairs.append((t, d))
                    per_seed[seed].append((t, d))
        c = contrast(pairs)
        c['models'] = sorted({m for seed, cells in stages for (m, a, t) in cells if a == 'dna' and (m, baseline, t) in cells})
        c['per_seed'] = {str(seed): contrast(p) for seed, p in per_seed.items()}
        contrasts[baseline] = c
    result = {'seeds': seeds, 'models': models, 'passes': {f'{m}|{a}': {str(s): v for s, v in d.items()} for (m, a), d in table.items()}, 'contrasts': contrasts}
    out = ROOT / 'test/webbench_dna/results'
    (out / 'seeds.json').write_text(json.dumps(result, ensure_ascii=False, indent=1))
    lines = ['# Web-Bench dom1 多种子（任务通过 / 20，最终版本）', '',
             f'零 API，`uv run python -m test.webbench_dna.seeds`。种子 {seeds}（GPT-5-mini 不接受种子参数，每个阶段是一次独立采样）。'
             '第一个种子来自 `test/webbench_dna/results/summary.json`，其余来自 `artifacts/webbench-dna-seed*/summary.json`；空格 = 该种子没跑这一做法。', '',
             '| 模型 | 做法 | ' + ' | '.join(f'种子 {s}' for s in seeds) + ' | 均值 |', '|---|---|' + '---:|' * (len(seeds) + 1)]
    for model in models:
        for arm in arms:
            d = table.get((model, arm))
            if not d:
                continue
            vals = [d.get(s) for s in seeds]
            have = [v for v in vals if v is not None]
            lines.append(f'| {SHORT[model]} | {NAMES[arm]} | ' + ' | '.join('' if v is None else str(v) for v in vals) + f' | {sum(have) / len(have):.1f} |')
    lines += ['', '## 配对差（GUI-DNA − 基线，百分点；按任务聚类 bootstrap）', '', '| 对比 | 模型数 | n 对 | 差值 | 95% 区间 | 胜/负/平 | 逐种子差值 |', '|---|---:|---:|---:|---:|---:|---|']
    for baseline, c in contrasts.items():
        per = '; '.join(f"{s}: {v['diff']:+.1f} ({v['wins']}/{v['losses']}/{v['ties']})" for s, v in c['per_seed'].items())
        lines.append(f"| vs {NAMES[baseline]} | {len(c['models'])} | {c['n']} | {c['diff']:+.1f} | {c['ci95']} | {c['wins']}/{c['losses']}/{c['ties']} | {per} |")
    (out / 'seeds.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
