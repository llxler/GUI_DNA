"""Web-Bench dom1: free incremental code vs rule wiring vs GUI-DNA plan, graded by the official per-task Playwright specs.

    uv run python -m test.webbench_dna.run --arms rule                     # zero-API control + official grading
    export OPENROUTER_API_KEY=...
    uv run python -m test.webbench_dna.run --arms free rule dna --models qwen/qwen3-coder-30b-a3b-instruct ...
    uv run python -m test.webbench_dna.run --evaluate-only                 # re-grade saved versions, no API

Protocol: `free` follows the benchmark (start from the official src-init page; at task k the model gets its own current
index.html plus task k's description and returns the whole file; its output carries over to task k+1).  `dna` writes an
independent plan per task from the descriptions 1..k.  Both get the same public feedback (page/console errors, tool
buttons clickable) for up to --max-repairs repairs.  Hidden grading = the official task-k.spec.js on first and final
versions, after all generation.  Also reported: the benchmark's sequential score (stop after two consecutive failures).
"""
from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

from gui_dna.budget import BudgetStop, Ledger
from gui_dna.provider import OpenRouter, ProviderError, parse_json
from gui_dna.tasks import dump

from . import domain, evaluate
from .library import library

HERE = domain.HERE
DEFAULT_OUT = domain.ROOT / 'artifacts/webbench-dna'
RESULTS = HERE / 'results'
INIT_HTML = HERE / 'harness' / 'src-init.index.html'


def slug(model):
    return model.replace('/', '__')


def attempt_loop(arm, model, task, lib, folder, provider, seed, max_repairs, messages, record):
    """Shared generate -> public check -> repair loop; returns the final usable artefact (html or script) or None."""
    final = None
    for attempt_no in range(1, max_repairs + 2):
        attempt = {'attempt': attempt_no, 'compile_error': None, 'public': None}
        try:
            raw = provider.call(model, messages, folder / f'call-{attempt_no}', f'webbench:{model}:{arm}:{task["id"]}:a{attempt_no}', seed=seed,
                                max_tokens=12000 if arm == 'free' else 3000)
        except BudgetStop:
            raise
        except ProviderError as error:
            attempt['compile_error'] = f'ProviderError: {error}'
            record['attempts'].append(attempt)
            break
        artefact = None
        try:
            parsed = parse_json(raw)
            if arm == 'free':
                artefact = parsed['html']
                if not isinstance(artefact, str) or '<html' not in artefact.lower():
                    raise ValueError('"html" must be the complete index.html document')
            else:
                attempt['plan'] = parsed
                artefact = domain.compile_plan(parsed, task['features'], lib)
        except (ValueError, KeyError, TypeError) as error:
            attempt['compile_error'] = f'{type(error).__name__}: {error}'
        if artefact is not None:
            version = f'v{attempt_no}'
            vf = evaluate.write_candidate(folder / version, html=artefact if arm == 'free' else None, script=None if arm == 'free' else artefact)
            attempt['public'] = evaluate.public_check(vf)
            record['versions'].append(version)
            final = artefact
        record['attempts'].append(attempt)
        if artefact is not None and not attempt['public']:
            break
        if attempt_no > max_repairs:
            break
        if attempt['compile_error']:
            feedback = ('The plan was rejected by the compiler:\n' if arm == 'dna' else 'Your output could not be used:\n') + attempt['compile_error']
        else:
            feedback = 'Public smoke check failed:\n- ' + '\n- '.join(attempt['public'])
        feedback += '\nReturn a corrected ' + ('plan' if arm == 'dna' else 'complete index.html') + ' as JSON only.'
        messages = messages + [{'role': 'assistant', 'content': raw}, {'role': 'user', 'content': feedback}]
    return final


