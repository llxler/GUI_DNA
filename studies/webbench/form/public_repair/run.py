"""Post-hoc, one public format repair across all arms of the frozen form trial."""
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from gui_dna.budget import BudgetStop, Ledger
from gui_dna.provider import ProviderError, parse_json
from scripts.check_openrouter_credits import check_credits
from studies.form_library_sources.run import END, MODEL, OUT as FIRST, ROOT, sha
from studies.interface_blind.core import compile_plan, config, dump, write_files
from studies.interface_blind.evaluate import grade
from studies.ledger_read import totals
from studies.provider_ext import ReasoningAwareOpenRouter
from studies.study_io import read

OUT = ROOT / 'artifacts/form-public-repair-20261121'
HERE = Path(__file__).resolve().parent


def generate():
    if datetime.now(timezone.utc) >= END or OUT.exists():
        raise SystemExit('Stage closed or already initialized')
    first = read(FIRST / 'generation-complete.json')
    previous = sum(totals(p)['exposure_usd'] for p in (FIRST / 'budget.sqlite3', FIRST / 'continuation/budget.sqlite3'))
    chart_cap = totals(ROOT / 'artifacts/svg-chart-sources-20261121/budget.sqlite3')['cap_usd']
    credits = check_credits(.5)
    if not credits['sufficient'] or previous + chart_cap + .5 > 3.138999695:
        raise SystemExit('Insufficient funded exposure')
    files = [HERE / 'run.py', HERE / 'PROTOCOL.md', FIRST / 'generation-complete.json',
             FIRST / 'reference-package.json', FIRST / 'ai-package.json', FIRST / 'freeze.json']
    for rec in first:
        if rec['generated'] and 'files' not in rec:
            folder = FIRST / rec['arm'] / rec['task'] / 'call'
            files.extend((folder / 'request.json', folder / 'response.json'))
    dump(OUT / 'freeze.json', {'inputs':{str(p.relative_to(ROOT)):sha(p) for p in files},
                               'previous_exposure':previous,'reserved_svg_stage_cap':chart_cap,'credits':credits})
    cfg = config()
    cfg.update(models=[MODEL], max_tokens=8192, provider_order={}, budget_usd=.5, stop_new_requests_usd=.5)
    cfg['model_price_caps'][MODEL] = {'prompt':.2, 'completion':.8}
    client = ReasoningAwareOpenRouter(cfg, Ledger(OUT / 'budget.sqlite3', .5, .5))
    client.RATE_LIMIT_TRIES = 1
    packages = {a:read(FIRST / f'{a}-package.json') for a in ('ai','reference')}
    def one(rec):
        arm, task = rec['arm'], rec['task']
        row = {'arm':arm, 'task':task}
        if 'files' in rec or not rec['generated']:
            return row | {'reused':True}
        src = FIRST / arm / task / 'call'
        folder = OUT / arm / task
        messages = read(src / 'request.json')['body']['messages']
        messages += [{'role':'assistant','content':read(src / 'response.json')['choices'][0]['message']['content']},
                     {'role':'user','content':'Public format/compiler feedback: '+rec['error']+'\nReturn the complete corrected JSON output. No behavioral feedback is available.'}]
        row['generated'] = False
        try:
            if datetime.now(timezone.utc) >= END:
                raise BudgetStop('deadline')
            raw = client.call(MODEL, messages, folder / 'call', arm, seed=20261121)
            row['generated'] = True
            parsed = parse_json(raw)
            files = parsed['files'] if arm == 'direct' else compile_plan(packages[arm], parsed)
            write_files(folder / 'page', files)
            row['files'] = {n:sha(folder / 'page' / n) for n in files}
        except (ValueError,KeyError,TypeError,ProviderError,BudgetStop) as exc:
            row['error'] = str(exc)[:1000]
        dump(folder / 'record.json', row)
        return row
    with ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(one, first))
    dump(OUT / 'generation-complete.json',rows)


def score():
    rows = read(OUT / 'generation-complete.json')
    initial = {(r['arm'],r['task']):r['passed'] for r in read(FIRST / 'results.json')['rows']}
    def one(row):
        arm, task = row['arm'],row['task']
        folder = OUT / arm / task
        if row.get('reused'):
            passed = initial[arm,task]
        elif 'files' in row:
            assert all(sha(folder / 'page' / n)==h for n,h in row['files'].items())
            passed = grade('form', folder / 'page', task, folder / 'official/report.json')['all_passed']
        else:
            passed = False if row['generated'] else None
        return {'arm':arm,'task':task,'passed':passed,'reused':row.get('reused',False)}
    with ThreadPoolExecutor(max_workers=3) as pool:
        scores = list(pool.map(one,rows))
    dump(OUT / 'results.json', {'rows':scores,'ledger':totals(OUT / 'budget.sqlite3')})


if __name__ == '__main__':
    generate()
    score()
