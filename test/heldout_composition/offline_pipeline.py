"""Wait for both complete cohorts, close spending, then score without API keys."""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from gui_dna.budget import Ledger
from test.interface_blind.core import ROOT, dump
from test.ledger_read import totals


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wait', action='store_true')
    parser.add_argument('--build-stage', type=Path, default=ROOT / 'artifacts/heldout-composition-build')
    parser.add_argument('--main-stage', type=Path, default=ROOT / 'artifacts/heldout-composition-run')
    parser.add_argument('--strong-stage', type=Path, default=ROOT / 'artifacts/heldout-composition-strong')
    args = parser.parse_args()
    stages = [args.main_stage.resolve(), args.strong_stage.resolve()]
    while args.wait and not all((stage / 'generation-complete.json').exists() for stage in stages):
        time.sleep(15)
    for stage, expected in zip(stages, (220, 24)):
        barrier = json.loads((stage / 'generation-complete.json').read_text())
        assert barrier['candidates'] == expected and barrier['transport_incomplete'] == 0
    plan_path = ROOT / 'artifacts/review-20261112/budget-plan.json'
    plan = json.loads(plan_path.read_text())
    for stage in stages:
        cost = totals(stage / 'budget.sqlite3')
        Ledger(stage / 'budget.sqlite3', cost['cap_usd'], 0)
        plan['stages'][stage.name].update(stop=0, closed=True, final_exposure=cost['exposure_usd'])
    maximum = sum(row['final_exposure'] if row.get('closed') else row['cap'] for row in plan['stages'].values())
    assert maximum <= plan['authorized_usd']
    plan['maximum_possible_exposure_usd'], plan['unallocated_usd'] = round(maximum, 6), round(20 - maximum, 6)
    dump(plan_path, plan)
    env = dict(os.environ)
    env.pop('OPENROUTER_API_KEY', None)
    common = ['--main-stage', str(stages[0]), '--strong-stage', str(stages[1])]
    modules = [('test.review_daily_costs', []),
               ('test.heldout_composition.evaluate', common),
               ('test.heldout_composition.controls', ['--build-stage', str(args.build_stage.resolve()), *common]),
               ('test.heldout_composition.analyze', ['--build-stage', str(args.build_stage.resolve()), *common])]
    for module, flags in modules:
        print('offline phase', module, flush=True)
        subprocess.run([sys.executable, '-m', module, *flags], cwd=ROOT, env=env, check=True)
    dump(stages[0] / 'offline-complete.json', {'modules': [m for m, _ in modules], 'model_calls': 0})


if __name__ == '__main__':
    main()
