"""Post-hoc reachability lower bounds from already scored legal plans only.

No search, model call, or browser execution. A successful saved run witnesses
one configuration on one official task file, not a universal correctness proof.
"""
from collections import Counter, defaultdict
from functools import lru_cache
import hashlib
import json
from pathlib import Path

from gui_dna.provider import parse_json
from .core import ROOT, PROJECTS, BUILDERS, PLANNERS, slug, digest, compile_plan, dump

MAIN = ROOT / 'artifacts/webbench-expand-run'
STRONG = ROOT / 'artifacts/webbench-expand-frontier-2'
CONTROL = ROOT / 'artifacts/webbench-expand-controls'


def read(path):
    return json.loads(path.read_text())


@lru_cache(maxsize=None)
def package(project, builder):
    return read(ROOT / 'artifacts/webbench-expand-build/libraries' / project / slug(builder) / 'package.json')


@lru_cache(maxsize=None)
def compile_cached(project, builder, plan_json):
    return compile_plan(package(project, builder), json.loads(plan_json))


def plan_page(folder, version, project, builder):
    index = version.removeprefix('version-')
    plan = parse_json(read(folder / f'output-{index}.json')['text'])
    page = folder / version
    source = read(page / 'source-manifest.json')
    files = compile_cached(project, builder, json.dumps(plan))
    assert digest(files) == source['output_sha256']
    assert {n: hashlib.sha256(s.encode()).hexdigest() for n, s in files.items()} == source['files_sha256']
    assert all((page / n).read_text() == s for n, s in files.items())
    return plan, page, digest(files)


def main():
    # The independent raw-report audit is a prerequisite, not a new evaluation.
    assert read(ROOT / 'test/results/webbench-expand-score-audit.json')['all_passed']
    evidence = defaultdict(list)
    outcomes = []

    def add(project, builder, task, plan, page, output_hash, score, score_path, kind):
        if not score['all_passed']:
            return
        evidence[project, builder, task].append({'kind': kind, 'plan': plan,
            'page': str(page.relative_to(ROOT)), 'output_sha256': output_hash,
            'score_path': str(score_path.relative_to(ROOT)), 'raw_report_sha256': score['report_sha256']})

    for stage in (MAIN, STRONG):
        for record_path in sorted((stage / 'runs').rglob('record.json')):
            record = read(record_path)
            if record['method'] != 'plan':
                continue
            project, builder, task = (record[k] for k in ('project', 'builder', 'task'))
            folder = record_path.parent
            scores = read(folder / 'hidden.json')
            outcomes.append({'stage': stage.name, 'project': project, 'builder': builder,
                             'model': record['model'], 'task': task, 'passed': scores['final']['all_passed'],
                             'page_hash': read(folder / record['versions'][-1] / 'source-manifest.json')['output_sha256'] if record['versions'] else None})
            if record['versions']:
                for label, version in dict(first=record['versions'][0], final=record['versions'][-1]).items():
                    if scores[label]['all_passed']:
                        plan, page, sha = plan_page(folder, version, project, builder)
                        add(project, builder, task, plan, page, sha, scores[label], folder / 'hidden.json', stage.name + '/' + label)
    for row in read(CONTROL / 'results.json')['rows']:
        project, builder, task, control, model = (row[k] for k in ('project', 'builder', 'task', 'control', 'model'))
        if not row['passed']:
            continue
        if control.startswith('example-'):
            plan = package(project, builder)['examples'][int(control[-1])]['plan']
            files = compile_cached(project, builder, json.dumps(plan))
            page = CONTROL / 'pages' / project / slug(builder) / control
            assert all((page / n).read_text() == s for n, s in files.items())
            sha = digest(files)
        else:
            folder = MAIN / 'runs' / project / slug(builder) / slug(model) / 'plan/task-20'
            version = read(folder / 'record.json')['versions'][-1]
            plan, page, sha = plan_page(folder, version, project, builder)
        score_path = CONTROL / 'scores' / project / slug(builder) / control / (slug(model) if model else 'none') / task / 'hidden.json'
        add(project, builder, task, plan, page, sha, read(score_path), score_path, control)
    frontier = read(ROOT / 'test/results/webbench-expand-frontier.json')
    for row in frontier['fixed_control_rows']:
        if not row['fixed_final']:
            continue
        project, builder, task = (row[k] for k in ('project', 'builder', 'task'))
        folder = STRONG / 'runs' / project / slug(builder) / slug(frontier['model']) / 'plan/task-20'
        version = read(folder / 'record.json')['versions'][-1]
        plan, page, sha = plan_page(folder, version, project, builder)
        path = STRONG / 'fixed-final' / project / slug(builder) / task / 'hidden.json'
        add(project, builder, task, plan, page, sha, read(path), path, 'gpt5-fixed-final')

    libraries = []
    for project in PROJECTS:
        for builder in BUILDERS:
            observed = [f'task-{k}' for k in range(1, 21) if evidence[project, builder, f'task-{k}']]
            libraries.append({'project': project, 'builder': builder, 'n': 20, 'with_observed_witness': len(observed),
                              'witness_tasks': observed, 'without_observed_witness': [f'task-{k}' for k in range(1, 21) if f'task-{k}' not in observed]})
    classes = defaultdict(Counter)
    for row in outcomes:
        witnesses = evidence[row['project'], row['builder'], row['task']]
        if row['passed']:
            category = 'passed'
        elif any(w['output_sha256'] == row['page_hash'] for w in witnesses):
            category = 'failed_but_identical_page_has_passing_run'
        elif witnesses:
            category = 'failed_with_different_page_witness'
        else:
            category = 'failed_without_observed_witness'
        row['category'] = category
        classes[row['stage']][category] += 1
    result = {'scope': 'Post-hoc union of observed successful legal plans and prespecified fixed controls; no new search or browser runs. Absence is not impossibility; a passing task file is not full-prefix correctness. Repeated-score disagreements are kept.',
              'library_task_pairs': 120, 'with_observed_witness': sum(r['with_observed_witness'] for r in libraries),
              'libraries': libraries, 'candidate_categories': {k: dict(v) for k, v in classes.items()},
              'outcomes': outcomes,
              'witnesses': [{'project': p, 'builder': b, 'task': t, 'observations': values} for (p, b, t), values in sorted(evidence.items()) if values]}
    dump(ROOT / 'test/results/webbench-expand-witnesses.json', result)
    print(json.dumps({k: v for k, v in result.items() if k not in ('outcomes', 'witnesses')}, indent=2))


if __name__ == '__main__':
    main()
