"""Exact saved-page equality and fixed-control score consistency diagnostics."""
from __future__ import annotations
import json
from collections import Counter
from .core import ROOT, PROJECTS, BUILDERS, PLANNERS, slug, digest, dump, compile_plan
from .frontier import MODEL, TASKS


def main():
    base = ROOT / 'artifacts/webbench-expand-run'
    frontier = ROOT / 'artifacts/webbench-expand-frontier-2'
    controls = json.loads((ROOT / 'artifacts/webbench-expand-controls/results.json').read_text())['rows']
    strong = json.loads((ROOT / 'test/results/webbench-expand-frontier.json').read_text())['fixed_control_rows']
    groups, inconsistencies = [], []
    for stage, models, tasks in ((base, PLANNERS, tuple(range(1, 21))), (frontier, (MODEL,), TASKS)):
        for project in PROJECTS:
            for builder in BUILDERS:
                package = json.loads((ROOT / 'artifacts/webbench-expand-build/libraries' / project / slug(builder) / 'package.json').read_text())
                examples = [digest(compile_plan(package, e['plan'])) for e in package['examples']]
                for model in models:
                    prefix = stage / 'runs' / project / slug(builder) / slug(model) / 'plan'

                    def saved(task):
                        folder = prefix / f'task-{task}'
                        record = json.loads((folder / 'record.json').read_text())
                        if not record['versions']:
                            return None
                        return json.loads((folder / record['versions'][-1] / 'source-manifest.json').read_text())['output_sha256']

                    final_hash = saved(20)
                    hashes, matched_examples, matched_final = [], [0, 0], 0
                    for task in tasks:
                        current = saved(task)
                        if not current:
                            continue
                        hashes.append(current)
                        observed = json.loads((prefix / f'task-{task}/hidden.json').read_text())['final']['all_passed']
                        if stage == base:
                            available = [r for r in controls if r['project'] == project and r['builder'] == builder and r['task'] == f'task-{task}']
                            scores = [next(r['passed'] for r in available if r['control'] == f'example-{i}') for i in range(2)]
                            fixed_score = next(r['passed'] for r in available if r['control'] == 'final-plan' and r['model'] == model)
                        else:
                            row = next(r for r in strong if r['project'] == project and r['builder'] == builder and r['task'] == f'task-{task}')
                            scores = [row[f'example-{i}'] for i in range(2)]
                            fixed_score = row['fixed_final']
                        for name, expected_hash, score in [(f'example-{i}', examples[i], scores[i]) for i in range(2)] + [('fixed-final', final_hash, fixed_score)]:
                            if current == expected_hash:
                                if name.startswith('example-'):
                                    matched_examples[int(name[-1])] += 1
                                else:
                                    matched_final += 1
                                if bool(score) != bool(observed):
                                    inconsistencies.append({'stage': stage.name, 'project': project, 'builder': builder, 'model': model,
                                        'task': f'task-{task}', 'control': name, 'per_task_passed': bool(observed), 'control_passed': bool(score),
                                        'output_sha256': current, 'in_predefined_sensitive_tasks': project == 'bom' and task in (7, 14, 19)})
                    groups.append({'stage': stage.name, 'project': project, 'builder': builder, 'model': model,
                        'tasks': len(tasks), 'executable_tasks': len(hashes), 'distinct_saved_file_maps': len(set(hashes)),
                        'exact_example0_matches': matched_examples[0], 'exact_example1_matches': matched_examples[1],
                        'exact_final_page_matches': matched_final})
    result = {'groups': groups, 'identical_page_score_disagreements': inconsistencies,
        'scope': 'Canonical hashes of full saved output file maps. Exact equality implies identical saved code; different hashes do not establish different behavior. Repeated-score disagreements are retained, not used for selective reruns or changing the predefined sensitivity set.'}
    dump(ROOT / 'test/results/webbench-expand-diagnostics.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
