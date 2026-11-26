"""Re-run frozen-library planning and low-scoring Self workflows on matched targets."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
import json
import re
import sys
import time

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read, paper_performance as paper
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from studies.webbench.compact_planning import run as compact
from studies.webbench.table.interaction_modules import run as pm
from . import todo


HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/library-source-diagnosis-20261126pm'
CAP=1.80
END=datetime(2026,11,26,13,55,tzinfo=timezone.utc)
WEB=(('table','gemma'),('svg-chart','qwen9'))
REG=OUT/'registration.json'
INITIAL=HERE/'initial-comparisons.json'

def baseline():
    destination=OUT/'matrix-at-registration.json'
    if not destination.exists():core.save(destination,read(compact.MATRIX))
    matrix=read(destination);rows=[]
    for project in (*paper.WEB_PROJECTS,'dom1','calculator','todomvc','duo'):
        for model,g in matrix.items():
            if project=='todomvc' and model not in paper.components.TODO_ROSTER:continue
            if project=='duo' and (model not in paper.BACKBONES or not paper.current_group(g,project)):continue
            if project in paper.WEB_PROJECTS and not paper.current_group(g,project):continue
            if project in ('dom1','calculator') and model not in (paper.components.QWEN9,paper.components.FLASH):continue
            counts = {arm:(list(map(int,r.groups())) if (r:=re.search(r'(\d+)/(\d+)',cell)) else None)
                      for arm,cell in zip(paper.METHODS,paper.project_cells(g,project),strict=True)}
            if counts['gpt5-library'] and counts['self']:assert counts['gpt5-library'][1]==counts['self'][1]
            rows.append(dict(model=model,project=project,cells=counts))
    snapshot=dict(source_sha256=sha(destination),rows=rows)
    if INITIAL.exists():assert read(INITIAL)==snapshot
    else:core.save(INITIAL,snapshot)

def register():
    baseline()
    files=[Path(__file__),HERE/'todo.py',HERE/'sequences.cjs',HERE/'PROTOCOL.md',INITIAL,OUT/'matrix-at-registration.json',
           todo.WEAK.GPT,Path(todo.WEAK.generic.__file__),Path(todo.WEAK.domain.__file__),Path(todo.MOD.__file__),
           todo.WEAK.suite.SOURCE/'build-inputs.json',todo.WEAK.suite.SOURCE/'targets.json',Path(compact.__file__)]
    files.extend(todo.source(t,r) for t in todo.SMALL for r in 'ab')
    cells=[]
    for p,t in WEB:
        model,source,old=compact.controls(p,t);path=compact.base.old_root(p,t)/'inputs'/p
        pkg=path/'gpt5-library.json';files.extend([source,pkg,path/'public.json',path/'browser.json'])
        cells.append(dict(project=p,tag=t,model=model,arm='gpt5-library',targets=list(range(1,21)),
                          package=str(pkg.relative_to(ROOT)),source=str(source.relative_to(ROOT)),
                          previous=sum(r['passed'] is True for r in old['gpt5-library'].values()),
                          old_status={str(k):r['status'] for k,r in old['gpt5-library'].items()},
                          direct=sum(r['passed'] is True for r in old['direct'].values())))
    sums={str(p.relative_to(ROOT)):sha(p) for p in files}
    if not REG.exists():
        b=check_credits(CAP);assert b['sufficient']
        core.save(REG,dict(utc=now(),deadline=END.isoformat(),cap=CAP,balance=b,sources=sums,cells=cells))
    assert read(REG)['sources']==sums
    return read(REG)

def generate():
    reg=register();ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    def params(p,t,stage):
        if p=='todomvc':return todo.slots.EVENTS.template(p,t,stage)
        return pm.old.settings(p,t,stage)
    with patch.multiple(compact.base,OUT=OUT,END=END,template=params),patch.multiple(compact,OUT=OUT,END=END):
        with ThreadPoolExecutor(max_workers=3) as pool:
            work=[pool.submit(compact.produce,cell,ledger) for cell in reg['cells']]
            work.append(pool.submit(todo.generate,OUT,ledger,REG))
            for job in work:job.result()
    core.save(OUT/'complete.json',dict(registration=sha(REG),cost=ledger_read.totals(OUT/'budget.sqlite3')))

def score():
    reg=register();assert read(OUT/'complete.json')['registration']==sha(REG)
    web=[]
    with patch.multiple(compact,OUT=OUT,END=END):
        for c in reg['cells']:
            p,t=c['project'],c['tag'];pkg=read(ROOT/c['package']);pub=read(compact.base.old_root(p,t)/'inputs'/p/'public.json')
            compact.evaluate(c)
            folder=OUT/p/t/'gpt5-library';d=read(folder/'comparison.json');extra=[]
            for idx,plan in enumerate(compact.choices(pkg,'gpt5-library',p)):
                page=compact.compile_page(p,'gpt5-library',pkg,plan,pub,folder/'examples'/str(idx))
                extra.extend(dict(project=p,arm=f'example-{idx}',task=n,**page) for n in c['targets'])
            proto=browser.verify_contract(p);fixed=browser.evaluate(extra,OUT,{p:proto},2)
            old=compact.controls(p,t)[2]
            d['examples']=[{k:r.get(k) for k in ('task','arm','status','passed','report_sha256')} for r in fixed]
            d['original_rows']={a:[{k:r.get(k) for k in ('task','arm','status','passed','report_sha256')} for r in old[a].values()] for a in ('gpt5-library','direct')}
            web.append(d)
    tags=list(dict.fromkeys([*todo.SUPPLIED,*todo.SMALL]))
    with patch.multiple(todo.WEAK,OUT=OUT,MODELS={t:todo.WEAK.MODELS[t] for t in tags}):
        todo.WEAK.score()
    groups={}
    for tag in tags:
        d=read(OUT/tag/'result.json');d['tag']=tag
        d['original_gpt5']=[r for r in read(todo.WEAK.OUT/tag/'result.json')['rows'] if r['arm']=='gpt5-library']
        if tag in todo.SMALL:
            d['builds']={r:{k:v for k,v in read(OUT/tag/r/'library.json').items() if k!='functions'} for r in 'ab'}
        groups[todo.WEAK.MODELS[tag]]=d
    cost=ledger_read.totals(OUT/'budget.sqlite3')
    breakdown={}
    for r in ledger_read.calls(OUT/'budget.sqlite3'):
        key=r['model']+' / '+r['purpose'].split('/')[0]
        v=breakdown.setdefault(key,dict(calls=0,settled_micro_usd=0,exposure_micro_usd=0,unsettled=0))
        v['calls']+=1;v['settled_micro_usd']+=r['actual'] or 0;v['unsettled']+=int(r['actual'] is None)
        v['exposure_micro_usd']+=r['reserved'] if r['actual'] is None else r['actual']
    core.save(HERE/'result.json',dict(registration=sha(REG),initial=sha(INITIAL),cost=cost,cost_by_model_and_phase=breakdown,web=web,todomvc=groups))

if __name__=='__main__':
    action=sys.argv[1] if len(sys.argv)>1 else 'all'
    if action=='queue':
        files=[ROOT/'studies/webbench/table/selection_binding/interaction_repairs/result.json',
               ROOT/'studies/webgen_bench/functional_pilot/function_binding/judgments.json']
        while not all(f.exists() for f in files):
            if datetime.now(timezone.utc)>=END:raise RuntimeError('Original table or main website evaluation still incomplete')
            time.sleep(6)
    with browser.lock(OUT/'run.lock'):
        if action in ('register','all','queue'):register()
        if action in ('generate','all','queue'):generate()
        if action in ('score','all','queue'):score()
