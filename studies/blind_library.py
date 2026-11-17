"""Blind library: who has to write the atoms?  (paid, small)

    uv run python -m test.blind_library --check            # zero API: print the builder prompt, assert it leaks no test
    uv run python -m test.blind_library --build            # one call (+ at most two repairs) per builder model, then freeze
    uv run python -m test.blind_library --adequacy         # zero API: is a fully correct plan available in each library?
    uv run python -m test.blind_library --plan             # planners write plans / free code over each frozen blind library
    uv run python -m test.blind_library --summary          # tables only

In the main TodoMVC study the 24 atoms and their variants were written by a person who could see the official tests.
Here a strong model writes atom bodies and alternatives over HUMAN-FIXED slots from public material only: the requirement sentences of the TodoMVC
specification (the same text every planner sees), the shell protocol and the plan schema.  It is told to provide,
for every slot, the behaviours a todo-app specification could plausibly ask for, and not to say which one this
specification needs.  Public feedback to the builder: JSON shape, syntax, and whether at least one assembly of its
core atoms passes the public smoke check (page errors + one added todo).  No official test, test title or result
reaches the builder or a planner.  The frozen library is then used exactly like the human one: same plan prompt,
same compiler (test/todomvc_dna/generic.py), same repair loop, same hidden grading.
Outputs: artifacts/todomvc-blind/ (own ledger), test/results/blind-library.{json,md}.
"""
from __future__ import annotations

import argparse
import itertools
import json
import re
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from gui_dna.budget import BudgetStop, Ledger
from gui_dna.provider import ProviderError, parse_json
from gui_dna.tasks import dump
from test import ledger_read
from test.review_stage import provider_for
from test.provider_ext import ReasoningAwareOpenRouter as OpenRouter
from test.todomvc_dna import domain, evaluate, generic
from test.todomvc_dna.library import EVENTS, FEATURES, VIEW_SLOTS, digest

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts' / 'todomvc-blind'
RESULTS = ROOT / 'test' / 'results'
BUILDERS = ['openai/gpt-5', 'anthropic/claude-sonnet-4.5']
PLANNERS = ['deepseek/deepseek-v4-pro-0813', 'qwen/qwen3-coder-30b-a3b-instruct', 'mistralai/mistral-small-3.2-24b-instruct',
            'google/gemma-3-12b-it', 'openai/gpt-5-mini', 'openai/gpt-oss-120b', 'google/gemini-2.5-flash', 'anthropic/claude-haiku-4.5']
ARMS = ['dna', 'free_lib']
SAMPLES, SEED = 2, 20261102
EVENT_FEATURE = {'add': 'core', **{e: f for f, events in EVENTS.items() for e in events}}
MAIN_SUMMARY = ROOT / 'test/todomvc_dna/results/summary.json'


def slug(model):
    return model.replace('/', '__')


