"""TodoMVC stage: free code vs rule wiring vs GUI-DNA plan, graded by the official Playwright TodoMVC spec.

    uv run python -m test.todomvc_dna.run --arms rule                       # zero-API control + hidden grading
    export OPENROUTER_API_KEY=...
    uv run python -m test.todomvc_dna.run --models deepseek/deepseek-v4-pro-0813 qwen/qwen3-coder-30b-a3b-instruct \
        --arms free rule dna --samples 1
    uv run python -m test.todomvc_dna.run --evaluate-only                   # re-grade saved versions, no API
Protocol (same for every arm): generate -> public smoke check (page errors + one add) -> up to --max-repairs repairs with
that feedback only -> hidden official spec on the first and the final version, graded on the task's enabled subset.
"""
from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

from gui_dna.budget import BudgetStop, Ledger
from gui_dna.provider import ProviderError, parse_json
from test.provider_ext import ReasoningAwareOpenRouter as OpenRouter
from gui_dna.tasks import dump

from . import domain, evaluate
from .library import library

HERE = domain.HERE
DEFAULT_OUT = domain.ROOT / 'artifacts/todomvc-dna'
RESULTS = HERE / 'results'


def slug(model):
    return model.replace('/', '__')


def generate(arm, model, task, lib, folder, provider, seed, max_repairs, server):
    record_path = folder / 'record.json'
    if record_path.exists():
        return json.loads(record_path.read_text())
    record = {'arm': arm, 'model': model, 'task': task['id'], 'features': task['features'], 'attempts': [], 'versions': []}
    if arm == 'rule':
        plan = domain.rule_plan(task['features'])
        code = domain.compile_plan(plan, task['features'], lib)
        page = evaluate.write_app(code, folder / 'v1')
        record['attempts'].append({'attempt': 1, 'plan': plan, 'compile_error': None, 'public': evaluate.public_check(server.url(page))})
        record['versions'].append('v1')
        dump(record_path, record)
        return record
    messages = domain.messages_for(task, 'free_lib' if arm == 'free_lib' else ('free' if arm == 'free' else 'dna'), lib)
    for attempt_no in range(1, max_repairs + 2):
        attempt = {'attempt': attempt_no, 'compile_error': None, 'public': None}
        try:
            raw = provider.call(model, messages, folder / f'call-{attempt_no}', f'todomvc:{model}:{arm}:{task["id"]}:a{attempt_no}', seed=seed)
        except BudgetStop:
            dump(record_path, record)
            raise
        except ProviderError as error:
            attempt['compile_error'] = f'ProviderError: {error}'
            record['attempts'].append(attempt)
            break
        code = None
        try:
            parsed = parse_json(raw)
            if arm in ('free', 'free_lib'):
                code = parsed['code']
                if not isinstance(code, str) or not code.strip():
                    raise ValueError('code must be a non-empty string')
            else:
                attempt['plan'] = parsed
                code = domain.compile_plan(parsed, task['features'], lib, checked=(arm == 'dna'))
        except (ValueError, KeyError, TypeError) as error:
            attempt['compile_error'] = f'{type(error).__name__}: {error}'
        if code is not None:
            version = f'v{attempt_no}'
            page = evaluate.write_app(code, folder / version)
            attempt['public'] = evaluate.public_check(server.url(page))
            record['versions'].append(version)
        record['attempts'].append(attempt)
        if code is not None and not attempt['public']:
            break
        if attempt_no > max_repairs:
            break
        is_plan = arm in ('dna', 'dna_unchecked')
        if attempt['compile_error']:
            feedback = ('The plan was rejected by the compiler:\n' if is_plan else 'Your output could not be used:\n') + attempt['compile_error']
        else:
            feedback = 'Public smoke check failed:\n- ' + '\n- '.join(attempt['public'])
        feedback += '\nReturn a corrected ' + ('plan' if is_plan else 'complete JavaScript source') + ' as JSON only.'
        messages = messages + [{'role': 'assistant', 'content': raw}, {'role': 'user', 'content': feedback}]
    dump(record_path, record)
    return record


