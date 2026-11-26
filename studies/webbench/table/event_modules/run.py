"""Build same-model table controllers around a shared installer signature and the public starter."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from itertools import combinations
import os
from pathlib import Path
import re
import time
from unittest.mock import patch
from urllib.parse import urlsplit

from gui_dna.budget import Ledger
from playwright.sync_api import sync_playwright
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,read,sha,now
from studies.webbench.compact_planning import run as compact
from studies.webbench.typed_components import run as typed
from studies.webbench.table.shared_state_contract import run as contract
from studies.webbench.table_interactions import run as profiles

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/table-event-modules-20261125'
RESULT=HERE/'result.json'
CAP=1.10
PARTS={
    'table':'Core selection and state helpers, cell click and editable clicks. Preserve original HTML table. Do not attach document keyboard or context menu handlers.',
    'menu':'Right-click menu, outside dismissal, row/column insertion/deletion/selection, filter and sort. Own all contextmenu handling; handle bubbling correctly.',
    'key':'Keyboard movement, clearing, edit start and end, range extension, copy and paste with table growth. Coordinate editing with core.',
    'mouse':'Shift click and mouse drag for rectangular selection. Do not interfere with ordinary click, right click, or editing.',
    'layout':'Resize rows and columns at their edges using the public minimum sizes.',
    'drag':'Reorder selected rows or columns by dragging across their midpoint; distinguish resize handles and cell editing.',
}
SHARED="""The loader passes the same ctx object to every installed module. Core initializes ctx.table to the existing .table;
ctx.selected is a Set of selected td/th; ctx.active and ctx.anchor are td/th or null. Core defines ctx.select(cells, active, anchor)
to update state and .selected CSS classes (cells is any iterable of elements); ctx.startEdit(cell) and ctx.stopEdit().
Only core initializes these fields. Other modules may use standard DOM APIs and these helpers. Work when siblings are omitted.
The loader wraps each returned function body in export default function install(ctx) and imports it from the public common/*.js name.
Return a single JSON object with js (function BODY, without imports, exports or enclosing function) and css strings.
Do not replace starter HTML, use external dependencies, or dispatch on task numbers. Implement all named public interactions."""
TAGS=('gemma','qwen9','qwen')


def register():
    path=OUT/'registration.json'
    if path.exists():
        reg=read(path)
        assert all(sha(ROOT/p)==h for p,h in reg['sources'].items())
        return reg
    bound=profiles.register()['prior_bound']+profiles.CAP+CAP
    balance=check_credits(CAP)
    assert bound<10 and balance['sufficient']
    files=[Path(__file__),HERE/'PROTOCOL.md',Path(contract.__file__),Path(compact.__file__),Path(typed.__file__),
           profiles.OUT/'registration.json']
    models={}
    for tag in TAGS:
        old=compact.base.old_root('table',tag)
        files.extend([old/'inputs/table/public.json',old/'inputs/table/browser.json'])
        model,_,_=compact.controls('table',tag)
        models[tag]=model
    core.save(path,dict(utc=now(),cap=CAP,deadline=compact.END.isoformat(),balance=balance,combined_bound=bound,
                        models=models,targets=list(range(1,21)),sources={str(p.relative_to(ROOT)):sha(p) for p in files}))
    return read(path)


def compile_page(public,parts,enabled,dest):
    names=['table',*enabled]
    files=dict(public['starter'])
    for k,part in parts.items():
        files[f'common/{k}.js']='export default function install(ctx){\n'+part['js']+'\n}'
    imports=[f"import {k} from './common/{k}.js';" for k in names]
    files['index.js']+='\n'+'\n'.join([*imports,'const ctx = {};',*[k+'(ctx);' for k in names]])
    files['index.css']+='\n'+'\n'.join(parts[k]['css'] for k in names)
    tree=core.emit('table',files,dest)
    return dict(status='valid',page=str(dest.relative_to(ROOT)),files=tree)


def observe(page):
    served=browser.served_page(OUT,'table',ROOT/page['page'],page['files'])
    with browser.serve('table',served) as url,sync_playwright() as pw,pw.chromium.launch(env=browser.browser_env()) as engine:
        tab=engine.new_page(service_workers='block')
        tab.route('**/*',lambda r:r.continue_() if urlsplit(r.request.url).netloc==urlsplit(url).netloc else r.abort())
        errors=[]
        tab.on('pageerror',lambda e:errors.append(str(e)[:350]))
        tab.goto(url+'/index.html',wait_until='load')
        cell=tab.locator('tbody td').first
        cell.click(button='right',timeout=3000)
        btn=tab.locator('.menu:visible .menu-item-insert-row-above:visible')
        rows=tab.locator('tbody tr').count()
        if btn.count():btn.first.click(timeout=3000)
        added=tab.locator('tbody tr').count()-rows
        tab.goto(url+'/index.html',wait_until='load')
        tab.locator('tbody td').first.click(timeout=3000)
        selected=tab.locator('tbody td').first.evaluate("e=>e.classList.contains('selected')")
        return dict(insert_delta=added,selected=selected,errors=errors)