# ---------------------------------------------------------------- builder prompt
def builder_messages():
    spec = '\n'.join(f'- [{feature}] {sentence}' for feature in ['core'] + FEATURES for sentence in domain.SPEC[feature])
    events = ', '.join(f'{e} (feature {f})' for e, f in EVENT_FEATURE.items())
    views = ', '.join(f'{s} (feature {f})' for s, f in VIEW_SLOTS.items())
    system = ('You write a small library of JavaScript functions ("atoms") for the state logic of todo-list web apps that run behind a fixed shell. '
              'Return JSON only: {"atoms": [{"name": "<identifier>", "kind": "init" | "event" | "after" | "view", "slot": "<event name or view slot; omit for init and after>", '
              '"feature": "<feature the atom belongs to, or core>", "description": "<one line: what the atom does>", "code": "function <name>(...) {...}"}]}.')
    user = f"""{domain.INTERFACE}

How the library will be used. Another model, which cannot write code, later receives a requirement and a list of enabled features and writes a plan: one init atom, one event atom for every enabled event, any number of after hooks, and one view atom for every enabled view slot. A compiler links the chosen atoms verbatim into
  init() {{ return <init atom>(); }}
  reduce(s, e) {{ switch (e.type) {{ case '<event>': <event atom>(s, e); break; ... }} <after hook>(s, e); ... return s; }}
  select(s) {{ return {{ <slot>: <view atom>(s), ..., hasTodos: s.todos.length > 0, editing: s.editing, filter: s.filter }}; }}
Only the atoms a plan selects are linked, so every atom must be self-contained: no calls to other atoms, no shared helpers, no DOM access, no imports.

Slots (exactly these):
- init: init() returns the initial state.
- event atoms, signature (s, e), mutate s in place; one slot per event: {events}.
- after hooks, signature (s, e), run after every event, for behaviour that cuts across events; feature core or the feature they need.
- view atoms, signature (s), return the value of their slot: {views}.
Features can be enabled independently (except core); an atom must work when the features other than its own are disabled.

A specification this library must be able to serve (TodoMVC application specification, functionality):
{spec}

What to write. Specifications of todo apps differ in their details. For every slot, write an atom for each behaviour that a specification could plausibly ask for there: the behaviour this specification describes and the alternatives another, simpler or differently worded specification would describe. Write at least two atoms for a slot wherever more than one behaviour is plausible. Describe each atom by what it does. Do not state or hint which atom this specification needs, and do not order the atoms by preference: the library is frozen and reused, and choosing is the other model's job.

Return the library as JSON only."""
    return [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]


def leak_check():
    """No official test title (or a distinctive part of one) may occur in the builder prompt."""
    text = ' '.join(m['content'] for m in builder_messages()).lower()
    for group, title in domain.TEST_FEATURES:
        assert title.lower() not in text, title
    spec = (evaluate.HARNESS / 'demo-todo-app.original.spec.ts').read_text()
    for line in spec.splitlines():
        line = line.strip()
        if len(line) > 40 and line.lower() in text:
            raise AssertionError(f'spec line in builder prompt: {line}')
    return True


# ---------------------------------------------------------------- validation (public only)
def to_library(parsed, builder):
    atoms = parsed.get('atoms') if isinstance(parsed, dict) else None
    if not isinstance(atoms, list) or not atoms:
        raise ValueError('"atoms" must be a non-empty array')
    functions, seen, problems = [], set(), []
    for i, a in enumerate(atoms):
        if not isinstance(a, dict):
            raise ValueError(f'atom #{i + 1} is not an object')
        name, kind, slot, feature, code = a.get('name'), a.get('kind'), a.get('slot'), a.get('feature'), a.get('code')
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z_$][\w$]*', name) or name in seen:
            problems.append(f'atom #{i + 1}: "name" must be a unique identifier (got {name!r})')
            continue
        seen.add(name)
        if kind not in ('init', 'event', 'after', 'view'):
            problems.append(f'{name}: "kind" must be init, event, after or view')
            continue
        if kind == 'event' and slot not in EVENT_FEATURE:
            problems.append(f'{name}: "slot" of an event atom must be one of {list(EVENT_FEATURE)}')
        if kind == 'view' and slot not in VIEW_SLOTS:
            problems.append(f'{name}: "slot" of a view atom must be one of {list(VIEW_SLOTS)}')
        expected = {'event': EVENT_FEATURE.get(slot), 'view': VIEW_SLOTS.get(slot), 'init': 'core'}.get(kind)
        if kind == 'after':
            if feature not in ['core'] + FEATURES:
                problems.append(f'{name}: "feature" must be core or one of {FEATURES}')
        elif expected:
            feature = expected            # the slot fixes the feature; a different label is corrected silently
        match = re.match(r'\s*function\s+([A-Za-z_$][\w$]*)\s*\(([^)]*)\)', code) if isinstance(code, str) else None
        if not match or match.group(1) != name:
            problems.append(f'{name}: "code" must be exactly one function declaration named {name}')
            continue
        functions.append({'name': name, 'kind': kind, 'slot': slot if kind in ('event', 'view') else None, 'feature': feature,
                          'description': str(a.get('description', '')).strip(), 'signature': f'{name}({match.group(2).strip()})', 'code': code.strip()})
    for event in EVENT_FEATURE:
        if not any(f['kind'] == 'event' and f['slot'] == event for f in functions):
            problems.append(f'no event atom for the event "{event}"')
    for view in VIEW_SLOTS:
        if not any(f['kind'] == 'view' and f['slot'] == view for f in functions):
            problems.append(f'no view atom for the slot "{view}"')
    if not any(f['kind'] == 'init' for f in functions):
        problems.append('no init atom')
    if problems:
        raise ValueError('library rejected:\n- ' + '\n- '.join(problems))
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as handle:
        handle.write('\n'.join(f['code'] for f in functions))
    done = subprocess.run(['node', '--check', handle.name], capture_output=True, text=True)
    Path(handle.name).unlink(missing_ok=True)
    if done.returncode:
        raise ValueError('library rejected: JavaScript syntax error\n' + done.stderr.replace(handle.name, 'library.js')[:800])
    lib = {'origin': f'Built blind by {builder} from the TodoMVC specification sentences, the shell protocol and the plan schema; no tests seen',
           'builder': builder, 'functions': functions}
    lib['sha256'] = digest(lib)
    return lib