def recompile(record, folder, task, lib, server):
    """Re-run saved dna responses through the current compiler without any API call (same stop rule as the live loop:
    stop at the first attempt that compiles and passes the public check).  The live record is kept as record.live.json."""
    if record['arm'] != 'dna' or (folder / 'record.live.json').exists():
        return record   # already replayed once; keep the first replay as the record of this compiler version
    shutil.copy(folder / 'record.json', folder / 'record.live.json')
    if (folder / 'hidden.json').exists():
        shutil.move(folder / 'hidden.json', folder / 'hidden.live.json')
    new = {**record, 'attempts': [], 'versions': [], 'recompiled': True, 'fresh': True}
    for old in record['attempts']:
        n = old['attempt']
        call = folder / f'call-{n}'
        candidates = [call / 'response.json'] + sorted(call.glob('http-retry-*/response.json'))
        saved = next((c for c in candidates if c.exists()), None)
        if saved is None:
            new['attempts'].append({**old, 'public': old.get('public')})
            continue
        raw = json.loads(saved.read_text())['choices'][0]['message']['content'] or ''
        attempt = {'attempt': n, 'compile_error': None, 'public': None}
        try:
            plan = parse_json(raw)
            attempt['plan'] = plan
            code = domain.compile_plan(plan, task['features'], lib)
        except (ValueError, KeyError, TypeError) as error:
            attempt['compile_error'] = f'{type(error).__name__}: {error}'
            new['attempts'].append(attempt)
            continue
        version = f'r{n}'
        page = evaluate.write_app(code, folder / version)
        attempt['public'] = evaluate.public_check(server.url(page))
        new['versions'].append(version)
        new['attempts'].append(attempt)
        if not attempt['public']:
            break
    dump(folder / 'record.json', new)
    return new


def grade_record(record, folder, task, server, evaluate_only):
    """Hidden grade of the first and the final version (reused when already present and not re-grading)."""
    hidden_path = folder / 'hidden.json'
    if hidden_path.exists() and not evaluate_only:
        return json.loads(hidden_path.read_text())
    out = {}
    versions = record['versions']
    if versions:
        for label, version in [('first', versions[0]), ('final', versions[-1])]:
            if label == 'final' and version == versions[0]:
                out['final'] = out['first']
                continue
            out[label] = evaluate.grade(server.url(folder / version / 'index.html'), folder / version / 'report.json', task['features'])
    else:
        empty = {'passed': 0, 'total': len(domain.hidden_subset(task['features'])), 'all_passed': False, 'tests': {}, 'note': 'no usable version'}
        out = {'first': empty, 'final': empty}
    dump(hidden_path, out)
    return out


def summarize(models, arms, tasks, samples, records, hidden, ledger_summary, max_repairs, extra_calls=()):
    calls = list(ledger_summary.get('calls', [])) + list(extra_calls)
    def cost(prefix):
        return sum((c['actual'] or 0) for c in calls if c['purpose'].startswith(prefix)) / 1e6
    label = {'free': '自由代码（基线）', 'rule': '规则组装（零 API 控制）', 'dna': 'GUI-DNA 组装方案 + 编译检查',
             'free_lib': '自由代码 + 同一函数库（对照）', 'dna_unchecked': '组装方案，不做覆盖检查（消融）'}
    summary = {'date_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'max_repairs': max_repairs, 'samples': samples, 'arms': arms,
               'tasks': [{k: t[k] for k in ['id', 'features']} | {'hidden_tests': len(domain.hidden_subset(t['features']))} for t in tasks],
               'accounting': {k: v for k, v in ledger_summary.items() if k != 'calls'}, 'models': []}
    for model in models:
        entry = {'model': model, 'arms': {}, 'rows': []}
        for task in tasks:
            for s in range(samples):
                row = {'task': task['id'], 'features': task['features'], 'sample': s}
                for arm in arms:
                    key = (model, arm, task['id'], s)
                    rec, h = records.get(key), hidden.get(key)
                    if not rec or not h:
                        row[arm] = None
                        continue
                    last = rec['attempts'][-1] if rec['attempts'] else {}
                    row[arm] = {'first_passed': h['first']['passed'], 'final_passed': h['final']['passed'], 'total': h['final']['total'],
                                'first_all': h['first']['all_passed'], 'final_all': h['final']['all_passed'],
                                'calls': len(rec['attempts']) if arm != 'rule' else 0,
                                'compile_errors': sum(1 for a in rec['attempts'] if a.get('compile_error')),
                                'public_failures': sum(1 for a in rec['attempts'] if a.get('public')),
                                'plan': last.get('plan'), 'compile_error': last.get('compile_error'),
                                'failed_tests': sorted(k for k, v in h['final']['tests'].items() if v != 'passed')}
                entry['rows'].append(row)
        for arm in arms:
            rows = [r[arm] for r in entry['rows'] if r[arm]]
            entry['arms'][arm] = {'n': len(rows), 'first_all': sum(r['first_all'] for r in rows), 'final_all': sum(r['final_all'] for r in rows),
                                  'first_tests': sum(r['first_passed'] for r in rows), 'final_tests': sum(r['final_passed'] for r in rows),
                                  'tests': sum(r['total'] for r in rows), 'calls': sum(r['calls'] for r in rows),
                                  'compile_errors': sum(r['compile_errors'] for r in rows), 'cost_usd': cost(f'todomvc:{model}:{arm}:')}
        if 'free' in arms and 'dna' in arms:
            pairs = [(r['free'], r['dna']) for r in entry['rows'] if r['free'] and r['dna']]
            entry['paired'] = {'dna_only': sum(d['final_all'] and not f['final_all'] for f, d in pairs),
                               'free_only': sum(f['final_all'] and not d['final_all'] for f, d in pairs),
                               'both': sum(f['final_all'] and d['final_all'] for f, d in pairs),
                               'neither': sum(not f['final_all'] and not d['final_all'] for f, d in pairs),
                               'test_delta': sum(d['final_passed'] - f['final_passed'] for f, d in pairs)}
        summary['models'].append(entry)
    summary['labels'] = label
    return summary


