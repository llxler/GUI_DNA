"""Validate generation seals and report independently matched Web-Bench outcomes."""
from collections import defaultdict
from studies.study_io import ROOT, digest, read, sha
from .browser import OUT, PROJECTS, TASKS, evaluate, lock, verify_contract, verify_page, verify_receipt, write_json

MILESTONES = (4, 8, 12, 16, 20)
FIELDS = ('project', 'arm', 'builder', 'rep', 'planner')


def enrolled_tasks(root, projects):
    scopes = {
        'public-library-transfer-remote-milestones-20261123': {'canvas', 'flex'},
        'public-library-transfer-remote-20261123': {'draw'},
    }
    sparse = scopes.get(root.name, set())
    return {p: MILESTONES if p in sparse else TASKS for p in projects}


def manifest_targets(rows):
    """Existing collectors can seal full or milestone panels; scoring also checks registration."""
    projects = defaultdict(set)
    for row in rows:
        projects[row['project']].add(row['task'])
    return {p: MILESTONES if values == set(MILESTONES) else TASKS for p, values in projects.items()}


def group_key(row):
    return tuple(row[k] for k in FIELDS)


def grouped(rows):
    groups = defaultdict(dict)
    for row in rows:
        key, task = group_key(row), row['task']
        if task in groups[key]:
            raise ValueError(f'Duplicate sealed target {key}/{task}')
        groups[key][task] = row
    return groups


def validate_rows(rows, targets=None):
    if not isinstance(rows, list) or not rows:
        raise ValueError('The seal must declare at least one complete project group')
    if targets is None:
        targets = manifest_targets(rows)
    for row in rows:
        project, arm, builder, rep, planner = group_key(row)
        allowed = targets[project]
        if project not in PROJECTS or type(row['task']) is not int or row['task'] not in allowed:
            raise ValueError(f'Invalid project or task: {project}/{row["task"]}')
        if type(rep) is not int or arm not in ('direct', 'plan', 'fixed'):
            raise ValueError(f'Invalid method or replicate: {arm}/{rep}')
        if (arm == 'direct') != (builder is None and rep == 0):
            raise ValueError('Direct generation has a shared replicate 0 and no builder')
        if arm != 'direct' and (not isinstance(builder, str) or not builder or rep < 1):
            raise ValueError('Library methods must identify the builder and positive replicate')
        if (arm == 'fixed' and planner is not None) or (arm != 'fixed' and (not isinstance(planner, str) or not planner)):
            raise ValueError('Identify the planner for direct and plan rows, and use null for fixed')
        if row['status'] == 'valid':
            if not row.get('page') or not row.get('files'):
                raise ValueError('A valid response requires a sealed page')
        elif row['status'] not in ('missing', 'invalid', 'build_failed') or row.get('page') or row.get('files'):
            raise ValueError(f'Invalid generation status or unexpected page: {row["status"]}')
    for key, by_task in grouped(rows).items():
        allowed = targets[key[0]]
        if set(by_task) != set(allowed):
            raise ValueError(f'{key}: expected explicit rows for the preregistered targets {allowed}')
        if key[1] == 'fixed':
            manifests = {digest(r['files']) for r in by_task.values() if r['status'] == 'valid'}
            if len(manifests) > 1:
                raise ValueError(f'{key}: the fixed control must use one identical page across tasks')


def observed(row):
    if row['status'] == 'missing':
        return None
    if row['status'] in ('invalid', 'build_failed'):
        return False
    if type(row['passed']) is not bool:
        raise ValueError('A valid page requires an official score')
    return row['passed']


def counts(rows):
    return {'planned': len(rows), 'known': sum(observed(r) is not None for r in rows),
            'passed': sum(observed(r) is True for r in rows), 'browser_tested': sum(r['status'] == 'valid' for r in rows),
            'browser_failed': sum(r['status'] == 'valid' and not r['passed'] for r in rows),
            'invalid': sum(r['status'] == 'invalid' for r in rows),
            'build_failed': sum(r['status'] == 'build_failed' for r in rows),
            'missing': sum(r['status'] == 'missing' for r in rows)}


def comparison(plan, other, targets):
    pairs = []
    unknown = []
    same_page = 0
    for task in targets:
        left, right = plan[task], other[task]
        values = (observed(left), observed(right))
        if None in values:
            unknown.append(task)
        else:
            pairs.append(values)
        if left['status'] == right['status'] == 'valid' and left['files'] == right['files']:
            same_page += 1
    return {'planned': len(targets), 'paired': len(pairs), 'missing_tasks': unknown,
            'plan_passed': sum(a for a, _ in pairs), 'comparator_passed': sum(b for _, b in pairs),
            'both': pairs.count((True, True)), 'plan_only': pairs.count((True, False)),
            'comparator_only': pairs.count((False, True)), 'neither': pairs.count((False, False)),
            'same_valid_page': same_page}


