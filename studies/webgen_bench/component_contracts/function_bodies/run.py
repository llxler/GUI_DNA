"""Ask the original builder to fill an empty component body with named DOM outlets."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import subprocess
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from .. import run as prior

gen=prior.gen
HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/webgen-function-bodies-20261127'
CAP=.55
STRUCTURE={
    'tabs':"const nav=document.createElement('nav'), outlet=document.createElement('section'); root.append(nav,outlet);",
    'dialog':"const dialog=document.createElement('section'); root.append(dialog);",
    'form':"const form=document.createElement('form'); root.append(form);",
}
ASSIGNMENTS={
    'tabs':"For EACH entry add a clickable button to nav, with text from entry.title. Write a show(entry) helper that clears outlet and calls env.mount(outlet,entry.body). Click calls it with that entry. Show the first entry on initialization. Never inspect child types or manufacture child nodes. Never clear root or nav after startup.",
    'dialog':"Inside dialog display component.title as a heading, delegate its content to env.mount(dialog,component.body), and create a Close button that removes dialog.",
    'form':"Mount component.body and component.actions into form by calling env.mount twice. Prevent default in the submit event handler, collect values using FormData(form), and display the configured success message in the root. The literal text lives at component.onEvent.submitSucc.actions[0].args.msg. Do not create or shadow form.",
    'page':"Append a heading with component.title then call env.mount(root,component.body) exactly once regardless of the body type.",
    'panel':"Append a heading for the panel title, then delegate component.body unchanged to env.mount(root,component.body).",
    'container':"Pass the whole body to env.mount(root,component.body).",
}
def wrap(kind,body):
    return 'function(root,component,env){\n'+STRUCTURE.get(kind,'')+'\n'+body+'\n}'

def body_source(raw):
    text=raw.strip()
    fence=re.search(r'```(?:javascript|js)?\s*\n([\s\S]*?)```',text,re.I)
    text=(fence[1] if fence else text).strip()
    if re.match(r'^(?:function\b|\([^)]*\)\s*=>)',text):
        return '('+text.rstrip(';')+')(root,component,env);'
    return text

def improve(tag,kind,original,ledger):
    folder=OUT/'build'/tag/'components'/kind
    dest=folder/'record.json'
    if dest.exists():return read(dest)
    before=prior.public_probe(kind,original)
    old=original;observations=[before];last=None
    for i in range(2):
        if observations[-1].get('passed'):break
        example=prior.previous.parent.KINDS[kind]
        payload=dict(component_type=kind,public_component=example[1],objective=ASSIGNMENTS.get(kind,example[2]),
                     fixed_prefix=wrap(kind,'// YOUR STATEMENTS HERE'),public_observation=observations[-1])
        if last is not None:payload['your_first_body']=last
        msg=core.messages("Complete only the missing JavaScript statements in the supplied function. "
          "The named root, component, env and declared DOM outlets already exist. Use those variable names. "
          "Do not repeat the wrapper or add example invocations. All content comes from component. "
          "env.mount(realHTMLElement,schemaOrArray) mounts children and returns nothing; root.append(domNode) inserts real nodes. "
          "env.get(key) returns raw page data; env.text(value) returns interpolated text. No dependencies.",payload)
        try:
            last=body_source(gen.call(ledger,tag,folder/str(i),msg,'build',2700))
            candidate=wrap(kind,last)
            test=subprocess.run(['node','--check','-'],input='('+candidate+')',text=True,capture_output=True,timeout=6)
            if test.returncode:raise ValueError(test.stderr.splitlines()[0:5])
            observation=prior.public_probe(kind,candidate)
            if observation['passed']:old=candidate
        except gen.MISSING as e:
            observations.append(dict(missing=str(e)));break
        except gen.ERRORS as e:observation=dict(passed=False,error=str(e)[:300])
        observations.append(observation)
    core.save(dest,dict(source=old,changed=old!=original,observations=observations))
    return read(dest)

def build(tag,ledger):
    folder=OUT/'build'/tag;dest=folder/'library.json'
    if dest.exists():return read(dest)
    source=prior.OUT/'build'/tag/'library.json'
    initial=read(source)
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures={k:pool.submit(improve,tag,k,fn,ledger) for k,fn in initial['parts'].items()}
        recs={k:j.result() for k,j in futures.items()}
    parts={k:v['source'] for k,v in recs.items()};check=prior.pages.check(prior.previous.site(prior.schema.SAMPLE,parts,True))
    bare={k:wrap(k,'') for k in parts}
    barecheck=prior.pages.check(prior.previous.site(prior.schema.SAMPLE,bare,True))
    keep=all(not yes or check['checks'][k] for k,yes in initial['final']['checks'].items())
    final=check if keep else initial['final']
    status='valid' if len(final['checks'])==5 and all(final['checks'].values()) else 'build_failed'
    core.save(dest,dict(status=status,parts=parts if keep else initial['parts'],origin=sha(source),initial=initial['final'],
                         final=final,attempt=check,empty=barecheck,kept=keep,changed=[k for k,v in recs.items() if keep and v['changed']],
                         isolated={k:v['observations'] for k,v in recs.items()}))
    print(tag,status,final['checks'],flush=True)
    return read(dest)

def generate():
    earlier=prior.HERE/'candidates.json';previous=read(earlier);reg=OUT/'registration.json'
    paths=[Path(__file__),HERE/'PROTOCOL.md',earlier,Path(prior.__file__),prior.HERE/'probe.js',
           *[prior.OUT/'build'/t/'library.json' for t in prior.MODELS]]
    sums={str(p.relative_to(ROOT)):sha(p) for p in paths}
    if not reg.exists():
        b=check_credits(CAP);assert b['sufficient']
        core.save(reg,dict(utc=now(),deadline=prior.END.isoformat(),balance=b,cap=CAP,sources=sums))
    assert sums==read(reg)['sources']
    dest=HERE/'candidates.json'
    if dest.exists():return
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    with patch.multiple(gen.BASE,OUT=OUT,END=prior.END,template=gen.settings),ThreadPoolExecutor(max_workers=2) as pool:
        jobs={t:pool.submit(build,t,ledger) for t in prior.MODELS};libs={t:j.result() for t,j in jobs.items()}
    batches={}
    for name,plan_dir in [('development',prior.PILOT_PLANS),('holdout',prior.OUT/'plans')]:
        rows=previous[name]
        for t,lib in libs.items():
            for site,arms in rows[t].items():
                plan=read(plan_dir/t/site/'record.json')
                arms['self']=prior.render(t,site,'self',plan,lib,OUT/name)
        batches[name]=rows
    hashes={t:sha(OUT/'build'/t/'library.json') for t in libs}
    core.save(OUT/'seal.json',dict(registration=sha(reg),libraries=hashes,**batches))
    core.save(dest,dict(previous=sha(earlier),seal=sha(OUT/'seal.json'),registration=sha(reg),**batches,
       models=previous['models'],libraries={t:{k:v for k,v in lib.items() if k!='parts'} for t,lib in libs.items()},
       cost=ledger_read.totals(OUT/'budget.sqlite3')))

if __name__=='__main__':
    with browser.lock(OUT/'run.lock'):generate()
