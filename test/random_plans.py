"""Chance level of a plan: what does picking the variants at random achieve?  (zero API, local grading only)

    uv run python -m test.random_plans --suite webbench --workers 5
    uv run python -m test.random_plans --suite todomvc --workers 4
    uv run python -m test.random_plans --report            # tables from whatever has been graded so far

A plan over a frozen library is a handful of choices.  This script enumerates every assignment of the variant slots
(slots with more than one admissible atom), keeps everything that is not a choice between variants exactly as in the
spec-correct reference plan (tool buttons, menus, shortcuts, flags, hooks), compiles each plan with the unchanged
compiler and grades it with the official tests.  The share of assignments that pass a task is the probability that a
uniformly random variant choice passes it; the variant projection of the rule plan is one point; non-variant hooks/menus remain at the reference values.
Results are cached under artifacts/random-plans/ and summarised in test/results/random-plans.{json,md}.
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts' / 'random-plans'
RESULTS = ROOT / 'test' / 'results'


def assignments(slots):
    """slots: {slot: [variants]} -> list of {slot: variant}, in a fixed order."""
    names = list(slots)
    return [dict(zip(names, combo)) for combo in itertools.product(*(slots[n] for n in names))]


def key_of(assignment):
    return '+'.join(assignment.values()) or 'none'


# ---------------------------------------------------------------- Web-Bench dom1
def webbench_units():
    from test.webbench_dna import domain
    from test.webbench_dna.library import SLOT_FEATURE, SLOTS
    units = []
    for task in domain.tasks():
        enabled = {s: SLOTS[s] for s in SLOTS if SLOT_FEATURE[s] in task['features']}
        for a in assignments(enabled):
            units.append((task, a))
    return units


def webbench_grade(unit):
    from test.webbench_dna import domain, evaluate
    from test.webbench_dna.library import library
    task, a = unit
    folder = OUT / 'webbench' / task['id'] / key_of(a)
    saved = folder / 'result.json'
    if saved.exists():
        result = json.loads(saved.read_text())
        if result['total'] > 0:
            return task['id'], a, result
    plan = {**domain.reference_plan(task['features']), **a}
    evaluate.write_candidate(folder, script=domain.compile_plan(plan, task['features'], library()))
    result = evaluate.grade(folder, task, folder / 'report.json')
    saved.write_text(json.dumps(result, ensure_ascii=False))
    return task['id'], a, result


# ---------------------------------------------------------------- TodoMVC
def todomvc_units():
    from test.todomvc_dna import domain
    from test.todomvc_dna.library import INITS, ROUTES, VIEWS
    units = []
    for task in domain.tasks():
        slots = {'init': INITS}
        slots.update({e: ROUTES[e] for e in domain.enabled_events(task['features']) if len(ROUTES[e]) > 1})
        slots.update({s: VIEWS[s] for s in domain.enabled_slots(task['features']) if len(VIEWS[s]) > 1})
        for a in assignments(slots):
            units.append((task, a))
    return units


def todomvc_grade(unit, server):
    from test.todomvc_dna import domain, evaluate
    from test.todomvc_dna.library import ROUTES, library
    task, a = unit
    folder = OUT / 'todomvc' / task['id'] / key_of(a)
    saved = folder / 'result.json'
    if saved.exists():
        result = json.loads(saved.read_text())
        if not result.get('note'):
            return task['id'], a, result
    plan = domain.reference_plan(task['features'])
    plan['init'] = a['init']
    for slot, name in a.items():
        if slot in ROUTES:
            plan['handlers'][slot] = name
        elif slot != 'init':
            plan['view'][slot] = name
    page = evaluate.write_app(domain.compile_plan(plan, task['features'], library()), folder)
    from test.todomvc_dna.review_evaluate import grade
    result = grade(server.url(page), folder / 'report.json', task['features'])
    saved.write_text(json.dumps(result, ensure_ascii=False))
    return task['id'], a, result


# ---------------------------------------------------------------- report
def collect(suite, units):
    rows = {}
    for task, a in units:
        saved = OUT / suite / task['id'] / key_of(a) / 'result.json'
        if saved.exists():
            r = json.loads(saved.read_text())
            if r.get('note') or not r.get('total'):
                continue
            rows.setdefault(task['id'], []).append({'assignment': a, 'passed': r['passed'], 'total': r['total'], 'all': r['all_passed'], 'test_counts_complete': r.get('test_counts_complete', True)})
    return rows


def summarise(suite, units, reference, rule):
    """reference / rule: functions task -> {slot: variant} restricted to the task's variant slots."""
    rows = collect(suite, units)
    tasks = []
    seen = []
    for task, _ in units:
        if task['id'] not in seen:
            seen.append(task['id'])
            tasks.append(task)
    per_task, complete = [], True
    for task in tasks:
        got = rows.get(task['id'], [])
        n = sum(1 for t, _ in units if t['id'] == task['id'])
        complete &= len(got) == n
        passing = [g for g in got if g['all']]
        ref, rul = reference(task), rule(task)
        per_task.append({'task': task['id'], 'slots': len(got[0]['assignment']) if got else None, 'assignments': n, 'graded': len(got),
                         'passing': len(passing), 'p_pass': len(passing) / n if len(got) == n else None,
                         'mean_tests': sum(g['passed'] for g in got) / len(got) if got and all(g['test_counts_complete'] for g in got) else None, 'tests': got[0]['total'] if got else None,
                         'reference_passes': next((g['all'] for g in got if g['assignment'] == ref), None),
                         'rule_passes': next((g['all'] for g in got if g['assignment'] == rul), None)})
    out = {'suite': suite, 'complete': complete, 'tasks': per_task}
    if complete:
        out['expected_tasks_passed'] = sum(t['p_pass'] for t in per_task)
        # distribution over full assignments (every variant slot of the suite fixed once, then restricted per task)
        biggest = max(tasks, key=lambda t: len(rows[t['id']][0]['assignment']))
        full = [g['assignment'] for g in rows[biggest['id']]]
        scores = []
        for a in full:
            score = 0
            for task in tasks:
                for g in rows[task['id']]:
                    if all(a.get(s) == v for s, v in g['assignment'].items()):
                        score += g['all']
                        break
            scores.append(score)
        out['full_assignments'] = {'n': len(full), 'min': min(scores), 'max': max(scores), 'mean': sum(scores) / len(scores),
                                   'histogram': {str(s): scores.count(s) for s in sorted(set(scores))},
                                   'reaching_max': scores.count(max(scores))}
    return out


