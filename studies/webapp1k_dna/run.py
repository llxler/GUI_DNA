"""WebApp1K-Duo: free-form generation vs. frozen-atom composition (GUI-DNA plan + checked compiler).

Three arms per model on the same Duo tasks, same seed, same repair budget (public Jest feedback only):
  free  official WebApp1K prompt -> complete module                       (conventional method)
  rule  deterministic plan (model's own atoms, file order, no relabel)    (zero-API control)
  dna   model writes a plan; compile_plan checks + stitches frozen atoms  (GUI-DNA method)
Atoms = single-feature implementations generated once from the official single-feature tests (library.json
records origin, sha256 and whether each passed its own public tests).  Grading = official CRA/Jest.

    export OPENROUTER_API_KEY=...
    uv run python -m test.webapp1k_dna.run --models deepseek/deepseek-v4-pro-0813 qwen/qwen3-coder \
        --categories blogging taskmanagement --per-category 5 --arms free rule dna
    uv run python -m test.webapp1k_dna.run --arms rule            # no API key needed
    uv run python -m test.webapp1k_dna.run --evaluate-only        # re-grade saved outputs, no API
    uv run python -m test.webapp1k_dna.run --summarize-only       # rebuild summary.md/json from record.json, no Jest
Scale-up later: raise --per-category / add --categories; missing atoms are generated (paid) and verified.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from gui_dna.budget import BudgetStop, Ledger
from gui_dna.provider import OpenRouter, ProviderError, parse_json
from gui_dna.tasks import dump
from experiments.webapp1k_probe import PROBE, REPO, STAGING, SYSTEM, PROMPT, select_tasks, slug, generate as generate_atom

from . import compiler

HERE = Path(__file__).resolve().parent
ROOT = compiler.ROOT
DEFAULT_OUT = ROOT / 'artifacts/webapp1k-dna'
RESULTS = HERE / 'results'
ANSI = re.compile(r'\x1b\[[0-9;]*m')

DNA_SYSTEM = (
    'You are wiring frozen React feature modules ("atoms") into one page so that the given Jest + React Testing '
    'Library test file passes. You cannot write or edit code. Return JSON only, a plan of the form '
    '{"select": {"<atom>": "<variant>"}, "order": ["<atom>", ...], "relabel": [{"atom": "<atom>", "from": "<exact static string>", "to": "<new string>"}]}. '
    'The compiler mounts the selected variant of every atom, in the given order, inside one default-exported '
    'component that forwards all props to each atom. Atom logic is frozen. The plan may only: (1) choose one '
    'variant per atom; (2) choose the order; (3) relabel visible static strings of an atom (JSX text, placeholder, '
    'aria-label, alt, title, data-testid) so the atoms do not collide on the selectors used by the test. '
    'Prefer variants that pass their own public tests. Keep "relabel" empty unless a collision requires it.')
DNA_USER = ('Target test file `{name}.test.js` (both features must pass in one page):\n\n```js\n{tests}\n```\n\n'
            'Frozen atom library for this task (one variant must be selected per atom):\n\n{library}\n\n'
            'Return the plan as JSON only.')


def jest_feedback(verdict):
    if verdict.get('timed_out'):
        return 'Jest timed out (likely an infinite render/effect loop).'
    if not verdict.get('assertions'):
        return 'Jest could not run the test file:\n' + ANSI.sub('', verdict.get('message') or '')[-1200:]
    failed = [a for a in verdict['assertions'] if a['status'] != 'passed']
    lines = [f'{verdict["passed"]}/{verdict["tests"]} tests passed. Failing tests:']
    for a in failed:
        lines.append(f'- {a["title"]}: ' + ANSI.sub('', a.get('failure') or '').strip()[:700])
    return '\n'.join(lines)


def grade_files(category, test_path, files, report, timeout=180):
    """Copy the candidate files next to the official test inside the staging project; one Jest run."""
    folder = STAGING / 'src' / 'react' / category
    folder.mkdir(parents=True, exist_ok=True)
    name = Path(test_path).name[:-len('.test.js')]
    written = []
    test_copy = folder / f'{name}.test.js'
    shutil.copy(test_path, test_copy)
    written.append(test_copy)
    for rel, source in files.items():
        target = folder / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source)
        written.append(target)
    env = {**os.environ, 'CI': 'true'}
    env.pop('OPENROUTER_API_KEY', None)
    report = Path(report).resolve()   # Jest resolves --outputFile against the staging cwd
    command = ['npm', 'test', '--', '--json', f'--outputFile={report}', '--testPathPattern', f'src/react/{category}/{name}.test.js']
    verdict = {'tests': 0, 'passed': 0, 'all_passed': False, 'assertions': [], 'timed_out': False}
    try:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.unlink(missing_ok=True)   # never read a stale report
        done = subprocess.run(command, cwd=STAGING, env=env, capture_output=True, text=True, timeout=timeout)
        data = json.loads(Path(report).read_text()) if Path(report).exists() else None
        if data and data.get('testResults'):
            file_result = data['testResults'][0]
            verdict['assertions'] = [{'title': a['title'], 'status': a['status'], 'failure': (a.get('failureMessages') or [''])[0][:2000]}
                                     for a in file_result['assertionResults']]
            verdict['tests'] = len(verdict['assertions'])
            verdict['passed'] = sum(a['status'] == 'passed' for a in verdict['assertions'])
            verdict['all_passed'] = file_result['status'] == 'passed' and verdict['tests'] > 0
            verdict['message'] = (file_result.get('message') or '')[:1500]
        else:
            verdict['message'] = (done.stderr or done.stdout)[-1500:]
    except subprocess.TimeoutExpired:
        verdict['timed_out'] = True
        verdict['message'] = f'Jest exceeded {timeout}s'
    finally:
        for path in written:
            path.unlink(missing_ok=True)
        atoms_dir = folder / 'atoms'
        if atoms_dir.exists() and not any(atoms_dir.iterdir()):
            atoms_dir.rmdir()
    return verdict


def build_library(models, tasks, out, provider, seed):
    """Frozen atoms: one variant per source model, verified against the public single-feature test."""
    singles = [t for t in tasks if t['kind'] == 'single']
    library_path = out / 'library.json'
    library = json.loads(library_path.read_text()) if library_path.exists() else {}
    changed = False
    for atom_task in singles:
        atom = atom_task['name']
        entry = library.setdefault(atom, {'category': atom_task['category'], 'module': atom_task['module'], 'variants': []})
        for i, model in enumerate(models):
            variant = f'v{i + 1}'
            if any(v['variant'] == variant for v in entry['variants']):
                continue
            folder = PROBE / 'runs' / slug(model) / 'single' / atom_task['category'] / atom
            impl = folder / 'implementation.js'
            if not impl.exists() or not impl.read_text().strip():
                if provider is None:
                    raise SystemExit(f'atom {atom} for {model} missing; rerun with an API key to generate it')
                folder = out / 'atoms' / slug(model) / atom_task['category'] / atom
                generate_atom(provider, model, atom_task, folder, seed)
                impl = folder / 'implementation.js'
            code = impl.read_text()
            verdict = grade_files(atom_task['category'], atom_task['test'], {f'{atom_task["module"]}.js': code},
                                  out / 'atoms' / slug(model) / atom_task['category'] / atom / 'jest.json')
            entry['variants'].append({'variant': variant, 'origin': model, 'source_path': str(impl.relative_to(ROOT)),
                                      'code': code, 'sha256': compiler.sha256(code), 'verified': verdict['all_passed'],
                                      'single_tests': f'{verdict["passed"]}/{verdict["tests"]}'})
            changed = True
            print(f'atom {atom} {variant} ({model}): {verdict["passed"]}/{verdict["tests"]}', flush=True)
    if changed or not library_path.exists():
        dump(library_path, library)
    return library


def atoms_of(library, duo):
    return {a: library[a]['variants'] for a in duo['atoms']}


def run_arm(arm, model, duo, library, out, provider, seed, max_repairs, evaluate_only):
    record_path = out / 'record.json'
    if record_path.exists() and not evaluate_only:
        return json.loads(record_path.read_text())
    tests = Path(duo['test']).read_text()
    lib = atoms_of(library, duo)
    attempts = []
    record = {'arm': arm, 'model': model, 'category': duo['category'], 'name': duo['name'], 'atoms': duo['atoms'],
              'tests_expected': len(re.findall(r'^(?:test|it)\(', tests, flags=re.M)), 'attempts': attempts}
    if arm == 'rule':
        plan = compiler.rule_plan(duo, lib, prefer=model)
        attempt = {'plan': plan}
        try:
            compiled = compiler.compile_plan(plan, duo, lib, tests, checked=True)
            attempt.update({'compile_error': None, 'warnings': compiled['warnings'], 'selected': compiled['selected']})
            attempt['verdict'] = grade_files(duo['category'], duo['test'], compiled['files'], out / 'jest-1.json')
            dump(out / 'compiled-1.json', compiled['files'])
        except ValueError as error:
            attempt.update({'compile_error': str(error), 'verdict': None})
        attempts.append(attempt)
        dump(record_path, record)
        return record
    if arm == 'free':
        messages = [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': PROMPT.format(name=duo['module'], tests=tests)}]
    else:
        messages = [{'role': 'system', 'content': DNA_SYSTEM},
                    {'role': 'user', 'content': DNA_USER.format(name=duo['name'], tests=tests, library=compiler.library_prompt(duo, lib))}]
    for attempt_no in range(1, max_repairs + 2):
        attempt = {'attempt': attempt_no, 'compile_error': None, 'verdict': None}
        call_dir = out / f'call-{attempt_no}'
        if evaluate_only:
            saved = call_dir / 'response.json'
            if not saved.exists():
                break
            raw = json.loads(saved.read_text())['choices'][0]['message']['content'] or ''
        else:
            try:
                raw = provider.call(model, messages, call_dir, f'w1k-dna:{model}:{arm}:{duo["name"]}:a{attempt_no}', seed=seed)
            except BudgetStop:
                dump(record_path, record)
                raise
            except ProviderError as error:
                attempt['compile_error'] = f'ProviderError: {error}'
                attempts.append(attempt)
                break
        files = None
        try:
            parsed = parse_json(raw)
            if arm == 'free':
                code = parsed['code']
                if not isinstance(code, str) or not code.strip():
                    raise ValueError('code must be a non-empty string')
                files = {f'{duo["module"]}.js': code}
                attempt['code_sha256'] = compiler.sha256(code)
            else:
                attempt['plan'] = parsed
                compiled = compiler.compile_plan(parsed, duo, lib, tests, checked=True)
                files = compiled['files']
                attempt.update({'warnings': compiled['warnings'], 'selected': compiled['selected']})
        except (ValueError, KeyError, TypeError) as error:
            attempt['compile_error'] = f'{type(error).__name__}: {error}'
        if files is not None:
            dump(out / f'compiled-{attempt_no}.json', files)
            attempt['verdict'] = grade_files(duo['category'], duo['test'], files, out / f'jest-{attempt_no}.json')
        attempts.append(attempt)
        if attempt['verdict'] and attempt['verdict']['all_passed']:
            break
        if attempt_no > max_repairs:
            break
        feedback = ('The plan was rejected by the compiler:\n' + attempt['compile_error'] + '\nReturn a corrected plan as JSON only.'
                    if arm == 'dna' and attempt['compile_error'] else
                    ('Your output could not be used:\n' + attempt['compile_error'] + '\nReturn the full module again as JSON only.'
                     if attempt['compile_error'] else
                     jest_feedback(attempt['verdict']) + ('\nReturn a corrected plan as JSON only.' if arm == 'dna' else '\nReturn the corrected full module as JSON only.')))
        messages = messages + [{'role': 'assistant', 'content': raw}, {'role': 'user', 'content': feedback}]
    dump(record_path, record)
    return record


def outcome(record):
    attempts = record['attempts']
    def ok(a):
        return bool(a.get('verdict') and a['verdict']['all_passed'])
    def passed(a):
        return a['verdict']['passed'] if a.get('verdict') else 0
    first = attempts[0] if attempts else {}
    final = attempts[-1] if attempts else {}
    return {'first_pass': ok(first), 'final_pass': ok(final), 'first_assertions': passed(first), 'final_assertions': passed(final),
            'tests': (final.get('verdict') or {}).get('tests') or record.get('tests_expected', 4), 'attempts': len(attempts),
            'compile_errors': sum(1 for a in attempts if a.get('compile_error')),
            'timed_out': any((a.get('verdict') or {}).get('timed_out') for a in attempts)}


def summarize(models, arms, duos, records, library, ledger_summary, max_repairs):
    calls = ledger_summary.get('calls', [])
    def cost(prefix):
        return sum((c['actual'] or 0) for c in calls if c['purpose'].startswith(prefix)) / 1e6
    summary = {'date_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'max_repairs': max_repairs, 'arms': arms,
               'duos': [{k: d[k] for k in ['category', 'name', 'atoms']} for d in duos], 'models': [],
               'library': {a: [{k: v[k] for k in ['variant', 'origin', 'sha256', 'verified', 'single_tests']} for v in e['variants']]
                           for a, e in library.items()},
               'accounting': {k: v for k, v in ledger_summary.items() if k != 'calls'}}
    for model in models:
        entry = {'model': model, 'arms': {}, 'rows': []}
        for duo in duos:
            row = {'category': duo['category'], 'name': duo['name'], 'atoms': duo['atoms'],
                   'atoms_verified': {a: [v['variant'] for v in library[a]['variants'] if v['verified']] for a in duo['atoms']}}
            for arm in arms:
                rec = records.get((model, arm, duo['name']))
                row[arm] = outcome(rec) if rec else None
                if rec and arm != 'free':
                    last = rec['attempts'][-1] if rec['attempts'] else {}
                    row[arm]['plan'] = last.get('plan')
                    row[arm]['compile_error'] = last.get('compile_error')
            entry['rows'].append(row)
        for arm in arms:
            rows = [r[arm] for r in entry['rows'] if r[arm]]
            entry['arms'][arm] = {'n': len(rows), 'first_pass': sum(r['first_pass'] for r in rows), 'final_pass': sum(r['final_pass'] for r in rows),
                                  'first_assertions': sum(r['first_assertions'] for r in rows), 'final_assertions': sum(r['final_assertions'] for r in rows),
                                  'assertions': sum(r['tests'] for r in rows), 'calls': sum(r['attempts'] for r in rows) if arm != 'rule' else 0,
                                  'compile_errors': sum(r['compile_errors'] for r in rows), 'cost_usd': cost(f'w1k-dna:{model}:{arm}:')}
        if 'free' in arms and 'dna' in arms:
            pairs = [(r['free'], r['dna']) for r in entry['rows'] if r['free'] and r['dna']]
            entry['paired'] = {'dna_only': sum(d['final_pass'] and not f['final_pass'] for f, d in pairs),
                               'free_only': sum(f['final_pass'] and not d['final_pass'] for f, d in pairs),
                               'both': sum(f['final_pass'] and d['final_pass'] for f, d in pairs),
                               'neither': sum(not f['final_pass'] and not d['final_pass'] for f, d in pairs)}
        summary['models'].append(entry)
    return summary


def markdown(summary):
    arms = summary['arms']
    label = {'free': '自由代码（基线）', 'rule': '规则组装（零 API 控制）', 'dna': 'GUI-DNA 组装方案 + 编译检查'}
    lines = ['# WebApp1K-Duo：自由代码 vs 冻结原子函数组装（GUI-DNA）', '',
             f"生成时间 {summary['date_utc']}。{len(summary['duos'])} 个 Duo 任务，官方 CRA/Jest 评分，每任务 4 项断言；"
             f"三种做法同种子、同反馈协议（公开 Jest 失败回传，最多 {summary['max_repairs']} 轮修复）。", '',
             '| 模型 | 方法 | 首次通过 | 最终通过 | 首次断言 | 最终断言 | 调用次数 | 编译/解析拒绝 | 费用 |', '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for m in summary['models']:
        for arm in arms:
            a = m['arms'][arm]
            lines.append(f"| {m['model']} | {label[arm]} | {a['first_pass']}/{a['n']} | **{a['final_pass']}/{a['n']}** | {a['first_assertions']}/{a['assertions']} | "
                         f"{a['final_assertions']}/{a['assertions']} | {a['calls']} | {a['compile_errors']} | ${a['cost_usd']:.4f} |")
        if m.get('paired'):
            p = m['paired']
            lines.append(f"| {m['model']} | 配对（最终） | 仅 DNA 过 {p['dna_only']} | 仅自由过 {p['free_only']} | 都过 {p['both']} | 都败 {p['neither']} | | | |")
    lines.append('')
    for m in summary['models']:
        lines += [f"## {m['model']}：逐任务（最终断言 / 4）", '', '| 类别 | 组合任务 | ' + ' | '.join(label[a] for a in arms) + ' | 原子单测通过的变体 | DNA 计划 |',
                  '|---|---|' + '---:|' * len(arms) + '---|---|']
        for r in m['rows']:
            cells = []
            for arm in arms:
                o = r[arm]
                if not o:
                    cells.append('—')
                else:
                    tag = '过' if o['final_pass'] else ('超时' if o['timed_out'] else '败')
                    cells.append(f"{o['final_assertions']}/{o['tests']} {tag}" + (f"（首次 {o['first_assertions']}）" if o['attempts'] > 1 else ''))
            verified = '; '.join(f"{a}:{','.join(v) or '无'}" for a, v in r['atoms_verified'].items())
            plan = r.get('dna') or {}
            plan_text = ''
            if plan.get('plan'):
                p = plan['plan']
                plan_text = ' '.join(f"{a}={v}" for a, v in (p.get('select') or {}).items()) + (' relabel' if p.get('relabel') else '')
            if plan.get('compile_error'):
                plan_text += ' ⟂拒绝'
            lines.append(f"| {r['category']} | {r['name']} | " + ' | '.join(cells) + f" | {verified} | {plan_text} |")
        lines.append('')
    a = summary['accounting']
    lines += [f"账本（独立于第三轮与探针账本）：已结算 ${a['actual_usd']:.6f}，敞口 ${a['exposure_usd']:.6f}，未结算 {a['unsettled_calls']}。", '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--models', nargs='+', default=['deepseek/deepseek-v4-pro-0813', 'qwen/qwen3-coder'])
    parser.add_argument('--categories', nargs='+', default=['blogging', 'taskmanagement'])
    parser.add_argument('--per-category', type=int, default=5)
    parser.add_argument('--arms', nargs='+', default=['free', 'rule', 'dna'], choices=['free', 'rule', 'dna'])
    parser.add_argument('--max-repairs', type=int, default=2)
    parser.add_argument('--seed', type=int, default=20261101)
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT)
    parser.add_argument('--cap-usd', type=float, default=1.0)
    parser.add_argument('--stop-usd', type=float, default=0.8)
    parser.add_argument('--evaluate-only', action='store_true', help='re-grade saved outputs; no API calls')
    parser.add_argument('--summarize-only', action='store_true', help='rebuild summary from saved record.json files; no grading')
    parser.add_argument('--label', default='', help='suffix for the copies written to test/webapp1k_dna/results/')
    args = parser.parse_args()
    if not (STAGING / 'node_modules').exists():
        raise SystemExit('WebApp1k staging dependencies missing; see experiments/webapp1k_probe.py')
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    tasks = select_tasks(args.categories, args.per_category)
    duos = [t for t in tasks if t['kind'] == 'duo']
    config = {'models': args.models, 'temperature': 0.6, 'max_tokens': 4000, 'max_repairs': args.max_repairs, 'seed': args.seed,
              'budget_usd': args.cap_usd, 'stop_new_requests_usd': args.stop_usd,
              'price_caps_per_million': {'prompt': 3.0, 'completion': 15.0},
              'model_price_caps': {'deepseek/deepseek-v4-pro-0813': {'prompt': 1.3, 'completion': 2.6},
                                   'qwen/qwen3-coder': {'prompt': 0.65, 'completion': 3.25}}}
    ledger = Ledger(out / 'budget.sqlite3', args.cap_usd, args.stop_usd)
    paid = (not args.evaluate_only) and (not args.summarize_only) and any(a in args.arms for a in ['free', 'dna'])
    provider = OpenRouter(config, ledger) if paid else None
    dump(out / 'manifest.json', {'config': config, 'arms': args.arms, 'categories': args.categories, 'per_category': args.per_category,
                                 'tasks': tasks, 'atom_source': 'artifacts/benchmark-probe/runs/<model>/single (2026-10-30 one-shot) or generated here',
                                 'compiler_sha256': compiler.sha256((HERE / 'compiler.py').read_text()),
                                 'analyzer_sha256': compiler.sha256((HERE / 'analyze.js').read_text())})
    library = build_library(args.models, tasks, out, provider, args.seed)
    records, stopped = {}, None
    for model in args.models:
        for duo in duos:
            for arm in args.arms:
                folder = out / 'runs' / slug(model) / arm / duo['category'] / duo['name']
                try:
                    if args.summarize_only:
                        if not (folder / 'record.json').exists():
                            continue
                        rec = json.loads((folder / 'record.json').read_text())
                    else:
                        rec = run_arm(arm, model, duo, library, folder, provider, args.seed, args.max_repairs, args.evaluate_only)
                except BudgetStop as error:
                    stopped = str(error)
                    break
                o = outcome(rec)
                records[(model, arm, duo['name'])] = rec
                print(f"{model} {arm:4} {duo['category']}/{duo['name']}: {o['final_assertions']}/{o['tests']} attempts={o['attempts']}", flush=True)
            if stopped:
                break
        if stopped:
            print('STOPPED:', stopped, flush=True)
            break
    summary = summarize(args.models, args.arms, duos, records, library, ledger.summary(), args.max_repairs)
    summary['stopped'] = stopped
    dump(out / 'summary.json', summary)
    (out / 'summary.md').write_text(markdown(summary))
    RESULTS.mkdir(exist_ok=True)
    suffix = f'-{args.label}' if args.label else ''
    for name in ['summary.json', 'summary.md', 'library.json']:
        shutil.copy(out / name, RESULTS / (name.replace('.', f'{suffix}.', 1) if name != 'library.json' else name))
    print(json.dumps([{'model': m['model'], 'arms': m['arms'], 'paired': m.get('paired')} for m in summary['models']], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
