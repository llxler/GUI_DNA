"""Prospective editor preparation on the public prefix, followed by ten deployments."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies.ledger_read import totals
from studies.public_library_transfer import core as c, build
from studies.public_library_transfer import browser
from studies.public_library_transfer_remote import run as remote
from studies.study_io import digest

HERE=Path(__file__).resolve().parent
OUT=c.ROOT/'artifacts/public-library-transfer-holdout-20261123'
PROJECT='expression-editor'
TASKS=tuple(range(11,21))
TAGS=('codex-1','codex-2')
CAP=.75


def register():
    public=c.read(c.OUT/'inputs'/f'{PROJECT}.json')
    c.save(OUT/'preparation.json',c.prefix(public,10))
    path=OUT/'registered.json'
    sources=[Path(__file__),HERE/'PROTOCOL.md',Path(c.__file__),Path(build.__file__),Path(remote.__file__),OUT/'preparation.json']
    hashes={str(p.relative_to(c.ROOT)):c.sha(p) for p in sources}
    if path.exists():
        assert c.read(path)['sources']==hashes
        return
    credit=check_credits(CAP)
    if not credit['sufficient']: raise RuntimeError('Unfunded study')
    c.save(path,{'registered':c.now(),'sources':hashes,'model':remote.MODELS['mistral'],
                 'builders':TAGS,'targets':TASKS,'budget':CAP,'credit':credit})


def prepare(tag):
    d=OUT/tag
    if (d/'status.json').exists(): return
    public=c.read(OUT/'preparation.json')
    msg=c.build_messages(public)
    status={'tag':tag,'attempts':[]}
    for attempt in range(2):
        folder=d/f'attempt-{attempt+1}'
        c.save(folder/'messages.json',msg)
        try: raw=build.subscribe(msg,folder)
        except Exception as e:
            status.update(status='missing',reason=str(e)); break
        c.save(folder/'raw.json',{'text':raw})
        try:
            pkg=c.package(public,c.parse(raw))
            for key,v in [('default',pkg['defaults']),('first',pkg['examples'][0]['plan'])]:
                page=folder/'public'/key
                c.materialize(PROJECT,pkg,v,page)
                errors=browser.public_load(PROJECT,page)
                c.save(folder/f'{key}-load.json',errors)
                if errors: raise ValueError(str(errors)[:1600])
            c.save(d/'package.json',pkg)
            status['attempts'].append({'attempt':attempt+1,'valid':True})
            status.update(status='valid',package_sha256=c.sha(d/'package.json'))
            break
        except (KeyError,TypeError,ValueError) as e:
            status['attempts'].append({'attempt':attempt+1,'valid':False,'reason':str(e)[:1600]})
            status.update(status='build_failed')
            msg=c.build_messages(public)+[{'role':'assistant','content':raw[:65000]},
               {'role':'user','content':'Public format/load error: '+str(e)[:1600]+'. Return the complete replacement JSON package.'}]
    c.save(d/'status.json',status)


def row(task,arm,tag,status='missing',page=None,files=None):
    return {'project':PROJECT,'task':task,'arm':arm,'rep':int(tag[-1]) if tag else 0,
            'builder':c.BUILDERS[tag] if tag else None,'planner':None if arm=='fixed' else remote.MODELS['mistral'],
            'status':status,'page':str(page.relative_to(c.ROOT)) if page else None,'files':files}


def deploy(arg):
    tag,task=arg
    d=OUT/tag/f'task-{task}'
    if (d/'rows.json').exists(): return
    admitted=c.read(OUT/tag/'status.json')
    if admitted['status']!='valid':
        c.save(d/'rows.json',[row(task,a,tag,admitted['status']) for a in ('plan','fixed')]); return
    public=c.read(c.OUT/'inputs'/f'{PROJECT}.json')
    pkg=c.read(OUT/tag/'package.json')
    messages=c.plan_messages(public,task,pkg)
    c.save(d/'messages.json',messages)
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    try:
        raw,sha=remote.call(d,'mistral',messages,'plan',pkg['plan_schema'],ledger,f'{tag}/task-{task}')
        c.save(d/'raw.json',{'text':raw,'response_sha256':sha})
        try:
            page=d/'page'
            files=c.materialize(PROJECT,pkg,c.parse(raw),page)
            target=row(task,'plan',tag,'valid',page,files)
        except (ValueError,KeyError,TypeError):
            target=row(task,'plan',tag,'invalid')
    except Exception as e:
        target=row(task,'plan',tag); target['error']=str(e)[:300]
    fixed=OUT/tag/'fixed'
    if not fixed.exists(): raise RuntimeError('Missing first example')
    c.save(d/'rows.json',[target,row(task,'fixed',tag,'valid',fixed,browser.tree(fixed))])


def targets():
    with ThreadPoolExecutor(2) as pool: list(pool.map(prepare,TAGS))
    for tag in TAGS:
        if c.read(OUT/tag/'status.json')['status']=='valid':
            pkg=c.read(OUT/tag/'package.json')
            c.materialize(PROJECT,pkg,pkg['examples'][0]['plan'],OUT/tag/'fixed')
    with ThreadPoolExecutor(4) as pool:
        list(pool.map(deploy,[(tag,t) for t in TASKS for tag in TAGS]))
    while True:
        paths=[remote.OUT/'runs'/'mistral'/PROJECT/'direct'/f'task-{n}'/'result.json' for n in TASKS]
        if all(p.exists() for p in paths): break
        time.sleep(10)
    direct=[c.read(p) for p in paths]
    assert [r['task'] for r in direct]==list(TASKS) and all(r['planner']==remote.MODELS['mistral'] for r in direct)
    rows=direct+[r for tag in TAGS for n in TASKS for r in c.read(OUT/tag/f'task-{n}/rows.json')]
    c.save(OUT/'sealed.json',{'rows':rows,'direct_sha256':{str(p.relative_to(c.ROOT)):c.sha(p) for p in paths}})


def score():
    from studies.public_library_transfer.report import comparison,counts,grouped
    seal=OUT/'sealed.json'
    result=browser.evaluate(c.read(seal)['rows'],OUT,{PROJECT:browser.verify_contract(PROJECT)},2)
    groups=grouped(result)
    pairs=[]
    for tag in TAGS:
        plan=groups[(PROJECT,'plan',c.BUILDERS[tag],int(tag[-1]),remote.MODELS['mistral'])]
        for baseline in ('direct','fixed'):
            key=(PROJECT,'direct',None,0,remote.MODELS['mistral']) if baseline=='direct' else (PROJECT,'fixed',c.BUILDERS[tag],int(tag[-1]),None)
            pairs.append({'tag':tag,'baseline':baseline,**comparison(plan,groups[key],TASKS)})
    ledger=OUT/'budget.sqlite3'
    c.save(c.ROOT/'studies/results/public-library-transfer-holdout-20261123.json',{
        'preparation_targets':list(range(1,11)),'evaluation_targets':TASKS,'builder':'gpt-6.2-astra',
        'planner':remote.MODELS['mistral'],'generation_sha256':c.sha(seal),'registered_sha256':c.sha(OUT/'registered.json'),
        'counts':[{'arm':k[1],'rep':k[3],**counts(v.values())} for k,v in groups.items()],
        'pairs':pairs,'rows':[{k:r[k] for k in ('task','arm','rep','status','passed','report_sha256')} for r in result],
        'ledger':totals(ledger) if ledger.exists() else None})


if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('phase',choices=('generate','score')); phase=ap.parse_args().phase
    register()
    if phase=='generate': targets()
    else: score()
