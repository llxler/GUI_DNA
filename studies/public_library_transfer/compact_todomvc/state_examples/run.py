"""Repair two existing small-model controllers from isolated state transitions."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.browser_worker import reentrant_slots
from studies.public_library_transfer import browser, core
from studies.public_library_transfer.source_diagnosis import run as previous, todo, public_worker
from studies.study_io import ROOT, now, read, sha
from .cases import examples

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/todo-state-examples-20261127'
ORIGINAL=previous.OUT
END=datetime(2026,11,27,12,48,tzinfo=timezone.utc)
CAP=.65
TAGS=('gemma4','ministral3')
ALL=dict.fromkeys(todo.MOD.OPTIONS,True)
SPEC=todo.WEAK.suite.SOURCE/'build-inputs.json'

def register():
    files=[Path(__file__),HERE/'check.cjs',HERE/'cases.py',HERE/'PROTOCOL.md',SPEC,Path(todo.__file__),
           Path(todo.MOD.__file__),Path(public_worker.__file__),todo.HERE/'sequences.cjs',previous.HERE/'result.json']
    for t in TAGS:
        files.append(ORIGINAL/t/'seal.json')
        files.extend(ORIGINAL/t/rep/'library.json' for rep in 'ab')
    hashes={str(p.relative_to(ROOT)):sha(p) for p in files};dest=OUT/'registration.json'
    if not dest.exists():
        balance=check_credits(CAP);assert balance['sufficient']
        core.save(dest,dict(utc=now(),deadline=END.isoformat(),balance=balance,cap=CAP,sources=hashes,
                            models={t:todo.WEAK.MODELS[t] for t in TAGS},targets=[t['id'] for t in todo.WEAK.domain.tasks()]))
    assert read(dest)['sources']==hashes
    return dest

def isolated(name,fn,scenarios):
    request=json.dumps(dict(name=name,source=fn,cases=scenarios))
    try:
        p=subprocess.run(['node','--max-old-space-size=160',str(HERE/'check.cjs')],input=request,text=True,
                         capture_output=True,timeout=5,check=True,env={'PATH':'/usr/bin:/bin'})
        return json.loads(p.stdout)
    except (subprocess.CalledProcessError,subprocess.TimeoutExpired):
        return [dict(passed=False,error='Isolated handler exceeded resources') for _ in scenarios]

def revise(tag,rep,name,original,spec,scenarios,ledger):
    folder=OUT/tag/rep/'owners'/name;f=folder/'result.json'
    if f.exists():return read(f)
    before=isolated(name,original,scenarios);best=original;history=[before]
    signature,group,goal=todo.MOD.CONTRACTS[name]
    for i in range(2):
        obs=history[-1]
        if all(r['passed'] for r in obs):break
        failed=[c|{'observed':r} for c,r in zip(scenarios,obs,strict=True) if not r['passed']]
        instruction='Return just one standalone JavaScript function matching the signature exactly. No UI or DOM. The shell passes a plain event object; all fields are directly on it. Return the new state object for every event handler. Keep unrelated state and rows. Use only localStorage for persistence. IDs, titles, filters and list lengths change; do not hardcode values.'
        msg=core.messages(instruction,dict(function=f'function {name}({signature})',purpose=goal,contract=spec['contract'],
                        requirements=spec['spec'].get(group,spec['spec']['core']),sample_transitions=failed,
                        previous_attempt=last if i else None))
        try:
            raw=todo.BASE.request(ledger,('todomvc',tag,rep),folder/str(i),msg,'build',2100)
            last=todo.MOD.extract(name,raw)
            if not last:
                history.append([dict(passed=False,error='Expected one complete named function') for _ in scenarios]);continue
            observed=isolated(name,last,scenarios)
            history.append(observed)
            if all(x['passed'] for x in observed):best=last
        except todo.slots.EVENTS.MISSING as e:
            history.append([dict(passed=False,missing=str(e)) for _ in scenarios]);break
    core.save(f,dict(function=best,changed=best!=original,history=history))
    return read(f)

def public(functions,spec,settings=ALL):
    return sorted(todo.passed(public_worker.features(functions,settings,spec)))

def build(tag,rep,ledger):
    folder=OUT/tag/rep;dest=folder/'library.json'
    if dest.exists():return read(dest)
    spec=read(SPEC)['todomvc'];source=ORIGINAL/tag/rep/'library.json'
    old=read(source);assert old['status']=='valid'
    scenarios=examples(7,23,'Basil','Moss') if rep=='a' else examples(11,32,'Linen','Bay')
    with ThreadPoolExecutor(max_workers=3) as pool:
        fs={k:pool.submit(revise,tag,rep,k,fn,spec,scenarios[k],ledger) for k,fn in old['functions'].items()}
        changes={k:j.result() for k,j in fs.items()}
    funcs={k:v['function'] for k,v in changes.items()}
    initial=public(old['functions'],spec);after=public(funcs,spec)
    if not set(initial)<=set(after):
        funcs=dict(old['functions']);after=initial
        for name in todo.MOD.CONTRACTS:
            if not changes[name]['changed']:continue
            updated=funcs|{name:changes[name]['function']};v=public(updated,spec)
            if set(after)<=set(v):funcs=updated;after=v
    opts=[k for k in ALL if set(after)-set(public(funcs,spec,ALL|{k:False}))]
    status='valid' if opts and set(initial)<=set(after) else 'build_failed'
    core.save(dest,dict(status=status,origin=sha(source),functions=funcs,initial=initial,public=after,options=opts,
        changed=[k for k in funcs if funcs[k]!=old['functions'][k]],
        isolated={k:dict(before=changes[k]['history'][0],after=isolated(k,funcs[k],scenarios[k])) for k in funcs}))
    print(tag,rep,len(initial),len(after),opts,flush=True)
    return read(dest)

def candidate(folder,script):
    f=folder/'files.json';core.save(f,{'candidate.js':script})
    return dict(status='valid',file=str(f.relative_to(ROOT)),files_sha256=sha(f))

def generate(reg):
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    with patch.multiple(todo.BASE,OUT=OUT,END=END,template=todo.slots.EVENTS.template),patch.object(previous,'OUT',OUT):
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs={(t,r):pool.submit(build,t,r,ledger) for t in TAGS for r in 'ab'}
            libs={k:j.result() for k,j in jobs.items()}
        for t in TAGS:
            rows={};original=read(ORIGINAL/t/'seal.json')['rows']
            for task in todo.WEAK.domain.tasks():
                key=task['id'];row=dict(original[key]);rows[key]={a:v for a,v in row.items() if a in ('direct','human','gpt5-library')}
                for r in 'ab':
                    lib=libs[t,r]
                    rows[key]['original-'+r]=row[r];rows[key]['original-fixed-'+r]=row['fixed-'+r]
                    rows[key].update(todo.render(ledger,t,r,task,OUT,lib))
                    if lib['status']!='valid':continue
                    base=ORIGINAL/t/key/r/'selected.json'
                    if base.exists():
                        old_choice=read(base);opts={k:old_choice.get(k,'enabled')=='enabled' for k in ALL}
                        rows[key]['old-choice-'+r]=candidate(OUT/t/key/r/'prior-plan',todo.MOD.assemble(lib['functions'],opts))
                    old=read(ORIGINAL/t/r/'library.json')['functions']
                    plain=todo.MOD.assemble(old,ALL)
                    dispatch='fn(state, event)'
                    assert plain.count(dispatch)==1
                    adapter=plain.replace(dispatch,'fn(state, {...event, detail: {...event}})')
                    rows[key]['envelope-'+r]=candidate(OUT/t/key/r/'old-envelope',adapter)
            core.save(OUT/t/'seal.json',dict(registration=sha(reg),rows=rows,libraries={r:{'status':libs[t,r]['status'],'sha256':sha(OUT/t/r/'library.json')} for r in 'ab'}))

def score(reg):
    with patch.multiple(todo.WEAK,OUT=OUT,MODELS={t:todo.WEAK.MODELS[t] for t in TAGS}):
        todo.WEAK.score()
    groups={}
    for t in TAGS:
        seal=OUT/t/'seal.json';digest=sha(seal);n=int(digest[:6],16)
        unseen=examples(100+n,211+n,'Iris '+digest[:5],'Slate '+digest[5:10])
        g=read(OUT/t/'result.json');assert g['seal_sha256']==digest
        g['replicas']={}
        for r in 'ab':
            new=read(OUT/t/r/'library.json');old=read(ORIGINAL/t/r/'library.json')
            g['replicas'][r]={k:v for k,v in new.items() if k!='functions'}
            g['replicas'][r]['unseen']={stage:{k:sum(x['passed'] for x in isolated(k,fn,unseen[k])) for k,fn in lib['functions'].items()}
                                           for stage,lib in [('before',old),('after',new)]}
        groups[todo.WEAK.MODELS[t]]=g
    core.save(HERE/'result.json',dict(registration=sha(reg),models=groups,cost=ledger_read.totals(OUT/'budget.sqlite3')))

if __name__=='__main__':
    with browser.lock(OUT/'run.lock'),patch.object(browser,'browser_slot',reentrant_slots(browser.browser_slot)):
        reg=register();generate(reg);score(reg)
