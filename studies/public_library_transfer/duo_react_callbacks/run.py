"""Evaluate model-written React behavior hooks and views with matched fresh direct code."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import re
import subprocess
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,now,read,sha
from ..duo_donor_library import run as donor
from ..self_refinement.duo_components.compact import run as compact,runtime

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/duo-react-callbacks-20261126'
CAP=1.25
TAGS=('qwen9','deepseek-flash')
REPS=('a','b')
action=donor.action
original=donor.original
IMPORTS="""import React,{useState,useEffect,useRef,useReducer,useMemo,useCallback} from 'react';
import * as Router from 'react-router-dom';
const {useParams,useLocation,useNavigate}=Router;
"""
WRAP='export default function Feature(props){ const vm = useBehavior(props); return View(props,vm); }'


def register():
    files=[Path(__file__),HERE/'PROTOCOL.md',HERE/'function.cjs',compact.OUT/'public-contracts.json',Path(runtime.__file__),
           original.EXTRA/'targets.json',original.EXTRA/'build-inputs.json',Path(donor.components.bundle.__code__.co_filename)]
    hashes={str(p.relative_to(ROOT)):sha(p) for p in files}
    f=OUT/'registration.json'
    if not f.exists():
        balance=check_credits(CAP)
        assert balance['sufficient']
        core.save(f,dict(utc=now(),deadline=action.END.isoformat(),cap=CAP,balance=balance,sources=hashes,
                         models={t:action.settings('table',t,'plan')['model'] for t in TAGS}))
    assert read(f)['sources']==hashes
    return read(f)


def extract(name,raw):
    res=subprocess.run(['node',str(HERE/'function.cjs')],input=json.dumps(dict(name=name,raw=raw)),text=True,
                       capture_output=True,timeout=15)
    if res.returncode:raise ValueError('Expected a complete named React function '+name)
    return res.stdout


def component(job):
    tag,rep,domain,names,label,public,ledger=job
    folder=OUT/tag/rep/domain/label
    stamp=folder/'component.json'
    if stamp.exists():return
    checks,funcs={},{}
    def ask(name,phase,feedback=()):
        sig='function useBehavior(props)' if name=='useBehavior' else 'function View(props, vm)'
        desc=('Own the actual state, fetches, click/change/submit callbacks and success/failure branches. '
              'Return an object with named values and callback functions. No rendering.' if name=='useBehavior' else
              'Read vm from the supplied behavior hook. Render a React fragment or JSX, match the roles/labels/test IDs, '
              'wire real callbacks. Do not remount routing providers or call any hooks here.')
        msg=core.messages('Write one complete named JavaScript function (JSX allowed). No imports, other functions, explanation or mocks. '+desc,
             dict(signature=sig,available_imports=IMPORTS,component=label,public_features=public,
                  implementation=funcs.get('useBehavior') if name=='View' else None,existing_view=funcs.get('View') if name=='useBehavior' else None,
                  previous=funcs.get(name),public_feedback=feedback))
        for i in range(2):
            raw=action.compact.base.request(ledger,('table',tag,rep),folder/'calls'/name/phase/str(i),msg,'build' if rep in REPS else 'plan',4600)
            try:return extract(name,raw)
            except ValueError as exc:
                if i:raise
                msg=msg+[dict(role='user',content=str(exc)+'. Give only this complete function; no other files.')]
    def code(f):return IMPORTS+'\n'+f['useBehavior']+'\n'+f['View']+'\n'+WRAP
    def measure(f,phase):
        evaluated={}
        for n in names:
            dest=folder/'public'/phase/n
            verdict=runtime.single((dest,domain,n,code(f)))[1]
            evaluated[n]=dict(passed=verdict['passed'],feedback=verdict.get('feedback',[])[:2],
                              report_sha256=verdict['report_sha256'])
        return evaluated
    history=[]
    try:
        for name in ('useBehavior','View'):funcs[name]=ask(name,'first')
        checks=measure(funcs,'first')
        history.append({n:v['passed'] for n,v in checks.items()})
        failed=[v for v in checks.values() if not v['passed']]
        if failed:
            hints=[h for v in failed for h in v['feedback']]
            text=json.dumps(hints).lower()
            owner='View' if any(k in text for k in ('unable to find','found multiple','could not find','no accessible','not defined')) else 'useBehavior'
            try:
                candidate={**funcs,owner:ask(owner,'repair',hints)}
                after=measure(candidate,'repair')
                before={n for n,v in checks.items() if v['passed']}
                new={n for n,v in after.items() if v['passed']}
                if before<new:funcs,checks=candidate,after
                history.append({n:v['passed'] for n,v in after.items()})
            except (ValueError,*action.typed.MISSING):pass
        result=dict(status='valid',source=code(funcs),checks=checks)
    except action.typed.MISSING as exc:result=dict(status='missing',reason=str(exc))
    except ValueError as exc:result=dict(status='invalid',reason=str(exc))
    core.save(stamp,dict(history=history,**result))


def generate():
    spec=read(compact.OUT/'public-contracts.json')['features']
    tasks=original.inputs()
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    jobs=[]
    for tag in TAGS:
        for domain,features in spec.items():
            for n,brief in features.items():
                for r in REPS:jobs.append((tag,r,domain,[n],n,{n:brief},ledger))
        for task,row in tasks.items():
            dom=row['group']
            names=task.split('_')
            jobs.append((tag,'direct',dom,names,task,{n:spec[dom][n] for n in names},ledger))
    with patch.multiple(action.compact.base,OUT=OUT,END=action.END,template=action.settings):
        with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(component,jobs))
        libs={}
        for tag in TAGS:
            for r in REPS:
                for domain,features in spec.items():
                    comps={n:read(OUT/tag/r/domain/n/'component.json') for n in features}
                    valid=any(x['status']=='valid' and x['checks'][n]['passed'] for n,x in comps.items())
                    status='valid' if valid else ('missing' if any(x['status']=='missing' for x in comps.values()) else 'build_failed')
                    libs[tag,r,domain]=dict(status=status,modules={n:v['source'] for n,v in comps.items() if v['status']=='valid'},
                                             singles={n:v.get('checks',{}).get(n,{}).get('passed') for n,v in comps.items()})
        def assemble(job):
            tag,task=job
            dom=tasks[task]['group']
            module=tasks[task]['public']['module']
            folder=OUT/tag/'deployment'/task
            f=folder/'rows.json'
            if f.exists():return
            direct=read(OUT/tag/'direct'/dom/task/'component.json')
            def store(arm,files):
                p=folder/(arm+'.json')
                core.save(p,files)
                return dict(status='valid',file=str(p.relative_to(OUT)),files_sha256=sha(p))
            data={'direct':store('direct',{module+'.js':direct['source']}) if direct['status']=='valid' else dict(status=direct['status'])}
            for r in REPS:
                lib=libs[tag,r,dom]
                if lib['status']!='valid':
                    for arm in (r,'names-'+r,'fixed-'+r):data[arm]=dict(status=lib['status'])
                    continue
                ids=sorted(lib['modules'])
                def choose(arm,found):
                    stamps=(found+['NONE','NONE'])[:2]
                    library={'components':[dict(id=k,source=v) for k,v in lib['modules'].items()]}
                    return store(arm,donor.components.bundle(module,library,dict(zip(('first','second'),stamps,strict=True))))
                data['fixed-'+r]=choose('fixed-'+r,ids[:2])
                data['names-'+r]=choose('names-'+r,[k for k in task.split('_') if k in ids])
                msg=core.messages('Choose up to two component indices for the requested feature pair. '
                                  'Return only a JSON array of integer indices.',
                                  dict(required=task.split('_'),components=dict(enumerate(ids))))
                try:
                    raw=action.compact.base.request(ledger,('table',tag,r),folder/'calls'/r,msg,'plan',2200)
                    v=json.loads(action.compact.base.uncode(raw))
                    if not isinstance(v,list) or len(v)>2 or any(type(i)!=int or not 0<=i<len(ids) for i in v):
                        raise ValueError('Expected up to two module indices')
                    data[r]=choose(r,[ids[i] for i in v])
                except action.typed.MISSING as e:data[r]=dict(status='missing',reason=str(e))
                except ValueError as e:data[r]=dict(status='invalid',reason=str(e))
            core.save(f,data)
        with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(assemble,((t,n) for t in TAGS for n in tasks)))
    files=list(OUT.glob('*/*/*/*/component.json'))+list(OUT.glob('*/deployment/*/rows.json'))
    core.save(OUT/'seal.json',dict(registration=sha(OUT/'registration.json'),sources={str(p.relative_to(OUT)):sha(p) for p in sorted(files)},
        libraries={t:{r:{g:{k:v for k,v in libs[t,r,g].items() if k!='modules'} for g in spec} for r in REPS} for t in TAGS}))


def score(reg):
    seal=read(OUT/'seal.json')
    assert seal['registration']==sha(OUT/'registration.json') and all(sha(OUT/f)==v for f,v in seal['sources'].items())
    tasks=original.inputs()
    result={}
    jobs={}
    for t in TAGS:
        result[reg['models'][t]]=[]
        for n,row in tasks.items():
            for arm,v in read(OUT/t/'deployment'/n/'rows.json').items():
                rec=dict(arm=arm,task=n,status=v['status'],passed=False if v['status']=='invalid' else None)
                result[reg['models'][t]].append(rec)
                if v['status']!='valid':continue
                path=OUT/v['file']
                assert sha(path)==v['files_sha256']
                jobs.setdefault((n,sha(path)),(path,[]))[1].append(rec)
    def grade(item):
        (n,checksum),(f,entries)=item
        row=tasks[n]
        dest=OUT/'scores'/n/checksum
        val=runtime.score((row['group'],row,read(f),dest,None))
        assert val['report_sha256']==sha(dest/'jest.json')
        for rec in entries:
            rec.update(passed=val['passed'],report_sha256=val['report_sha256'],official_cases_passed=val['assertion_statuses'].count('passed'))
    with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(grade,jobs.items()))
    core.save(HERE/'result.json',dict(registration=sha(OUT/'registration.json'),seal=sha(OUT/'seal.json'),
             libraries=seal['libraries'],models=result,cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=('generate','score'))
    phase=p.parse_args().action
    with browser.lock(OUT/(phase+'.lock')):
        reg=register()
        generate() if phase=='generate' else score(reg)