def tables_of(lib):
    fs = lib['functions']
    return {'routes': {e: [f['name'] for f in fs if f['kind'] == 'event' and f['slot'] == e] for e in EVENT_FEATURE},
            'inits': [f['name'] for f in fs if f['kind'] == 'init'],
            'afters': {f['name']: f['feature'] for f in fs if f['kind'] == 'after'},
            'views': {s: [f['name'] for f in fs if f['kind'] == 'view' and f['slot'] == s] for s in VIEW_SLOTS}}


def core_smoke(lib, folder, server, limit=24):
    """Public: does any assembly of the core atoms (init x add x visible x a choice of core hooks) pass the smoke check?"""
    t = tables_of(lib)
    hooks = [n for n, f in t['afters'].items() if f == 'core']
    hook_choices = [hooks] + [[h] for h in hooks if len(hooks) > 1] + ([[]] if hooks else [])   # hooks can be variants of each other
    first = None
    combos = itertools.product(hook_choices, t['inits'], t['routes']['add'], t['views']['visible'])
    for i, (after, init, add, visible) in enumerate(itertools.islice(combos, limit)):
        plan = {'init': init, 'handlers': {'add': add}, 'after': after, 'view': {'visible': visible}}
        page = evaluate.write_app(generic.compile_plan(plan, [], lib, t), folder / f'smoke-{i}')
        problems = evaluate.public_check(server.url(page))
        if not problems:
            return []
        first = first or (plan, problems)
    plan, problems = first
    return [f'no assembly of the core atoms passes the public smoke check; for example {json.dumps(plan)} gives: ' + '; '.join(problems[:4])]


def build(builder, provider, server, max_repairs=2):
    folder = OUT / 'build' / slug(builder)
    frozen = OUT / f'library-{slug(builder)}.json'
    if frozen.exists():
        return json.loads(frozen.read_text())
    messages, log = builder_messages(), []
    for n in range(1, max_repairs + 2):
        raw = provider.call(builder, messages, folder / f'call-{n}', f'blind:build:{builder}:a{n}', max_tokens=16000)
        problems, lib = [], None
        try:
            lib = to_library(parse_json(raw), builder)
            problems = core_smoke(lib, folder / f'v{n}', server)
        except (ValueError, KeyError, TypeError) as error:
            problems = [f'{type(error).__name__}: {error}']
        log.append({'attempt': n, 'problems': problems})
        if lib is not None and not problems:
            lib['build_attempts'] = log
            dump(frozen, lib)
            return lib
        if n > max_repairs:
            break
        messages = messages + [{'role': 'assistant', 'content': raw},
                               {'role': 'user', 'content': 'Public check of the library failed:\n- ' + '\n- '.join(problems) + '\nReturn the corrected complete library as JSON only.'}]
    dump(folder / 'failed.json', log)
    raise RuntimeError(f'{builder}: no usable library after {max_repairs + 1} attempts: {log[-1]}')