def summarize(scored, targets=None):
    if targets is None:
        targets = manifest_targets(scored)
    groups = grouped(scored)
    arms, paired = [], []
    bom_source = ROOT / 'studies/results/end_to_end.json'
    includes_bom = any(k[0] == 'bom' for k in groups)
    bom_excluded = ({int(v.removeprefix('task-')) for v in read(bom_source)['bom_sensitivity']['excluded_tasks']}
                    if includes_bom else set())
    for key, by_task in groups.items():
        group = dict(zip(FIELDS, key))
        arms.append({**group, 'all_tasks': counts(list(by_task.values())),
                     'milestones': counts([by_task[n] for n in MILESTONES])})
        project, arm, builder, rep, planner = key
        allowed = targets[project]
        retained = [n for n in allowed if n not in bom_excluded]
        if project == 'bom':
            arms[-1]['bom_sensitivity'] = counts([by_task[n] for n in retained])
        if arm != 'plan':
            continue
        for other_key in ((project, 'direct', None, 0, planner), (project, 'fixed', builder, rep, None)):
            if other_key not in groups:
                continue
            paired.append({**group, 'comparator': other_key[1],
                           'all_tasks': comparison(by_task, groups[other_key], allowed),
                           'milestones': comparison(by_task, groups[other_key], MILESTONES)})
            if project == 'bom':
                paired[-1]['bom_sensitivity'] = comparison(by_task, groups[other_key], retained)
    result = {'groups': arms, 'pairs': paired}
    if includes_bom:
        result['bom_sensitivity_source'] = {'excluded_tasks': sorted(bom_excluded),
                                             'path': str(bom_source.relative_to(ROOT)), 'sha256': sha(bom_source)}
    return result


def contents(rows):
    return sorted(digest(r) for r in rows)


def verify_global_file(root, seal):
    for field in ('register_sha256', 'registration_sha256'):
        if field in seal and seal[field] != sha(root / 'registered.json'):
            raise ValueError('Global seal points to a different registration')
    if 'project_seals' in seal:
        expected = {r['project'] for r in seal['rows']}
        if set(seal['project_seals']) != expected:
            raise ValueError('Global seal omits a project manifest')
        for name, fingerprint in seal['project_seals'].items():
            if sha(root / 'project-seals' / f'{name}.json') != fingerprint:
                raise ValueError(f'Globally frozen project manifest changed: {name}')


def audit(root):
    """Validate a published cohort from original sealed inputs and browser reports, without executing a browser."""
    path = root / 'scoring.json'
    full = read(path)
    public = read(ROOT / 'studies/results' / f'{root.name}.json')
    generation = root / 'generation-sealed.json'
    if sha(path) != public['scoring_sha256'] or sha(generation) != full['generation_sha256']:
        raise ValueError('The published claim does not match its stored evidence')
    frozen = read(generation)
    verify_global_file(root, frozen)
    inputs = frozen['rows']
    targets = enrolled_tasks(root, {r['project'] for r in inputs})
    validate_rows(inputs, targets)
    if len(inputs) != len(full['rows']) or len(inputs) != len(public['rows']):
        raise ValueError('A generation record was omitted')
    protocols = {p: digest(verify_contract(p)) for p in full['contracts']}
    if public['contract_sha256'] != protocols or protocols != {p: digest(v) for p, v in full['contracts'].items()}:
        raise ValueError('The historical evaluation environment differs from the published one')
    checked = {}
    for row, result, compact in zip(inputs, full['rows'], public['rows']):
        if (any(result[k] != v for k, v in row.items())
                or any(compact[k] != result[k] for k in (*FIELDS, 'task', 'status', 'passed', 'report', 'report_sha256'))
                or compact['files_digest'] != (digest(row['files']) if row['files'] else None)):
            raise ValueError('A published target differs from the generation or scoring manifest')
        if row['status'] != 'valid':
            if result['report'] is not None or result['passed'] is not None:
                raise ValueError('Non-executable generation has an unexpected browser result')
            continue
        project, task, fingerprint = row['project'], row['task'], digest(row['files'])
        verify_page(ROOT / row['page'], row['files'], project)
        key = (project, task, fingerprint)
        if key not in checked:
            expected = {'project': project, 'task': task, 'files_digest': fingerprint, 'contract_digest': protocols[project]}
            checked[key] = verify_receipt(root, root / 'browser/scores' / project / f'task-{task}' / fingerprint / 'score.json', expected)
        receipt = checked[key]
        if any(result[k] != receipt[k] for k in ('report', 'passed', 'report_sha256')):
            raise ValueError('A target differs from its official test report')
    if any(public[k] != v for k, v in summarize(full['rows'], targets).items()):
        raise ValueError('Published denominators or paired outcomes do not reproduce')
    return len(inputs), len(checked)


