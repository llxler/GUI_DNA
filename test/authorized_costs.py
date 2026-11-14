"""Read a dated authorization plan and all its ledgers without changing their limits."""
import argparse
import json
from pathlib import Path
import re

from test.ledger_read import totals

ROOT = Path(__file__).resolve().parents[1]


def summarize(date):
    if not re.fullmatch(r'\d{8}', date):
        raise ValueError('Date must be YYYYMMDD')
    plan = json.loads((ROOT / f'artifacts/review-{date}/budget-plan.json').read_text())
    stages = {}
    for name, allocation in plan['stages'].items():
        path = ROOT / 'artifacts' / name / 'budget.sqlite3'
        stages[name] = totals(path) if path.exists() else {
            'calls': 0, 'settled_usd': 0, 'exposure_usd': 0, 'unsettled_calls': 0,
            'cap_usd': allocation['cap'], 'stop_usd': allocation['stop'], 'not_started': True}
    result = {'date': plan['date'], 'authorization_usd': plan['authorized_usd'], 'stages': stages,
        'settled_usd': round(sum(v['settled_usd'] for v in stages.values()), 6),
        'exposure_usd': round(sum(v['exposure_usd'] for v in stages.values()), 6),
        'maximum_with_open_caps_usd': round(sum(v['exposure_usd'] if v['stop_usd'] == 0 else v['cap_usd'] for v in stages.values()), 6),
        'scope': 'New calls in this authorization only. Earlier unresolved reservations remain in their original closed ledgers. '
                 'Abandoned protocol-development calls are included. Local compute and human time are unpriced.'}
    assert result['maximum_with_open_caps_usd'] <= result['authorization_usd']
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date', required=True)
    args = parser.parse_args()
    result = summarize(args.date)
    (ROOT / f'test/results/review-{args.date}-costs.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
