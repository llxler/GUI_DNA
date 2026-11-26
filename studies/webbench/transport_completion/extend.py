"""Apply the frozen deployed methods to the remaining targets in shortened Web-Bench rows."""
import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import re
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read,paper_component_followup as paper
from studies.public_library_transfer import browser,core
from studies.public_library_transfer.self_refinement.suite_recovery import paper as recovery
from studies.study_io import ROOT,now,read,sha,digest
from studies.webbench.compact_planning import run as compact
from studies.webbench.compact_planning.visible_decoding import run as visible
from studies.webbench.self_build_modules import run as base
from studies.webbench.self_build_modules.score import controls
from studies.webbench.typed_components import run as typed,integration,svg_admission,entrypoints
from studies.webbench.typed_components.unavailable import run as absent
from . import run as restore

OUT=ROOT/'artifacts/web-extended-targets-20261125'
HERE=Path(__file__).resolve().parent
RESULT=HERE/'extension-result.json'
CAP=1.25
COHORTS={paper.TYPED:typed.OUT,paper.ABSENT:absent.OUT,paper.INTEGRATION:integration.OUT,paper.SVG_ADMISSION:svg_admission.OUT,paper.ENTRYPOINT:entrypoints.OUT}


def register():
    path=OUT/'registration.json'
    if path.exists():
        reg=read(path)
        assert all(sha(ROOT/f)==h for f,h in reg['sources'].items())
        return reg
    from studies.paper_performance import current_group
    matrix=read(compact.MATRIX)
    # Reconstruct from the unchanged archive and the registered follow-ups even after publication.
    for model in matrix.values():
        model.pop('component_followup',None)
        model.pop('extended_targets',None)
    paper.attach(matrix)
    files=[Path(__file__),HERE/'extension.md',Path(paper.__file__),Path(typed.__file__),Path(integration.__file__),
           *(f for f in paper.SOURCES if f!=paper.RESTORED),restore.OUT/'registration.json',*recovery.SOURCES]
    spent={}
    phases=(compact,visible,typed,absent,integration,svg_admission,entrypoints)
    for name,f in [('small-todomvc-20261125',paper.SMALL),('small-events-20261125',paper.EVENTS),('todo-delivery-20261125',paper.DELIVERY)]:
        spent[name]=read(f)['cost']['exposure_usd']
    for mod in phases:
        cost=ledger_read.totals(mod.OUT/'budget.sqlite3')
        spent[mod.OUT.name]=cost['exposure_usd']
    balance=check_credits(CAP)
    spent[restore.OUT.name]=restore.CAP
    assert sum(spent.values())+CAP < 10 and balance['sufficient']
    trials={(cell['model'],cell['project']):cell for _,cell in recovery.cohorts()}
    jobs=[]
    for p in restore.PROJECTS:
        for t in typed.ALL_TAGS:
            model,old_result,arms=controls(p,t)
            entry=matrix[model]
            g=entry.get('component_followup',{}).get(p,current_group(entry,p))
            if g['n']==20: continue
            files.append(old_result)
            extra=sorted(set(range(1,21))-set(g['targets']))
            for arm,score in g['passed'].items():
                stage=g.get('markers',{}).get(arm,'original')
                raw=dict(project=p,tag=t,model=model,arm=arm,initial_targets=g['targets'],initial_passes=score,
                         targets=extra,stage=stage)
                if stage in ('menu','visible'):
                    src=visible.HERE/'result.json' if stage=='visible' else compact.RESULT
                    row=next(c for c in read(src)['cells'] if (c['project'],c['tag'],c['arm'])==(p,t,arm))
                    raw['package']=row['package'];files.append(ROOT/row['package'])
                elif stage=='typed':
                    src=ROOT/g['implementation_sources'][arm]
                    record=next(c for c in read(src)['cases'] if c['project']==p and t in c['deploy'] and c['arm']==arm and c['status']=='valid')
                    directory=COHORTS[src]/p/record['builder']
                    old_seal=directory/'seal.json'; files.append(old_seal)
                    raw['source']=str(directory.relative_to(ROOT))
                    raw['source_stage']=str(src.relative_to(ROOT))
                else:
                    vals={n:v['passed'] for n,v in arms[arm].items()}
                    if stage=='rebuild':
                        results=trials[model,p]['builds']['a']['arms']['self']
                        vals={int(n):r['passed'] for n,r in results.items()}
                    assert sum(vals[n] for n in g['targets'])==score
                    raw['observations']={str(n):vals.get(n) for n in extra}
                jobs.append(raw)
    core.save(path,dict(utc=now(),deadline=compact.END.isoformat(),cap=CAP,balance=balance,prior_exposure=spent,
             jobs=jobs,sources={str(f.relative_to(ROOT)):sha(f) for f in files}))
    return read(path)