def markdown(summary):
    arms, label = summary['arms'], summary['labels']
    n_tasks = len(summary['tasks'])
    lines = ['# TodoMVC（官方 Playwright 测试集）：自由代码 vs 冻结原子函数组装（GUI-DNA）', '',
             f"生成时间 {summary['date_utc']}。{n_tasks} 个功能族任务 × {summary['samples']} 个样本；隐藏评测 = 官方 Playwright TodoMVC 示例测试集（24 项）中该任务启用功能覆盖的子集；"
             f"三种做法同种子、同公开反馈（页面错误 + 一次添加的冒烟检查），最多 {summary['max_repairs']} 轮修复；隐藏测试从不进入提示词。", '',
             '| 模型 | 方法 | 任务全过（首次） | 任务全过（最终） | 隐藏测试通过（首次） | 隐藏测试通过（最终） | 调用 | 编译/解析拒绝 | 费用 |', '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for m in summary['models']:
        for arm in arms:
            a = m['arms'][arm]
            lines.append(f"| {m['model']} | {label[arm]} | {a['first_all']}/{a['n']} | **{a['final_all']}/{a['n']}** | {a['first_tests']}/{a['tests']} | "
                         f"**{a['final_tests']}/{a['tests']}** | {a['calls']} | {a['compile_errors']} | ${a['cost_usd']:.4f} |")
        if m.get('paired'):
            p = m['paired']
            lines.append(f"| {m['model']} | 配对（最终，DNA vs 自由） | 仅 DNA 全过 {p['dna_only']} | 仅自由全过 {p['free_only']} | 都过 {p['both']} | 都败 {p['neither']} | 测试数差 {p['test_delta']:+d} | | |")
    lines.append('')
    for m in summary['models']:
        lines += [f"## {m['model']}：逐任务（隐藏测试通过 首次 → 最终 / 总数）", '', '| 任务 | 启用功能 | ' + ' | '.join(label[a] for a in arms) + ' | 最终仍失败的测试（DNA） |',
                  '|---|---|' + '---:|' * len(arms) + '---|']
        for r in m['rows']:
            cells = []
            for arm in arms:
                o = r[arm]
                if not o:
                    cells.append('—')
                else:
                    cells.append(f"{o['first_passed']} → **{o['final_passed']}** / {o['total']}" + (' ⟂' if o['compile_error'] else ''))
            failed = '; '.join(t.split(' › ')[1] for t in (r.get('dna') or {}).get('failed_tests', [])[:4]) if r.get('dna') else ''
            lines.append(f"| {r['task']}{'' if summary['samples'] == 1 else ' s' + str(r['sample'])} | {', '.join(r['features'])} | " + ' | '.join(cells) + f" | {failed} |")
        lines.append('')
    a = summary['accounting']
    lines += [f"账本（独立）：已结算 ${a['actual_usd']:.6f}，敞口 ${a['exposure_usd']:.6f}，未结算 {a['unsettled_calls']}。", '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--models', nargs='+', default=['deepseek/deepseek-v4-pro-0813', 'qwen/qwen3-coder-30b-a3b-instruct'])
    parser.add_argument('--arms', nargs='+', default=['free', 'rule', 'dna'], choices=domain.METHODS)
    parser.add_argument('--samples', type=int, default=1)
    parser.add_argument('--max-repairs', type=int, default=2)
    parser.add_argument('--seed', type=int, default=20261102)
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT)
    parser.add_argument('--cap-usd', type=float, default=1.0)
    parser.add_argument('--stop-usd', type=float, default=0.8)
    parser.add_argument('--evaluate-only', action='store_true', help='re-grade saved versions; no API calls')
    parser.add_argument('--label', default='')
    parser.add_argument('--extra-ledgers', nargs='*', default=[], help='older ledgers whose settled calls count in the cost columns')
    parser.add_argument('--recompile', action='store_true', help='re-link saved dna responses with the current compiler (no API), then grade')
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    lib = library()
    tasks = domain.tasks()
    config = {'models': args.models, 'temperature': 0.6, 'max_tokens': 4000, 'max_repairs': args.max_repairs, 'seed': args.seed,
              'budget_usd': args.cap_usd, 'stop_new_requests_usd': args.stop_usd,
              'price_caps_per_million': {'prompt': 3.0, 'completion': 15.0},
              'reasoning_effort': {'openai/gpt-5-mini': 'low', 'openai/gpt-oss-120b': 'low'},
              'omit_params': {'openai/gpt-5-mini': ['temperature', 'seed']},
              'model_price_caps': {'deepseek/deepseek-v4-pro-0813': {'prompt': 1.3, 'completion': 4.1},
                                   'qwen/qwen3-coder': {'prompt': 0.65, 'completion': 3.25},
                                   'qwen/qwen3-coder-30b-a3b-instruct': {'prompt': 0.1, 'completion': 0.4},
                                   'google/gemma-3-12b-it': {'prompt': 0.1, 'completion': 0.3},
                                   'mistralai/mistral-small-3.2-24b-instruct': {'prompt': 0.1, 'completion': 0.3},
                                   'openai/gpt-5-mini': {'prompt': 0.3, 'completion': 2.1}, 'openai/gpt-oss-120b': {'prompt': 0.2, 'completion': 0.7},
                                   'google/gemini-2.5-flash': {'prompt': 0.35, 'completion': 2.6}, 'anthropic/claude-haiku-4.5': {'prompt': 1.1, 'completion': 5.1}}}
    ledger = Ledger(out / 'budget.sqlite3', args.cap_usd, args.stop_usd)
    paid = (not args.evaluate_only) and (not args.recompile) and any(a in args.arms for a in ['free', 'dna'])
    provider = OpenRouter(config, ledger) if paid else None
    dump(out / 'manifest.json', {'config': config, 'arms': args.arms, 'samples': args.samples, 'tasks': tasks, 'library_sha256': lib['sha256'],
                                 'domain_sha256': evaluate.sha256((HERE / 'domain.py').read_text()),
                                 'shell_sha256': evaluate.sha256(evaluate.SHELL.read_text()),
                                 'official_spec_sha256': evaluate.sha256((evaluate.HARNESS / 'demo-todo-app.original.spec.ts').read_text()),
                                 'harness_spec_sha256': evaluate.sha256((evaluate.HARNESS / 'demo-todo-app.spec.ts').read_text()),
                                 'spec_source': 'create-playwright 1.17.129 assets/demo-todo-app.spec.ts; the harness copy changes only the goto URL'})
    server = evaluate.Server(out)
    records, hidden, stopped = {}, {}, None
    try:
        for model in args.models:
            for task in tasks:
                for s in range(args.samples):
                    for arm in args.arms:
                        folder = out / 'runs' / slug(model) / arm / task['id'] / f's{s}'
                        if args.evaluate_only or args.recompile:
                            if not (folder / 'record.json').exists():
                                continue
                            rec = json.loads((folder / 'record.json').read_text())
                            if args.recompile:
                                rec = recompile(rec, folder, task, lib, server)
                        else:
                            try:
                                rec = generate(arm, model, task, lib, folder, provider, args.seed + s, args.max_repairs, server)
                            except BudgetStop as error:
                                stopped = str(error)
                                break
                        records[(model, arm, task['id'], s)] = rec
                        print(f"{model} {arm:4} {task['id']} s{s}: attempts={len(rec['attempts'])} versions={len(rec['versions'])}", flush=True)
                    if stopped:
                        break
                if stopped:
                    break
            if stopped:
                print('STOPPED:', stopped, flush=True)
                break
        # Hidden grading only after every generation finished (same discipline as round 3).
        for (model, arm, task_id, s), rec in records.items():
            task = next(t for t in tasks if t['id'] == task_id)
            folder = out / 'runs' / slug(model) / arm / task_id / f's{s}'
            hidden[(model, arm, task_id, s)] = h = grade_record(rec, folder, task, server, args.evaluate_only or rec.pop('fresh', False))
            print(f"hidden {model} {arm:4} {task_id} s{s}: {h['first']['passed']} -> {h['final']['passed']} / {h['final']['total']}", flush=True)
    finally:
        server.close()
    extra = [c for path in args.extra_ledgers for c in Ledger(path, 0.000001, 0.000001).summary()['calls']]
    summary = summarize(args.models, args.arms, tasks, args.samples, records, hidden, ledger.summary(), args.max_repairs, extra)
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
