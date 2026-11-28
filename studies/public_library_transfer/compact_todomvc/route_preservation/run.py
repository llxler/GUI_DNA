"""Repair a route event without changing the selected view function, plans or baseline pages."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import shutil
import subprocess
from unittest.mock import patch

from playwright.sync_api import Error, sync_playwright
from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.public_library_transfer.compact_todomvc.filtered_view import run as view
from studies.study_io import ROOT, now, read, sha
from studies.webgen_bench.functional_pilot import pages

state, weak = view.state, view.weak
HERE = Path(__file__).resolve().parent
OUT = ROOT/'artifacts/todo-route-preservation-20261128'
CAP = .15


def sequence(ids, flags, editing, filters):
    rows = [dict(id=i,title=f'Fern {i}',completed=f) for i,f in zip(ids,flags,strict=True)]
    return dict(state=dict(todos=rows,editing=editing,filter='all',nextId=max(ids,default=0)+3), filters=filters)


TRAIN = [sequence([9,31],[False,True],None,['active','completed','all']),
         sequence([3,7,2],[True,False,True],7,['completed','active']), sequence([],[],None,['completed','all'])]
UNSEEN = [sequence([41,99,16],[False,True,False],None,['active','all','completed','all']),
          sequence([12],[True],12,['completed','active','all']), sequence([60,21],[False,False],None,['completed','all','active'])]


def check(fn, cases):
    node = shutil.which('node')
    if not node:
        raise RuntimeError('Node unavailable')
    p = subprocess.run([node,'--max-old-space-size=128',str(HERE/'check.cjs')],
                       input=json.dumps(dict(source=fn,cases=cases)),text=True,capture_output=True,timeout=8,check=True)
    return json.loads(p.stdout)


def browser_back(engine, fn):
    with pages.local_tab(engine, '<!doctype html><body></body>') as tab:
        try:
            tab.add_script_tag(content=fn)
            tab.evaluate("""() => {
                window.s={todos:[{id:13,title:'Mica',completed:false},{id:51,title:'Lime',completed:true}],
                          editing:null,nextId:56,filter:'all'};
                window.seen=[];
                window.addEventListener('hashchange',()=>{
                  const filter=location.hash.slice(1)||'all';
                  s=route(s,{type:'route',filter});
                  seen.push({filter:s.filter,ids:s.todos.map(x=>x.id)});
                });
            }""")
            for i,action in enumerate(("location.hash='completed'","location.hash='active'","history.back()","history.forward()"),1):
                tab.evaluate(action)
                tab.wait_for_function('n=>seen.length===n',arg=i,timeout=1600)
            observed=tab.evaluate('seen')
            return dict(observed=observed,passed=observed==[dict(filter=f,ids=[13,51]) for f in ('completed','active','completed','active')])
        except Error as exc:
            return dict(passed=False,error=str(exc).splitlines()[0][:200])


def register():
    inputs=[Path(__file__),HERE/'check.cjs',HERE/'PROTOCOL.md',view.HERE/'result.json',view.OUT/'seal.json',
            view.choices.OUT/'seal.json',Path(state.todo.MOD.__file__),state.SPEC]
    inputs.extend(view.OUT/t/r/'library.json' for t in state.TAGS for r in 'ab')
    sums={str(p.relative_to(ROOT)):sha(p) for p in inputs}
    f=OUT/'registration.json'
    if not f.exists():
        balance=check_credits(CAP)
        if not balance['sufficient']:
            raise RuntimeError('Insufficient balance')
        core.save(f,dict(utc=now(),deadline=view.choices.prior.END.isoformat(),cap=CAP,balance=balance,
                         sources=sums,train=TRAIN,unseen=UNSEEN))
    assert read(f)['sources']==sums


def revise(tag,rep,ledger):
    f=OUT/tag/rep/'library.json'
    if f.exists():
        return read(f)
    old=read(view.OUT/tag/rep/'library.json')['functions']
    fn=old['route']
    initial=check(fn,TRAIN)
    history=[]
    if not all(c['passed'] for c in initial):
        msg=core.messages('Implement only function route(state,event) for the TodoMVC controller. On a route event update '
                          'the filter to event.filter. Keep the backing todo collection including every item in its '
                          'original order, the editing marker and nextId. select(state) separately computes visible rows. '
                          'Return the complete state. No DOM or storage. Return only the function.',
                          dict(old_function=fn,contract=read(state.SPEC)['todomvc']['contract'],public_sequences=TRAIN,observations=initial))
        for attempt in range(2):
            try:
                raw=state.todo.BASE.request(ledger,('todomvc',tag,rep),f.parent/'calls'/str(attempt),msg,'build',950)
                proposal=state.todo.MOD.extract('route',raw)
                result=check(proposal,TRAIN) if proposal else [dict(passed=False,error='Expected route(state,event)')]
                history.append(result)
                if all(v['passed'] for v in result):
                    fn=proposal
                    break
                msg += [dict(role='assistant',content=raw),dict(role='user',content='Correct the entire function using these public observations. '+json.dumps(result))]
            except state.todo.slots.EVENTS.MISSING as exc:
                history.append([dict(missing=str(exc))])
                break
    core.save(f,dict(functions=old|{'route':fn},changed=fn!=old['route'],initial=initial,history=history))
    return read(f)


def generate():
    seal=OUT/'seal.json'
    if seal.exists():
        return
    votes=read(view.choices.OUT/'seal.json')['decisions']
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    targets=[t['id'] for t in weak.domain.tasks()]
    records={}
    with patch.multiple(state.todo.BASE,OUT=OUT,END=view.choices.prior.END,template=state.todo.slots.EVENTS.template),ThreadPoolExecutor(max_workers=3) as pool:
        jobs={(t,r):pool.submit(revise,t,r,ledger) for t in state.TAGS for r in 'ab'}
        for (tag,rep),job in jobs.items():
            lib=job.result()
            rows=records.setdefault(tag,[])
            for key in targets:
                vote=votes[tag][rep][key]
                for arm in (rep,'fixed-'+rep):
                    if arm==rep and vote['status']!='valid':
                        value={'status':vote['status']}
                    else:
                        disabled=vote['disabled'] if arm==rep else []
                        code=state.todo.MOD.assemble(lib['functions'],{k:k not in disabled for k in state.ALL})
                        value=state.candidate(OUT/tag/rep/key/arm,code)
                    rows.append(dict(task=key,arm=arm,**value))
    core.save(seal,dict(registration=sha(OUT/'registration.json'),rows=records,
                        libraries={t:{r:sha(OUT/t/r/'library.json') for r in 'ab'} for t in state.TAGS}))


def score():
    result=HERE/'result.json'
    if result.exists():
        return
    seal=read(OUT/'seal.json')
    assert seal['registration']==sha(OUT/'registration.json')
    earlier=read(view.HERE/'result.json')['models']
    cache={}
    for cohort in earlier.values():
        for r in cohort['rows']:
            if r['status']=='valid':
                key=(r['task'],r['files_sha256'])
                assert key not in cache or cache[key]['passed']==r['passed']
                cache[key]=r
    targets,_=weak.suite.inputs()
    server=weak.evaluate.todo.Server(OUT)
    models={}
    try:
        for tag,frozen in seal['rows'].items():
            m=weak.MODELS[tag]
            rows=[r for r in earlier[m]['rows'] if r['arm'] in ('direct','human','gpt5-library')]
            reps={}
            with browser.browser_slot(),sync_playwright() as pw,pw.chromium.launch(env=browser.browser_env()) as engine:
                for rep in 'ab':
                    path=OUT/tag/rep/'library.json'
                    assert sha(path)==seal['libraries'][tag][rep]
                    lib=read(path)
                    before=read(view.OUT/tag/rep/'library.json')['functions']['route']
                    fn=lib['functions']['route']
                    fresh=check(fn,UNSEEN)
                    reps[rep]=dict(changed=lib['changed'],before=check(before,UNSEEN),after=fresh,training=lib['history'],
                                   history_navigation=browser_back(engine,fn) if all(c['passed'] for c in fresh) else dict(status='failed_public_check'))
            for item in frozen:
                task,arm,status=item['task'],item['arm'],item['status']
                r=dict(task=task,arm=arm,status=status,passed=False if status=='invalid' else None)
                if status=='valid':
                    path=ROOT/item['file'];digest=sha(path)
                    assert digest==item['files_sha256']
                    if (task,digest) in cache:
                        r=dict(cache[task,digest],arm=arm,reused=True)
                    else:
                        out=OUT/'scores'/task/digest
                        with browser.browser_slot():
                            weak.evaluate.score(('todomvc',targets[task],read(path),out,server))
                        r.update(weak.recovery.todo.binding.official(out,targets[task],{}),files_sha256=digest,reused=False)
                        cache[task,digest]=r
                rows.append(r)
            models[m]=dict(rows=rows,libraries=reps)
    finally:
        server.close()
    core.save(result,dict(registration=seal['registration'],seal=sha(OUT/'seal.json'),models=models,
                          previous=sha(view.HERE/'result.json'),cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__=='__main__':
    with browser.lock(OUT/'study.lock'):
        register()
        generate()
        score()
