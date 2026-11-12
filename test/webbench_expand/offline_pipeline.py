"""Close generation spending, then grade and audit only after the cohort barrier."""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from gui_dna.budget import Ledger
from test.ledger_read import totals
from .core import ROOT, dump


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wait', action='store_true')
    args = parser.parse_args()
    stage = ROOT / 'artifacts/webbench-expand-run'
    barrier = stage / 'generation-complete.json'
    frontier = ROOT / 'artifacts/webbench-expand-frontier-2'
    frontier_barrier = frontier / 'generation-complete.json'
    while args.wait and not (barrier.exists() and frontier_barrier.exists()):
        time.sleep(30)
    data = json.loads(barrier.read_text())
    assert data['transport_incomplete'] == 0 and data['candidates'] == 600
    data = json.loads(frontier_barrier.read_text())
    assert data['transport_incomplete'] == 0 and data['candidates'] == 60
    Ledger(stage / 'budget.sqlite3', 5, 0)
    Ledger(frontier / 'budget.sqlite3', 2, 0)
    plan_path = ROOT / 'artifacts/review-20261112/budget-plan.json'
    plan = json.loads(plan_path.read_text())
    plan['stages']['webbench-expand-run'].update(stop=0, closed=True,
        final_exposure=totals(stage / 'budget.sqlite3')['exposure_usd'])
    plan['stages']['webbench-expand-frontier-2'].update(stop=0, closed=True,
        final_exposure=totals(frontier / 'budget.sqlite3')['exposure_usd'])
    plan['maximum_possible_exposure_usd'] = sum(v.get('final_exposure', v['cap']) if v.get('closed') else v['cap'] for v in plan['stages'].values())
    plan['unallocated_usd'] = 20 - plan['maximum_possible_exposure_usd']
    assert plan['unallocated_usd'] >= 0
    dump(plan_path, plan)
    env = dict(os.environ)
    env.pop('OPENROUTER_API_KEY', None)
    commands = [('test.review_daily_costs', []), ('test.webbench_expand.snapshot', []), ('test.webbench_expand.audit', []),
                ('test.webbench_expand.evaluate_pinned', ['--workers', '6']),
                ('test.webbench_expand.controls', ['--workers', '6']),
                ('test.webbench_expand.analyze', []),
                ('test.webbench_expand.evaluate_pinned', ['--stage', str(frontier), '--workers', '6']),
                ('test.webbench_expand.frontier_analyze', [])]
    for module, flags in commands:
        print('offline phase', module, flush=True)
        subprocess.run([sys.executable, '-m', module, *flags], cwd=ROOT, env=env, check=True)
    dump(stage / 'offline-complete.json', {'modules': [m for m, _ in commands], 'model_calls': 0})


if __name__ == '__main__':
    main()
