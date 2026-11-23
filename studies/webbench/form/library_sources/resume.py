"""Continue only undispatched slots after the November 21 process interruption."""
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from gui_dna.budget import BudgetStop, Ledger
from gui_dna.provider import ProviderError, parse_json
from scripts.check_openrouter_credits import check_credits
from studies.interface_blind.core import compile_plan, config, dump, planner_messages, write_files
from studies.ledger_read import calls, totals
from studies.provider_ext import ReasoningAwareOpenRouter
from .run import END, MODEL, OUT, ROOT, TARGETS, score, sha


def main():
    folder = OUT / 'continuation'
    if datetime.now(timezone.utc) >= END or (OUT / 'generation-complete.json').exists():
        raise SystemExit('Generation closed')
    if not all(sha(ROOT / k) == v for k, v in json.loads((OUT / 'freeze.json').read_text()).items()):
        raise SystemExit('Frozen input changed')
    original = totals(OUT / 'budget.sqlite3')
    cap = round(2.95 - original['exposure_usd'], 6)
    cfg = config()
    cfg.update(models=[MODEL], max_tokens=8192, provider_order={}, budget_usd=cap, stop_new_requests_usd=cap)
    cfg['model_price_caps'][MODEL] = {'prompt':.2, 'completion':.8}
    if not (folder / 'freeze.json').exists():
        credits = check_credits(cap)
        if not credits['sufficient']:
            raise SystemExit('Insufficient funds')
        dump(folder / 'freeze.json', {'original':original,'cap':cap,'credits':credits,'source':sha(Path(__file__)),
                                      'scope':'Only never-dispatched positions; no retries of interrupted calls.'})
    client = ReasoningAwareOpenRouter(cfg, Ledger(folder / 'budget.sqlite3', cap, cap))
    client.RATE_LIMIT_TRIES = 1
    known = {r['id']:r for path in (OUT / 'budget.sqlite3', folder / 'budget.sqlite3') for r in calls(path)}
    packages = {a:json.loads((OUT / f'{a}-package.json').read_text()) for a in ('ai','reference')}
    def one(job):
        arm, task = job
        dest = OUT / arm / task
        record_path = dest / 'record.json'
        if record_path.is_file():
            return json.loads(record_path.read_text())
        record = {'arm':arm,'task':task,'generated':False}
        package = packages.get(arm)
        messages = planner_messages('form', task, 'plan' if package else 'free', package)
        if arm == 'reference':
            messages[-1]['content'] = messages[-1]['content'].replace('Frozen requirements-only library','Frozen reference-derived library')
        try:
            request = dest / 'call/request.json'
            if request.exists():
                req = json.loads(request.read_text())
                assert req['body']['messages'] == messages
                if known[req['call_id']]['actual'] is None or not (dest / 'call/response.json').exists():
                    raise ProviderError('Interrupted after reservation; no complete settled response. Not resent.')
                raw = json.loads((dest / 'call/response.json').read_text())['choices'][0]['message']['content']
            else:
                if datetime.now(timezone.utc) >= END:
                    raise BudgetStop('deadline')
                raw = client.call(MODEL, messages, dest / 'call', arm, seed=20261121)
            record['generated'] = True
            parsed = parse_json(raw)
            files = compile_plan(package, parsed) if package else parsed['files']
            write_files(dest / 'page', files)
            record['files'] = {name:sha(dest / 'page' / name) for name in files}
        except (BudgetStop,ProviderError,ValueError,KeyError,TypeError) as exc:
            record['error'] = str(exc)[:1000]
        dump(record_path,record)
        return record
    with ThreadPoolExecutor(max_workers=3) as pool:
        records = list(pool.map(one,TARGETS))
    dump(OUT / 'generation-complete.json', records)
    score(records)


if __name__ == '__main__':
    main()