# ---------------------------------------------------------------- adequacy (hidden tests, reporting only, after the freeze)
def adequacy(builder, server, workers=4):
    """Post-hoc coordinate search; a witness is a lower bound, not a proof of library inadequacy."""
    path = OUT / f'adequacy-{slug(builder)}.json'
    if path.exists():
        return json.loads(path.read_text())
    lib = json.loads((OUT / f'library-{slug(builder)}.json').read_text())
    t = tables_of(lib)
    features = list(FEATURES)
    slots = {'init': t['inits'], **{f'h:{e}': v for e, v in t['routes'].items()}, **{f'v:{s}': v for s, v in t['views'].items()},
             **{f'a:{n}': [True, False] for n in t['afters']}}
    cache = {}

    def plan_of(choice):
        return {'init': choice['init'], 'handlers': {e: choice[f'h:{e}'] for e in t['routes']},
                'after': [n for n in t['afters'] if choice[f'a:{n}']], 'view': {s: choice[f'v:{s}'] for s in t['views']}}

    def score(choice):
        key = json.dumps(choice, sort_keys=True)
        if key not in cache:
            folder = OUT / 'adequacy' / slug(builder) / digest(choice)[:12]
            page = evaluate.write_app(generic.compile_plan(plan_of(choice), features, lib, t), folder)
            cache[key] = evaluate.grade(server.url(page), folder / 'report.json', features)
        return cache[key]['passed']
    best = {s: v[0] for s, v in slots.items()}
    best_score = score(best)
    for _ in range(3):
        improved = False
        for slot, variants in slots.items():
            candidates = [{**best, slot: v} for v in variants if v != best[slot]]
            if not candidates:
                continue
            with ThreadPoolExecutor(max_workers=workers) as pool:
                scores = list(pool.map(score, candidates))
            top = max(scores)
            if top > best_score:
                best, best_score, improved = candidates[scores.index(top)], top, True
        if not improved or best_score == 24:
            break
    final = cache[json.dumps(best, sort_keys=True)]
    out = {'builder': builder, 'atoms': len(lib['functions']), 'slots': {s: len(v) for s, v in slots.items()},
           'variant_slots': sum(1 for s, v in slots.items() if not s.startswith('a:') and len(v) > 1), 'plans_graded': len(cache),
           'best_plan': plan_of(best), 'best_passed': best_score, 'total': final['total'],
           'best_failed_tests': sorted(k for k, v in final['tests'].items() if v != 'passed')}
    dump(path, out)
    return out


# ---------------------------------------------------------------- planners
def run_folder(builder, model, arm, task, sample):
    return OUT / 'runs' / slug(builder) / slug(model) / arm / task['id'] / f's{sample}'


