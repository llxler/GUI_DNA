"""Prespecified fixed examples, fixed final plans, and textual delta composition."""
from __future__ import annotations
import argparse
import hashlib
import json
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from test.interface_blind.core import ROOT, dump, digest, slug, write_files
from .core import BUILDERS, PLANNERS, STRONG, development_inputs, compile_plan
from .domain import PROJECTS, CLAUSES, heldout, strong_tasks
from .fixtures import cases
from .browser import evaluate


def changes(before, after, path=()):
    if before == after:
        return {}
    if isinstance(before, dict) and isinstance(after, dict):
        result = {}
        for key in sorted(set(before) | set(after)):
            child = (*path, key)
            if key not in after:
                result[child] = ('delete', None)
            elif key not in before:
                result[child] = ('set', deepcopy(after[key]))
            else:
                result.update(changes(before[key], after[key], child))
        return result
    return {path: ('set', deepcopy(after))}


def delta_plan(project, requirement, package):
    examples = {e['id']: e['plan'] for e in package['examples']}
    base = examples['dev-0']
    updates = {}
    for index, options in enumerate(CLAUSES[project]):
        present = [text in requirement for text in options]
        if sum(present) != 1:
            raise ValueError('Requirement must contain exactly one known sentence for each policy')
        if present[0]:
            continue
        dev = next(t for t in development_inputs(project) if options[1] in t['requirement'])
        delta = changes(base, examples[dev['id']])
        for path, operation in delta.items():
            if any(path[:len(other)] == other or other[:len(path)] == path for other in updates):
                raise ValueError('Conflicting development-plan updates at ' + repr(path))
            updates[path] = operation
    plan = deepcopy(base)
    for path, (operation, value) in updates.items():
        if not path:
            plan = deepcopy(value)
            continue
        parent = plan
        for key in path[:-1]:
            parent = parent[key]
        if operation == 'delete':
            parent.pop(path[-1])
        else:
            parent[path[-1]] = deepcopy(value)
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-stage', type=Path, default=ROOT / 'artifacts/heldout-composition-build')
    parser.add_argument('--main-stage', type=Path, default=ROOT / 'artifacts/heldout-composition-run')
    parser.add_argument('--strong-stage', type=Path, default=ROOT / 'artifacts/heldout-composition-strong')
    parser.add_argument('--out', type=Path, default=ROOT / 'artifacts/heldout-composition-controls')
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    out = args.out.resolve()
    for stage in (args.main_stage, args.strong_stage):
        assert (stage / 'grading-complete.json').exists()
    protocol = {'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'build': str(args.build_stage.resolve().relative_to(ROOT)),
                'main': str(args.main_stage.resolve().relative_to(ROOT)), 'strong': str(args.strong_stage.resolve().relative_to(ROOT)),
                'controls': 'All five development plans; task with four changed policies fixed; textual nonconflicting example deltas. No score-based selection.'}
    target = out / 'protocol.json'
    if target.exists():
        assert json.loads(target.read_text()) == protocol
    else:
        dump(target, protocol)
    jobs = []
    for project in PROJECTS:
        full_task = next(t for t in heldout(project) if sum(t['policy']) == 4)
        for builder in BUILDERS:
            library = args.build_stage / 'libraries' / project / slug(builder)
            record = json.loads((library / 'record.json').read_text())
            package = json.loads((library / 'package.json').read_text()) if record['status'] != 'failed' else None
            if package is not None:
                assert digest(package) == record['package_sha256']
            examples = {e['id']: e['plan'] for e in package['examples']} if package else {}
            for name in [f'dev-{i}' for i in range(5)] + ['delta']:
                for task in heldout(project):
                    folder = out / project / slug(builder) / name / task['id']
                    error, page = None, None
                    try:
                        if not package:
                            raise ValueError('Library unavailable')
                        plan = delta_plan(project, task['requirement'], package) if name == 'delta' else examples[name]
                        files = compile_plan(package, plan)
                        page = folder / 'page'
                        write_files(page, files)
                        dump(folder / 'plan.json', plan)
                        dump(folder / 'source.json', {'output_sha256': digest(files)})
                    except (ValueError, KeyError, TypeError) as exc:
                        error = str(exc)
                    jobs.append((project, builder, name, None, task, folder, page, error))
            for stage, models, tasks in ((args.main_stage, PLANNERS, heldout(project)), (args.strong_stage, (STRONG,), strong_tasks(project))):
                for model in models:
                    source = stage / 'runs' / project / slug(builder) / slug(model) / 'plan' / full_task['id']
                    candidate = json.loads((source / 'record.json').read_text())
                    page = source / candidate['versions'][-1] if candidate['versions'] else None
                    for task in tasks:
                        folder = out / project / slug(builder) / 'fixed-final' / slug(model) / task['id']
                        jobs.append((project, builder, 'fixed-final', model, task, folder, page, None if page else 'No executable final plan'))

    def one(job):
        project, builder, name, model, task, folder, page, error = job
        target = folder / 'hidden.json'
        if not target.exists():
            result = {'all_passed': False, 'reason': error} if page is None else evaluate(page, project, cases(project, task['policy']))
            dump(target, result)
        result = json.loads(target.read_text())
        return {'project': project, 'builder': builder, 'control': name, 'model': model, 'task': task['id'],
                'passed': bool(result['all_passed']), 'reason': result.get('reason'),
                'report_path': str(target.relative_to(ROOT)), 'report_sha256': hashlib.sha256(target.read_bytes()).hexdigest()}

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = []
        for i, row in enumerate(pool.map(one, jobs), 1):
            rows.append(row)
            if i % 20 == 0 or i == len(jobs):
                print('controls', i, '/', len(jobs), flush=True)
    assert len(rows) == 364
    dump(out / 'results.json', {'protocol': protocol, 'rows': rows})


if __name__ == '__main__':
    main()