def run_model(arm, model, tasks, lib, out, provider, seed, max_repairs, server_unused=None):
    """All 20 tasks for one model and arm (free is sequential, so it runs as a unit)."""
    records = {}
    current_html = INIT_HTML.read_text()
    for task in tasks:
        folder = out / 'runs' / slug(model) / arm / task['id']
        record_path = folder / 'record.json'
        if record_path.exists():
            rec = json.loads(record_path.read_text())
            if arm == 'free' and rec['versions']:
                current_html = (folder / rec['versions'][-1] / 'index.html').read_text()
            records[task['id']] = rec
            continue
        rec = {'arm': arm, 'model': model, 'task': task['id'], 'features': task['features'], 'attempts': [], 'versions': []}
        if arm == 'rule':
            plan = domain.rule_plan(task['features'])
            script = domain.compile_plan(plan, task['features'], lib)
            vf = evaluate.write_candidate(folder / 'v1', script=script)
            rec['attempts'].append({'attempt': 1, 'plan': plan, 'compile_error': None, 'public': evaluate.public_check(vf)})
            rec['versions'].append('v1')
        elif arm == 'dna':
            attempt_loop(arm, model, task, lib, folder, provider, seed, max_repairs, domain.messages_for(task, 'dna', lib), rec)
        else:
            final = attempt_loop(arm, model, task, lib, folder, provider, seed, max_repairs, domain.free_messages(task, current_html), rec)
            if final is not None:
                current_html = final   # the benchmark's sequential dependency: next task starts from this output
        dump(record_path, rec)
        records[task['id']] = rec
        print(f"{model} {arm:4} {task['id']:8}: attempts={len(rec['attempts'])} versions={len(rec['versions'])}", flush=True)
    return records


def grade_record(rec, folder, task, evaluate_only):
    hidden_path = folder / 'hidden.json'
    if hidden_path.exists() and not evaluate_only:
        return json.loads(hidden_path.read_text())
    out = {}
    if rec['versions']:
        for label, version in [('first', rec['versions'][0]), ('final', rec['versions'][-1])]:
            if label == 'final' and version == rec['versions'][0]:
                out['final'] = out['first']
                continue
            out[label] = evaluate.grade(folder / version, task, folder / version / 'report.json')
    else:
        empty = {'passed': 0, 'total': 0, 'all_passed': False, 'tests': {}, 'note': 'no usable version'}
        out = {'first': empty, 'final': empty}
    dump(hidden_path, out)
    return out


def sequential_score(passes):
    """Web-Bench style: count passed tasks in order, stop after two consecutive failures."""
    score, fails = 0, 0
    for ok in passes:
        if ok:
            score += 1
            fails = 0
        else:
            fails += 1
            if fails >= 2:
                break
    return score


def summarize(models, arms, tasks, records, hidden, ledger_summary, max_repairs):
    calls = ledger_summary.get('calls', [])
    def cost(prefix):
        return sum((c['actual'] or 0) for c in calls if c['purpose'].startswith(prefix)) / 1e6
    label = {'free': '自由增量代码（基准协议）', 'rule': '规则组装（零 API 控制）', 'dna': 'GUI-DNA 组装方案 + 编译检查'}
    summary = {'date_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'max_repairs': max_repairs, 'arms': arms, 'labels': label,
               'tasks': [{'id': t['id'], 'level': t['level'], 'features': t['features']} for t in tasks],
               'accounting': {k: v for k, v in ledger_summary.items() if k != 'calls'}, 'models': []}
    for model in models:
        entry = {'model': model, 'arms': {}, 'rows': []}
        for task in tasks:
            row = {'task': task['id'], 'level': task['level']}
            for arm in arms:
                rec, h = records.get((model, arm, task['id'])), hidden.get((model, arm, task['id']))
                if not rec or not h:
                    row[arm] = None
                    continue
                last = rec['attempts'][-1] if rec['attempts'] else {}
                row[arm] = {'first_passed': h['first']['passed'], 'final_passed': h['final']['passed'], 'total': h['final']['total'],
                            'first_all': h['first']['all_passed'], 'final_all': h['final']['all_passed'],
                            'calls': len(rec['attempts']) if arm != 'rule' else 0,
                            'compile_errors': sum(1 for a in rec['attempts'] if a.get('compile_error')),
                            'plan': last.get('plan'), 'compile_error': last.get('compile_error'),
                            'failed_tests': sorted(k for k, v in h['final']['tests'].items() if v != 'passed')}
            entry['rows'].append(row)
        for arm in arms:
            rows = [r[arm] for r in entry['rows'] if r[arm]]
            entry['arms'][arm] = {'n': len(rows), 'first_all': sum(r['first_all'] for r in rows), 'final_all': sum(r['final_all'] for r in rows),
                                  'first_tests': sum(r['first_passed'] for r in rows), 'final_tests': sum(r['final_passed'] for r in rows),
                                  'tests': sum(r['total'] for r in rows), 'calls': sum(r['calls'] for r in rows),
                                  'compile_errors': sum(r['compile_errors'] for r in rows),
                                  'sequential_first': sequential_score([r['first_all'] for r in rows]),
                                  'sequential_final': sequential_score([r['final_all'] for r in rows]),
                                  'cost_usd': cost(f'webbench:{model}:{arm}:')}
        if 'free' in arms and 'dna' in arms:
            pairs = [(r['free'], r['dna']) for r in entry['rows'] if r['free'] and r['dna']]
            entry['paired'] = {'dna_only': sum(d['final_all'] and not f['final_all'] for f, d in pairs),
                               'free_only': sum(f['final_all'] and not d['final_all'] for f, d in pairs),
                               'both': sum(f['final_all'] and d['final_all'] for f, d in pairs),
                               'neither': sum(not f['final_all'] and not d['final_all'] for f, d in pairs)}
        summary['models'].append(entry)
    return summary


