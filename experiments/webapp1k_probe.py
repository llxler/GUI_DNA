"""WebApp1K / WebApp1K-Duo feasibility probe (2026-10-30).

Question: does the public benchmark show the phenomenon our method targets, i.e. a model that
implements each atomic feature correctly still fails when two atoms must be wired into one module?

Design (free-form baseline only; no plan compiler here):
- Pick N Duo tasks per category from the official repo, plus every atomic (single) task they are
  built from. Prompt is the official WebApp1K prompt wrapped in this project's JSON output format.
- Grade with the official CRA/Jest harness (deterministic, no LLM judge), one Jest run per test
  file so a hanging candidate cannot hide the others.
- Paid calls go through this project's OpenRouter client with a SEPARATE small ledger
  (artifacts/benchmark-probe/budget.sqlite3); the round-3 ledger is never touched.

Setup once (the clone lives under the git-ignored artifacts/ directory):
    git clone --depth 1 https://github.com/onekq/WebApp1k.git artifacts/benchmark-probe/WebApp1k
    (cd artifacts/benchmark-probe/WebApp1k/staging && npm install && npm install react-router-dom@6 node-fetch@2)
    # Pins needed for the official tests under CRA 5 / Jest 27 (verified 2026-10-30 with a hand-written component):
    #   fetch-mock 9.11.0 (tests call reset()/restore(), removed in v10+), react-router-dom 6.x (v7 uses package
    #   "exports" that Jest 27 cannot resolve), node-fetch 2.x (fetch-mock 9 peer dependency).
Run:
    uv run python -m experiments.webapp1k_probe --models deepseek/deepseek-v4-pro-0813 qwen/qwen3-coder \
        --categories blogging taskmanagement --per-category 5
    uv run python -m experiments.webapp1k_probe --evaluate-only      # re-grade saved implementations
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import time
from collections import defaultdict
from pathlib import Path

from gui_dna.budget import BudgetStop, Ledger
from gui_dna.provider import OpenRouter, ProviderError, parse_json
from gui_dna.tasks import ROOT, dump

PROBE = ROOT / 'artifacts/benchmark-probe'
REPO = PROBE / 'WebApp1k'
STAGING = REPO / 'staging'
SYSTEM = ('You write one self-contained React module that must pass the given Jest + React Testing Library test file. '
          'Return JSON only: {"code": "<complete JavaScript source of the module>"}. '
          'The module must default-export the component imported by the test, use fetch for API calls, '
          'and must not import files other than react and react-router-dom.')
# Official WebApp1K prompt (generate_code.py), kept verbatim inside the user turn.
PROMPT = 'Generate {name}.js to pass the tests below:\n\n{tests}. RETURN CODE ONLY.'


def slug(model):
    return model.replace('/', '__')


def module_name(test_source):
    match = re.search(r"from\s+['\"]\./([A-Za-z0-9_]+)['\"]", test_source)
    if not match:
        raise ValueError('Cannot find the implementation import in the test file')
    return match.group(1)


def select_tasks(categories, per_category):
    tasks = []
    for category in categories:
        duos = sorted((REPO / 'duo_tests/react' / category).glob('*.test.js'))[:per_category]
        atoms = []
        for duo in duos:
            parts = duo.name[:-len('.test.js')].split('_')
            atoms.extend(p for p in parts if p not in atoms)
        for path in duos:
            tasks.append({'kind': 'duo', 'category': category, 'name': path.name[:-8], 'test': str(path),
                          'atoms': path.name[:-8].split('_')})
        for atom in atoms:
            path = REPO / 'tests/react' / category / f'{atom}.test.js'
            if path.exists():
                tasks.append({'kind': 'single', 'category': category, 'name': atom, 'test': str(path), 'atoms': [atom]})
            else:
                print(f'WARNING: no single test for atom {category}/{atom}', flush=True)
    for task in tasks:
        task['module'] = module_name(Path(task['test']).read_text())
    return tasks


def generate(provider, model, task, out, seed):
    out.mkdir(parents=True, exist_ok=True)
    implementation = out / 'implementation.js'
    record_path = out / 'record.json'
    if record_path.exists():
        return json.loads(record_path.read_text())
    tests = Path(task['test']).read_text()
    messages = [{'role': 'system', 'content': SYSTEM},
                {'role': 'user', 'content': PROMPT.format(name=task['module'], tests=tests)}]
    dump(out / 'messages.json', messages)
    record = {'model': model, **task, 'generated': False, 'error': None}
    started = time.monotonic()
    try:
        raw = provider.call(model, messages, out / 'call', f'webapp1k:{model}:{task["kind"]}:{task["name"]}', seed=seed)
        code = parse_json(raw)['code']
        if not isinstance(code, str) or not code.strip():
            raise ValueError('code must be a non-empty string')
        implementation.write_text(code)
        record['generated'] = True
    except BudgetStop:
        raise
    except (ProviderError, ValueError, KeyError, TypeError) as error:
        record['error'] = f'{type(error).__name__}: {error}'
        implementation.write_text('')
    record['elapsed_seconds'] = time.monotonic() - started
    dump(record_path, record)
    return record


def grade(model, tasks, timeout=180):
    """One Jest invocation per test file inside the official staging project."""
    src = STAGING / 'src'
    if src.exists():
        shutil.rmtree(src)
    results = {}
    for task in tasks:
        folder = src / 'react' / task['category']
        folder.mkdir(parents=True, exist_ok=True)
        test_copy = folder / f'{task["name"]}.test.js'
        shutil.copy(task['test'], test_copy)
        implementation = PROBE / 'runs' / slug(model) / task['kind'] / task['category'] / task['name'] / 'implementation.js'
        (folder / f'{task["module"]}.js').write_text(implementation.read_text() if implementation.exists() else '')
        report = PROBE / 'runs' / slug(model) / task['kind'] / task['category'] / task['name'] / 'jest.json'
        env = {**os.environ, 'CI': 'true'}
        env.pop('OPENROUTER_API_KEY', None)
        command = ['npm', 'test', '--', '--json', f'--outputFile={report}', '--testPathPattern', f'src/react/{task["category"]}/{task["name"]}.test.js']
        verdict = {'tests': 0, 'passed': 0, 'all_passed': False, 'assertions': [], 'timed_out': False}
        try:
            completed = subprocess.run(command, cwd=STAGING, env=env, capture_output=True, text=True, timeout=timeout)
            data = json.loads(report.read_text()) if report.exists() else None
            if data and data.get('testResults'):
                file_result = data['testResults'][0]
                verdict['assertions'] = [{'title': a['title'], 'status': a['status']} for a in file_result['assertionResults']]
                verdict['tests'] = len(verdict['assertions'])
                verdict['passed'] = sum(a['status'] == 'passed' for a in verdict['assertions'])
                verdict['all_passed'] = file_result['status'] == 'passed' and verdict['tests'] > 0
                verdict['message'] = (file_result.get('message') or '')[:1500]
            else:
                verdict['message'] = (completed.stderr or completed.stdout)[-1500:]
        except subprocess.TimeoutExpired:
            verdict['timed_out'] = True
            verdict['message'] = f'Jest exceeded {timeout}s (likely an infinite loop in the candidate)'
        # Keep the staging tree small and avoid cross-file interference.
        test_copy.unlink()
        (folder / f'{task["module"]}.js').unlink()
        results[(task['kind'], task['category'], task['name'])] = verdict
        print(f'{model} {task["kind"]:6} {task["category"]}/{task["name"]}: {verdict["passed"]}/{verdict["tests"]}', flush=True)
    return results


def summarize(models, tasks, graded, accounting):
    summary = {'date_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'models': [], 'accounting': accounting,
               'tasks': [{k: t[k] for k in ['kind', 'category', 'name', 'atoms']} for t in tasks]}
    for model in models:
        rows = graded[model]
        singles = [t for t in tasks if t['kind'] == 'single']
        duos = [t for t in tasks if t['kind'] == 'duo']
        single_pass = {(t['category'], t['name']): rows[('single', t['category'], t['name'])]['all_passed'] for t in singles}
        duo_rows = []
        for t in duos:
            verdict = rows[('duo', t['category'], t['name'])]
            # Duo tests are ordered: two assertions per atom, atom order follows the file name.
            per_atom = {}
            for i, atom in enumerate(t['atoms']):
                part = verdict['assertions'][2 * i:2 * i + 2]
                per_atom[atom] = {'passed': sum(a['status'] == 'passed' for a in part), 'total': len(part),
                                  'single_passed': single_pass.get((t['category'], atom))}
            both_atoms_pass_alone = all(single_pass.get((t['category'], a)) for a in t['atoms'])
            duo_rows.append({'category': t['category'], 'name': t['name'], 'passed': verdict['passed'], 'tests': verdict['tests'],
                             'all_passed': verdict['all_passed'], 'timed_out': verdict['timed_out'], 'per_atom': per_atom,
                             'both_atoms_pass_alone': both_atoms_pass_alone,
                             'composition_failure': both_atoms_pass_alone and not verdict['all_passed']})
        records = [PROBE / 'runs' / slug(model) / t['kind'] / t['category'] / t['name'] / 'record.json' for t in tasks]
        generation_errors = sum(1 for r in records if not r.exists() or not json.loads(r.read_text())['generated'])
        summary['models'].append({
            'model': model,
            'singles': {'n': len(singles), 'passed': sum(single_pass.values())},
            'duos': {'n': len(duos), 'passed': sum(r['all_passed'] for r in duo_rows),
                     'both_atoms_pass_alone': sum(r['both_atoms_pass_alone'] for r in duo_rows),
                     'composition_failures': sum(r['composition_failure'] for r in duo_rows),
                     'assertions_passed': sum(r['passed'] for r in duo_rows), 'assertions': sum(r['tests'] for r in duo_rows)},
            'generation_errors': generation_errors,
            'duo_rows': duo_rows,
            'single_rows': [{'category': c, 'name': n, 'all_passed': v} for (c, n), v in sorted(single_pass.items())]})
    return summary


def markdown(summary):
    lines = ['# WebApp1K / WebApp1K-Duo 探针结果', '',
             f"生成时间 {summary['date_utc']}。自由代码基线（无计划编译器），官方 CRA/Jest 评分，每个测试文件单独一次 Jest 进程。",
             '', '| 模型 | 单功能通过 | 双功能组合通过 | 组合断言通过 | 两个原子单独都过的组合数 | 其中组合仍失败（组合缺口） | 生成失败 |', '|---|---:|---:|---:|---:|---:|---:|']
    for m in summary['models']:
        s, d = m['singles'], m['duos']
        lines.append(f"| {m['model']} | {s['passed']}/{s['n']} | {d['passed']}/{d['n']} | {d['assertions_passed']}/{d['assertions']} | {d['both_atoms_pass_alone']} | {d['composition_failures']} | {m['generation_errors']} |")
    lines += ['', '「组合缺口」= 两个原子功能各自单独实现都通过，但把二者接进同一个模块时失败的任务数。这正是本项目方法针对的现象。', '']
    for m in summary['models']:
        lines += [f"## {m['model']}：逐任务", '', '| 类别 | 组合任务 | 原子 A（单独 / 组合内） | 原子 B（单独 / 组合内） | 组合 4 项断言 | 组合缺口 |', '|---|---|---|---|---:|---|']
        for r in m['duo_rows']:
            cells = []
            for atom, v in r['per_atom'].items():
                alone = {True: '过', False: '败', None: '无'}[v['single_passed']]
                cells.append(f"{atom}：{alone} / {v['passed']}/{v['total']}")
            while len(cells) < 2:
                cells.append('')
            flag = '是' if r['composition_failure'] else ('超时' if r['timed_out'] else '')
            lines.append(f"| {r['category']} | {r['name']} | {cells[0]} | {cells[1]} | {r['passed']}/{r['tests']} | {flag} |")
        lines.append('')
    a = summary['accounting']
    lines += [f"探针账本（独立于第三轮账本）：已结算 ${a['actual_usd']:.6f}，含未结算预留的敞口 ${a['exposure_usd']:.6f}，未结算请求 {a['unsettled_calls']}。", '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--models', nargs='+', default=['deepseek/deepseek-v4-pro-0813'])
    parser.add_argument('--categories', nargs='+', default=['blogging', 'taskmanagement'])
    parser.add_argument('--per-category', type=int, default=5)
    parser.add_argument('--cap-usd', type=float, default=1.5)
    parser.add_argument('--stop-usd', type=float, default=1.2)
    parser.add_argument('--evaluate-only', action='store_true', help='Skip generation; grade saved implementations')
    args = parser.parse_args()
    if not (STAGING / 'node_modules').exists():
        raise SystemExit('WebApp1k staging dependencies missing; see module docstring')
    tasks = select_tasks(args.categories, args.per_category)
    print(f'{len(tasks)} tasks: {sum(t["kind"] == "duo" for t in tasks)} duo + {sum(t["kind"] == "single" for t in tasks)} single', flush=True)
    config = {'models': args.models, 'temperature': 0.6, 'max_tokens': 4000, 'max_repairs': 0, 'seed': 20261030,
              'budget_usd': args.cap_usd, 'stop_new_requests_usd': args.stop_usd,
              'price_caps_per_million': {'prompt': 3.0, 'completion': 15.0},
              'model_price_caps': {'deepseek/deepseek-v4-pro-0813': {'prompt': 1.3, 'completion': 2.6},
                                   'qwen/qwen3-coder': {'prompt': 0.65, 'completion': 3.25}}}
    ledger = Ledger(PROBE / 'budget.sqlite3', args.cap_usd, args.stop_usd)
    dump(PROBE / 'manifest.json', {'config': config, 'categories': args.categories, 'per_category': args.per_category,
                                   'tasks': tasks, 'repo': 'https://github.com/onekq/WebApp1k', 'pins': {'fetch-mock': '9.11.0', 'react-router-dom': '6.x', 'node-fetch': '2.x'},
                                   'note': 'Separate ledger; round-3 ledger untouched. Free-form baseline only.'})
    stopped = None
    if not args.evaluate_only:
        provider = OpenRouter(config, ledger)
        for model in args.models:
            for task in tasks:
                out = PROBE / 'runs' / slug(model) / task['kind'] / task['category'] / task['name']
                try:
                    record = generate(provider, model, task, out, config['seed'])
                except BudgetStop as error:
                    stopped = str(error)
                    break
                print(f'{model} {task["kind"]:6} {task["category"]}/{task["name"]}: {"ok" if record["generated"] else record["error"]}', flush=True)
            if stopped:
                print('STOPPED:', stopped, flush=True)
                break
    graded = {model: grade(model, tasks) for model in args.models}
    summary = summarize(args.models, tasks, graded, {k: v for k, v in ledger.summary().items() if k != 'calls'})
    summary['stopped'] = stopped
    dump(PROBE / 'summary.json', summary)
    (PROBE / 'summary.md').write_text(markdown(summary))
    print(json.dumps([{k: m[k] for k in ['model', 'singles', 'duos', 'generation_errors']} for m in summary['models']], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