def deploy(job,ledger):
    p,t,a,stage=(job[k] for k in ('project','tag','arm','stage'))
    folder=OUT/p/t/a
    result=folder/'seal.json'
    if result.exists():return
    original=base.template
    def template(project,tag,purpose):
        settings=original(project,tag,purpose)
        if stage=='visible' or (stage=='typed' and t in ('qwen9','deepseek-flash','deepseek-pro')):
            settings['reasoning']={'enabled':False}
        return settings
    pub=read(base.old_root(p,t)/'inputs'/p/'public.json')
    targets=job['targets']
    rows=[]
    def page(path):
        return dict(status='valid',page=str(path.relative_to(ROOT)),files=browser.tree(path))
    with patch.multiple(base,OUT=OUT,END=compact.END,template=template):
        if stage in ('menu','visible'):
            pkg=read(ROOT/job['package'])
            options=compact.choices(pkg,a,p)
            free=p=='form' and a=='gpt5-library'
            fixed=compact.compile_page(p,a,pkg,options[0],pub,folder/'fixed')
            def plan(n):
                dest=folder/str(n)
                try:
                    raw=base.request(ledger,(p,t,'a'),dest/'call',compact.make_messages(pub,n,pkg,options,free),'plan',
                                     8192 if stage=='visible' else (4096 if free else 1024))
                    val=base.uncode(raw).strip()
                    if free:config=base.parse_json(val)
                    elif re.fullmatch(r'[0-9]{1,4}',val) and int(val)<len(options):config=options[int(val)]
                    else:raise ValueError('Invalid selection')
                    return compact.compile_page(p,a,pkg,config,pub,dest/'page')
                except typed.MISSING as exc:return dict(status='missing',reason=str(exc))
                except base.ERRORS as exc:return dict(status='invalid',reason=str(exc)[:350])
            with ThreadPoolExecutor(max_workers=3) as pool:plans=list(pool.map(plan,targets))
        else:
            origin=ROOT/job['source']
            old_seal=read(origin/'seal.json')
            old_fixed=next(r for r in old_seal['rows'] if r['tag']==t and r['arm']=='fixed')
            fixed={k:v for k,v in old_fixed.items() if k in ('status','page','files','reason')}
            if p=='table':
                file=origin/('library.json' if ROOT/job['source_stage'] in (paper.INTEGRATION,paper.ENTRYPOINT) else 'package.json')
                second,plans=typed.table_deploy(ledger,t,targets,pub,read(file),folder)
                assert second['files']==fixed['files']
            elif p=='form':
                if ROOT/job['source_stage'] in (paper.INTEGRATION,paper.ENTRYPOINT):modules=read(origin/'library.json')
                else:
                    with patch.object(typed.form,'OUT',origin):modules=typed.form.module_files('build-a')
                def ask(dest,ledger,system,prompt,purpose,seed,limit,previous=None):
                    try:return base.request(ledger,(p,t,'a'),dest,[dict(role='system',content=system),dict(role='user',content=prompt)],'plan',8192),dict(status='returned')
                    except typed.MISSING as exc:return '',dict(status='missing',reason=str(exc))
                def plan(n):
                    val=typed.form.make_plan(('build-a',n,'selected',pub,ledger))
                    return page(folder/'build-a/selected'/str(n)/'page') if val['status']=='valid' else {k:v for k,v in val.items() if k in ('status','reason')}
                with patch.multiple(typed.form,OUT=folder,module_files=lambda rep:modules,ask=ask), ThreadPoolExecutor(max_workers=3) as pool:
                    plans=list(pool.map(plan,targets))
            else:
                svg=typed.charts.base
                observation=read(origin/'admission.json')['public']
                source=ROOT/fixed['page']
                modules={key:(source/key).read_text() for key in read(origin/'A/modules.json')}
                def ask(ledger,name,messages,limit,schema=None):
                    msg=messages+[dict(role='user',content='Return only the JSON object. Required fields: '+json.dumps(schema['required']))]
                    return base.request(ledger,(p,t,'a'),folder/'calls'/name,msg,'plan',8192)
                with patch.multiple(svg,OUT=folder,ask=ask,MISSING=typed.MISSING),ThreadPoolExecutor(max_workers=3) as pool:
                    plans=list(pool.map(lambda n:svg.choose(ledger,'A',n,pub,dict(status='valid',selected={'public':observation}),modules),targets))
        for n,v in zip(targets,plans,strict=True):
            for label,candidate in (('planned',v),('fixed',fixed)):
                rows.append(dict(project=p,task=n,arm=label,**{k:v for k,v in candidate.items() if k in ('page','files','status','reason')}))
    core.save(result,dict(job=job,registration=sha(OUT/'registration.json'),rows=rows))
    print('sealed',p,t,a,flush=True)


