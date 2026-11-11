"""Do plans pick the right variant because of the atoms' names and descriptions?  (paid, small; plans only)

    uv run python -m test.name_sensitivity --check                 # zero API: prompt/compiler equivalence, print one prompt
    uv run python -m test.name_sensitivity                         # all conditions, both suites, four cheap models
    uv run python -m test.name_sensitivity --no-generate           # grade + summarise what is saved

The plan prompt of the main study shows every atom with a descriptive name and a one-line description.  Four
conditions change only that presentation; requirement, shell protocol, schema, compiler and tests are untouched:

  neutral          atom names replaced by opaque aliases (f01, f02, ...); descriptions kept
  nodesc           names kept; descriptions removed
  neutral_nodesc   opaque aliases and no descriptions (TodoMVC still shows the function bodies, as in the main study;
                   the Web-Bench plan prompt never shows bodies, so there body/name evidence is removed, but ordering and schema cues remain)
  shuffle          names and descriptions kept; order of the atoms and of every allowed-list shuffled per task

The baseline (`original`) is the GUI-DNA record of the main study for the same model, task and sample.
Outputs: artifacts/name-sensitivity/ (own ledger), test/results/name-sensitivity.{json,md}.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from gui_dna.budget import BudgetStop, Ledger
from gui_dna.provider import ProviderError, parse_json
from gui_dna.tasks import dump
from test import ledger_read
from test.review_stage import provider_for
from test.provider_ext import ReasoningAwareOpenRouter as OpenRouter
from test.todomvc_dna import domain as td, evaluate as te, generic as tg
from test.todomvc_dna.library import library as todomvc_library
from test.webbench_dna import domain as wd, evaluate as we
from test.webbench_dna.library import COMMANDS, SHORTCUT_KEYS, SLOT_FEATURE, SLOTS, TOOLS, library as webbench_library

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts' / 'name-sensitivity'
RESULTS = ROOT / 'test' / 'results'
CONDITIONS = ['neutral', 'nodesc', 'neutral_nodesc', 'shuffle']
MODELS = {'todomvc': ['qwen/qwen3-coder-30b-a3b-instruct', 'mistralai/mistral-small-3.2-24b-instruct', 'openai/gpt-oss-120b', 'deepseek/deepseek-v4-pro-0813'],
          'webbench': ['qwen/qwen3-coder-30b-a3b-instruct', 'mistralai/mistral-small-3.2-24b-instruct', 'openai/gpt-oss-120b', 'deepseek/deepseek-v4-flash']}
BASELINE = {'todomvc': ROOT / 'test/todomvc_dna/results/summary.json', 'webbench': ROOT / 'test/webbench_dna/results/summary.json'}
SAMPLES = 2          # TodoMVC samples per family, as in the main study
SEED = 20261102      # seed of the main study (sample s uses SEED + s on TodoMVC)


def slug(model):
    return model.replace('/', '__')


def aliases(lib, on):
    """name -> alias in listing order (identity when off)."""
    return {f['name']: (f'f{i + 1:02}' if on else f['name']) for i, f in enumerate(lib['functions'])}


# ---------------------------------------------------------------- TodoMVC
def todomvc_view(task, sample, condition):
    """The library and tables as the model sees them, plus alias -> original name."""
    lib, tables = todomvc_library(), tg.human_tables()
    alias = aliases(lib, 'neutral' in condition)
    functions = []
    for f in lib['functions']:
        a = alias[f['name']]
        functions.append({**f, 'name': a, 'signature': a + f['signature'][len(f['name']):],
                          'code': f['code'].replace(f"function {f['name']}(", f'function {a}(', 1)})
    shown = {'routes': {e: [alias[n] for n in v] for e, v in tables['routes'].items()}, 'inits': [alias[n] for n in tables['inits']],
             'afters': {alias[n]: f for n, f in tables['afters'].items()}, 'views': {s: [alias[n] for n in v] for s, v in tables['views'].items()}}
    if condition == 'shuffle':
        rng = random.Random(f"{task['id']}:{sample}")
        rng.shuffle(functions)
        for group in (*shown['routes'].values(), *shown['views'].values(), shown['inits']):
            rng.shuffle(group)
        hooks = list(shown['afters'].items())
        rng.shuffle(hooks)
        shown['afters'] = dict(hooks)
    return {'functions': functions}, shown, {a: n for n, a in alias.items()}


def todomvc_messages(task, sample, condition):
    lib, shown, _ = todomvc_view(task, sample, condition)
    return tg.plan_messages(task, lib, shown, descriptions='nodesc' not in condition)


def todomvc_compile(plan, task, sample, condition):
    lib, shown, _ = todomvc_view(task, sample, condition)
    return tg.compile_plan(plan, task['features'], lib, shown)


def todomvc_choices(plan, task, sample, condition):
    """(correct, total) variant choices of a plan against the spec-correct reference, in original names."""
    _, _, back = todomvc_view(task, sample, condition)
    ref = td.reference_plan(task['features'])
    plan = td._unwrap_names(plan) if isinstance(plan, dict) else {}
    pairs = [(plan.get('init'), ref['init'])]
    handlers, view = plan.get('handlers') or {}, plan.get('view') or {}
    pairs += [(handlers.get(e) if isinstance(handlers, dict) else None, n) for e, n in ref['handlers'].items() if len(tg.human_tables()['routes'][e]) > 1]
    pairs += [(view.get(s) if isinstance(view, dict) else None, n) for s, n in ref['view'].items() if len(tg.human_tables()['views'][s]) > 1]
    return sum(isinstance(got, str) and back.get(got, got) == want for got, want in pairs), len(pairs)


# ---------------------------------------------------------------- Web-Bench
def webbench_view(task, condition):
    lib = webbench_library()
    alias = aliases(lib, 'neutral' in condition)
    functions = [{**f, 'name': alias[f['name']], 'signature': alias[f['name']] + f['signature'][len(f['name']):]} for f in lib['functions']]
    slots = {s: [alias[n] for n in options] for s, options in SLOTS.items()}
    if condition == 'shuffle':
        rng = random.Random(task['id'])
        rng.shuffle(functions)
        for options in slots.values():
            rng.shuffle(options)
    return functions, slots, {a: n for n, a in alias.items()}


def webbench_listing(functions, descriptions):
    lines = []
    for kind, title in [('helper', 'helpers (always linked)'), ('infra', 'infrastructure atoms'), ('event', 'behaviour atoms (several are variants of one slot)'), ('view', 'label atoms')]:
        lines.append(f'### {title}')
        for f in functions:
            if f['kind'] == kind:
                lines.append(f"- `{f['signature']}` [feature: {f['feature']}]" + (f" — {f['description']}" if descriptions else ''))
    return '\n'.join(lines)


def webbench_messages(task, condition):
    functions, slots, _ = webbench_view(task, condition)
    system = wd.messages_for(task, 'dna', webbench_library())[0]['content']
    requirement = '\n'.join(task['descriptions'])
    schema = ('Allowed values — tools: ' + json.dumps(list(TOOLS)) + '; slots: ' + json.dumps(slots) +
              '; menu commands: ' + json.dumps(list(COMMANDS)) + ' (menu keys: file, dir, entries); shortcut keys: ' + json.dumps(SHORTCUT_KEYS) +
              ' (value = command). Items for features that are not enabled are ignored.')
    user = (f"Enabled features for this task (cumulative): {task['features']}.\n\nTask descriptions so far (the requirement):\n{requirement}\n\n"
            f"{wd.INTERFACE}\n\nFrozen library:\n{webbench_listing(functions, 'nodesc' not in condition)}\n\n{schema}\nReturn the plan as JSON only.")
    return [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]


def webbench_compile(plan, task, condition):
    """Map aliases back to the frozen names, compile with the unchanged compiler, report errors in alias space."""
    _, _, back = webbench_view(task, condition)
    forward = {n: a for a, n in back.items()}
    mapped = plan
    if isinstance(plan, dict):
        mapped = {k: (back.get(v, v) if k in SLOTS and isinstance(v, str) else v) for k, v in plan.items()}
    try:
        return wd.compile_plan(mapped, task['features'], webbench_library())
    except ValueError as error:
        text = re.sub(r"(['\"])(\w+)\1", lambda m: m.group(1) + forward.get(m.group(2), m.group(2)) + m.group(1), str(error))
        raise ValueError(text) from None


def webbench_choices(plan, task, condition):
    _, _, back = webbench_view(task, condition)
    ref = wd.reference_plan(task['features'])
    slots = [s for s in SLOTS if SLOT_FEATURE[s] in task['features']]
    plan = plan if isinstance(plan, dict) else {}
    return sum(isinstance(plan.get(s), str) and back.get(plan[s], plan[s]) == ref[s] for s in slots), len(slots)


# ---------------------------------------------------------------- generation
def units(suite):
    if suite == 'todomvc':
        return [(task, s) for task in td.tasks() for s in range(SAMPLES)]
    return [(task, 0) for task in wd.tasks()]


def folder_of(suite, condition, model, task, sample):
    return OUT / 'runs' / suite / condition / slug(model) / task['id'] / f's{sample}'


def generate(suite, condition, model, task, sample, provider, server, max_repairs=2):
    folder = folder_of(suite, condition, model, task, sample)
    record_path = folder / 'record.json'
    if record_path.exists():
        return json.loads(record_path.read_text())
    record = {'suite': suite, 'condition': condition, 'model': model, 'task': task['id'], 'sample': sample, 'attempts': [], 'versions': []}
    messages = todomvc_messages(task, sample, condition) if suite == 'todomvc' else webbench_messages(task, condition)
    for n in range(1, max_repairs + 2):
        attempt = {'attempt': n, 'compile_error': None, 'public': None}
        try:
            raw = provider.call(model, messages, folder / f'call-{n}', f'sens:{suite}:{condition}:{model}:{task["id"]}:s{sample}:a{n}',
                                seed=SEED + sample, max_tokens=4000 if suite == 'todomvc' else 3000)
        except ProviderError as error:
            attempt['compile_error'] = f'ProviderError: {error}'
            record['attempts'].append(attempt)
            break
        code = None
        try:
            plan = parse_json(raw)
            attempt['plan'] = plan
            code = todomvc_compile(plan, task, sample, condition) if suite == 'todomvc' else webbench_compile(plan, task, condition)
        except (ValueError, KeyError, TypeError) as error:
            attempt['compile_error'] = f'{type(error).__name__}: {error}'
        if code is not None:
            version = f'v{n}'
            if suite == 'todomvc':
                attempt['public'] = te.public_check(server.url(te.write_app(code, folder / version)))
            else:
                attempt['public'] = we.public_check(we.write_candidate(folder / version, script=code))
            record['versions'].append(version)
        record['attempts'].append(attempt)
        if (code is not None and not attempt['public']) or n > max_repairs:
            break
        feedback = ('The plan was rejected by the compiler:\n' + attempt['compile_error']) if attempt['compile_error'] else \
            ('Public smoke check failed:\n- ' + '\n- '.join(attempt['public']))
        messages = messages + [{'role': 'assistant', 'content': raw}, {'role': 'user', 'content': feedback + '\nReturn a corrected plan as JSON only.'}]
    dump(record_path, record)
    return record


def grade(suite, condition, model, task, sample, server):
    folder = folder_of(suite, condition, model, task, sample)
    hidden = folder / 'hidden.json'
    if hidden.exists():
        saved = json.loads(hidden.read_text())
        if saved.get('total', 0) > 0 or saved.get('note') == 'no usable version':
            return saved
    record = json.loads((folder / 'record.json').read_text())
    if not record['versions']:
        total = len(td.hidden_subset(task['features'])) if suite == 'todomvc' else 0
        out = {'passed': 0, 'total': total, 'all_passed': False, 'tests': {}, 'note': 'no usable version'}
    elif suite == 'todomvc':
        version = folder / record['versions'][-1]
        out = te.grade(server.url(version / 'index.html'), version / 'report.json', task['features'])
    else:
        version = folder / record['versions'][-1]
        out = we.grade(version, task, version / 'report.json')
    dump(hidden, out)
    return out


# ---------------------------------------------------------------- summary
def baseline_rows(suite, model):
    summary = json.loads(BASELINE[suite].read_text())
    entry = next(m for m in summary['models'] if m['model'] == model)
    rows = {}
    for r in entry['rows']:
        if r.get('dna'):
            rows[(r['task'], r.get('sample', 0))] = r['dna']
    return rows


def summarise(ledger, extra_ledgers=()):
    calls = list(ledger.summary()['calls']) + [c for path in extra_ledgers for c in ledger_read.calls(path)]
    data = {'date_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'suites': {}}
    for suite in MODELS:
        table = {}
        for model in MODELS[suite]:
            base = baseline_rows(suite, model)
            row = {}
            passed = correct = total = n = 0
            for task, s in units(suite):
                b = base.get((task['id'], s))
                if not b:
                    continue
                n += 1
                passed += bool(b['final_all'])
                c, t = (todomvc_choices(b['plan'], task, s, 'original') if suite == 'todomvc' else webbench_choices(b['plan'], task, 'original'))
                correct, total = correct + c, total + t
            row['original'] = {'n': n, 'passed': passed, 'choices_correct': correct, 'choices': total}
            for condition in CONDITIONS:
                passed = correct = total = n = rejected = transport = 0
                for task, s in units(suite):
                    folder = folder_of(suite, condition, model, task, s)
                    if not (folder / 'record.json').exists() or not (folder / 'hidden.json').exists():
                        continue
                    record, hidden = json.loads((folder / 'record.json').read_text()), json.loads((folder / 'hidden.json').read_text())
                    if any('ProviderError' in (a.get('compile_error') or '') for a in record['attempts']):
                        transport += 1
                        continue
                    n += 1
                    passed += bool(hidden['all_passed'])
                    rejected += sum(1 for a in record['attempts'] if a.get('compile_error'))
                    plans = [a['plan'] for a in record['attempts'] if 'plan' in a and not a.get('compile_error')]
                    c, t = (todomvc_choices(plans[-1] if plans else None, task, s, condition) if suite == 'todomvc'
                            else webbench_choices(plans[-1] if plans else None, task, condition))
                    correct, total = correct + c, total + t
                prefix = f'sens:{suite}:{condition}:{model}:'
                row[condition] = {'n': n, 'passed': passed, 'choices_correct': correct, 'choices': total, 'rejections': rejected,
                                  'transport_failures': transport,
                                  'cost_usd': round(sum((c['actual'] or 0) for c in calls if c['purpose'].startswith(prefix)) / 1e6, 4)}
            table[model] = row
        data['suites'][suite] = table
    data['accounting'] = {'actual_usd': sum((c['actual'] or 0) for c in calls) / 1e6, 'unsettled_calls': sum(c['actual'] is None for c in calls),
                          'ledgers': [str(Path(p).resolve().relative_to(ROOT)) for p in [OUT / 'budget.sqlite3', *extra_ledgers]]}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / 'name-sensitivity.json').write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    names = {'original': '原提示词（主实验）', 'neutral': '中性名字', 'nodesc': '去掉描述', 'neutral_nodesc': '中性名字 + 去掉描述', 'shuffle': '打乱顺序'}
    lines = ['# 方案对原子名字 / 描述 / 顺序的敏感性（`uv run python -m test.name_sensitivity`）', '',
             '每格：任务全过数 / 已评分任务数（与参考方案相同的变体数 / 槽位数）；并非行为正确率。原提示词取主实验。TodoMVC 每格预期 16，Web-Bench 20；缺失与传输失败排除，分母不齐时不作完整配对结论。', '']
    for suite, title in [('todomvc', 'TodoMVC（8 族 × 2 采样；提示词里始终带函数体）'), ('webbench', 'Web-Bench dom1（20 个任务；方案提示词不带函数体）')]:
        lines += [f'## {title}', '', '| 模型 | ' + ' | '.join(names[c] for c in ['original'] + CONDITIONS) + ' |', '|---|' + '---:|' * (len(CONDITIONS) + 1)]
        totals = {c: [0, 0, 0, 0] for c in ['original'] + CONDITIONS}
        for model, row in data['suites'][suite].items():
            cells = []
            for c in ['original'] + CONDITIONS:
                r = row[c]
                cells.append(f"{r['passed']}/{r['n']}（{r['choices_correct']}/{r['choices']}）")
                for i, k in enumerate(['passed', 'n', 'choices_correct', 'choices']):
                    totals[c][i] += r[k]
            lines.append(f"| {model.split('/')[-1]} | " + ' | '.join(cells) + ' |')
        lines.append('| **合计** | ' + ' | '.join(f'**{t[0]}/{t[1]}**（{t[2]}/{t[3]}）' for t in totals.values()) + ' |')
        lines.append('')
    a = data['accounting']
    lines += [f"账本（独立）：{'、'.join('`' + x + '`' for x in a['ledgers'])}；已结算合计 ${a['actual_usd']:.4f}，未结算调用 {a['unsettled_calls']}。", '']
    (RESULTS / 'name-sensitivity.md').write_text('\n'.join(lines))
    print('\n'.join(lines))


def check():
    assert tg.check_equivalence()
    for task, s in units('todomvc'):
        assert todomvc_messages(task, s, 'original') == td.messages_for(task, 'dna', todomvc_library())
        ref = td.reference_plan(task['features'])
        assert todomvc_compile(ref, task, s, 'shuffle') == td.compile_plan(ref, task['features'], todomvc_library())
        assert todomvc_choices(ref, task, s, 'original')[0] == todomvc_choices(ref, task, s, 'original')[1]
    for task, _ in units('webbench'):
        assert webbench_messages(task, 'original') == wd.messages_for(task, 'dna', webbench_library())
        ref = wd.reference_plan(task['features'])
        forward = {n: a for a, n in webbench_view(task, 'neutral')[2].items()}
        aliased = {k: (forward[v] if k in SLOTS else v) for k, v in ref.items()}
        assert webbench_compile(aliased, task, 'neutral') == wd.compile_plan(ref, task['features'], webbench_library())
    print('prompt and compiler equivalence: ok')


def main():
    global OUT
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--no-generate', action='store_true')
    parser.add_argument('--generate-only', action='store_true')
    parser.add_argument('--suites', nargs='+', default=list(MODELS), choices=list(MODELS))
    parser.add_argument('--conditions', nargs='+', default=CONDITIONS, choices=CONDITIONS)
    parser.add_argument('--cap-usd', type=float, default=0.6)
    parser.add_argument('--stop-usd', type=float, default=0.55)
    parser.add_argument('--threads', type=int, default=6)
    parser.add_argument('--grade-workers', type=int, default=3)
    parser.add_argument('--out', type=Path, default=OUT, help='stage directory (a new one continues a stage whose ledger is exhausted)')
    parser.add_argument('--extra-ledgers', nargs='*', default=[], help='ledgers of earlier stage directories, read-only, for the cost columns')
    args = parser.parse_args()
    OUT = args.out.resolve()
    check()
    if args.check:
        task = wd.tasks()[4]
        print(webbench_messages(task, 'neutral_nodesc')[1]['content'][-2600:])
        return
    OUT.mkdir(parents=True, exist_ok=True)
    ledger = ledger_read.ReadOnlyLedger(OUT / 'budget.sqlite3') if args.no_generate else Ledger(OUT / 'budget.sqlite3', args.cap_usd, args.stop_usd)
    config = {'models': sorted({m for s in MODELS.values() for m in s}), 'temperature': 0.6, 'max_tokens': 4000, 'max_repairs': 2, 'seed': SEED,
              'budget_usd': args.cap_usd, 'stop_new_requests_usd': args.stop_usd, 'price_caps_per_million': {'prompt': 3.0, 'completion': 15.0},
              'reasoning_effort': {'openai/gpt-oss-120b': 'low'},
              # caps follow the 2026-11-11 catalogue (two list prices rose above the caps of the earlier stages)
              'model_price_caps': {'deepseek/deepseek-v4-pro-0813': {'prompt': 1.3, 'completion': 4.6}, 'deepseek/deepseek-v4-flash': {'prompt': 0.2, 'completion': 0.4},
                                   'qwen/qwen3-coder-30b-a3b-instruct': {'prompt': 0.2, 'completion': 0.8},
                                   'mistralai/mistral-small-3.2-24b-instruct': {'prompt': 0.1, 'completion': 0.3},
                                   'openai/gpt-oss-120b': {'prompt': 0.2, 'completion': 0.7}}}
    if not args.no_generate:
        from test.review_stage import freeze
        freeze(OUT, config, ['test/name_sensitivity.py', 'test/todomvc_dna/generic.py', 'test/todomvc_dna/domain.py', 'test/webbench_dna/domain.py'],
               {'conditions': CONDITIONS, 'samples': SAMPLES, 'todomvc_library': todomvc_library()['sha256'], 'webbench_library': webbench_library()['sha256']})
    server = te.Server(OUT)
    jobs = [(suite, c, m) for suite in args.suites for c in args.conditions for m in MODELS[suite]]
    try:
        if not args.no_generate:
            provider = provider_for(config, ledger, args.extra_ledgers)

            def run(job):
                suite, condition, model = job
                try:
                    for task, s in units(suite):
                        generate(suite, condition, model, task, s, provider, server)
                except BudgetStop as error:
                    return job, f'STOPPED: {error}'
                return job, 'done'
            with ThreadPoolExecutor(max_workers=args.threads) as pool:
                for job, status in pool.map(run, jobs):
                    print(*job, status, flush=True)
        todo = [(suite, c, m, task, s) for suite, c, m in jobs for task, s in units(suite)
                if (folder_of(suite, c, m, task, s) / 'record.json').exists()]
        if not args.generate_only:
            with ThreadPoolExecutor(max_workers=args.grade_workers) as pool:
                for i, h in enumerate(pool.map(lambda j: grade(*j, server), todo), 1):
                    if i % 20 == 0:
                        print(f'graded {i}/{len(todo)}', flush=True)
    finally:
        server.close()
    summarise(ledger, args.extra_ledgers)


if __name__ == '__main__':
    main()
