"""Repair publicly witnessed renderer interfaces and emit a source-neutral, shorter plan."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import argparse
import json
import subprocess
import sys
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,now,read,sha
from .. import generate as gen,pages,schema
from . import content

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/webgen-native-plans-20261126pm'
CAP=1.00
def register():
    dest=OUT/'registration.json'
    files=[Path(__file__),HERE/'content.py',HERE/'dispatch.cjs',HERE/'PROTOCOL.md',Path(gen.__file__),Path(schema.__file__),
           Path(pages.__file__),gen.HERE/'candidates.json',gen.OUT/'seal.json',gen.OUT/'generation-input.json',gen.DIST]
    sums={str(p.relative_to(ROOT)):sha(p) for p in files}
    if not dest.exists():
        balance=check_credits(CAP);assert balance['sufficient']
        core.save(dest,dict(utc=now(),balance=balance,cap=CAP,deadline=gen.END.isoformat(),sources=sums))
    assert read(dest)['sources']==sums

def normalize(config):
    if isinstance(config,list):return [normalize(v) for v in config]
    if not isinstance(config,dict):return config
    out={}
    for k,v in config.items():
        if k=='body' and not isinstance(v,list):v=[v]
        out[k]=normalize(v) if k not in ('data','value') else v
    return out

def html(config,parts,mode):
    if mode=='original':return pages.page(config,parts)
    text=pages.page(normalize(config),parts)
    return text.replace('let f=document.createDocumentFragment();','let f=document.createElement("div");')

def linked(parts):
    updated={};counts={}
    for g,v in parts.items():
        r=subprocess.run(['node',str(HERE/'dispatch.cjs'),str(gen.transport.build.modules.ACORN)],input=v,text=True,capture_output=True,check=True)
        data=json.loads(r.stdout);updated[g]=data['source'];counts[g]=data['calls']
    return updated,counts

def inspect_sample(path):
    from playwright.sync_api import sync_playwright
    source=path.read_text()
    out=pages.check(source)
    with browser.browser_slot(),sync_playwright() as pw,pw.chromium.launch(env=browser.browser_env()) as eng,pages.local_tab(eng,'<p></p>') as tab:
        errors=[];tab.on('pageerror',lambda e:errors.append(str(e)[:280]))
        tab.set_content(source,wait_until='load',timeout=6500)
        out['errors']=errors+out['errors']
        out['visible']=tab.locator('body').inner_text()[:350]
    return out

def trial(parts,mode,folder):
    dest=folder/'public.json'
    if not dest.exists():
        rec=pages.write_html(folder,html(schema.SAMPLE,parts,mode))
        try:
            r=subprocess.run([sys.executable,'-m','studies.webgen_bench.functional_pilot.native_plans.run','sample',str(ROOT/rec['file'])],capture_output=True,text=True,timeout=35,check=True)
            z=json.loads(r.stdout)
        except subprocess.TimeoutExpired:z=dict(checks={},errors=['Public sample exceeded 35 seconds'])
        core.save(dest,z)
    return read(dest)

def prepare(tag,ledger):
    folder=OUT/'build'/tag;f=folder/'library.json'
    if f.exists():return read(f)
    initial=read(gen.OUT/'build'/tag/'library.json')
    parts=initial['parts'];mode='original';history=[]
    if initial['status']=='build_failed':
        initial_check=trial(parts,mode,folder/'before');best=initial_check
        def passes(v):return {k for k,x in v['checks'].items() if x}
        maps={}
        for key,new in [('containers',parts),('dispatch',None)]:
            if key=='dispatch':new,maps=linked(parts)
            v=trial(new,key,folder/key)
            oldgood,newgood=passes(best),passes(v)
            keep=newgood>oldgood or (newgood==oldgood and len(v['errors'])<len(best['errors']))
            history.append(dict(mode=key,retained=keep,checks=v,dispatch_edits=maps))
            if keep:mode=key;parts=new;best=v
            if len(passes(best))==5:break
        owners={'layout':('start','tabs'),'records':('record',),'input':('form',),'form':('form',),'actions':('details',)}
        for group,needs in owners.items():
            if all(best['checks'].get(k) for k in needs):continue
            brief=(pages.ABI+' ctx.render(nodeOrArray) always returns a DOM element when using the containers ABI; '
                   'delegate every child to ctx.render, including nodes of other types. Do not call your local renderNode recursively. '
                   'A body or tab.body can be a single object or a list. Never set styles on a fragment. '
                   'Use a wrapper element for tab panes. Each function returns a DOM element even when receiving no children.')
            msg=core.messages(brief,dict(types={k:schema.FIELDS[k] for k in pages.GROUPS[group]},sample=schema.SAMPLE,
                    existing_source=parts.get(group),runtime_observation=best,output='Return complete function renderNode(node,ctx){ ... } only.'))
            try:
                func=gen.function(gen.call(ledger,tag,folder/'repair'/group/'call',msg,'build',4600))
                nextparts=parts|{group:func};nextmode='containers' if mode=='original' else mode
                v=trial(nextparts,nextmode,folder/'repair'/group/'test')
                keep=passes(v)>passes(best)
                history.append(dict(group=group,observation=v,retained=keep))
                if keep:best=v;parts=nextparts;mode=nextmode
            except (gen.MISSING+gen.ERRORS) as exc:history.append(dict(group=group,error=str(exc)))
        status='valid' if len(passes(best))==5 else 'build_failed'
    else:status=initial['status'];best=initial.get('final')
    core.save(f,dict(status=status,mode=mode,parts=parts,checks=best,history=history,previous=sha(gen.OUT/'build'/tag/'library.json')))
    return read(f)

def plan(tag,site,brief,ledger):
    folder=OUT/'plans'/tag/site;f=folder/'record.json'
    if f.exists():return read(f)
    msg=core.messages(content.SPEC,dict(brief=brief,format_example=content.EXAMPLE,output='Start with { and finish with }. Return exactly one JSON document.'))
    for i in range(2):
        try:
            raw=gen.call(ledger,tag,folder/str(i),msg,'plan',6000)
            cfg=content.compile_plan(gen.parse(raw))
            value=dict(status='valid',config=cfg);break
        except gen.MISSING as e:value=dict(status='missing',reason=str(e));break
        except gen.ERRORS as e:
            value=dict(status='invalid',reason=str(e)[:200])
            msg+=[dict(role='assistant',content=raw),dict(role='user',content='Schema validation failed: '+str(e)[:180]+'. Return a complete corrected and shorter JSON document.')]
    core.save(f,value);return read(f)

def generate():
    register();dest=HERE/'candidates.json'
    if dest.exists():return
    old=read(gen.HERE/'candidates.json');sites=read(gen.OUT/'generation-input.json')
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP);new={}
    with patch.multiple(gen.BASE,OUT=OUT,END=gen.END,template=gen.settings),ThreadPoolExecutor(max_workers=6) as pool:
        fs={t:pool.submit(prepare,t,ledger) for t in gen.BUILDERS}
        plans={(t,site):pool.submit(plan,t,site,b,ledger) for t in gen.TAGS for site,b in sites.items()}
        libs={t:f.result() for t,f in fs.items()}
        for t in gen.TAGS:
            new[t]={}
            for site in sites:
                row={'direct':old['rows'][t][site]['direct']};p=plans[t,site].result()
                for arm,who in [('human','human'),('gpt5-library','gpt5'),('self',t)]:
                    if who!='human' and libs[who]['status']!='valid':v=dict(status=libs[who]['status'])
                    elif p['status']!='valid':v={k:z for k,z in p.items() if k!='config'}
                    else:
                        doc=pages.page(p['config'],'human') if who=='human' else html(p['config'],libs[who]['parts'],libs[who]['mode'])
                        v=pages.write_html(OUT/'sites'/t/site/arm,doc)
                    row[arm]=v
                new[t][site]=row
    core.save(OUT/'seal.json',dict(registration=sha(OUT/'registration.json'),libraries={t:sha(OUT/'build'/t/'library.json') for t in libs},
              plans={str(f.relative_to(OUT)):sha(f) for f in (OUT/'plans').rglob('record.json')},rows=new))
    core.save(dest,dict(registration=sha(OUT/'registration.json'),seal=sha(OUT/'seal.json'),previous=sha(gen.HERE/'candidates.json'),cost=ledger_read.totals(OUT/'budget.sqlite3'),
                        libraries={t:{k:z for k,z in lib.items() if k!='parts'} for t,lib in libs.items()},rows=new))
if __name__=='__main__':
    if sys.argv[1:2]==['sample']:print(json.dumps(inspect_sample(Path(sys.argv[2]))))
    else:
        with browser.lock(OUT/'run.lock'):generate()
