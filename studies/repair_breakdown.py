"""Where does correctness arrive: at the first version or only after repair?  (zero API)

    uv run python -m test.repair_breakdown

For every suite and method, each candidate falls into one of: `first` (first version passes all hidden tests),
`repaired` (first version fails, final version passes), `never` (final version fails), `regressed` (first passes, final
fails; possible only when a public-check failure triggered a repair of a hidden-correct version).  Sources:
test/todomvc_dna/results/summary.json, test/webbench_dna/results/summary.json (rows carry first_all / final_all) and
artifacts/scale-study/results.json restricted to the 47 complete four-method groups (same rule as analyze.py).
Writes test/results/repair-breakdown.{json,md}; prints LaTeX rows for the paper.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'test' / 'results'
LIST16_METHODS = ['dna', 'linked_js', 'plan_unchecked', 'plan_checked']
PAPER = {  # paper names per suite method key
    'list16': {'linked_js': 'Free', 'dna': 'Free+Lib', 'plan_unchecked': 'Plan-', 'plan_checked': 'GUI-DNA'},
    'external': {'free': 'Free', 'free_lib': 'Free+Lib', 'rule': 'Rule', 'dna_unchecked': 'Plan-', 'dna': 'GUI-DNA'},
}
ORDER = ['Free', 'Free+Lib', 'Rule', 'Plan-', 'GUI-DNA']


def classify(first, final):
    if first and final:
        return 'first'
    if final:
        return 'repaired'
    if first:
        return 'regressed'
    return 'never'


def external(summary_path):
    summary = json.loads(summary_path.read_text())
    total, per_model = defaultdict(Counter), defaultdict(lambda: defaultdict(Counter))
    for entry in summary['models']:
        for row in entry['rows']:
            for arm in summary['arms']:
                cell = row.get(arm)
                if not cell:
                    continue
                c = classify(cell['first_all'], cell['final_all'])
                total[PAPER['external'][arm]][c] += 1
                per_model[PAPER['external'][arm]][entry['model']][c] += 1
    return total, per_model


def list16():
    runs = json.loads((ROOT / 'artifacts/scale-study/results.json').read_text())['runs']
    groups = defaultdict(dict)
    for r in runs:
        groups[(r['model'], r['task_id'], r['repetition'])][r['method']] = r
    complete = [g for g in groups.values() if set(g) == set(LIST16_METHODS) and all(r['status'] == 'generated' for r in g.values())]
    total, per_model = defaultdict(Counter), defaultdict(lambda: defaultdict(Counter))
    for g in complete:
        for method, r in g.items():
            c = classify(r['first_hidden']['passed'], r['hidden']['passed'])
            total[PAPER['list16'][method]][c] += 1
            per_model[PAPER['list16'][method]][r['model']][c] += 1
    return total, per_model, len(complete)


def fmt(counter):
    n = sum(counter.values())
    return {'n': n, 'first': counter['first'], 'repaired': counter['repaired'], 'never': counter['never'], 'regressed': counter['regressed']}


def main():
    l_total, l_models, groups = list16()
    t_total, t_models = external(ROOT / 'test/todomvc_dna/results/summary.json')
    w_total, w_models = external(ROOT / 'test/webbench_dna/results/summary.json')
    suites = [('List-16', l_total, l_models), ('TodoMVC', t_total, t_models), ('Web-Bench dom1', w_total, w_models)]
    result = {'note': 'first = first version passes all hidden tests; repaired = only the final version passes; never = final fails; regressed = first passes, final fails',
              'list16_complete_groups': groups, 'suites': {}}
    md = ['# 收益来自首次还是修复？（首次即对 / 修复后才对 / 修复也不对）', '',
          '零 API，`uv run python -m test.repair_breakdown`。每个候选按隐藏测试全过与否分三类：**首次即对**（第一个版本全过）、**修复后才对**（首个版本失败、最终版本全过）、'
          '**修复也不对**（最终版本仍失败）；「首次对、最终错」单列。自建任务只计 47 个完整四方法组（与 analyze.py 相同）。', '',
          '| 数据集 | 做法 | n | 首次即对 | 修复后才对 | 修复也不对 | 首次对最终错 |', '|---|---|---:|---:|---:|---:|---:|']
    tex = []
    for name, total, models in suites:
        result['suites'][name] = {'total': {m: fmt(total[m]) for m in ORDER if m in total},
                                  'per_model': {m: {model: fmt(c) for model, c in models[m].items()} for m in ORDER if m in models}}
        for m in ORDER:
            if m not in total:
                continue
            f = fmt(total[m])
            md.append(f"| {name} | {m} | {f['n']} | {f['first']} | {f['repaired']} | {f['never']} | {f['regressed']} |")
            tex.append(f"{name} & {m} & {f['n']} & {f['first']} & {f['repaired']} & {f['never']} \\\\")
    md += ['', '## 逐模型（自由代码与 GUI-DNA）', '', '| 数据集 | 做法 | 模型 | n | 首次即对 | 修复后才对 | 修复也不对 |', '|---|---|---|---:|---:|---:|---:|']
    for name, total, models in suites:
        for m in ['Free', 'Free+Lib', 'GUI-DNA']:
            for model, c in models.get(m, {}).items():
                f = fmt(c)
                md.append(f"| {name} | {m} | {model} | {f['n']} | {f['first']} | {f['repaired']} | {f['never']} |")
    OUT.mkdir(exist_ok=True)
    (OUT / 'repair-breakdown.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    (OUT / 'repair-breakdown.md').write_text('\n'.join(md) + '\n')
    print('\n'.join(md))
    print('\nLaTeX rows:')
    print('\n'.join(tex))


if __name__ == '__main__':
    main()
