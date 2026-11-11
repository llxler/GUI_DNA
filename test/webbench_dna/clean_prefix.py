"""Web-Bench dom1: remove the protocol asymmetry between free-form code and plans.  (paid, small)

    uv run python -m test.webbench_dna.clean_prefix --check        # zero API: the clean prefixes pass their own tasks' specs
    uv run python -m test.webbench_dna.clean_prefix                # generate both controls, grade, summarise
    uv run python -m test.webbench_dna.clean_prefix --no-generate  # grade + summarise what is saved

In the main study free-form code follows the benchmark protocol: at task k it edits its own previous page and sees
only the description of task k, so one early mistake is inherited by every later task.  A plan is written afresh at
every task from the descriptions 1..k.  Two controls separate "what the model writes" from "what it starts from":

  free_clean   free-form code, same prompt as `free`, but the page handed to the model at task k is a correct page
               for tasks 1..k-1 (the reference plan for those tasks, compiled; the official initial page at task 1).
               Every task is independent; nothing can be inherited.
  dna_inc      a plan written incrementally like free-form code: at task k the model sees its own previous plan and
               the description of task k only, and returns the complete updated plan.

Baselines `free` and `dna` are the records of the main study (test/webbench_dna/results/summary.json), same seed.
Outputs: artifacts/webbench-dna-clean/ (own ledger), test/webbench_dna/results/clean-prefix.{json,md}.
"""
from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from gui_dna.budget import BudgetStop, Ledger
from gui_dna.tasks import dump
from test.provider_ext import ReasoningAwareOpenRouter as OpenRouter
from test import ledger_read

from . import domain, evaluate, run
from .library import library

OUT = domain.ROOT / 'artifacts' / 'webbench-dna-clean'
RESULTS = domain.HERE / 'results'
MODELS = ['qwen/qwen3-coder-30b-a3b-instruct', 'mistralai/mistral-small-3.2-24b-instruct', 'deepseek/deepseek-v4-flash',
          'openai/gpt-oss-120b', 'google/gemini-2.5-flash', 'openai/gpt-5-mini']
ARMS = ['free_clean', 'dna_inc']
SEED = 20261102


def clean_page(task, lib):
    """A correct page for the tasks before `task`: the official initial page, or the compiled reference plan of task k-1."""
    if task['k'] == 1:
        return run.INIT_HTML.read_text()
    features = domain.tasks()[task['k'] - 2]['features']
    script = domain.compile_plan(domain.reference_plan(features), features, lib)
    return evaluate.SHELL.read_text().replace('/*__CANDIDATE__*/', script.replace('</script', '<\\/script'))


def inc_messages(task, previous_plan, lib):
    """The plan prompt of the main study with the requirement narrowed to what free-form code sees: own previous output + task k."""
    system, user = [m['content'] for m in domain.messages_for(task, 'dna', lib)]
    full = 'Task descriptions so far (the requirement):\n' + '\n'.join(task['descriptions'])
    assert full in user
    current = json.dumps(previous_plan) if previous_plan is not None else '(none yet: this is the first task)'
    narrowed = ('Your current plan, written for the previous tasks:\n' + current + '\n\nNew task (the requirement to add):\n' + task['descriptions'][-1])
    user = user.replace(full, narrowed).replace('Return the plan as JSON only.', 'Return the complete updated plan as JSON only.')
    return [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]


def run_model(arm, model, tasks, lib, provider):
    previous = None
    for task in tasks:
        folder = OUT / 'runs' / run.slug(model) / arm / task['id']
        record_path = folder / 'record.json'
        if record_path.exists():
            rec = json.loads(record_path.read_text())
        else:
            rec = {'arm': arm, 'model': model, 'task': task['id'], 'features': task['features'], 'attempts': [], 'versions': []}
            if arm == 'free_clean':
                run.attempt_loop('free', model, task, lib, folder, provider, SEED, 2, domain.free_messages(task, clean_page(task, lib)), rec)
            else:
                run.attempt_loop('dna', model, task, lib, folder, provider, SEED, 2, inc_messages(task, previous, lib), rec)
            dump(record_path, rec)
            print(f"{model} {arm} {task['id']}: attempts={len(rec['attempts'])} versions={len(rec['versions'])}", flush=True)
        if arm == 'dna_inc' and rec['versions']:
            compiled = [a for a in rec['attempts'] if a.get('plan') is not None and not a.get('compile_error')]
            if compiled:
                previous = compiled[-1]['plan']