def generate(builder, lib, model, arm, task, sample, provider, server, max_repairs=2):
    folder = run_folder(builder, model, arm, task, sample)
    record_path = folder / 'record.json'
    if record_path.exists():
        return json.loads(record_path.read_text())
    tables = tables_of(lib)
    record = {'builder': builder, 'arm': arm, 'model': model, 'task': task['id'], 'sample': sample, 'attempts': [], 'versions': []}
    messages = generic.plan_messages(task, lib, tables) if arm == 'dna' else generic.free_lib_messages(task, lib)
    for n in range(1, max_repairs + 2):
        attempt = {'attempt': n, 'compile_error': None, 'public': None}
        try:
            raw = provider.call(model, messages, folder / f'call-{n}', f'blind:{builder}:{model}:{arm}:{task["id"]}:s{sample}:a{n}', seed=SEED + sample)
        except ProviderError as error:
            attempt['compile_error'] = f'ProviderError: {error}'
            record['attempts'].append(attempt)
            break
        code = None
        try:
            parsed = parse_json(raw)
            if arm == 'free_lib':
                code = parsed['code']
                if not isinstance(code, str) or not code.strip():
                    raise ValueError('code must be a non-empty string')
            else:
                attempt['plan'] = parsed
                code = generic.compile_plan(parsed, task['features'], lib, tables)
        except (ValueError, KeyError, TypeError) as error:
            attempt['compile_error'] = f'{type(error).__name__}: {error}'
        if code is not None:
            version = f'v{n}'
            attempt['public'] = evaluate.public_check(server.url(evaluate.write_app(code, folder / version)))
            record['versions'].append(version)
        record['attempts'].append(attempt)
        if (code is not None and not attempt['public']) or n > max_repairs:
            break
        is_plan = arm == 'dna'
        if attempt['compile_error']:
            feedback = ('The plan was rejected by the compiler:\n' if is_plan else 'Your output could not be used:\n') + attempt['compile_error']
        else:
            feedback = 'Public smoke check failed:\n- ' + '\n- '.join(attempt['public'])
        feedback += '\nReturn a corrected ' + ('plan' if is_plan else 'complete JavaScript source') + ' as JSON only.'
        messages = messages + [{'role': 'assistant', 'content': raw}, {'role': 'user', 'content': feedback}]
    dump(record_path, record)
    return record


def grade(builder, model, arm, task, sample, server):
    folder = run_folder(builder, model, arm, task, sample)
    hidden = folder / 'hidden.json'
    if hidden.exists():
        return json.loads(hidden.read_text())
    record = json.loads((folder / 'record.json').read_text())
    empty = {'passed': 0, 'total': len(domain.hidden_subset(task['features'])), 'all_passed': False, 'tests': {}, 'note': 'no usable version'}
    out = {}
    for label, version in ([('first', record['versions'][0]), ('final', record['versions'][-1])] if record['versions'] else []):
        if label == 'final' and version == record['versions'][0]:
            out['final'] = out['first']
        else:
            out[label] = evaluate.grade(server.url(folder / version / 'index.html'), folder / version / 'report.json', task['features'])
    out = out or {'first': empty, 'final': empty}
    dump(hidden, out)
    return out


