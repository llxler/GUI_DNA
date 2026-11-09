"""Settled cost per study, recomputed from every ledger under artifacts/ (zero API, read-only).

    uv run python -m test.ledger_costs

Groups: the main ledger artifacts/budget.sqlite3 by purpose prefix (round 1 = generate + library + connectivity-probe,
round 2 = v2 + compact + linked, round 3 = scale); every other stage by directory prefix.  Ledger copies under
scale-study/checkpoints/ are skipped.  Prints a Markdown table and the LaTeX rows for the paper's cost table.
"""
from __future__ import annotations

import sqlite3
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN_GROUPS = {'generate': 'Pilot round 1', 'library': 'Pilot round 1', 'connectivity-probe': 'Pilot round 1',
               'v2': 'Pilot round 2', 'compact': 'Pilot round 2', 'linked': 'Pilot round 2', 'scale': 'List-16 (round 3)'}
DIR_GROUPS = [('benchmark-probe', 'WebApp1K-Duo (probe + comparison)'), ('webapp1k-dna-quartet', 'Not reported: WebApp1K Quartet attempt'),
              ('webapp1k-weak-baseline', 'Not reported: WebApp1K weak-baseline probe'), ('webapp1k-dna', 'WebApp1K-Duo (probe + comparison)'),
              ('todomvc-dna-5', 'TodoMVC, samples 3-5 (stage 5)'), ('todomvc-dna', 'TodoMVC, eight-model study (stages 1-4)'),
              ('webbench-dna-seed', 'Web-Bench dom1, seeds 2-3'), ('webbench-dna-frontier', 'Web-Bench dom1, GPT-5'),
              ('webbench-dna', 'Web-Bench dom1, eight-model study (stages 1-6)')]


def rows(path):
    db = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    try:
        return db.execute('SELECT purpose, actual, reserved FROM calls').fetchall()
    finally:
        db.close()


def main():
    settled, unsettled, calls, stages = defaultdict(float), defaultdict(float), defaultdict(int), defaultdict(set)
    for path in sorted(ROOT.glob('artifacts/**/budget.sqlite3')):
        if 'checkpoints' in path.parts:
            continue
        rel = path.relative_to(ROOT / 'artifacts')
        for purpose, actual, reserved in rows(path):
            if rel.parts[0] == 'budget.sqlite3':
                group = MAIN_GROUPS.get(purpose.split(':')[0], f'main ledger: {purpose.split(":")[0]}')
            else:
                group = next((g for prefix, g in DIR_GROUPS if rel.parts[0].startswith(prefix)), rel.parts[0])
            stages[group].add(str(rel.parent) if rel.parts[0] != 'budget.sqlite3' else 'budget.sqlite3')
            calls[group] += 1
            if actual is None:
                unsettled[group] += reserved / 1e6
            else:
                settled[group] += actual / 1e6
    reported = [g for g in settled if not g.startswith('Not reported')]
    print('| 阶段 | 账本 | 调用 | 已结算 (USD) | 未确认预留 (USD) |')
    print('|---|---|---:|---:|---:|')
    order = ['Pilot round 1', 'Pilot round 2', 'List-16 (round 3)', 'WebApp1K-Duo (probe + comparison)', 'TodoMVC, eight-model study (stages 1-4)',
             'TodoMVC, samples 3-5 (stage 5)', 'Web-Bench dom1, eight-model study (stages 1-6)', 'Web-Bench dom1, seeds 2-3', 'Web-Bench dom1, GPT-5']
    order += [g for g in settled if g not in order]
    for g in order:
        if g in settled or g in unsettled:
            print(f'| {g} | {len(stages[g])} | {calls[g]} | {settled[g]:.4f} | {unsettled[g]:.4f} |')
    total = sum(settled[g] for g in reported)
    print(f'| **合计（论文报告的实验）** | | | **{total:.4f}** | {sum(unsettled[g] for g in reported):.4f} |')
    print('\nLaTeX rows:')
    for g in order:
        if g in settled and not g.startswith('Not reported'):
            print(f'{g} & {settled[g]:.2f} \\\\')
    print(f'Total & {total:.2f} \\\\')
    for g in order:
        if g.startswith('Not reported'):
            print(f'{g} & {settled[g]:.2f} \\\\')


if __name__ == '__main__':
    main()
