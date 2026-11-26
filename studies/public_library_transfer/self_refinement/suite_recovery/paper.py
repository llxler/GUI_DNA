"""Align the first registered rebuild to its genuine original comparison arms."""
from studies.study_io import ROOT, read, sha

WEB = ROOT/'studies/webbench/self_build_modules/module_links/result.json'
OPTIONS = WEB.parents[1]/'observed_options/result.json'
ENTRY = WEB.parents[1]/'entry_recovery/result.json'
MODULES = WEB.parents[1]/'source_delivery/result.json'
SUITES = ROOT/'studies/public_library_transfer/self_refinement/suite_recovery/result.json'
CONFIRM = SUITES.parent/'duo_confirmation/result.json'
DUO_RECEIVER = SUITES.parent/'duo_delivery/result.json'
SOURCES = (WEB, OPTIONS, ENTRY, MODULES, SUITES, DUO_RECEIVER, CONFIRM)


def cohorts():
    for path in (WEB, SUITES, CONFIRM):
        data=read(path)
        if path==WEB:
            assert data['options_result_sha256']==sha(OPTIONS) and read(OPTIONS)['entry_result_sha256']==sha(ENTRY)
            assert read(ENTRY)['primary_result_sha256']==sha(MODULES)
        if path==CONFIRM:
            assert data['pilot_sha256']==sha(DUO_RECEIVER)
        for cell in data['cells']:
            confirmed_cell=(cell['project']=='duo' and cell['model']=='mistralai/mistral-small-3.2-24b-instruct')
            if path==SUITES and confirmed_cell:
                continue
            if path==CONFIRM:
                assert confirmed_cell
            yield path, cell


def paired(cell, rep):
    build = cell['builds'][rep]
    old_targets = cell['original_shared']
    controls = [a for a in ('direct','human','gpt5-library') if a in cell['original']]
    if 'groups' in build:
        admitted = [t for t in old_targets if build['arms']['fixed'][str(t)]['status'] == 'valid']
        state = 'valid' if admitted else ('missing' if 'missing' in build['groups'].values() else 'build_failed')
        origin='controller' if cell['project']=='todomvc' else 'components'
    else:
        state=build['status']
        admitted=old_targets if state=='valid' else []
        origin=build['preparation']
    eligible=[t for t in admitted if build['arms']['self'][str(t)]['passed'] is not None]
    complete=bool(admitted) and eligible==admitted
    targets=eligible if complete else old_targets
    values={a:sum(cell['original'][a][str(t)] for t in targets) for a in controls}
    group=dict(n=len(targets),targets=targets,passed=values,preparation=origin,build_status=state,
               eligible=admitted,observed=eligible,rep=rep,complete=complete,seal_sha256=build['seal_sha256'])
    if complete:
        values['self']=sum(build['arms']['self'][str(t)]['passed'] for t in targets)
        group['fixed_passed']=sum(build['arms']['fixed'][str(t)]['passed'] for t in targets)
    elif state=='build_failed':
        group['excluded_build_arms']=['self']
    return group


def attach(matrix):
    seen=set()
    for path,cell in cohorts():
        project,model=cell['project'],cell['model']
        assert (project,model) not in seen
        seen.add((project,model))
        assert sha(ROOT/cell['original_source'])==cell['original_sha256']
        old=matrix[model]['current'][project]
        assert old['targets']==cell['original_shared']
        for arm,count in old['passed'].items():
            assert sum(cell['original'][arm][str(t)] for t in old['targets'])==count
        a=paired(cell,'a')
        b=paired(cell,'b')
        if path==CONFIRM:
            a['preparation']=b['preparation']='components with JSON block receiver'
        matrix[model].setdefault('self_recovery',{})[project]=dict(first=a,replication=b,
                                    source=str(path.relative_to(ROOT)),source_sha256=sha(path))
    assert len(seen)==25