def report():
    from test.todomvc_dna import domain as td
    from test.todomvc_dna.library import INITS, ROUTES, VIEWS
    from test.webbench_dna import domain as wd
    from test.webbench_dna.library import SLOT_FEATURE, SLOTS

    def wb_restrict(plan, task):
        return {s: plan[s] for s in SLOTS if SLOT_FEATURE[s] in task['features']}

    def td_flat(plan, task):
        flat = {'init': plan['init']}
        flat.update({e: n for e, n in plan['handlers'].items() if len(ROUTES[e]) > 1})
        flat.update({s: n for s, n in plan['view'].items() if len(VIEWS[s]) > 1})
        return flat
    data = {
        'webbench': summarise('webbench', webbench_units(), lambda t: wb_restrict(wd.reference_plan(t['features']), t),
                              lambda t: wb_restrict(wd.rule_plan(t['features']), t)),
        'todomvc': summarise('todomvc', todomvc_units(), lambda t: td_flat(td.reference_plan(t['features']), t),
                             lambda t: td_flat(td.rule_plan(t['features']), t)),
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / 'random-plans.json').write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    lines = ['# 随机方案基线：随机选变体能过多少任务（零 API，`uv run python -m test.random_plans`）', '',
             '变体槽位的每一种取法都编译并用官方测试评分；非变体部分（工具按钮、菜单、快捷键、开关、钩子）取按规范写出的参考方案。'
             '「通过概率」= 穷举完成后通过取法数 / 全部取法数。它是固定正确菜单/钩子条件下的概率，不是整个方案语言的均匀随机基线。TodoMVC 遇到首个反例即停止，其余测试未执行，不报告测试级均分。', '']
    for suite, title in [('webbench', 'Web-Bench dom1（20 个任务）'), ('todomvc', 'TodoMVC（8 个功能族）')]:
        d = data[suite]
        lines += [f'## {title}', '']
        if not d['complete']:
            lines += ['评分未完成；未评分不等于失败，只有穷举完成的任务才报告概率。', '']
        lines += ['| 任务 | 变体槽位数 | 已评/全部取法 | 通过的取法 | 通过概率 | 平均测试通过 | 参考变体 | 规则变体 |', '|---|---:|---:|---:|---:|---:|---|---|']
        for t in d['tasks']:
            if not t['graded']:
                continue
            probability = f"{t['p_pass']:.3f}" if t['p_pass'] is not None else '待完成'
            mean = f"{t['mean_tests']:.1f}/{t['tests']}" if t['mean_tests'] is not None else '提前停止，不计'
            status = lambda value: '未评' if value is None else ('过' if value else '不过')
            lines.append(f"| {t['task']} | {t['slots']} | {t['graded']}/{t['assignments']} | {t['passing']} | {probability} | {mean} | "
                         f"{status(t['reference_passes'])} | {status(t['rule_passes'])} |")
        if d['complete']:
            f = d['full_assignments']
            lines += ['', f"期望通过任务数（各任务通过概率之和）：**{d['expected_tasks_passed']:.2f} / {len(d['tasks'])}**。",
                      f"把全部变体槽位一次取定（共 {f['n']} 种完整取法）再逐任务评分：通过任务数最少 {f['min']}、平均 {f['mean']:.2f}、最多 {f['max']}；"
                      f"达到最多的取法有 {f['reaching_max']} 种。分布：" + '，'.join(f'{k} 个任务 × {v}' for k, v in f['histogram'].items()) + '。']
        lines.append('')
    (RESULTS / 'random-plans.md').write_text('\n'.join(lines))
    print('\n'.join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--suite', choices=['webbench', 'todomvc'])
    parser.add_argument('--workers', type=int, default=4, help='concurrent official-test runs')
    parser.add_argument('--browser-workers', type=int, default=2, help='Playwright workers inside each run')
    parser.add_argument('--report', action='store_true')
    args = parser.parse_args()
    if args.suite:
        os.environ['WORKERS'] = str(args.browser_workers)
        if args.suite == 'webbench':
            units, grade, server = webbench_units(), webbench_grade, None
        else:
            from test.todomvc_dna.evaluate import Server
            server = Server(OUT / 'todomvc')
            units, grade = todomvc_units(), (lambda u: todomvc_grade(u, server))
        (OUT / args.suite).mkdir(parents=True, exist_ok=True)
        print(f'{args.suite}: {len(units)} plans', flush=True)
        try:
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                for i, (task_id, a, r) in enumerate(pool.map(grade, units), 1):
                    if i % 20 == 0 or not r['total']:
                        print(f"{i}/{len(units)} {task_id} {key_of(a)}: {r['passed']}/{r['total']} {r.get('note', '')[:80]}", flush=True)
        finally:
            if server:
                server.close()
    report()


if __name__ == '__main__':
    main()
