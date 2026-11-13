"""Reconcile archived interrupted calls using provider-confirmed charges only.

GET metadata does not generate content. No charge is inferred from connection
errors or missing records; those reservations remain untouched.
"""
import argparse
import json
import os
import httpx
from gui_dna.budget import Ledger
from test.ledger_read import calls, totals
from .core import OUT, read, dump, config
from .run import now

FIELDS = ('id', 'model', 'total_cost', 'usage', 'cancelled', 'finish_reason',
          'native_finish_reason', 'generation_time', 'latency', 'tokens_prompt',
          'tokens_completion', 'native_tokens_prompt', 'native_tokens_completion',
          'native_tokens_reasoning', 'provider_name', 'created_at')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    initial = totals(OUT / 'budget.sqlite3')
    pending = {r['id'] for r in calls(OUT / 'budget.sqlite3') if r['actual'] is None}
    ledger = Ledger(OUT / 'budget.sqlite3', config()['budget_usd'], initial['stop_usd']) if args.apply else None
    rows = []
    for path in sorted((OUT / 'discarded-transport').rglob('request.json')):
        request = read(path)
        if request['call_id'] not in pending:
            continue
        stream = path.with_name('stream-events.jsonl')
        ids = set()
        if stream.exists():
            for line in stream.read_text().splitlines():
                event = json.loads(line)
                if event.get('id'):
                    ids.add(event['id'])
        if len(ids) != 1:
            continue
        generation_id = ids.pop()
        target = OUT / 'billing-reconciliation' / (request['call_id'] + '.json')
        if target.exists():
            receipt = read(target)
        else:
            try:
                response = httpx.get('https://openrouter.ai/api/v1/generation', params={'id': generation_id},
                    headers={'Authorization': 'Bearer ' + os.environ['OPENROUTER_API_KEY']}, timeout=30, trust_env=False)
                response.raise_for_status()
                data = response.json()['data']
            except (httpx.HTTPError, KeyError, ValueError) as error:
                print('metadata unavailable', path.relative_to(OUT), type(error).__name__, flush=True)
                continue
            assert data['id'] == generation_id
            receipt = {'checked_utc': now(), 'source_request': str(path.relative_to(OUT)),
                       'call_id': request['call_id'], 'metadata': {k: data.get(k) for k in FIELDS}}
            dump(target, receipt)
        metadata = receipt['metadata']
        cost = metadata['total_cost']
        if not isinstance(cost, (float, int)) or cost < 0:
            continue
        if not (metadata.get('finish_reason') or metadata.get('cancelled')):
            print('generation not confirmed terminal', path.relative_to(OUT), flush=True)
            continue
        if ledger:
            ledger.settle(request['call_id'], cost, generation_id=generation_id,
                          usage={'cost': cost, 'source': 'GET /api/v1/generation', 'reconciled_interrupted_transport': True})
        rows.append({'source_request': str(path.relative_to(OUT)), 'cost': cost, 'applied': args.apply})
        print('confirmed interrupted charge', cost, path.relative_to(OUT), flush=True)
    dump(OUT / 'billing-reconciliation' / ('applied.json' if args.apply else 'preview.json'),
         {'before': initial, 'after': totals(OUT / 'budget.sqlite3'), 'rows': rows,
          'policy': 'Only provider-confirmed terminal charges; unknown connections remain reserved.'})


if __name__ == '__main__':
    main()
