"""Recompute library sizes, the transport-clean main table, and review-budget accounting."""
from __future__ import annotations

import json
from pathlib import Path

from test.ledger_read import totals
from test.paired_intervals import contrast, rows_for

ROOT = Path(__file__).resolve().parents[1]
STAGES = ['todomvc-blind', 'name-sensitivity', 'todomvc-blind-2', 'name-sensitivity-2',
          'webbench-dna-clean', 'webbench-dna-frontier-lib', 'webbench-dna-clean-2']
# The first two stages predate this continuation; include their exposure conservatively.
NEW_CAPS = {'todomvc-blind-2': 2.8, 'name-sensitivity-2': .35,
            'webbench-dna-clean': 2.4, 'webbench-dna-frontier-lib': 2.8, 'webbench-dna-clean-2': .85}


def library_sizes():
    from experiments.scale_study.domain import library as ll
    from test.todomvc_dna.library import library as tl, ROUTES, VIEWS, INITS
    from test.webbench_dna.library import library as wl, SLOTS

    rows = []
    for name, load, variants, path, shell in [
        ('List-16', ll, None, 'experiments/scale_study/domain.py', 'src/gui_dna/assets/shell.html'),
        ('TodoMVC', tl, sum(len(x) > 1 for x in [INITS, *ROUTES.values(), *VIEWS.values()]), 'test/todomvc_dna/library.py', 'test/todomvc_dna/shell.html'),
        ('Web-Bench dom1', wl, len(SLOTS), 'test/webbench_dna/library.py', 'test/webbench_dna/shell.html'),
    ]:
        lib = load()
        code = '\n'.join(f['code'] for f in lib['functions'])
        source = (ROOT / path).read_text()
        rows.append({'suite': name, 'atoms': len(lib['functions']), 'variant_slots': variants,
                     'atom_source_bytes': len(code.encode()), 'atom_nonblank_lines': sum(bool(x.strip()) for x in code.splitlines()),
                     'library_file_nonblank_lines': sum(bool(x.strip()) for x in source.splitlines()),
                     'shell_bytes': (ROOT / shell).stat().st_size, 'source': path, 'human_hours': None})
    duo = json.loads((ROOT / 'test/webapp1k_dna/results/library.json').read_text())
    code = '\n'.join(v['code'] for atom in duo.values() for v in atom['variants'])
    rows.append({'suite': 'WebApp1K-Duo', 'atoms': len(duo), 'variant_slots': len(duo),
                 'implementations': sum(len(atom['variants']) for atom in duo.values()),
                 'atom_source_bytes': len(code.encode()), 'atom_nonblank_lines': sum(bool(x.strip()) for x in code.splitlines()),
                 'library_file_nonblank_lines': None, 'shell_bytes': None,
                 'source': 'test/webapp1k_dna/results/library.json', 'human_hours': None})
    return rows


def clean_main():
    summary = json.loads((ROOT / 'test/webbench_dna/results/summary.json').read_text())
    models = [m for m in summary['models'] if m['model'] != 'google/gemma-3-12b-it']
    totals_ = {arm: {'passed': sum(bool(r[arm]['final_all']) for m in models for r in m['rows']),
                     'n': sum(r.get(arm) is not None for m in models for r in m['rows'])}
               for arm in ['free', 'free_lib', 'dna_unchecked', 'dna', 'rule']}
    comparisons = {}
    for baseline in ['free', 'free_lib', 'dna_unchecked', 'rule']:
        triples = [x for m in models for x in rows_for(summary, m, baseline, 'final')]
        row = contrast([(t, d) for t, _, d in triples])
        row['ci95_model_clusters'] = contrast([(m, d) for _, m, d in triples])['ci95']
        comparisons[baseline] = row
    return {'models': [m['model'] for m in models], 'totals': totals_, 'comparisons': comparisons,
            'scope': 'Seven observed models, one project. Task-cluster intervals do not account for sequential dependence; model clusters do not establish project generalization.'}


def budget():
    rows = {s: totals(ROOT / 'artifacts' / s / 'budget.sqlite3') for s in STAGES
            if (ROOT / 'artifacts' / s / 'budget.sqlite3').exists()}
    exposure = sum(r['exposure_usd'] for r in rows.values())
    # Old stages have ended; their exposure is fixed. New ledgers enforce these caps.
    ceiling = sum(rows[s]['exposure_usd'] for s in STAGES[:2]) + sum(NEW_CAPS.values())
    assert exposure <= 10 and ceiling <= 10, (exposure, ceiling)
    for s, cap in NEW_CAPS.items():
        if s in rows:
            assert rows[s]['cap_usd'] <= cap
    return {'limit_usd': 10, 'maximum_combined_exposure_usd': ceiling,
            'settled_usd': sum(r['settled_usd'] for r in rows.values()), 'exposure_usd': exposure, 'stages': rows}