# ---------------------------------------------------------------- summary
def summarise(ledger, extra_ledgers=(), planners=PLANNERS):
    calls = list(ledger.summary()['calls']) + [c for path in extra_ledgers for c in ledger_read.calls(path)]
    main = {m['model']: m for m in json.loads(MAIN_SUMMARY.read_text())['models']}
    tasks = domain.tasks()
    data = {'date_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'builders': {}}
    for builder in BUILDERS:
        frozen = OUT / f'library-{slug(builder)}.json'
        if not frozen.exists():
            continue
        lib = json.loads(frozen.read_text())
        t = tables_of(lib)
        entry = {'library': {'sha256': lib['sha256'], 'atoms': len(lib['functions']), 'build_attempts': len(lib.get('build_attempts', [])),
                             'variants_per_slot': {'init': len(t['inits']), **{e: len(v) for e, v in t['routes'].items()}, **{s: len(v) for s, v in t['views'].items()}},
                             'after_hooks': len(t['afters']),
                             'build_cost_usd': round(sum((c['actual'] or 0) for c in calls if c['purpose'].startswith(f'blind:build:{builder}:')) / 1e6, 4)},
                 'models': {}}
        adequacy_path = OUT / f'adequacy-{slug(builder)}.json'
        if adequacy_path.exists():
            entry['adequacy'] = json.loads(adequacy_path.read_text())
        for model in planners:
            row = {}
            base = {(r['task'], r['sample']): r for r in main[model]['rows']}
            for arm in ARMS:
                n = first = final = transport = rejections = 0
                wins = losses = 0
                for task in tasks:
                    for s in range(SAMPLES):
                        folder = run_folder(builder, model, arm, task, s)
                        if not (folder / 'record.json').exists() or not (folder / 'hidden.json').exists():
                            continue
                        record, hidden = json.loads((folder / 'record.json').read_text()), json.loads((folder / 'hidden.json').read_text())
                        if any('ProviderError' in (a.get('compile_error') or '') for a in record['attempts']):
                            transport += 1
                            continue
                        n += 1
                        first += bool(hidden['first']['all_passed'])
                        final += bool(hidden['final']['all_passed'])
                        rejections += sum(1 for a in record['attempts'] if a.get('compile_error'))
                        free = base[(task['id'], s)].get('free')
                        if free:
                            wins += bool(hidden['final']['all_passed'] and not free['final_all'])
                            losses += bool(free['final_all'] and not hidden['final']['all_passed'])
                row[arm] = {'n': n, 'first': first, 'final': final, 'rejections': rejections, 'transport_failures': transport,
                            'wins_vs_free': wins, 'losses_vs_free': losses,
                            'cost_usd': round(sum((c['actual'] or 0) for c in calls if c['purpose'].startswith(f'blind:{builder}:{model}:{arm}:')) / 1e6, 4)}
            row['main_free'] = main[model]['arms']['free']['final_all']
            row['main_dna'] = main[model]['arms']['dna']['final_all']
            row['main_free_lib'] = main[model]['arms']['free_lib']['final_all']
            entry['models'][model] = row
        data['builders'][builder] = entry
    data['accounting'] = {'actual_usd': sum((c['actual'] or 0) for c in calls) / 1e6, 'unsettled_calls': sum(c['actual'] is None for c in calls),
                          'ledgers': [str(Path(p).resolve().relative_to(ROOT)) for p in [OUT / 'budget.sqlite3', *extra_ledgers]]}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / 'blind-library.json').write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    lines = ['# 盲建库：函数库由只看需求的模型来写（`uv run python -m test.blind_library`）', '',
             '建库模型只看到公开 TodoMVC 规范、外壳协议和人工固定的槽位，看不到官方测试；它生成函数与变体，不发现槽位。公开反馈只有 JSON 形状、语法、核心原子能否过公开冒烟检查。'
             '冻结后的库与人工库用同构的方案提示词、编译器、修复流程和隐藏评测。每格分母预期 16；缺失与传输失败排除，分母不齐时不能直接比较总分。', '']
    for builder, entry in data['builders'].items():
        lib = entry['library']
        lines += [f'## 建库模型：{builder}', '',
                  f"- 库：{lib['atoms']} 个原子，建库调用 {lib['build_attempts']} 次，费用 ${lib['build_cost_usd']:.4f}；每个槽位的原子数：`{json.dumps(lib['variants_per_slot'])}`，after 钩子 {lib['after_hooks']} 个。"]
        if 'adequacy' in entry:
            a = entry['adequacy']
            lines.append(f"- 事后覆盖能力探针（固定槽位；坐标搜索只给可达下界，评了 {a['plans_graded']} 个方案，只用于报告）：最好的方案过 **{a['best_passed']}/{a['total']}** 项官方测试"
                         + ('。' if not a['best_failed_tests'] else f"；仍失败：{'；'.join(x.split(' › ')[1] for x in a['best_failed_tests'])}。"))
        lines += ['', '| 模型 | 自由代码（主实验，无库） | 自由代码 + 盲建库 | **方案 + 盲建库**（首次） | 方案 + 人工库（主实验） | 方案 + 盲建库 对 自由代码：胜 / 负 |', '|---|---:|---:|---:|---:|---|']
        tot = {'free': 0, 'fl': 0, 'fl_n': 0, 'dna': 0, 'dna_first': 0, 'dna_n': 0, 'human': 0, 'w': 0, 'l': 0, 'models': 0}
        for model, row in entry['models'].items():
            d, f = row['dna'], row['free_lib']
            if not d['n'] and not f['n']:
                continue
            note = f"（另 {d['transport_failures'] + f['transport_failures']} 条传输失败未计）" if d['transport_failures'] + f['transport_failures'] else ''
            lines.append(f"| {model.split('/')[-1]} | {row['main_free']}/16 | {f['final']}/{f['n']} | **{d['final']}/{d['n']}**（{d['first']}） | {row['main_dna']}/16 | "
                         f"{d['wins_vs_free']} / {d['losses_vs_free']}{note} |")
            tot['free'] += row['main_free']; tot['fl'] += f['final']; tot['fl_n'] += f['n']; tot['dna'] += d['final']; tot['dna_first'] += d['first']
            tot['dna_n'] += d['n']; tot['human'] += row['main_dna']; tot['w'] += d['wins_vs_free']; tot['l'] += d['losses_vs_free']; tot['models'] += 1
        lines.append(f"| **合计** | {tot['free']}/{16 * tot['models']} | {tot['fl']}/{tot['fl_n']} | **{tot['dna']}/{tot['dna_n']}**（{tot['dna_first']}） | "
                     f"{tot['human']}/{16 * tot['models']} | {tot['w']} / {tot['l']} |")
        lines.append('')
    a = data['accounting']
    lines += [f"账本（独立）：{'、'.join('`' + x + '`' for x in a['ledgers'])}；已结算合计 ${a['actual_usd']:.4f}，未结算调用 {a['unsettled_calls']}。", '']
    (RESULTS / 'blind-library.md').write_text('\n'.join(lines))
    print('\n'.join(lines))


