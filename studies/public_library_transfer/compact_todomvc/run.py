"""Run three small generators on the eight registered TodoMVC families."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import httpx
from gui_dna.budget import Ledger, BudgetStop
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.blind_library import tables_of
from studies.public_library_transfer import browser,core
from studies.public_library_transfer.backbone_suites import run as suite
from studies.public_library_transfer.other_benchmarks import evaluate
from studies.public_library_transfer.self_refinement.suite_recovery import run as recovery
from studies.study_io import ROOT, now, read, sha
from studies.todomvc_dna import domain,generic,library
from studies.webbench.compact_planning import run as compact
from studies.webbench.self_build_modules import run as base

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/small-todomvc-20261125'
CAP=2
SMALL={'gemma4':'google/gemma-3-4b-it','llama3':'meta-llama/llama-3.2-3b-instruct',
       'ministral3':'mistralai/ministral-3b-2512'}
MODELS=SMALL | {key:v[0] for key,v in suite.MODELS.items()}
GPT=ROOT/'artifacts/todomvc-blind/library-openai__gpt-5.json'


def register():
    where=OUT/'registration.json'
    if where.exists():
        data=read(where)
        assert all(sha(ROOT/f)==h for f,h in data['sources'].items())
        return data
    balance=check_credits(CAP)
    assert balance['sufficient']
    response=httpx.get('https://openrouter.ai/api/v1/models',timeout=25)
    response.raise_for_status()
    catalog={m['id']:m for m in response.json()['data']}
    sources=[Path(__file__),HERE/'PROTOCOL.md',GPT,Path(generic.__file__),Path(domain.__file__),
             Path(recovery.__file__),Path(recovery.todo.__file__),suite.SOURCE/'targets.json',
             suite.SOURCE/'build-inputs.json',evaluate.todo.SHELL,evaluate.todo.HARNESS/'demo-todo-app.spec.ts']
    generic.check_equivalence()
    assert read(GPT)['builder']=='openai/gpt-5'
    core.save(where,dict(utc=now(),deadline=compact.END.isoformat(),models=MODELS,cap=CAP,balance=balance,
        sources={str(f.relative_to(ROOT)):sha(f) for f in sources},
        allowed={k:catalog[m]['supported_parameters'] for k,m in MODELS.items()}))
    return read(where)


def generate(reg):
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    def template(project,tag,stage):
        if tag not in SMALL:
            return recovery.template(project,tag,stage)
        params=dict(model=SMALL[tag],provider={'sort':'price','allow_fallbacks':True,'max_price':{
                    'prompt':0.30,'completion':0.8,'request':0}})
        for key,value in [('temperature',0),('seed',20261125)]:
            if key in reg['allowed'][tag]:params[key]=value
        return params
    targets,briefs=suite.inputs()
    def run_tag(tag):
        root=OUT/tag
        if (root/'seal.json').exists():return
        jobs=[]
        rows={}
        libraries={}
        for rep in ('a','b') if tag in SMALL else ():
            dest=root/rep/'build'
            try:
                libraries[rep]=recovery.controller(ledger,('todomvc',tag,rep),dest,briefs['todomvc'])
            except (base.original.Unavailable,BudgetStop) as exc:
                libraries[rep]=dict(status='missing',reason=str(exc))
        for task in domain.tasks():
            for arm in (('direct','human','gpt5-library','a','b') if tag in SMALL else ('gpt5-library',)):
                jobs.append((task,arm))
        def one(job):
            task,arm=job
            key=task['id']
            dest=root/key/arm
            case=('todomvc',tag,'a')
            if arm in libraries:
                pair=recovery.candidates(ledger,('todomvc',tag,arm),root/arm,key,targets[key],libraries[arm])
                return key,{arm:pair['self'],'fixed-'+arm:pair['fixed']}
            try:
                if arm=='direct':
                    msg=core.messages(suite.menus.DIRECT+' Provide browser JS assigning window.candidate.',
                          dict(public=targets[key]['public'],output_schema=suite.menus.DIRECT_SCHEMA))
                elif arm=='human':
                    msg=domain.messages_for(task,'dna',library.library())
                else:
                    lib=read(GPT)
                    msg=generic.plan_messages(task,lib,tables_of(lib))
                raw=base.request(ledger,case,dest/'call',msg,'plan',8192)
                value=base.parse_json(raw)
                if arm=='direct':
                    source=value['source']
                    if not isinstance(source,str) or not source.strip():raise ValueError('Empty source')
                elif arm=='human':
                    source=domain.compile_plan(value,task['features'],library.library())
                else:
                    source=generic.compile_plan(value,task['features'],lib,tables_of(lib))
                file=dest/'files.json'
                core.save(file,{'candidate.js':source})
                row=dict(status='valid',file=str(file.relative_to(ROOT)),files_sha256=sha(file))
            except (BudgetStop,base.original.Unavailable) as exc:
                row=dict(status='missing',reason=str(exc))
            except base.ERRORS as exc:
                row=dict(status='invalid',reason=str(exc)[:240])
            return key,{arm:row}
        with ThreadPoolExecutor(max_workers=3) as pool:
            for key,values in pool.map(one,jobs):
                rows.setdefault(key,{}).update(values)
        core.save(root/'seal.json',dict(rows=rows,libraries=libraries,registration=sha(OUT/'registration.json')))
        print('sealed',tag,flush=True)
    with patch.multiple(base,OUT=OUT,END=compact.END,template=template),ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(run_tag,MODELS))


def score():
    import os,time
    from datetime import datetime,timezone
    for k in tuple(os.environ):
        if k.endswith(('_API_KEY','_AUTH_TOKEN','_ACCESS_TOKEN')):os.environ.pop(k)
    targets,_=suite.inputs()
    server=evaluate.todo.Server(OUT)
    try:
        for tag in MODELS:
            path=OUT/tag/'seal.json'
            while not path.exists():
                if datetime.now(timezone.utc)>compact.END:return
                time.sleep(2)
            result=OUT/tag/'result.json'
            if result.exists():continue
            seal=read(path)
            assert seal['registration']==sha(OUT/'registration.json')
            def one(job):
                task,arm,row=job
                out=dict(task=task,arm=arm,status=row['status'],passed=False if row['status']=='invalid' else None)
                if row['status']=='valid':
                    file=ROOT/row['file']
                    assert sha(file)==row['files_sha256']
                    dest=OUT/'scores'/task/sha(file)
                    with browser.lock(dest/'.lock'),browser.browser_slot():
                        v=evaluate.score(('todomvc',targets[task],read(file),dest,server))
                        out.update(recovery.todo.binding.official(dest,targets[task],{}),files_sha256=sha(file))
                return out
            jobs=[(t,a,row) for t,arms in seal['rows'].items() for a,row in arms.items()]
            with ThreadPoolExecutor(max_workers=2) as pool: rows=list(pool.map(one,jobs))
            core.save(result,dict(rows=rows,seal_sha256=sha(path),libraries={k:v['status'] for k,v in seal['libraries'].items()}))
            print('scored',tag,flush=True)
    finally:server.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('register','generate','score','publish'))
    args=parser.parse_args()
    reg=register()
    if args.action=='generate':generate(reg)
    if args.action=='score':score()
    if args.action=='publish':
        core.save(HERE/'result.json',dict(registration=sha(OUT/'registration.json'),cost=ledger_read.totals(OUT/'budget.sqlite3'),
                  models={model:read(OUT/tag/'result.json') for tag,model in MODELS.items()}))
