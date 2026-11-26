"""Replay the authors' exact returned expressions and check generic output binding."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import re
import subprocess
import sys
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from .. import generate as gen, pages, schema
from ..component_functions import run as parent


HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/webgen-function-binding-20261126pm'
CAP=.25
MODULE='studies.webgen_bench.functional_pilot.function_binding.run'

def bind(text, adapt):
    raw=gen.BASE.uncode(text).strip()
    fence=re.search(r'```(?:javascript|js)?\s*\n([\s\S]*?)```',raw,re.I)
    raw=(fence[1] if fence else raw).strip().rstrip(';')
    if not re.match(r'^(?:function\s*(?:\w+\s*)?\(|\([^)]*\)\s*=>)',raw):
        raw='function render(root,component,env){\n'+raw+'\n}'
    proc=subprocess.run(['node',str(HERE/'outputs.cjs'),str(gen.transport.build.modules.ACORN)],
                        input=json.dumps(dict(source=raw,adapt=adapt)),text=True,capture_output=True,timeout=6)
    if proc.returncode:raise ValueError('A valid three-parameter JavaScript function or body is required')
    return json.loads(proc.stdout)

def site(config, parts, adapt):
    out=parent.html(config,parts)
    if adapt:
        out=out.replace('if (!node || !handlers[node.type]) continue;',
                        'if (node instanceof Node) { parent.append(node); continue; }\n      if (!node || !handlers[node.type]) continue;')
    return out

def trace(html):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw,pw.chromium.launch(env=browser.browser_env()) as eng,pages.local_tab(eng,'<p></p>') as tab:
        log=[];errs=[];tab.on('pageerror',lambda e:errs.append(str(e)[:170]))
        tab.set_content(html,wait_until='load',timeout=7000);log.append(tab.locator('body').inner_text()[:300])
        for name in ('Workshop','Read details'):
            try:tab.get_by_text(name,exact=True).first.click();log.append(tab.locator('body').inner_text()[:300])
            except Exception as exc:log.append(str(exc).splitlines()[0]);break
        return dict(visible=log,errors=errs)

def build(tag,ledger):
    directory=OUT/'build'/tag;dest=directory/'library.json'
    if dest.exists():return read(dest)
    parts={};checks={};mode=False;history=[];delivered={}
    def public(candidate,adapt,folder):
        rec=pages.write_html(folder,site(schema.SAMPLE,candidate,adapt))
        return parent.previous.check('integration',ROOT/rec['file'])
    def passing(obs):return {k for k,v in obs.get('checks',{}).items() if v}
    for i,adapt in [(0,False),(0,True),(1,True)]:
        candidate={};edits={}
        for k in parent.KINDS:
            folder=parent.OUT/'build'/tag/'types'/k/str(i)/'call'
            if not folder.exists():folder=parent.OUT/'build'/tag/'types'/k/'0/call'
            receipts=sorted(folder.glob('transmission-*/settled.json'))
            if not receipts:continue
            response=receipts[0].with_name('response.json');assert sha(response)==read(receipts[0])['response_sha256']
            try:data=bind(read(response)['choices'][0]['message']['content'],adapt)
            except ValueError:continue
            candidate[k]=data['source'];edits[k]=data['outputs']
        label=f'saved-{i}-'+str(adapt).lower()
        new=public(candidate,adapt,directory/label)
        accept=passing(checks)<=passing(new) and len(candidate)>=len(parts)
        history.append(dict(stage=label,checks=new,outputs=edits,retained=accept,delivered=len(candidate)))
        if accept:parts=candidate;checks=new;mode=adapt
        if len(passing(checks))==5 and len(parts)==len(parent.KINDS):break
    for names in [('page','tpl','tabs'),('table',),('button','dialog'),('form','submit','input-text')]:
        needs={'page':'start','table':'record','button':'details','form':'form'}
        if checks.get('checks',{}).get(needs[names[0]]) and (names[0]!='page' or checks['checks'].get('tabs')):continue
        file=pages.write_html(directory/('trace-'+names[0]),site(schema.SAMPLE,parts,mode))
        with browser.browser_slot():
            try:
                obs=json.loads(subprocess.run([sys.executable,'-m',MODULE,'trace',str(ROOT/file['file'])],text=True,capture_output=True,timeout=24,check=True).stdout)
            except (subprocess.TimeoutExpired,subprocess.CalledProcessError):obs={}
        def repair(k):
            ex=parent.KINDS[k]
            msg=core.messages(parent.PROMPT+' For writing text use root.textContent or append a text node. env.get returns a value and env.mount appends child schemas. Keep all helpers inside. Output a complete anonymous function(root,component,env){ ... }.',
                     dict(single_type=k,behavior=ex[2],example=ex[1],your_previous_code=parts.get(k),public_runtime=obs,public_checks=checks,
                          expected='First tab shows Local notices. Workshop shows Local guide, Read details opens Shelf amber, and named input plus Save entry visibly shows Entry saved. Never hardcode these example values.'))
            try:return bind(gen.call(ledger,tag,directory/'repairs'/k/'call',msg,'build',3000),True)['source']
            except (gen.MISSING+gen.ERRORS):return ''
        with ThreadPoolExecutor(max_workers=3) as pool:
            candidate=dict(parts);jobs={k:pool.submit(repair,k) for k in names}
            for k,job in jobs.items():
                if fn:=job.result():candidate[k]=fn
        check=public(candidate,True,directory/('after-'+names[0]))
        accept=passing(checks)<=passing(check) and len(candidate)>=len(parts)
        history.append(dict(stage='public-repair-'+names[0],checks=check,retained=accept,trace=obs))
        if accept:parts=candidate;checks=check;mode=True
    valid=len(parts)==len(parent.KINDS) and len(passing(checks))==5
    core.save(dest,dict(status='valid' if valid else 'build_failed',parts=parts,mode=mode,integration=checks,history=history))
    return read(dest)

def generate():
    doc=parent.HERE/'candidates.json';prior=read(doc);reg=OUT/'registration.json'
    files=[Path(__file__),HERE/'outputs.cjs',HERE/'PROTOCOL.md',Path(parent.__file__),doc,
           parent.OUT/'seal.json',parent.previous.native.OUT/'seal.json']
    sums={str(p.relative_to(ROOT)):sha(p) for p in files}
    if not reg.exists():
        balance=check_credits(CAP);assert balance['sufficient']
        core.save(reg,dict(utc=now(),cap=CAP,balance=balance,deadline=gen.END.isoformat(),sources=sums))
    assert read(reg)['sources']==sums
    if (HERE/'candidates.json').exists():return
    rows=prior['rows'];libs=prior['libraries'];tags=[t for t in gen.TAGS if libs[t]['status']=='build_failed']
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    with patch.multiple(gen.BASE,OUT=OUT,END=gen.END,template=gen.settings),ThreadPoolExecutor(max_workers=2) as pool:
        jobs={t:pool.submit(build,t,ledger) for t in tags}
        for t,job in jobs.items():
            lib=job.result();libs[t]={k:v for k,v in lib.items() if k!='parts'}
            for s,arms in rows[t].items():
                plan=read(parent.previous.native.OUT/'plans'/t/s/'record.json')
                if lib['status']!='valid':score=dict(status=lib['status'])
                elif plan['status']!='valid':score={k:v for k,v in plan.items() if k!='config'}
                else:score=pages.write_html(OUT/'sites'/t/s/'self',site(plan['config'],lib['parts'],lib['mode']))
                arms['self']=score
    core.save(OUT/'seal.json',dict(registration=sha(reg),rows=rows,libraries={t:sha(OUT/'build'/t/'library.json') for t in tags}))
    core.save(HERE/'candidates.json',dict(registration=sha(reg),seal=sha(OUT/'seal.json'),previous=sha(doc),rows=rows,libraries=libs,cost=ledger_read.totals(OUT/'budget.sqlite3')))

if __name__=='__main__':
    if sys.argv[1:2]==['trace']:print(json.dumps(trace(Path(sys.argv[2]).read_text())))
    else:
        with browser.lock(OUT/'run.lock'):generate()