def main():
    global OUT
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for flag in ('check', 'build', 'adequacy', 'plan', 'summary', 'no-generate', 'generate-only'):
        parser.add_argument(f'--{flag}', action='store_true')
    parser.add_argument('--builders', nargs='+', default=BUILDERS)
    parser.add_argument('--planners', nargs='+', default=PLANNERS)
    parser.add_argument('--arms', nargs='+', default=ARMS, choices=ARMS)
    parser.add_argument('--cap-usd', type=float, default=2.0)
    parser.add_argument('--stop-usd', type=float, default=1.9)
    parser.add_argument('--threads', type=int, default=6)
    parser.add_argument('--grade-workers', type=int, default=3)
    parser.add_argument('--out', type=Path, default=OUT, help='stage directory (a new one continues a stage whose ledger is exhausted)')
    parser.add_argument('--extra-ledgers', nargs='*', default=[], help='ledgers of earlier stage directories, read-only, for the cost columns')
    args = parser.parse_args()
    OUT = args.out.resolve()
    assert generic.check_equivalence() and leak_check()
    if args.check:
        for m in builder_messages():
            print(f"--- {m['role']}\n{m['content']}\n")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    paid = args.build or (args.plan and not args.no_generate)
    ledger = Ledger(OUT / 'budget.sqlite3', args.cap_usd, args.stop_usd) if paid else ledger_read.ReadOnlyLedger(OUT / 'budget.sqlite3')
    config = {'models': BUILDERS + PLANNERS, 'temperature': 0.6, 'max_tokens': 4000, 'max_repairs': 2, 'seed': SEED,
              'budget_usd': args.cap_usd, 'stop_new_requests_usd': args.stop_usd, 'price_caps_per_million': {'prompt': 3.0, 'completion': 15.0},
              'reasoning_effort': {'openai/gpt-5-mini': 'low', 'openai/gpt-oss-120b': 'low', 'openai/gpt-5': 'medium'},
              'provider_order': {'google/gemma-3-12b-it': ['NextBit']},
              'omit_params': {'openai/gpt-5-mini': ['temperature', 'seed'], 'openai/gpt-5': ['temperature', 'seed']},
              # caps follow the 2026-11-11 catalogue (two list prices rose above the caps of the earlier stages)
              'model_price_caps': {'openai/gpt-5': {'prompt': 1.3, 'completion': 10.5}, 'anthropic/claude-sonnet-4.5': {'prompt': 3.1, 'completion': 15.5},
                                   'deepseek/deepseek-v4-pro-0813': {'prompt': 1.3, 'completion': 4.6},
                                   'qwen/qwen3-coder-30b-a3b-instruct': {'prompt': 0.2, 'completion': 0.8},
                                   'google/gemma-3-12b-it': {'prompt': 0.1, 'completion': 0.3},
                                   'mistralai/mistral-small-3.2-24b-instruct': {'prompt': 0.1, 'completion': 0.3},
                                   'openai/gpt-5-mini': {'prompt': 0.3, 'completion': 2.1}, 'openai/gpt-oss-120b': {'prompt': 0.2, 'completion': 0.7},
                                   'google/gemini-2.5-flash': {'prompt': 0.35, 'completion': 2.6}, 'anthropic/claude-haiku-4.5': {'prompt': 1.1, 'completion': 5.1}}}
    if paid:
        from test.review_stage import freeze
        freeze(OUT, config, ['test/blind_library.py', 'test/todomvc_dna/generic.py', 'test/todomvc_dna/domain.py', 'test/todomvc_dna/shell.html'],
               {'schema': 'human-fixed', 'builder_prompt': builder_messages(), 'seed': SEED, 'samples': SAMPLES,
                'libraries': {p.name: evaluate.sha256(p.read_text()) for p in sorted(OUT.glob('library-*.json'))}})
    server = evaluate.Server(OUT)
    try:
        if args.build:
            provider = provider_for(config, ledger, args.extra_ledgers)
            dump(OUT / 'builder-prompt.json', builder_messages())
            for builder in args.builders:
                lib = build(builder, provider, server)
                print(builder, 'atoms', len(lib['functions']), 'attempts', len(lib['build_attempts']), flush=True)
        if args.adequacy:
            for builder in args.builders:
                if (OUT / f'library-{slug(builder)}.json').exists():
                    a = adequacy(builder, server)
                    print(builder, 'best plan', a['best_passed'], '/', a['total'], 'graded', a['plans_graded'], a['best_failed_tests'], flush=True)
        if args.plan or args.no_generate:
            provider = provider_for(config, ledger, args.extra_ledgers) if args.plan and not args.no_generate else None
            libs = {b: json.loads((OUT / f'library-{slug(b)}.json').read_text()) for b in args.builders if (OUT / f'library-{slug(b)}.json').exists()}
            jobs = [(b, m, arm) for b in libs for m in args.planners for arm in args.arms]

            def run(job):
                builder, model, arm = job
                try:
                    for task in domain.tasks():
                        for s in range(SAMPLES):
                            generate(builder, libs[builder], model, arm, task, s, provider, server)
                except BudgetStop as error:
                    return job, f'STOPPED: {error}'
                return job, 'done'
            if provider is not None:
                with ThreadPoolExecutor(max_workers=args.threads) as pool:
                    for job, status in pool.map(run, jobs):
                        print(*job, status, flush=True)
            todo = [(b, m, arm, task, s) for b, m, arm in jobs for task in domain.tasks() for s in range(SAMPLES)
                    if (run_folder(b, m, arm, task, s) / 'record.json').exists()]
            if not args.generate_only:
                with ThreadPoolExecutor(max_workers=args.grade_workers) as pool:
                    for i, _ in enumerate(pool.map(lambda j: grade(*j, server), todo), 1):
                        if i % 20 == 0:
                            print(f'graded {i}/{len(todo)}', flush=True)
    finally:
        server.close()
    summarise(ledger, args.extra_ledgers, args.planners)


if __name__ == '__main__':
    main()