def summarise(ledger, tasks, models=MODELS):
    calls = ledger.summary()['calls']
    baseline = {m['model']: m for m in json.loads((RESULTS / 'summary.json').read_text())['models']}
    data = {'models': {}, 'paired': {}, 'accounting': {k: v for k, v in ledger.summary().items() if k != 'calls'}}
    for model in models:
        base = {r['task']: r for r in baseline[model]['rows']}
        values = {a: [bool(base[t['id']][a]['final_all']) for t in tasks] for a in ['free', 'dna']}
        info = {}
        for arm in ARMS:
            values[arm] = []
            transport = 0
            for task in tasks:
                folder = OUT / 'runs' / run.slug(model) / arm / task['id']
                if not (folder / 'hidden.json').exists():
                    values[arm].append(None)
                    continue
                rec = json.loads((folder / 'record.json').read_text())
                bad = any('ProviderError' in (a.get('compile_error') or '') for a in rec['attempts'])
                transport += bad
                hidden = json.loads((folder / 'hidden.json').read_text())['final']
                unavailable = bad or (rec['versions'] and (hidden.get('note') or not hidden['total']))
                values[arm].append(None if unavailable else bool(hidden['all_passed']))
            kind = 'free' if arm == 'free_clean' else 'dna'
            info[arm] = {'transport_failures': transport, 'cost_usd': sum((c['actual'] or 0) for c in calls
                          if c['purpose'].startswith(f'webbench:{model}:{kind}:')) / 1e6}
        data['models'][model] = {'passes': values, 'info': info,
            'totals': {k: {'passed': sum(x is True for x in v), 'n': sum(x is not None for x in v)} for k, v in values.items()},
            'sequential': {k: run.sequential_score(v) if all(x is not None for x in v) else None for k, v in values.items()}}
    for a, b in [('dna', 'free'), ('dna', 'free_clean'), ('dna_inc', 'free'), ('dna_inc', 'free_clean'), ('free_clean', 'free'), ('dna', 'dna_inc')]:
        pairs = [(x, y) for m in data['models'].values() for x, y in zip(m['passes'][a], m['passes'][b]) if x is not None and y is not None]
        data['paired'][f'{a}_vs_{b}'] = {'n': len(pairs), 'won': sum(x and not y for x, y in pairs), 'lost': sum(y and not x for x, y in pairs)}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / 'clean-prefix.json').write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    lines = ['# Web-Bench 协议对照', '',
        '自由代码每次从参考方案编译的前缀页面出发；增量方案只见上一方案和当前需求。缺失、传输失败和评测器错误不计为模型失败。',
        '干净前缀同时改变了代码来源与错误继承，因此差值不能单独解释成“继承错误的因果贡献”。参考前缀按上一任务的官方测试校准，未证明满足所有历史规格。', '',
        '| 模型 | 自由增量代码 | 干净前缀代码 | 增量方案 | 从头方案 |', '|---|---:|---:|---:|---:|']
    order = ['free', 'free_clean', 'dna_inc', 'dna']
    for model, row in data['models'].items():
        lines.append('| ' + model + ' | ' + ' | '.join(f"{row['totals'][k]['passed']}/{row['totals'][k]['n']}" for k in order) + ' |')
    lines += ['| **合计** | ' + ' | '.join(f"{sum(r['totals'][k]['passed'] for r in data['models'].values())}/{sum(r['totals'][k]['n'] for r in data['models'].values())}" for k in order) + ' |', '',
              '| 配对比较 | 有效配对 | 胜 | 负 |', '|---|---:|---:|---:|']
    for name, pair in data['paired'].items():
        lines.append(f"| {name} | {pair['n']} | {pair['won']} | {pair['lost']} |")
    lines += ['', f"已结算费用 ${data['accounting']['actual_usd']:.4f}；未结算调用 {data['accounting']['unsettled_calls']}。", '']
    (RESULTS / 'clean-prefix.md').write_text('\n'.join(lines))
    print('\n'.join(lines))