def score(root, project=None, workers=3):
    global_seal = root / 'generation-sealed.json'
    seal = root / 'project-seals' / f'{project}.json' if project else global_seal
    if not seal.is_file():
        raise FileNotFoundError(f'No sealed generation manifest at {seal}')
    initial_sha = sha(seal)
    frozen = read(seal)
    if not project:
        verify_global_file(root, frozen)
    rows = frozen['rows']
    targets = enrolled_tasks(root, {r['project'] for r in rows})
    validate_rows(rows, targets)
    projects = sorted({r['project'] for r in rows})
    if project and projects != [project]:
        raise ValueError(f'{seal} must contain exactly {project}')
    if not project:
        omitted = {p.stem for p in (root / 'project-seals').glob('*.json')} - set(projects)
        if omitted:
            raise ValueError(f'Global seal omitted already frozen projects: {sorted(omitted)}')
    for name in projects:
        single = root / 'project-seals' / f'{name}.json'
        if global_seal.exists() and single.exists():
            aggregate = [r for r in read(global_seal)['rows'] if r['project'] == name]
            if contents(read(single)['rows']) != contents(aggregate):
                raise ValueError(f'Frozen {name} rows differ from global seal')
    protocols = {p: verify_contract(p) for p in projects}
    scored = evaluate(rows, root, protocols, workers)
    if sha(seal) != initial_sha:
        raise ValueError('Generation manifest changed during scoring')
    calibration = {}
    for name in projects:
        checkpoint = OUT / 'browser/calibration' / name / 'tasks-20.json'
        controls = read(checkpoint)
        if (digest(controls['contract']) != digest(protocols[name])
                or {(r['arm'], r['task']) for r in controls['rows']} != {('reference', 20), ('blank', 20)}):
            raise ValueError(f'Control in different project environment: {checkpoint}')
        for row in controls['rows']:
            if sha(OUT / row['report']) != row['report_sha256']:
                raise ValueError(f'Control report differs: {checkpoint}')
        calibration[name] = {'path': str(checkpoint.relative_to(ROOT)), 'sha256': sha(checkpoint),
                             'reference_passed': next(r['passed'] for r in controls['rows'] if r['arm'] == 'reference'),
                             'blank_passed': next(r['passed'] for r in controls['rows'] if r['arm'] == 'blank')}
    info = {'generation_seal': str(seal.relative_to(ROOT)), 'generation_sha256': initial_sha,
            'definition': 'One current official file per target. Invalid responses and failed builds are known pipeline failures. Missing responses are unknown. Pairs use the same project, target and deployment model; fixed pages share builder and replicate.',
            'milestone_tasks': list(MILESTONES), 'task20_calibration': calibration, 'contracts': protocols, 'rows': scored}
    if any(v != TASKS for v in targets.values()):
        info['enrolled_tasks_by_project'] = {k: list(targets[k]) for k in sorted(targets)}
    result = summarize(scored, targets)
    path = root / 'browser/project-scores' / f'{project}.json' if project else root / 'scoring.json'
    with lock(path.with_suffix('.lock')):
        if path.exists() and read(path) != info:
            raise ValueError(f'Existing scoring evidence differs: {path}')
        write_json(path, info)
        if not project:
            compact = [{**{k: r[k] for k in (*FIELDS, 'task', 'status', 'passed', 'report', 'report_sha256')},
                        'files_digest': digest(r['files']) if r['files'] else None,
                        **{k: r[k] for k in ('reused_from','source_receipt_sha256') if k in r}} for r in scored]
            public = {k: v for k, v in info.items() if k not in ('contracts', 'rows')}
            public.update({'scoring': str(path.relative_to(ROOT)), 'scoring_sha256': sha(path),
                           'contract_sha256': {p: digest(v) for p, v in protocols.items()},
                           'rows': compact, **result})
            dest = ROOT / 'studies/results' / f'{root.name}.json'
            if dest.exists() and read(dest) != public:
                previous = read(dest)
                if previous.get('scoring_sha256') != public['scoring_sha256'] or previous.get('rows') != public['rows']:
                    raise ValueError(f'Published summary differs from sealed evidence: {dest}')
                write_json(root / 'browser/derived-history' / f'{sha(dest)}.json', previous)
            write_json(dest, public)
    return result
