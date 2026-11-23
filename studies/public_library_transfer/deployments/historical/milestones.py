"""Independent five-target transfer on the canvas and flex projects."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import json
from pathlib import Path

from gui_dna.budget import BudgetStop, Ledger
from studies.ledger_read import calls, totals
from studies.public_library_transfer import core
from studies.public_library_transfer.report import validate_rows
from studies.study_io import ROOT, now, read, sha
from . import run, supplement

OUT = ROOT/'artifacts/public-library-transfer-remote-milestones-20261123'
BILL = ROOT/'studies/results/public-library-transfer-remote-milestones-billing-20261123.json'
BASE_BILL = ROOT/'studies/results/public-library-transfer-remote-billing-20261123.json'
PROJECTS = ('canvas','flex')
TASKS = (4,8,12,16,20)


def targets():
    for p in PROJECTS:
        for m in run.MODELS:
            for n in TASKS:
                for tag in ('direct',*supplement.TAGS):
                    yield p,m,n,tag


def register():
    sources=[Path(__file__),run.HERE/'MILESTONES.md',Path(run.__file__),Path(supplement.__file__),Path(core.__file__)]
    meta={'sources':{str(p.relative_to(ROOT)):sha(p) for p in sources},
          'inputs':{p:sha(run.MAIN/'inputs'/f'{p}.json') for p in PROJECTS},
          'grid':list(map(list,targets())),'shared_deployment_budget_usd':{m:run.CAP for m in run.MODELS},
          'model_ids':run.MODELS,'source_repetitions':{'codex-1':1,'codex-2':2},'deadline':run.END.isoformat()}
    path=OUT/'registered.json'
    if path.exists():
        if read(path)['registration']!=meta:
            raise ValueError('Milestone registration changed')
    else:
        core.save(path,{'registered_utc':now(),'registration':meta})


def one(t,ledger):
    p,m,n,tag=t
    folder=OUT/'runs'/p/m/tag/f'task-{n}'
    dest=folder/'result.json'
    if dest.exists():
        return read(dest)
    direct=tag=='direct'
    public=read(run.MAIN/'inputs'/f'{p}.json')
    initial={'project':p,'task':n,'planner':run.MODELS[m],'arm':'direct' if direct else 'plan',
             'builder':None if direct else core.BUILDERS[tag], 'rep':0 if direct else int(tag[-1]),
             'page':None,'files':None}
    if direct:
        messages=core.direct_messages(public,n)
        schema=core.obj({'files':core.array(core.FILE)})
    else:
        state,package=supplement.prepared(p,tag)
        if state is None: return None
        initial['build_status_sha256']=sha(run.MAIN/'builds'/p/tag/'status.json')
        if package is None:
            core.save(dest,initial|{'status':state['status'],'reason':state.get('reason','No accepted preparation')})
            return read(dest)
        initial['package_sha256']=state['package_sha256']
        messages=core.plan_messages(public,n,package)
        schema=package['plan_schema']
    deny=OUT/f'{m}-denied.json'
    if deny.exists():
        value=initial | {'status':'missing','reason':'Previously denied provider admission'}
    else:
        try:
            text,response_sha=run.call(folder,m,messages,'page' if direct else 'plan',schema,ledger,f'milestones/{p}/{tag}/task-{n}')
        except (RuntimeError,BudgetStop) as e:
            value=initial | {'status':'missing','reason':str(e)[:500]}
            if str(e)=='HTTP 403':
                core.save(deny,{'model':run.MODELS[m], 'error':'HTTP 403'})
        else:
            page=folder/'page'
            try:
                parsed=json.loads(text)
                files=core.materialize_direct(p,public,parsed,page) if direct else core.materialize(p,package,parsed,page)
                value=initial | {'status':'valid','page':str(page.relative_to(ROOT)),'files':files}
            except (ValueError,KeyError,TypeError) as e:
                value=initial | {'status':'invalid','reason':str(e)[:500]}
            value['response_sha256']=response_sha
    core.save(dest,value)
    return value


def generate(workers):
    register()
    if not BASE_BILL.is_file() or not (run.OUT/'generation-sealed.json').is_file():
        raise ValueError('Acquisition of the earlier eight projects must close before new admissions.')
    ledgers={m:Ledger(run.OUT/m/'budget.sqlite3',run.CAP,run.CAP) for m in run.MODELS}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        resolved=list(pool.map(lambda t:one(t,ledgers[t[1]]),targets()))
    print(f'{sum(r is not None for r in resolved)}/{len(resolved)} milestone deployments resolved')


def close():
    register()
    rows=[]
    for p in PROJECTS:
        project_rows=[]
        for _,m,n,tag in (t for t in targets() if t[0]==p):
            project_rows.append(read(OUT/'runs'/p/m/tag/f'task-{n}'/'result.json'))
        for tag in supplement.TAGS:
            state,package=supplement.prepared(p,tag)
            extra={'status':state['status'],'build_status_sha256':sha(run.MAIN/'builds'/p/tag/'status.json')}
            if package is not None:
                page=OUT/'fixed'/p/tag/'page'
                extra.update(page=str(page.relative_to(ROOT)),files=core.materialize(p,package,package['examples'][0]['plan'],page))
            project_rows.extend(supplement.row(p,None,n,tag,'fixed') | extra for n in TASKS)
        validate_rows(project_rows)
        core.save(OUT/'project-seals'/f'{p}.json',{'project':p,'rows':project_rows})
        rows.extend(project_rows)
    core.save(OUT/'generation-sealed.json',{'registration_sha256':sha(OUT/'registered.json'),'rows':rows})
    costs={}
    for m,model in run.MODELS.items():
        path=run.OUT/m/'budget.sqlite3'
        entries=[r for r in calls(path) if r['purpose'].startswith('milestones/')]
        splits={}
        for tag in ('direct',*supplement.TAGS):
            arm=[r for r in entries if r['purpose'].split('/')[2]==tag]
            splits[tag]={'calls':len(arm),'settled_microusd':sum(r['actual'] or 0 for r in arm),
                         'exposure_microusd':sum(r['actual'] if r['actual'] is not None else r['reserved'] for r in arm),
                         'unsettled_calls':sum(r['actual'] is None for r in arm)}
        costs[model]={'only_milestones':splits,'whole_shared_ledger':totals(path),'ledger':str(path.relative_to(ROOT))}
    core.save(BILL,{'deployment':costs,'previous_eight_project_snapshot':str(BASE_BILL.relative_to(ROOT)),
                    'snapshot_sha256':sha(BASE_BILL),'registration_sha256':sha(OUT/'registered.json'),
                    'construction':'Counted once in parent study, shared across all deployers.'})


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['register','generate','seal'])
    parser.add_argument('--workers',type=int,default=6)
    args=parser.parse_args()
    if args.action=='register':register()
    elif args.action=='seal':close()
    else:
        OUT.mkdir(parents=True,exist_ok=True)
        with (OUT/'generation.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            generate(args.workers)
