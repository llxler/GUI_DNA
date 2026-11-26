"""Assign each installer only its own public requirement texts and observe the shared interface."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
import time
from unittest.mock import patch
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
from scripts.check_openrouter_credits import check_credits
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,read,sha,now
from studies.webbench.form.flash_self_build.visible_targets import run as flash
from . import run as parent,source_recovery as recovery

HERE=parent.HERE
OUT=ROOT/'artifacts/table-focused-installers-20261125'
RESULT=HERE/'focused-result.json'
CAP=1
SCOPES={'table':(4,11),'menu':(1,2,3,7,19,20),'key':(5,6,8,9,12,13,14),
        'mouse':(9,10),'layout':(15,16),'drag':(17,18)}
CONTRACT="""ctx.table is the real starter table, ctx.selected a Set, ctx.active and ctx.anchor cells or null.
Core must assign functions as properties ctx.select(cells,active,anchor), ctx.startEdit(cell), ctx.stopEdit(), for all sibling modules to call.
ctx.select replaces the selected set and classes and records active and anchor. Only core defines these helpers.
Implement ONLY your assigned role and requirements, using DOM events and these shared functions. No sibling installation or imports."""


def register():
    path=OUT/'registration.json'
    if path.exists():
        reg=read(path)
        assert all(sha(ROOT/p)==h for p,h in reg['sources'].items())
        return reg
    old=recovery.register()
    bound=flash.register()['combined_bound']+CAP
    balance=check_credits(CAP)
    assert bound<10 and balance['sufficient']
    files=[Path(__file__),HERE/'focused.md',Path(recovery.__file__),Path(parent.__file__),recovery.OUT/'registration.json',flash.OUT/'registration.json']
    core.save(path,dict(utc=now(),balance=balance,cap=CAP,combined_bound=bound,deadline=old['deadline'],targets=old['targets'],models=old['models'],
              eligibility='All publicly failed source-recovery builds, irrespective of scores.',sources={str(p.relative_to(ROOT)):sha(p) for p in files}))
    return read(path)


def component(tag,k,pub,parts,folder,ledger,hint=None):
    messages=core.messages('Write one ES module exporting default function install(ctx). Return only JavaScript. Do not include other modules or an extra call to install. Keep the module concise. ' + CONTRACT,
        dict(module='common/'+k+'.js',role=parent.PARTS[k],initial_html=pub['starter']['index.html'],
             requirements=[pub['requirements'][n-1]['description'] for n in SCOPES[k]]))
    if hint:
        messages.extend([dict(role='assistant',content=parts[k]['js']),dict(role='user',content='Correct this entire module using the observed public interaction. Return the actual working implementation. '+str(hint))])
    for attempt in range(1 if hint else 2):
        raw=parent.compact.base.request(ledger,('table',tag,'a'),folder/str(attempt),messages,'build',5500)
        try:return recovery.recover(raw)
        except parent.compact.base.ERRORS as err:messages.append(dict(role='user',content='Return a valid complete install(ctx) module. '+str(err)[:180]))
    raise ValueError('Unusable public source for '+k)


def observe(page):
    served=browser.served_page(OUT,'table',ROOT/page['page'],page['files'])
    with browser.serve('table',served) as url,sync_playwright() as pw,pw.chromium.launch(env=browser.browser_env()) as engine:
        tab=engine.new_page(service_workers='block')
        tab.route('**/*',lambda r:r.continue_() if urlsplit(r.request.url).netloc==urlsplit(url).netloc else r.abort())
        errors=[]
        tab.on('pageerror',lambda e:errors.append(str(e)[:260]))
        tab.goto(url+'/index.html',wait_until='load')
        api=tab.evaluate("""async()=>{const {publicState:s}=await import('/index.js');return Object.fromEntries(['select','startEdit','stopEdit'].map(k=>[k,typeof s[k]==='function']))}""")
        cell=tab.locator('tbody td').first
        cell.click(timeout=3000)
        clicked=cell.evaluate("e=>e.classList.contains('selected')")
        tab.goto(url+'/index.html',wait_until='load')
        cell.click(button='right',timeout=3000)
        btn=tab.locator('.menu:visible .menu-item-insert-row-above:visible')
        visible=tab.locator('.menu:visible').count()
        items=tab.locator('.menu:visible').all_text_contents()
        before=tab.locator('tbody tr').count()
        if btn.count():btn.first.click(timeout=3000)
        return dict(insert_delta=tab.locator('tbody tr').count()-before,selected=clicked and all(api.values()),clicked=clicked,
                    shared_functions=api,visible_menus=visible,menu_text=items,errors=errors)


def main(action):
    reg=register()
    if action=='generate':
        original_compile=parent.compile_page
        def compile_page(pub,parts,enabled,dest):
            starter=dict(pub['starter'])
            starter['index.js']+='\nexport {ctx as publicState};\n'
            prefix="Object.assign(ctx,{table:document.querySelector('.table'),selected:new Set(),active:null,anchor:null});\n"
            adjusted=dict(parts,table=dict(parts['table'],js=prefix+parts['table']['js']))
            return original_compile(dict(pub,starter=starter),adjusted,enabled,dest)
        orig=parent.compact.base.template
        def settings(p,t,s):
            cfg=orig(p,t,s)
            if t=='qwen9':cfg['reasoning']={'enabled':False}
            return cfg
        def one(t):
            prev=recovery.OUT/t/'seal.json'
            recovery.wait_for(prev)
            if read(prev)['status']=='build_failed':parent.generate(t,reg)
            elif not (OUT/t/'seal.json').exists():
                core.save(OUT/t/'parts.json',{})
                core.save(OUT/t/'seal.json',dict(tag=t,model=reg['models'][t],registration=sha(OUT/'registration.json'),
                    parts_sha256=sha(OUT/t/'parts.json'),status='ineligible',reasons=['Earlier preparation '+read(prev)['status']],public=[],rows=[]))
        with patch.multiple(parent,OUT=OUT,CAP=CAP,build_part=component,compile_page=compile_page,observe=observe),patch.multiple(parent.compact.base,OUT=OUT,END=parent.compact.END,template=settings),ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(one,parent.TAGS))
    elif action=='score':
        for t in parent.TAGS:recovery.wait_for(OUT/t/'seal.json')
        with patch.multiple(parent,OUT=OUT,RESULT=RESULT,register=lambda:reg):parent.main('score')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('register','generate','score'))
    main(parser.parse_args().action)