def check(tasks, lib):
    """Each clean prefix must pass the official spec of its own last task (so it is a correct starting point)."""
    for task in tasks[1:]:
        prev = tasks[task['k'] - 2]
        folder = OUT / 'check' / prev['id']
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'index.html').write_text(clean_page(task, lib))
        result = evaluate.grade(folder, prev, folder / 'report.json')
        assert result['all_passed'], (prev['id'], result['tests'])
    print(f'clean prefixes: {len(tasks) - 1} pages pass the official spec of their last task')
    print(inc_messages(tasks[4], domain.reference_plan(tasks[3]['features']), lib)[1]['content'][:1500])


def main():
    global OUT
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--no-generate', action='store_true')
    parser.add_argument('--generate-only', action='store_true')
    parser.add_argument('--out', type=Path, default=OUT)
    parser.add_argument('--models', nargs='+', default=MODELS)
    parser.add_argument('--arms', nargs='+', default=ARMS, choices=ARMS)
    parser.add_argument('--cap-usd', type=float, default=1.9)
    parser.add_argument('--stop-usd', type=float, default=1.8)
    parser.add_argument('--threads', type=int, default=6)
    parser.add_argument('--grade-workers', type=int, default=3)
    args = parser.parse_args()
    OUT = args.out.resolve()
    lib, tasks = library(), domain.tasks()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.check:
        check(tasks, lib)
        return
    ledger = ledger_read.ReadOnlyLedger(OUT / 'budget.sqlite3') if args.no_generate else Ledger(OUT / 'budget.sqlite3', args.cap_usd, args.stop_usd)
    config = {'models': MODELS, 'temperature': 0.6, 'max_tokens': 12000, 'max_repairs': 2, 'seed': SEED,
              'budget_usd': args.cap_usd, 'stop_new_requests_usd': args.stop_usd, 'price_caps_per_million': {'prompt': 3.0, 'completion': 15.0},
              'reasoning_effort': {'openai/gpt-5-mini': 'low', 'openai/gpt-oss-120b': 'low'},
              'omit_params': {'openai/gpt-5-mini': ['temperature', 'seed']},
              # caps follow the 2026-11-11 catalogue (one list price rose above the cap of the earlier stages)
              'model_price_caps': {'deepseek/deepseek-v4-flash': {'prompt': 0.2, 'completion': 0.4},
                                   'qwen/qwen3-coder-30b-a3b-instruct': {'prompt': 0.2, 'completion': 0.8},
                                   'mistralai/mistral-small-3.2-24b-instruct': {'prompt': 0.1, 'completion': 0.3},
                                   'openai/gpt-5-mini': {'prompt': 0.3, 'completion': 2.1}, 'openai/gpt-oss-120b': {'prompt': 0.2, 'completion': 0.7},
                                   'google/gemini-2.5-flash': {'prompt': 0.35, 'completion': 2.6}}}
    if not args.no_generate:
        from test.review_stage import freeze
        freeze(OUT, config, ['test/webbench_dna/clean_prefix.py', 'test/webbench_dna/run.py', 'test/webbench_dna/domain.py', 'test/webbench_dna/library.py'],
               {'arms': ARMS, 'tasks': tasks, 'library_sha256': lib['sha256']})
        provider = OpenRouter(config, ledger)

        def job(pair):
            model, arm = pair
            try:
                run_model(arm, model, tasks, lib, provider)
            except BudgetStop as error:
                return pair, f'STOPPED: {error}'
            return pair, 'done'
        with ThreadPoolExecutor(max_workers=args.threads) as pool:
            for pair, status in pool.map(job, [(m, a) for a in args.arms for m in args.models]):
                print(*pair, status, flush=True)
    todo = [(m, a, t) for m in args.models for a in args.arms for t in tasks if (OUT / 'runs' / run.slug(m) / a / t['id'] / 'record.json').exists()]

    def grade(item):
        model, arm, task = item
        folder = OUT / 'runs' / run.slug(model) / arm / task['id']
        return run.grade_record(json.loads((folder / 'record.json').read_text()), folder, task, False)
    if not args.generate_only:
        with ThreadPoolExecutor(max_workers=args.grade_workers) as pool:
            for i, _ in enumerate(pool.map(grade, todo), 1):
                if i % 20 == 0:
                    print(f'graded {i}/{len(todo)}', flush=True)
    summarise(ledger, tasks, args.models)


if __name__ == '__main__':
    main()
