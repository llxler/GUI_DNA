"""Read-only paired summaries for the separate public-behavior pilot."""
from __future__ import annotations
import json
from collections import defaultdict

from test.behavior_feedback import OUT, ROOT, SOURCE, SPLIT, jobs
from test.interface_blind.core import dump
from test.ledger_read import totals
from gui_dna.provider import parse_json
from test.interface_blind_diagnostics import code_shaped_root


def main():
    groups = defaultdict(list)
    missing = []
    for relative in jobs():
        folder = OUT / 'runs' / relative
        record_path, hidden_path = folder / 'record.json', folder / 'hidden.json'
        if not record_path.exists() or not hidden_path.exists():
            missing.append({'candidate': str(relative), 'reason': 'unrecorded or ungraded'})
            continue
        record = json.loads(record_path.read_text())
        hidden = json.loads(hidden_path.read_text())
        if hidden.get('excluded'):
            missing.append({'candidate': str(relative), 'reason': hidden['reason']})
            continue
        code_shaped = False
        if record['method'] == 'plan' and record['final']:
            final_page = ROOT / record['final']
            number = final_page.name.split('-')[-1]
            raw = json.loads((final_page.parent / f'output-{number}.json').read_text())['text']
            code_shaped = code_shaped_root(parse_json(raw))
        key = record['project'], record['builder'], record['model']
        groups[key].append({'task': record['task'], 'method': record['method'],
                           'initial': bool(hidden['initial']['all_passed']), 'final': bool(hidden['final']['all_passed']),
                           'initial_public': bool(record.get('initial_public', {}).get('all_passed')),
                           'final_public': bool((record['attempts'][-1].get('public', {}) if record['attempts'] else record.get('initial_public', {})).get('all_passed')),
                           'repair_calls': len(record['attempts']), 'final_code_shaped_plan': code_shaped})
    result = {'protocol': 'Five prespecified milestones per project; half of each task file public; remaining tests hidden. Initial and repaired candidates scored on the same hidden subset.',
              'base_stage': str(SOURCE.relative_to(ROOT)), 'split': str(SPLIT.relative_to(ROOT)),
              'cost': totals(OUT / 'budget.sqlite3'), 'missing': missing, 'groups': []}
    lines = ['# 公开行为反馈小试', '',
             '这是独立公开/隐藏划分，只在同库两种做法均有效的共同任务上比较修复前后；不能把这里的通过率直接拼入全隐藏主表。', '',
             '| 项目 | 建库者 | 规划者 | 同库自由代码：修复前→后 | 方案：修复前→后 | 最终方案 vs 同库 胜/负/平 |',
             '|---|---|---|---:|---:|---:|']
    for key, rows in sorted(groups.items()):
        summaries = {}
        indexed = defaultdict(dict)
        for row in rows:
            indexed[row['task']][row['method']] = row
        common = {task for task, methods in indexed.items() if set(methods) == {'free_lib', 'plan'}}
        unmatched = [r for r in rows if r['task'] not in common]
        for method in ('free_lib', 'plan'):
            selected = [r for r in rows if r['method'] == method and r['task'] in common]
            summaries[method] = {'n': len(selected), 'initial': sum(r['initial'] for r in selected),
                'final': sum(r['final'] for r in selected), 'improved': sum(r['final'] and not r['initial'] for r in selected),
                'regressed': sum(r['initial'] and not r['final'] for r in selected),
                'final_code_shaped_plan': sum(r['final_code_shaped_plan'] for r in selected), 'repair_calls': sum(r['repair_calls'] for r in selected),
                'initial_public': sum(r['initial_public'] for r in selected), 'final_public': sum(r['final_public'] for r in selected)}
        pairs = [(v['plan']['final'], v['free_lib']['final']) for v in indexed.values() if len(v) == 2]
        contrast = {'n': len(pairs), 'won': sum(p and not f for p, f in pairs), 'lost': sum(f and not p for p, f in pairs), 'tied': sum(p == f for p, f in pairs)}
        result['groups'].append({'project': key[0], 'builder': key[1], 'model': key[2], 'methods': summaries,
                                 'paired_final': contrast, 'rows': rows, 'unmatched_valid': unmatched})
        a, b = summaries['free_lib'], summaries['plan']
        lines.append('| ' + ' | '.join(key) + f" | {a['initial']}→{a['final']}/{a['n']} | {b['initial']}→{b['final']}/{b['n']} | {contrast['won']}/{contrast['lost']}/{contrast['tied']} |")
    fields = ('n', 'initial', 'final', 'improved', 'regressed', 'repair_calls', 'initial_public', 'final_public', 'final_code_shaped_plan')
    result['aggregate'] = {}
    scopes = {'all': result['groups']}
    for field in ('project', 'model'):
        for name in sorted({g[field] for g in result['groups']}):
            scopes[field + ':' + name] = [g for g in result['groups'] if g[field] == name]
    for scope, selected_groups in scopes.items():
        result['aggregate'][scope] = {
            method: {field: sum(g['methods'][method][field] for g in selected_groups) for field in fields}
            for method in ('free_lib', 'plan')}
    lines += ['', f"新增行为修复费用：已结算 ${result['cost']['settled_usd']:.6f}；含预留 ${result['cost']['exposure_usd']:.6f}。",
              f'缺失或未评分：{len(missing)} 个候选。', '',
              '每项目只有五个相关里程碑、两个规划模型和两个库；不据此进行跨项目显著性推断。给出具体断言反馈仍不等于具备浏览器工具的完整代理。', '']
    dump(ROOT / 'test/results/behavior-feedback.json', result)
    (ROOT / 'test/results/behavior-feedback.md').write_text('\n'.join(lines))
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
