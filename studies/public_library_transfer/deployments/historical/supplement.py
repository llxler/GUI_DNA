"""Cross both independently constructed subscription libraries with the historical deployers."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import json
from pathlib import Path

from gui_dna.budget import BudgetStop, Ledger
from studies.ledger_read import calls, totals
from studies.public_library_transfer import core
from studies.public_library_transfer.browser import write_json
from studies.study_io import ROOT, dump, now, read, sha
from . import run

TAGS = ('codex-1','codex-2')
SUP = run.OUT/'supplement'
REG = SUP/'registered.json'


def scheduled():
    for p,m,n,arm in run.scheduled():
        if arm=='direct':
            for tag in TAGS:
                yield (p,m,n,tag)


def register():
    run.register()
    paths=[Path(__file__),run.HERE/'CODEX-SUPPLEMENT.md',run.OUT/'registered.json',Path(core.__file__)]
    hashes={str(p.relative_to(ROOT)):sha(p) for p in paths}
    if REG.exists():
        if read(REG)['sources']!=hashes:
            raise ValueError('Registered supplement dependencies changed')
    else:
        core.save(REG,{'registered_utc':now(),'sources':hashes,'targets':list(scheduled()),
                      'shared_ledgers':{m:str((run.OUT/m/'budget.sqlite3').relative_to(ROOT)) for m in run.MODELS},
                      'shared_direct':'Original run table of projects, deployers and targets; one direct page per group.',
                      'deadline_utc':run.END.isoformat()})


def row(p,m,n,tag,arm):
    return {'project':p,'task':n,'arm':arm,'rep':int(tag[-1]) if tag in TAGS else 1,
            'builder':core.BUILDERS[tag],'planner':run.MODELS[m] if arm=='plan' else None,
            'page':None,'files':None}


def prepared(p,tag):
    folder=run.MAIN/'builds'/p/tag
    if not (folder/'status.json').is_file():
        return None,None
    state=read(folder/'status.json')
    if state['status']=='valid':
        if state['package_sha256']!=sha(folder/'package.json'):
            raise ValueError('Builder seal differs from package')
        return state,read(folder/'package.json')
    if state['status'] not in ('missing','build_failed'):
        raise ValueError('Unexpected construction status: '+state['status'])
    return state,None


def plan(target, ledger):
    p,m,n,tag=target
    dest=SUP/'runs'/m/p/tag/f'task-{n}'
    result=dest/'result.json'
    if result.exists():
        return read(result)
    state,package=prepared(p,tag)
    if state is None:
        return None
    initial=row(p,m,n,tag,'plan')
    state_sha=sha(run.MAIN/'builds'/p/tag/'status.json')
    initial['build_status_sha256']=state_sha
    if package is None:
        core.save(result, initial | {'status':state['status'],'reason':state.get('reason','No accepted preparation')})
        return read(result)
    path=run.MAIN/'inputs'/f'{p}.json'
    if sha(path)!=read(run.OUT/'registered.json')['inputs_sha256'][p]:
        raise ValueError('Input hash changed')
    public=read(path)
    schema=package['plan_schema']
    initial['package_sha256']=state['package_sha256']
    messages=core.plan_messages(public,n,package)
    block=SUP/f'{m}-provider-denied.json'
    if block.is_file():
        value=initial | {'status':'missing','reason':'Earlier provider-denied admission', 'denial_sha256':sha(block)}
    else:
        try:
            reply,response_sha=run.call(dest,m,messages,'plan',schema,ledger,f'codex-supplement/{p}/{tag}/task-{n}')
        except (BudgetStop,RuntimeError) as exc:
            if str(exc)=='HTTP 403' and not block.exists():
                # Concurrent admissions already in flight remain separately recorded.
                core.save(block,{'status':'HTTP 403','model':run.MODELS[m]})
            value=initial | {'status':'missing','reason':str(exc)[:500]}
        else:
            try:
                page=dest/'page'
                files=core.materialize(p,package,json.loads(reply),page)
                value=initial | {'status':'valid','page':str(page.relative_to(ROOT)), 'files':files}
            except (ValueError,KeyError,TypeError) as exc:
                value=initial | {'status':'invalid','reason':str(exc)[:500]}
            value['response_sha256']=response_sha
    core.save(result,value)
    return value


def generate(projects,workers):
    register()
    ledgers={m:Ledger(run.OUT/m/'budget.sqlite3',run.CAP,run.CAP) for m in run.MODELS}
    targets=[t for t in scheduled() if t[0] in projects]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        done=list(pool.map(lambda t:plan(t,ledgers[t[1]]),targets))
    print(f'{sum(t is not None for t in done)}/{len(done)} new-builder deployments resolved',flush=True)


def fixed(p,tag,ns):
    state,package=prepared(p,tag)
    if state is None: return None
    base={'status':state['status'],'build_status_sha256':sha(run.MAIN/'builds'/p/tag/'status.json')}
    if package is not None:
        page=SUP/'fixed'/p/tag/'page'
        files=core.materialize(p,package,package['examples'][0]['plan'],page)
        base.update(files=files,page=str(page.relative_to(ROOT)),package_sha256=state['package_sha256'])
    return [row(p,None,n,tag,'fixed') | base for n in sorted(ns)]


def project_rows(p):
    rows=[]
    fixed_targets={}
    for _,m,n,arm in (t for t in run.scheduled() if t[0]==p):
        f=run.OUT/'runs'/m/p/arm/f'task-{n}'/'result.json'
        if arm=='direct':
            if not f.exists(): return None
            rows.append(read(f))
            for tag in TAGS:
                plan_file=SUP/'runs'/m/p/tag/f'task-{n}'/'result.json'
                if not plan_file.exists(): return None
                rows.append(read(plan_file))
                fixed_targets.setdefault(tag,set()).add(n)
        else:
            state,package=prepared(p,arm)
            if state is None: return None
            if package is None:
                # The original acquisition runner predated the denied build routes.
                # Read the sealed build status directly to distinguish no response from invalid content.
                rows.append(row(p,m,n,arm,'plan') | {'status':state['status'],
                    'reason':state.get('reason','No accepted preparation'),
                    'build_status_sha256':sha(run.MAIN/'builds'/p/arm/'status.json')})
            else:
                if not f.exists(): return None
                rows.append(read(f))
            fixed_targets.setdefault(arm,set()).add(n)
    for tag, ns in fixed_targets.items():
        group=fixed(p,tag,ns)
        if group is None: return None
        rows.extend(group)
    return rows


def seal():
    from studies.public_library_transfer.report import validate_rows
    register()
    all_rows=[]
    completed=[]
    for p in run.PROJECTS:
        rows=project_rows(p)
        if rows is None: continue
        validate_rows(rows)
        core.save(run.OUT/'project-seals'/f'{p}.json',{'project':p,'rows':rows,'supplement_seal_sha256':sha(REG)})
        all_rows.extend(rows)
        completed.append(p)
    if completed==list(run.PROJECTS):
        validate_rows(all_rows)
        core.save(run.OUT/'generation-sealed.json',{'rows':all_rows,'registration_sha256':sha(run.OUT/'registered.json'),
                                                   'supplement_sha256':sha(REG)})
        accounting={}
        for k,m in run.MODELS.items():
            path=run.OUT/k/'budget.sqlite3'
            entries=calls(path)
            purposes={}
            for record in entries:
                purpose=record['purpose']
                phase='subscription_library_planning' if purpose.startswith('codex-supplement/') else ('direct' if '/direct/' in purpose else 'historical_builder_planning')
                bucket=purposes.setdefault(phase,{'calls':0,'settled_microusd':0,'exposure_microusd':0,'unsettled':0})
                bucket['calls']+=1
                bucket['settled_microusd']+=record['actual'] or 0
                bucket['exposure_microusd']+=record['actual'] if record['actual'] is not None else record['reserved']
                bucket['unsettled']+=record['actual'] is None
            accounting[m]={'ledger':str(path.relative_to(ROOT)),'totals':totals(path),'by_purpose':purposes}
        core.save(ROOT/'studies/results/public-library-transfer-remote-billing-20261123.json',
                  {'models':accounting,'construction':'Accounted in the parent study; no construction charge in these deployment ledgers.',
                   'registration_sha256':sha(REG), 'generation_sha256':sha(run.OUT/'generation-sealed.json')})
    print('Sealed:', ', '.join(completed),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['register','generate','seal'])
    parser.add_argument('--projects',nargs='+',choices=run.PROJECTS,default=list(run.PROJECTS))
    parser.add_argument('--workers',type=int,default=10)
    args=parser.parse_args()
    if args.action=='register':register()
    elif args.action=='seal':seal()
    else:
        SUP.mkdir(parents=True,exist_ok=True)
        with (SUP/'run.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            generate(args.projects,args.workers)