def frontier():
    original = json.loads((ROOT / 'test/webbench_dna/results/summary-frontier.json').read_text())['models'][0]
    assisted = json.loads((ROOT / 'test/webbench_dna/results/summary-frontier-lib.json').read_text())['models'][0]
    library_rows = {r['task']: r['free_lib'] for r in assisted['rows']}
    pairs = [(r['dna']['final_all'], library_rows[r['task']]['final_all']) for r in original['rows']]
    return {'model': original['model'], 'free': original['arms']['free']['final_all'],
            'free_lib': assisted['arms']['free_lib']['final_all'], 'dna': original['arms']['dna']['final_all'],
            'n': len(pairs), 'dna_vs_free_lib': {'wins': sum(d and not f for d, f in pairs),
                'losses': sum(f and not d for d, f in pairs), 'ties': sum(d == f for d, f in pairs)},
            'failed_library_tasks': [r['task'] for r in assisted['rows'] if not r['free_lib']['final_all']],
            'free_lib_cost_usd': assisted['arms']['free_lib']['cost_usd']}


def matched_protocol():
    path = ROOT / 'test/webbench_dna/results/clean-prefix.json'
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    arms = ['free', 'free_clean', 'dna_inc', 'dna']
    rows = {}
    for model, values in data['models'].items():
        passes = values['passes']
        indices = [i for i in range(len(passes['free'])) if all(passes[a][i] is not None for a in arms)]
        rows[model] = {'n': len(indices), 'passed': {a: sum(bool(passes[a][i]) for i in indices) for a in arms},
                       'excluded_task_numbers': [i + 1 for i in range(len(passes['free'])) if i not in indices]}
    return {'models': rows, 'n': sum(r['n'] for r in rows.values()),
            'passed': {a: sum(r['passed'][a] for r in rows.values()) for a in arms},
            'scope': 'Intersection of observed candidates across all four protocols; missing transport outputs excluded uniformly.'}


def main():
    data = {'libraries': library_sizes(), 'webbench_seven': clean_main(), 'budget': budget(), 'frontier': frontier(),
            'matched_protocol': matched_protocol()}
    out = ROOT / 'test/results/review-metrics.json'
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    lines = ['# 审稿补充：库规模、去除传输缺失后的主表与预算', '',
             '代码行数按非空物理行计，压缩风格使它不适合作为人工工时的替代；同时报告实际函数字节数。List-16 为 5 个语义维度，不与独立槽位数混为一谈。人时未记录。', '',
             '| 数据集 | 原子 | 变体槽位 | 函数字节 | 函数非空行 | 定义文件非空行 | 外壳字节 |', '|---|---:|---:|---:|---:|---:|---:|']
    for row in data['libraries']:
        lines.append(f"| {row['suite']} | {row['atoms']} | {row['variant_slots'] if row['variant_slots'] is not None else '5 个语义维度'} | {row['atom_source_bytes']} | {row['atom_nonblank_lines']} | {row['library_file_nonblank_lines'] if row['library_file_nonblank_lines'] is not None else '—'} | {row['shell_bytes'] if row['shell_bytes'] is not None else '—'} |")
    lines += ['', 'Web-Bench 主表排除两种自由代码有传输缺失的 Gemma；所有列统一使用其余 7 个模型，原始 8 模型结果保留。', '', '| 做法 | 全过/候选 |', '|---|---:|']
    for name, row in data['webbench_seven']['totals'].items():
        lines.append(f"| {name} | {row['passed']}/{row['n']} |")
    lines += ['', '按模型聚类仍只有 7 个模型、1 个项目，不能提供跨项目显著性。', '', '| 对照 | 差值百分点 | 模型簇区间 | 胜/负/平 |', '|---|---:|---|---|']
    for name, row in data['webbench_seven']['comparisons'].items():
        lines.append(f"| {name} | {row['diff']} | {row['ci95_model_clusters']} | {row['wins']}/{row['losses']}/{row['ties']} |")
    f = data['frontier']
    lines += ['', f"GPT-5：自由 {f['free']}/{f['n']}，自由 + 同一函数库 {f['free_lib']}/{f['n']}，方案 {f['dna']}/{f['n']}；方案对带库自由代码的配对结果 {f['dna_vs_free_lib']}。新增已结算 ${f['free_lib_cost_usd']:.6f}。"]
    if data['matched_protocol']:
        p = data['matched_protocol']
        lines += ['', f"四种协议的共同有效子集 n={p['n']}，全过数：{p['passed']}。缺失候选在所有列同步排除。"]
    b = data['budget']
    lines += ['', f"本轮（含接手前两个阶段）：已结算 ${b['settled_usd']:.6f}，含未确认预留的敞口 ${b['exposure_usd']:.6f}。所有新账本上限加历史敞口至多 ${b['maximum_combined_exposure_usd']:.6f}，小于用户授权 $10。", '']
    out.with_suffix('.md').write_text('\n'.join(lines))
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
