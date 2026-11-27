"""Evaluate the sealed default-preserving plans, reusing only identical per-target pages."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
import time

from playwright.sync_api import sync_playwright
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,read,sha
from studies.webgen_bench.functional_pilot import pages
from . import defaults as run

state=run.state
weak=state.todo.WEAK


def evaluate():
    seal=run.OUT/'seal.json'
    while not seal.exists():
        if datetime.now(timezone.utc)>=state.END:raise TimeoutError('No candidate manifest at deadline')
        time.sleep(2)
    if run.RESULT.exists():return
    old=read(run.HERE/'result.json');frozen=read(seal)
    assert frozen['registration']==sha(run.OUT/'registration.json')
    targets,_=weak.suite.inputs()
    cache={}
    for m,study in old['models'].items():
        for r in study['rows']:
            if r['status']=='valid' and type(r['passed']) is bool:
                key=(r['task'],r['files_sha256'])
                if key in cache:assert cache[key]['passed']==r['passed']
                cache[key]=r
    server=weak.evaluate.todo.Server(run.OUT)
    def official(job):
        task,r,decision=job
        status=decision['status']
        row=dict(task=task,arm=r,status=status,passed=False if status=='invalid' else None)
        if status!='valid':return row
        item=decision['candidate'];f=ROOT/item['file'];digest=sha(f)
        assert item['files_sha256']==digest
        if (task,digest) in cache:
            prior=cache[task,digest]
            return dict(prior,arm=r,reused=True)
        dest=run.OUT/'scores'/task/digest
        with browser.lock(dest/'.lock'),browser.browser_slot():
            weak.evaluate.score(('todomvc',targets[task],read(f),dest,server))
            return row|weak.recovery.todo.binding.official(dest,targets[task],{})|dict(files_sha256=digest,reused=False)
    results={}
    try:
        for tag,reps in frozen['decisions'].items():
            model=weak.MODELS[tag]
            rows=[]
            for row in old['models'][model]['rows']:
                if row['arm'] in ('direct','human','gpt5-library','fixed-a','fixed-b'):
                    rows.append(row)
                elif row['arm'] in ('a','b'):
                    rows.append(row|{'arm':'before-'+row['arm']})
            jobs=[(k,r,v) for r,decisions in reps.items() for k,v in decisions.items() if k not in run.EXTRA]
            with ThreadPoolExecutor(max_workers=2) as pool:
                rows.extend(pool.map(official,jobs))
            extra={}
            choices={}
            for r,decisions in reps.items():
                choices[r]={k:{f:v[f] for f in ('status','disabled') if f in v} for k,v in decisions.items()}
                extra[r]={}
                for k in run.EXTRA:
                    item=decisions[k]
                    if item['status']!='valid':
                        extra[r][k]=dict(status=item['status']);continue
                    f=ROOT/item['candidate']['file'];digest=sha(f)
                    assert digest==item['candidate']['files_sha256']
                    source=read(f)['candidate.js']
                    # The immutable controller is an IIFE exposing window.candidate. Alias
                    # its public methods for the generic probe in its local function scope.
                    script=source+'\nconst {init,reduce,select}=window.candidate;'
                    observations=[]
                    with browser.browser_slot(),sync_playwright() as pw,pw.chromium.launch(env=browser.browser_env()) as engine:
                        for prefix in (digest[:6],digest[6:12]):
                            with pages.local_tab(engine,'<!doctype html><body></body>') as tab:
                                try:
                                    changed=tab.evaluate((run.HERE/'default_toggle.cjs').read_text(),
                                          dict(source=script,id=100+int(prefix,16),title='Slate '+prefix))
                                    observations.append(dict(toggled=changed,passed=changed==(k=='permit-toggle')))
                                except Exception as exc:observations.append(dict(passed=False,error=str(exc)[:250]))
                    extra[r][k]=dict(status='observed',observations=observations,passed=all(s['passed'] for s in observations))
            results[model]=dict(rows=rows,choices=choices,counterfactual=extra)
    finally:server.close()
    core.save(run.RESULT,dict(seal=sha(seal),registration=frozen['registration'],scorer=sha(Path(__file__)),
                              prior=sha(run.HERE/'result.json'),models=results,cost=ledger_read.totals(run.OUT/'budget.sqlite3')))


if __name__=='__main__':
    with browser.lock(run.OUT/'eval.lock'):evaluate()
