"""One independently frozen, three-workflow comparison on all form targets."""
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from gui_dna.budget import BudgetStop, Ledger
from gui_dna.provider import ProviderError, parse_json
from scripts.check_openrouter_credits import check_credits
from studies.interface_blind.core import (
    ROOT, UPSTREAM, compile_plan, config, dump, planner_messages, write_files,
)
from studies.interface_blind.evaluate import HARNESS, grade
from studies.ledger_read import totals
from studies.provider_ext import ReasoningAwareOpenRouter

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/form-library-sources-20261121'
SOURCE = UPSTREAM / 'projects/form'
AI = ROOT / 'artifacts/interface-blind-build-2/libraries/form/openai__gpt-5/package.json'
MODEL = 'mistralai/mistral-small-3.2-24b-instruct'
ARMS = ('reference', 'ai', 'direct')
TARGETS = [(arm, f'task-{n}') for n in range(1, 21) for arm in ARMS]
END = datetime.fromisoformat('2026-11-21T11:45:00+00:00')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def human_package():
    files = {str(p.relative_to(SOURCE / 'src')): p.read_text()
             for p in sorted((SOURCE / 'src/common').rglob('*.js'))}
    files['index.css'] = (SOURCE / 'src/index.css').read_text()
    files['index.html'] = (SOURCE / 'src-init/index.html').read_text()
    return {'files': files, 'compiler': (HERE / 'compiler.js').read_text(),
            'plan_schema': 'Return {questions:[{type: exact exported Question subclass name (or Question), args: positional constructor parameters, position:"prepend" or "append"}],surveyTitle:string or null,exportData:boolean}. Operations run in listed order. Null mounts directly in form. A survey title uses Survey. exportData binds an export button to survey serialization.'}


def freeze(packages):
    files = [HERE / 'run.py', HERE / 'compiler.js', HERE / 'PROTOCOL.md', AI, SOURCE / 'tasks.jsonl',
             SOURCE / 'src/index.css', SOURCE / 'src-init/index.html', *sorted((SOURCE / 'src/common').rglob('*.js'))]
    for path in sorted((SOURCE / 'test').rglob('*')):
        if path.is_file():
            assert sha(path) == sha(HARNESS / 'form/test' / path.relative_to(SOURCE / 'test'))
            files.append(path)
    for source in ('studies/interface_blind/core.py', 'studies/interface_blind/compile.cjs',
                   'studies/interface_blind/evaluate.py', 'studies/provider_ext.py', 'src/gui_dna/budget.py'):
        files.append(ROOT / source)
    dump(OUT / 'freeze.json', {str(p.relative_to(ROOT)): sha(p) for p in files})
    for arm, package in packages.items():
        if package:
            dump(OUT / f'{arm}-package.json', package)


def main():
    if datetime.now(timezone.utc) >= END or OUT.exists():
        raise SystemExit('Stage closed or already initialized')
    credits = check_credits(2.95)
    if not credits['sufficient']:
        raise SystemExit('Insufficient balance')
    dump(OUT / 'credits.json', credits)
    packages = {'reference': human_package(), 'ai': json.loads(AI.read_text()), 'direct': None}
    freeze(packages)
    cfg = config()
    cfg.update(models=[MODEL], max_tokens=8192, provider_order={}, budget_usd=2.95, stop_new_requests_usd=2.95)
    cfg['model_price_caps'][MODEL] = {'prompt': .2, 'completion': .8}
    ledger = Ledger(OUT / 'budget.sqlite3', 2.95, 2.95)
    client = ReasoningAwareOpenRouter(cfg, ledger)
    client.RATE_LIMIT_TRIES = 1

    def generate(key):
        arm, task = key
        folder = OUT / arm / task
        package = packages[arm]
        messages = planner_messages('form', task, 'plan' if package else 'free', package)
        if arm == 'reference':
            messages[-1]['content'] = messages[-1]['content'].replace('Frozen requirements-only library', 'Frozen reference-derived library')
        record = {'arm': arm, 'task': task, 'generated': False}
        try:
            if datetime.now(timezone.utc) >= END:
                raise BudgetStop('deadline reached')
            raw = client.call(MODEL, messages, folder / 'call', arm, seed=20261121)
            record['generated'] = True
            parsed = parse_json(raw)
            files = compile_plan(package, parsed) if package else parsed['files']
            write_files(folder / 'page', files)
            record['files'] = {name: sha(folder / 'page' / name) for name in files}
        except (ProviderError, BudgetStop, ValueError, KeyError, TypeError) as exc:
            record['error'] = str(exc)[:1000]
        dump(folder / 'record.json', record)
        return record

    with ThreadPoolExecutor(max_workers=3) as pool:
        first = list(pool.map(generate, TARGETS[:3]))
        if not any(r['generated'] for r in first):
            raise SystemExit('No endpoint returned a first batch response; stage stopped')
        records = first + list(pool.map(generate, TARGETS[3:]))
    dump(OUT / 'generation-complete.json', records)
    score(records)


def score(records):
    def one(record):
        folder = OUT / record['arm'] / record['task']
        passed = False if record['generated'] else None
        if 'files' in record:
            assert all(sha(folder / 'page' / n) == h for n, h in record['files'].items())
            result = grade('form', folder / 'page', record['task'], folder / 'official/report.json')
            passed = result['all_passed']
        return {k: record[k] for k in ('arm', 'task')} | {'passed': passed}

    with ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(one, records))
    dump(OUT / 'results.json', {'rows': rows, 'ledger': totals(OUT / 'budget.sqlite3')})
    print({arm: sum(r['passed'] is True for r in rows if r['arm'] == arm) for arm in ARMS})


if __name__ == '__main__':
    main()