def score(job):
    p,t,a=job['project'],job['tag'],job['arm']
    root=OUT/p/t/a
    f=root/'result.json'
    if f.exists():return read(f)
    if 'observations' in job:
        vals=dict(job['observations'])
        for r in read(paper.RESTORED)['rows']:
            k=str(r['task'])
            if (r['project'],r['tag'],r['arm'])==(p,t,a) and k in vals:
                assert vals[k] is None
                vals[k]=r['passed']
        return dict(job,observations=vals)
    seal=read(root/'seal.json')
    assert seal['registration']==sha(OUT/'registration.json') and seal['job']==job
    protocol=browser.verify_contract(p)
    assert protocol==read(base.old_root(p,t)/'inputs'/p/'browser.json')
    rs=browser.evaluate(seal['rows'],OUT,{p:protocol},3)
    rows=[{k:v for k,v in r.items() if k in ('task','status','arm','passed','report_sha256','reason')} for r in rs]
    for r in rows:
        if r['status']=='invalid':r['passed']=False
    vals=paper.outcomes(rows,'planned')
    record=dict(**job,rows=rows,seal_sha256=sha(root/'seal.json'),observations={str(n):v for n,v in vals.items()})
    core.save(f,record)
    return record


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('register','generate','score'))
    args=parser.parse_args()
    reg=register()
    if args.action=='generate':
        ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
        for j in reg['jobs']:
            if 'observations' not in j:deploy(j,ledger)
    elif args.action=='score':
        import time
        from datetime import datetime,timezone
        for k in tuple(os.environ):
            if k.endswith(('_API_KEY','_AUTH_TOKEN','_ACCESS_TOKEN')):os.environ.pop(k)
        browser.OUT=OUT
        while not paper.RESTORED.exists():
            if datetime.now(timezone.utc)>=compact.END:raise SystemExit('deadline')
            time.sleep(2)
        records=[]
        for j in reg['jobs']:
            f=OUT/j['project']/j['tag']/j['arm']/'seal.json'
            while 'observations' not in j and not f.exists():
                if datetime.now(timezone.utc)>=compact.END:raise SystemExit('deadline')
                time.sleep(2)
            records.append(score(j))
        core.save(RESULT,dict(registration=sha(OUT/'registration.json'),restored_sha256=sha(paper.RESTORED),records=records,cost=ledger_read.totals(OUT/'budget.sqlite3')))
