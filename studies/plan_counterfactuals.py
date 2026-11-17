"""Post-hoc interventions on failed Web-Bench plans, without model calls or prompt changes.

Replace variants, menus, or both with the reference choices. This distinguishes
mere disagreement with a reference plan from changes that repair observed tests.
Original runs are never edited. Results are diagnostic, not new model successes.
"""
from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from test.review_checks import ROOT, saved_plan
from test.webbench_dna import domain, evaluate
from test.webbench_dna.library import SLOTS, SLOT_FEATURE, library

OUT = ROOT / 'artifacts/plan-counterfactuals'


def units():
    summary = json.loads((ROOT / 'test/webbench_dna/results/summary.json').read_text())
    tasks = {t['id']: t for t in domain.tasks()}
    for model in summary['models']:
        for row in model['rows']:
            if not row['dna']['final_all']:
                yield model['model'], tasks[row['task']], saved_plan('webbench', model['model'], row)


def grade(unit):
    model, task, plan = unit
    result = {'model': model, 'task': task['id'], 'executable': isinstance(plan, dict)}
    if not result['executable']:
        return result
    reference = domain.reference_plan(task['features'])
    for change in ['variants', 'menu', 'both']:
        fixed = copy.deepcopy(plan)
        if change in ('variants', 'both'):
            fixed.update({s: reference[s] for s in SLOTS if SLOT_FEATURE[s] in task['features']})
        if change in ('menu', 'both'):
            fixed['menu'] = copy.deepcopy(reference['menu'])
        folder = OUT / model.replace('/', '__') / task['id'] / change
        code = domain.compile_plan(fixed, task['features'], library())
        cache = folder / 'result.json'
        if cache.exists():
            saved = json.loads(cache.read_text())
            if saved['code_sha256'] != evaluate.sha256(code):
                raise ValueError(f'{folder}: changed intervention')
            scored = saved['score']
        else:
            evaluate.write_candidate(folder, script=code)
            scored = evaluate.grade(folder, task, folder / 'report.json')
            if not scored['total'] or scored.get('note'):
                raise RuntimeError(f'{folder}: harness failure')
            cache.write_text(json.dumps({'code_sha256': evaluate.sha256(code), 'score': scored}, indent=2) + '\n')
        result[change] = scored['all_passed']
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(grade, units()))
    counts = Counter()
    for row in rows:
        if not row['executable']:
            counts['no_executable'] += 1
        elif row['menu'] and not row['variants']:
            counts['menu_sufficient'] += 1
        elif row['variants'] and not row['menu']:
            counts['variants_sufficient'] += 1
        elif row['menu'] and row['variants']:
            counts['either_sufficient'] += 1
        elif row['both']:
            counts['joint_repair_required'] += 1
        else:
            counts['unresolved'] += 1
    data = {'scope': 'post-hoc; original model scores unchanged', 'counts': dict(counts), 'rows': rows}
    path = ROOT / 'test/results/plan-counterfactuals.json'
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(counts, indent=2))


if __name__ == '__main__':
    main()