def markdown(summary):
    arms, label = summary['arms'], summary['labels']
    lines = ['# Web-Bench dom1（官方 Playwright 测试）：自由增量代码 vs 冻结原子函数组装（GUI-DNA）', '',
             f"生成时间 {summary['date_utc']}。20 个顺序任务，隐藏评测 = 官方 `task-k.spec.js`（共 85 项断言测试）；自由代码按基准协议从官方初始页面逐任务增量修改，"
             f"GUI-DNA 每个任务独立写组装方案；两者同种子、同公开反馈（页面/控制台错误、工具按钮可点击），最多 {summary['max_repairs']} 轮修复。"
             '「顺序分」= 基准口径：按任务顺序累计通过数，连续两次失败即停止。', '',
             '| 模型 | 方法 | 任务通过（首次） | 任务通过（最终） | 顺序分（最终） | 测试通过（最终） | 调用 | 编译/解析拒绝 | 费用 |', '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for m in summary['models']:
        for arm in arms:
            a = m['arms'][arm]
            lines.append(f"| {m['model']} | {label[arm]} | {a['first_all']}/{a['n']} | **{a['final_all']}/{a['n']}** | {a['sequential_final']}/{a['n']} | "
                         f"{a['final_tests']}/{a['tests']} | {a['calls']} | {a['compile_errors']} | ${a['cost_usd']:.4f} |")
        if m.get('paired'):
            p = m['paired']
            lines.append(f"| {m['model']} | 配对（最终，DNA vs 自由） | 仅 DNA 过 {p['dna_only']} | 仅自由过 {p['free_only']} | 都过 {p['both']} | 都败 {p['neither']} | | | |")
    lines.append('')
    for m in summary['models']:
        lines += [f"## {m['model']}：逐任务（测试通过 首次 → 最终 / 总数）", '', '| 任务 | 难度 | ' + ' | '.join(label[a] for a in arms) + ' | DNA 最终仍失败的测试 |',
                  '|---|---|' + '---:|' * len(arms) + '---|']
        for r in m['rows']:
            cells = []
            for arm in arms:
                o = r[arm]
                cells.append('—' if not o else f"{o['first_passed']} → **{o['final_passed']}** / {o['total']}" + (' ⟂' if o['compile_error'] else ''))
            failed = '; '.join((r.get('dna') or {}).get('failed_tests', [])[:3]) if r.get('dna') else ''
            lines.append(f"| {r['task']} | {r['level']} | " + ' | '.join(cells) + f" | {failed} |")
        lines.append('')
    a = summary['accounting']
    lines += [f"账本（独立）：已结算 ${a['actual_usd']:.6f}，敞口 ${a['exposure_usd']:.6f}，未结算 {a['unsettled_calls']}。", '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--models', nargs='+', default=['qwen/qwen3-coder-30b-a3b-instruct', 'mistralai/mistral-small-3.2-24b-instruct', 'google/gemma-3-12b-it'])
    parser.add_argument('--arms', nargs='+', default=['free', 'rule', 'dna'], choices=domain.METHODS)
    parser.add_argument('--max-repairs', type=int, default=2)
    parser.add_argument('--seed', type=int, default=20261102)
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT)
    parser.add_argument('--cap-usd', type=float, default=1.5)
    parser.add_argument('--stop-usd', type=float, default=1.3)
    parser.add_argument('--evaluate-only', action='store_true')
    parser.add_argument('--label', default='')
    parser.add_argument('--grade-workers', type=int, default=4, help='concurrent official spec runs during hidden grading')
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    lib = library()
    tasks = domain.tasks()
    config = {'models': args.models, 'temperature': 0.6, 'max_tokens': 12000, 'max_repairs': args.max_repairs, 'seed': args.seed,
              'budget_usd': args.cap_usd, 'stop_new_requests_usd': args.stop_usd,
              'price_caps_per_million': {'prompt': 3.0, 'completion': 15.0},
              'model_price_caps': {'deepseek/deepseek-v4-pro-0813': {'prompt': 1.3, 'completion': 4.1},
                                   'deepseek/deepseek-v4-flash': {'prompt': 0.2, 'completion': 0.4},
                                   'qwen/qwen3-coder-30b-a3b-instruct': {'prompt': 0.1, 'completion': 0.4},
                                   'google/gemma-3-12b-it': {'prompt': 0.1, 'completion': 0.3},
                                   'mistralai/mistral-small-3.2-24b-instruct': {'prompt': 0.1, 'completion': 0.3}}}
    ledger = Ledger(out / 'budget.sqlite3', args.cap_usd, args.stop_usd)
    paid = (not args.evaluate_only) and any(a in args.arms for a in ['free', 'dna'])
    provider = OpenRouter(config, ledger) if paid else None
    dump(out / 'manifest.json', {'config': config, 'arms': args.arms, 'tasks': tasks, 'library_sha256': lib['sha256'],
                                 'domain_sha256': evaluate.sha256((HERE / 'domain.py').read_text()),
                                 'shell_sha256': evaluate.sha256(evaluate.SHELL.read_text()),
                                 'specs_sha256': {p.name: evaluate.sha256(p.read_text()) for p in sorted((evaluate.HARNESS / 'dom1-tests').glob('*.spec.js'))},
                                 'source': 'bytedance/web-bench projects/dom1 (tests, tasks.jsonl, src-init verbatim; src decomposed into the library)'})
    records, hidden, stopped = {}, {}, None
    for model in args.models:
        for arm in args.arms:
            if args.evaluate_only:
                for task in tasks:
                    p = out / 'runs' / slug(model) / arm / task['id'] / 'record.json'
                    if p.exists():
                        records[(model, arm, task['id'])] = json.loads(p.read_text())
                continue
            try:
                for task_id, rec in run_model(arm, model, tasks, lib, out, provider, args.seed, args.max_repairs).items():
                    records[(model, arm, task_id)] = rec
            except BudgetStop as error:
                stopped = str(error)
                break
        if stopped:
            print('STOPPED:', stopped, flush=True)
            break
    # Hidden grading only after every generation finished; several candidates are graded concurrently (each spec run
    # has its own static server and browser processes).
    from concurrent.futures import ThreadPoolExecutor

    def grade_one(key):
        model, arm, task_id = key
        task = next(t for t in tasks if t['id'] == task_id)
        folder = out / 'runs' / slug(model) / arm / task_id
        return key, grade_record(records[key], folder, task, args.evaluate_only)
    with ThreadPoolExecutor(max_workers=args.grade_workers) as pool:
        for key, h in pool.map(grade_one, list(records)):
            hidden[key] = h
            print(f"hidden {key[0]} {key[1]:4} {key[2]:8}: {h['first']['passed']} -> {h['final']['passed']} / {h['final']['total']}", flush=True)
    summary = summarize(args.models, args.arms, tasks, records, hidden, ledger.summary(), args.max_repairs)
    summary['stopped'] = stopped
    dump(out / 'summary.json', summary)
    (out / 'summary.md').write_text(markdown(summary))
    RESULTS.mkdir(exist_ok=True)
    suffix = f'-{args.label}' if args.label else ''
    shutil.copy(out / 'summary.json', RESULTS / f'summary{suffix}.json')
    shutil.copy(out / 'summary.md', RESULTS / f'summary{suffix}.md')
    print(json.dumps([{'model': m['model'], 'arms': m['arms'], 'paired': m.get('paired')} for m in summary['models']], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
