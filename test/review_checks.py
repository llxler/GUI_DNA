"""Zero-API checks behind four statements a reviewer would probe.  (read-only on every result file)

    uv run python -m test.review_checks

1. post-freeze: TodoMVC samples s2-s4 were generated after the plan compiler stopped changing (2026-11-02 11:48), so
   they test the relaxed compiler prospectively, with nothing replayed.  Source: summary-samples5.json.
2. cost: settled cost per method on Web-Bench dom1 and TodoMVC, summed over the eight models.  Source: summary.json.
3. repair-source: on List-16, how many repaired candidates had their first plan rejected by the compiler (a diagnostic)
   rather than failing the public check.  Source: artifacts/scale-study/results.json, 47 complete groups.
4. inheritance: under the sequential Web-Bench protocol free-form code edits its own previous page.  Counts the first
   failing task per model, pass rates conditioned on the previous task, and how many of the plan's paired wins follow a
   task the free-form page had already failed.  Source: summary.json.
Writes test/results/review-checks.{json,md}.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'test' / 'results'
LIST16 = {'linked_js': 'Free', 'dna': 'Free+Lib', 'plan_unchecked': 'Plan-', 'plan_checked': 'GUI-DNA'}


def short(model):
    return model.split('/')[-1]


def post_freeze():
    summary = json.loads((ROOT / 'test/todomvc_dna/results/summary-samples5.json').read_text())
    rows = {}
    for m in summary['models']:
        free, dna, pairs, won, lost = [0, 0], [0, 0], 0, 0, 0
        for r in m['rows']:
            if r['sample'] < 2:
                continue
            f, d = r.get('free'), r.get('dna')
            if f:
                free[1] += 1
                free[0] += bool(f['final_all'])
            if d:
                dna[1] += 1
                dna[0] += bool(d['final_all'])
            if f and d:
                pairs += 1
                won += bool(d['final_all'] and not f['final_all'])
                lost += bool(f['final_all'] and not d['final_all'])
        rows[short(m['model'])] = {'free': free, 'dna': dna, 'pairs': pairs, 'won': won, 'lost': lost}
    total = {'free': [sum(r['free'][i] for r in rows.values()) for i in (0, 1)],
             'dna': [sum(r['dna'][i] for r in rows.values()) for i in (0, 1)],
             'pairs': sum(r['pairs'] for r in rows.values()), 'won': sum(r['won'] for r in rows.values()),
             'lost': sum(r['lost'] for r in rows.values())}
    return {'models': rows, 'total': total}


def costs():
    out = {}
    for suite, path in [('webbench', 'test/webbench_dna/results/summary.json'), ('todomvc', 'test/todomvc_dna/results/summary.json')]:
        summary = json.loads((ROOT / path).read_text())
        out[suite] = {arm: round(sum(m['arms'][arm]['cost_usd'] or 0 for m in summary['models']), 4) for arm in summary['arms']}
    return out


def repair_source():
    runs = [r for r in json.loads((ROOT / 'artifacts/scale-study/results.json').read_text())['runs'] if r['status'] == 'generated']
    groups = defaultdict(dict)
    for r in runs:
        groups[(r['model'], r['task_id'], r['repetition'])][r['method']] = r
    full = [g for g in groups.values() if len(g) == 4]
    out = {'groups': len(full)}
    for method, name in LIST16.items():
        repaired = after_reject = rejections = 0
        for g in full:
            r = g[method]
            errors = [v.get('compile_error') for v in r['versions']]
            rejections += sum(1 for e in errors if e)
            if r['hidden']['passed'] and not r['first_hidden']['passed']:
                repaired += 1
                after_reject += bool(errors[0])
        out[name] = {'repaired': repaired, 'first_version_rejected': after_reject, 'after_public_check': repaired - after_reject,
                     'rejections': rejections}
    return out


def inheritance():
    summary = json.loads((ROOT / 'test/webbench_dna/results/summary.json').read_text())
    n = len(summary['tasks'])
    out = {'per_task': {}, 'first_failure': {}, 'conditional': {}}
    for arm in ['free', 'free_lib', 'dna']:
        out['per_task'][arm] = [sum(bool(m['rows'][k][arm]['final_all']) for m in summary['models']) for k in range(n)]
        out['first_failure'][arm] = {short(m['model']): next((k + 1 for k in range(n) if not m['rows'][k][arm]['final_all']), None)
                                     for m in summary['models']}
    for arm in ['free', 'free_lib']:
        after_pass, after_fail = [0, 0], [0, 0]
        for m in summary['models']:
            for k in range(1, n):
                bucket = after_pass if m['rows'][k - 1][arm]['final_all'] else after_fail
                bucket[1] += 1
                bucket[0] += bool(m['rows'][k][arm]['final_all'])
        out['conditional'][arm] = {'pass_after_pass': after_pass, 'pass_after_fail': after_fail}
    clean = inherited = 0
    for m in summary['models']:
        for k in range(n):
            if m['rows'][k]['dna']['final_all'] and not m['rows'][k]['free']['final_all']:
                if k == 0 or m['rows'][k - 1]['free']['final_all']:
                    clean += 1
                else:
                    inherited += 1
    out['plan_wins_vs_free'] = {'first_task_or_after_free_pass': clean, 'after_free_failure': inherited}
    return out


# ---------------------------------------------------------------- plan-level checks on the saved plans (R2-R5)
def _webbench_normalise(plan, features):
    """What the linker keeps of a plan for these features (same pruning rules as compile_plan)."""
    from test.webbench_dna.domain import MENU_KINDS
    from test.webbench_dna.library import COMMANDS, SLOT_FEATURE, SLOTS
    menu = plan.get('menu') or {}
    kept = {k: [c for c in (menu.get(k) or []) if isinstance(c, str) and COMMANDS.get(c) in features] for k in MENU_KINDS} if 'menuEntry' in features else {}
    if 'menuPanel' not in features:
        kept.pop('entries', None)
    slots = {s: plan.get(s) for s in SLOTS if SLOT_FEATURE[s] in features}
    return kept, slots


def saved_record(suite, model, row, arm='dna'):
    stage = 'webbench-dna-6' if suite == 'webbench' else 'todomvc-dna-4'
    folder = ROOT / 'artifacts' / stage / 'runs' / model.replace('/', '__') / arm / row['task']
    if suite == 'todomvc':
        folder /= f"s{row['sample']}"
    return json.loads((folder / 'record.json').read_text())


def saved_plan(suite, model, row, arm='dna', phase='final'):
    rec = saved_record(suite, model, row, arm)
    if phase == 'first_attempt':
        return rec['attempts'][0].get('plan') if rec['attempts'] else None
    if not rec['versions']:
        return None
    # Match the executed version, not a later rejected attempt in the summary.
    version = rec['versions'][-1]
    number = int(version.lstrip('vr'))
    return next((a.get('plan') for a in rec['attempts'] if a['attempt'] == number), None)


def slot_accuracy(phase="final"):
    """Share of variant slots filled as in the spec-correct reference plan, per model and slot (final plans of the main study)."""
    from test.todomvc_dna import domain as td
    from test.todomvc_dna.library import ROUTES, VIEWS
    from test.webbench_dna import domain as wd
    from test.webbench_dna.library import SLOT_FEATURE, SLOTS
    out = {}
    summary = json.loads((ROOT / 'test/webbench_dna/results/summary.json').read_text())
    tasks = {t['id']: t for t in wd.tasks()}
    table = {}
    for m in summary['models']:
        row = defaultdict(lambda: [0, 0])
        for r in m['rows']:
            plan, task = saved_plan('webbench', m['model'], r, phase=phase), tasks[r['task']]
            ref = wd.reference_plan(task['features'])
            for slot in SLOTS:
                if SLOT_FEATURE[slot] in task['features']:
                    row[slot][1] += 1
                    row[slot][0] += isinstance(plan, dict) and plan.get(slot) == ref[slot]
        table[short(m['model'])] = dict(row)
    out['webbench'] = table
    summary = json.loads((ROOT / 'test/todomvc_dna/results/summary.json').read_text())
    tasks = {t['id']: t for t in td.tasks()}
    table = {}
    for m in summary['models']:
        row = defaultdict(lambda: [0, 0])
        for r in m['rows']:
            plan, task = td._unwrap_names(saved_plan('todomvc', m['model'], r, phase=phase) or {}), tasks[r['task']]
            plan = plan if isinstance(plan, dict) else {}
            ref = td.reference_plan(task['features'])
            pairs = [('init', plan.get('init'), ref['init'])]
            pairs += [(e, (plan['handlers'].get(e) if isinstance(plan.get('handlers'), dict) else None), n) for e, n in ref['handlers'].items() if len(ROUTES[e]) > 1]
            pairs += [(v, (plan['view'].get(v) if isinstance(plan.get('view'), dict) else None), n) for v, n in ref['view'].items() if len(VIEWS[v]) > 1]
            for slot, got, want in pairs:
                row[slot][1] += 1
                row[slot][0] += got == want
        table[short(m['model'])] = dict(row)
    out['todomvc'] = table
    return out


def residual_failures():
    """Why the remaining GUI-DNA tasks on Web-Bench fail: no plan compiled / wrong variant / extra menu command / missing menu command."""
    from test.webbench_dna import domain as wd
    summary = json.loads((ROOT / 'test/webbench_dna/results/summary.json').read_text())
    tasks = {t['id']: t for t in wd.tasks()}
    counts, primary, rows = defaultdict(int), defaultdict(int), []
    for m in summary['models']:
        for r in m['rows']:
            d = r['dna']
            if not d or d['final_all']:
                continue
            task = tasks[r['task']]
            labels = []
            plan = saved_plan('webbench', m['model'], r)
            if not isinstance(plan, dict):
                labels.append('rejected')
            else:
                menu, slots = _webbench_normalise(plan, task['features'])
                ref_menu, ref_slots = _webbench_normalise(wd.reference_plan(task['features']), task['features'])
                if slots != ref_slots:
                    labels.append('variant')
                if any(c not in ref_menu.get(k, []) for k, cs in menu.items() for c in cs):
                    labels.append('extra_command')
                if any(c not in menu.get(k, []) for k, cs in ref_menu.items() for c in cs):
                    labels.append('missing_command')
            labels = labels or ['other']
            for label in labels:
                counts[label] += 1
            primary[labels[0]] += 1
            rows.append({'model': short(m['model']), 'task': r['task'], 'labels': labels, 'failed_tests': d['failed_tests'][:3]})
    return {'failed_tasks': len(rows), 'labels': dict(counts), 'primary': dict(primary), 'rows': rows}


def coverage_replay():
    """Would the coverage check have rejected the final plans written without it?"""
    from test.todomvc_dna import domain as td
    from test.todomvc_dna.library import library as tlib
    from test.webbench_dna import domain as wd
    from test.webbench_dna.library import library as wlib
    out = {}
    for suite, mod, lib, path in [('webbench', wd, wlib(), 'test/webbench_dna/results/summary.json'), ('todomvc', td, tlib(), 'test/todomvc_dna/results/summary.json')]:
        summary = json.loads((ROOT / path).read_text())
        tasks = {t['id']: t for t in mod.tasks()}
        plans = no_plan = rejected = 0
        by_model = {}
        for m in summary['models']:
            mine = 0
            for r in m['rows']:
                d = r.get('dna_unchecked')
                if not d:
                    continue
                plan = saved_plan(suite, m['model'], r, arm='dna_unchecked')
                if not isinstance(plan, dict):
                    no_plan += 1
                    continue
                plans += 1
                try:
                    mod.compile_plan(plan, tasks[r['task']]['features'], lib, checked=True)
                except ValueError:
                    rejected += 1
                    mine += 1
            by_model[short(m['model'])] = mine
        out[suite] = {'final_plans_compiled': plans, 'no_compiled_plan': no_plan, 'would_be_rejected': rejected, 'by_model': by_model}
    return out


def exact_tests():
    """Per-model exact McNemar test (two-sided binomial on the discordant pairs) and a sign test across models, GUI-DNA vs free code."""
    from math import comb

    def two_sided(k, n):
        if n == 0:
            return 1.0
        tail = sum(comb(n, i) for i in range(0, min(k, n - k) + 1)) / 2 ** n
        return min(1.0, 2 * tail)
    out = {}
    for suite, path in [('webbench', 'test/webbench_dna/results/summary.json'), ('todomvc', 'test/todomvc_dna/results/summary.json')]:
        summary = json.loads((ROOT / path).read_text())
        rows, better, worse = {}, 0, 0
        for m in summary['models']:
            p = m['paired']
            rows[short(m['model'])] = {'dna_only': p['dna_only'], 'free_only': p['free_only'], 'p': two_sided(p['free_only'], p['dna_only'] + p['free_only'])}
            better += p['dna_only'] > p['free_only']
            worse += p['dna_only'] < p['free_only']
        won, lost = sum(r['dna_only'] for r in rows.values()), sum(r['free_only'] for r in rows.values())
        out[suite] = {'models': rows, 'models_better': better, 'models_worse': worse, 'models_tied': len(rows) - better - worse,
                      'sign_test_p': two_sided(worse, better + worse), 'pooled_discordant': [won, lost], 'pooled_p': two_sided(lost, won + lost)}
    return out


def main():
    data = {'post_freeze': post_freeze(), 'cost_usd': costs(), 'repair_source': repair_source(), 'inheritance': inheritance(),
            'slot_accuracy': slot_accuracy(), 'slot_first_attempt': slot_accuracy('first_attempt'), 'residual_failures': residual_failures(), 'coverage_replay': coverage_replay(), 'exact_tests': exact_tests()}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'review-checks.json').write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    pf, rs, ih = data['post_freeze'], data['repair_source'], data['inheritance']
    lines = ['# 审稿问题复核（包含 R2–R5）（零 API，`uv run python -m test.review_checks`）', '',
             '## 1. TodoMVC：编译器冻结之后才生成的采样（s2–s4，无重放）', '',
             '| 模型 | 自由代码 | GUI-DNA | 配对 | 仅 DNA 过 | 仅自由过 |', '|---|---:|---:|---:|---:|---:|']
    for model, r in pf['models'].items():
        lines.append(f"| {model} | {r['free'][0]}/{r['free'][1]} | {r['dna'][0]}/{r['dna'][1]} | {r['pairs']} | {r['won']} | {r['lost']} |")
    t = pf['total']
    lines += [f"| **合计** | {t['free'][0]}/{t['free'][1]} | {t['dna'][0]}/{t['dna'][1]} | {t['pairs']} | {t['won']} | {t['lost']} |", '',
              '## 2. 各做法已结算费用（8 模型合计，USD）', '', '| 数据集 | ' + ' | '.join(data['cost_usd']['webbench']) + ' |',
              '|---|' + '---:|' * len(data['cost_usd']['webbench'])]
    for suite, row in data['cost_usd'].items():
        lines.append(f'| {suite} | ' + ' | '.join(f'{v:.3f}' for v in row.values()) + ' |')
    lines += ['', f"## 3. 自建任务：修复后才对的候选，首个版本是否被编译器拒绝（{rs['groups']} 个完整组）", '',
              '| 做法 | 修复后才对 | 其中首个版本被编译器拒绝 | 其中首个版本只是公开检查失败 | 静态拒绝总数 |', '|---|---:|---:|---:|---:|']
    for name in LIST16.values():
        r = rs[name]
        lines.append(f"| {name} | {r['repaired']} | {r['first_version_rejected']} | {r['after_public_check']} | {r['rejections']} |")
    lines += ['', '## 4. Web-Bench 顺序协议下的错误继承', '', '逐任务通过的模型数（/8，任务 1–20）：', '']
    for arm, row in ih['per_task'].items():
        lines.append(f"- `{arm}`: {' '.join(str(x) for x in row)}（合计 {sum(row)}）")
    lines += ['', '首个失败任务：', '']
    for arm, row in ih['first_failure'].items():
        lines.append(f"- `{arm}`: " + '，'.join(f"{model} {task if task else '无'}" for model, task in row.items()))
    lines += ['', '| 做法 | 上一任务通过时本任务通过 | 上一任务失败时本任务通过 |', '|---|---:|---:|']
    for arm, c in ih['conditional'].items():
        lines.append(f"| {arm} | {c['pass_after_pass'][0]}/{c['pass_after_pass'][1]} | {c['pass_after_fail'][0]}/{c['pass_after_fail'][1]} |")
    w = ih['plan_wins_vs_free']
    lines += ['', f"GUI-DNA 对自由代码的 {w['first_task_or_after_free_pass'] + w['after_free_failure']} 个配对胜出里，"
              f"{w['first_task_or_after_free_pass']} 个出现在首个任务或自由代码上一任务仍通过之后，"
              f"{w['after_free_failure']} 个出现在自由代码上一任务已失败之后（可能含继承的错误）。", '']
    lines += ['槽位指标是与参考方案的逐字选择一致率，不等于行为正确率；等价变体可能同样过测试，缺失/无可执行方案仍计入分母。', '']
    for phase, suite, title in [(p, s, t) for p in ['slot_first_attempt', 'slot_accuracy'] for s, t in [('webbench', 'Web-Bench dom1'), ('todomvc', 'TodoMVC')]]:
        sa = data[phase]
        slots = list(next(iter(sa[suite].values())))
        lines += [f'## 5{"a" if suite == "webbench" else "b"}. 槽位参考一致率：{title}（{phase}，一致数 / 启用槽位数）', '',
                  '| 模型 | ' + ' | '.join(slots) + ' | 合计 |', '|---|' + '---:|' * (len(slots) + 1)]
        total = {slot: [0, 0] for slot in slots}
        for model, row in sa[suite].items():
            lines.append(f'| {model} | ' + ' | '.join(f'{row[slot][0]}/{row[slot][1]}' for slot in slots)
                         + f' | {sum(v[0] for v in row.values())}/{sum(v[1] for v in row.values())} |')
            for slot in slots:
                total[slot][0] += row[slot][0]
                total[slot][1] += row[slot][1]
        lines += ['| **合计** | ' + ' | '.join(f'{v[0]}/{v[1]}' for v in total.values())
                  + f' | **{sum(v[0] for v in total.values())}/{sum(v[1] for v in total.values())}** |', '']
    rf = data['residual_failures']
    names = {'rejected': '没有可执行版本', 'variant': '变体不同于参考（不必然导致失败）', 'extra_command': '菜单多接了命令', 'missing_command': '菜单少接了命令', 'other': '其他'}
    lines += [f"## 6. Web-Bench 上 GUI-DNA 剩余的 {rf['failed_tasks']} 个失败任务", '', '| 原因 | 任务数（可多选） | 按固定顺序分组（非因果） |', '|---|---:|---:|']
    for key, label in names.items():
        if rf['labels'].get(key):
            lines.append(f"| {label} | {rf['labels'][key]} | {rf['primary'].get(key, 0)} |")
    lines += ['', '逐条：' + '；'.join(f"{r['model']} {r['task']}（{'+'.join(r['labels'])}）" for r in rf['rows']), '']
    cr = data['coverage_replay']
    lines += ['## 7. 覆盖检查重放：「方案不做覆盖检查」的最终方案会不会被检查拒绝', '', '| 数据集 | 已编译的最终方案 | 会被覆盖检查拒绝 | 没有可编译方案 |', '|---|---:|---:|---:|']
    for suite, c in cr.items():
        lines.append(f"| {suite} | {c['final_plans_compiled']} | {c['would_be_rejected']}（{'，'.join(f'{k} {v}' for k, v in c['by_model'].items() if v) or '无'}） | {c['no_compiled_plan']} |")
    et = data['exact_tests']
    lines += ['', '## 8. 探索性精确检验（双侧）', '', 'McNemar 的二项参考分布假定配对任务彼此独立；Web-Bench 顺序任务不满足此条件。下列 p 仅是该假设下的参考值，不是解决顺序依赖后的显著性结论；合并任务的 p 不作为证据。跨模型符号检验也依赖模型独立/可交换假设，不能替代项目级复现。', '']
    for suite, e in et.items():
        lines += [f'### {suite}', '', '| 模型 | 仅 DNA 过 | 仅自由过 | p |', '|---|---:|---:|---:|']
        for model, r in e['models'].items():
            lines.append(f"| {model} | {r['dna_only']} | {r['free_only']} | {r['p']:.4f} |")
        lines += ['', f"变好 {e['models_better']} 个模型、变差 {e['models_worse']} 个、持平 {e['models_tied']} 个；符号检验双侧 p = {e['sign_test_p']:.4f}。"
                  f"合并不一致对 {e['pooled_discordant'][0]} 比 {e['pooled_discordant'][1]}（仅描述）。", '']
    (OUT / 'review-checks.md').write_text('\n'.join(lines))
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