def build_part(tag,k,pub,parts,folder,ledger,hint=None):
    inputs=dict(requirements=pub['requirements'],starter=pub['starter'],contract=SHARED,role=PARTS[k],file=f'common/{k}.js')
    if k!='table':inputs['installed_core']=parts['table']['js']
    if hint:inputs.update(previous=parts[k],public_observation=hint)
    msg=core.messages('Implement this one complete reusable table component.',inputs)
    for attempt in range(1 if hint else 2):
        raw=compact.base.request(ledger,('table',tag,'a'),folder/str(attempt),msg,'build',8192)
        try:return contract.component_ok(compact.base.parse_json(raw))
        except compact.base.ERRORS as err:
            msg=msg+[dict(role='assistant',content=raw),dict(role='user',content='Correct the JSON or function syntax: '+str(err)[:400])]
    raise ValueError('Invalid component '+k)


def generate(tag,reg):
    base=compact.base
    folder=OUT/tag
    if (folder/'seal.json').exists():return
    pub=read(base.old_root('table',tag)/'inputs/table/public.json')
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    optional=list(PARTS)[1:]
    parts={};probes=[];rows=[];failures=[]
    try:
        parts['table']=build_part(tag,'table',pub,parts,folder/'build/table',ledger)
        with ThreadPoolExecutor(max_workers=3) as pool:
            returned=list(pool.map(lambda k:build_part(tag,k,pub,parts,folder/'build'/k,ledger),optional))
        parts.update(zip(optional,returned))
        fixed=compile_page(pub,parts,optional,folder/'public/initial')
        probes.append(observe(fixed))
        for k in ('table','menu'):
            obs=probes[-1]
            if (k=='table' and obs['selected']) or (k=='menu' and obs['insert_delta']==1 and not obs['errors']):continue
            parts[k]=build_part(tag,k,pub,parts,folder/'public-repair'/k,ledger,obs)
            fixed=compile_page(pub,parts,optional,folder/'public'/k)
            probes.append(observe(fixed))
        obs=probes[-1]
        if not (obs['selected'] and obs['insert_delta']==1 and not obs['errors']):raise ValueError('Public actions failed')
        menu=[optional,*[list(x) for i in range(len(optional)) for x in combinations(optional,i)]]
        opts=[{'enabled':v} for v in menu]
        def choose(n):
            dest=folder/'deployment'/str(n)
            msg=compact.make_messages(pub,n,dict(plan_documentation=PARTS),opts,False)
            try:
                raw=base.request(ledger,('table',tag,'a'),dest/'call',msg,'plan',8192)
                v=base.uncode(raw).strip()
                if not re.fullmatch(r'[0-9]{1,2}',v) or int(v)>=len(menu):raise ValueError('Invalid selection')
                return compile_page(pub,parts,menu[int(v)],dest/'page')
            except typed.MISSING as exc:return dict(status='missing',reason=str(exc))
            except base.ERRORS as exc:return dict(status='invalid',reason=str(exc)[:250])
        with ThreadPoolExecutor(max_workers=3) as pool:plans=list(pool.map(choose,reg['targets']))
        for n,plan in zip(reg['targets'],plans,strict=True):
            rows.extend([dict(project='table',task=n,arm='planned',**plan),dict(project='table',task=n,arm='fixed',**fixed)])
        state='valid'
    except typed.MISSING as exc:state='missing';failures.append(str(exc))
    except base.ERRORS as exc:state='build_failed';failures.append(str(exc))
    core.save(folder/'parts.json',parts)
    core.save(folder/'seal.json',dict(tag=tag,model=reg['models'][tag],registration=sha(OUT/'registration.json'),
        parts_sha256=sha(folder/'parts.json'),status=state,reasons=failures,public=probes,rows=rows))
    print('sealed',tag,state,flush=True)


def main(action):
    reg=register()
    if action=='generate':
        orig=compact.base.template
        def settings(p,t,s):
            cfg=orig(p,t,s)
            if t=='qwen9':cfg['reasoning']={'enabled':False}
            return cfg
        with patch.multiple(compact.base,OUT=OUT,END=compact.END,template=settings),ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda t:generate(t,reg),TAGS))
    if action=='score':
        for k in tuple(os.environ):
            if k.endswith(('_API_KEY','_AUTH_TOKEN','_ACCESS_TOKEN')):os.environ.pop(k)
        browser.OUT=OUT
        protocol=browser.verify_contract('table')
        cases=[]
        for t in TAGS:
            folder=OUT/t
            while not (folder/'seal.json').exists():
                if datetime.now(timezone.utc)>=compact.END:raise SystemExit('deadline')
                time.sleep(2)
            seal=read(folder/'seal.json')
            assert seal['registration']==sha(OUT/'registration.json') and sha(folder/'parts.json')==seal['parts_sha256']
            assert protocol==read(compact.base.old_root('table',t)/'inputs/table/browser.json')
            vals=browser.evaluate(seal['rows'],OUT,{'table':protocol},2)
            rows=[{k:v for k,v in r.items() if k in ('task','arm','status','passed','reason','report_sha256')} for r in vals]
            for r in rows:
                if r['status']=='invalid':r['passed']=False
            cases.append(dict(**{k:v for k,v in seal.items() if k!='rows'},seal_sha256=sha(folder/'seal.json'),rows=rows))
            print('scored',t,flush=True)
        core.save(RESULT,dict(registration=sha(OUT/'registration.json'),cases=cases,cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('register','generate','score'))
    main(parser.parse_args().action)
