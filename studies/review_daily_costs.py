"""Read-only accounting for the 2026-11-12 authorization, including failed transports."""
from __future__ import annotations
import json
from pathlib import Path
from test.ledger_read import totals

ROOT = Path(__file__).resolve().parents[1]


def main():
    plan = json.loads((ROOT / 'artifacts/review-20261112/budget-plan.json').read_text())
    stages = {}
    for name, allocation in plan['stages'].items():
        path = ROOT / 'artifacts' / name / 'budget.sqlite3'
        stages[name] = totals(path) if path.exists() else {
            'calls': 0, 'settled_usd': 0, 'exposure_usd': 0, 'unsettled_calls': 0,
            'cap_usd': allocation['cap'], 'stop_usd': allocation['stop'], 'not_started': True}
    result = {'date': '2026-11-12', 'authorization_usd': plan['authorized_usd'], 'stages': stages,
              'settled_usd': round(sum(v['settled_usd'] for v in stages.values()), 6),
              'exposure_usd': round(sum(v['exposure_usd'] for v in stages.values()), 6),
              'maximum_with_open_caps_usd': round(sum(v['exposure_usd'] if v['stop_usd'] == 0 else v['cap_usd'] for v in stages.values()), 6),
              'scope': 'API ledger costs only; local compute and human time unpriced. Unknown transport charges retain full reservations.'}
    assert result['maximum_with_open_caps_usd'] <= result['authorization_usd'], 'Authorized daily cap exceeded'
    path = ROOT / 'test/results/review-20261112-costs.json'
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
