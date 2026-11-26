"""Generate behavior implementations with a DOM mount supplied for each component."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
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
from ..native_plans import run as native

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/webgen-mounted-components-20261126pm'
CAP = .60
MODULE = 'studies.webgen_bench.functional_pilot.mounted_components.run'
ABI = """Write only function mountNode(el,node,ctx){...} with all helpers inside.
The parent el exists and is already in the document. Append DOM elements to el. Return nothing.
ctx.mount(parentElement,nodeOrArray) appends children handled by the dispatcher. It returns nothing.
ctx.data is the root data object, ctx.get(name) reads it, ctx.text(str) interpolates simple names.
You handle the types listed, including events. Use native form controls with names, labels, and buttons.
No imports, remote services or dependencies. Text is plain. Do not hardcode the public example."""
ROLES = {
 'layout': 'page and panel mount heading and body; tpl uses textContent=ctx.text(node.tpl); tabs switch real panes and mount each tab.body, whether array or single. container mounts body.',
 'records': 'table strips literal ${ and } from source to obtain key, reads ctx.data[key] as array. Render a real th for each column.label and td for row[column.name].',
 'actions': 'button has visible label and actionType. For dialog, display dialog.title, mount dialog.body, and provide a close control. Toast shows supplied message.',
 'input': 'Mount visible labeled native named input, select or textarea depending on type, with value, options, and required if set.',
 'form': 'Mount native form. ctx.mount(form,node.body) and ctx.mount(form,node.actions), both inside form. submit renderer appends native button type=submit with label. On valid submit preventDefault, collect named values, and show text from node.onEvent.submitSucc.actions[0].args.msg when supplied. No server.',
}
# These stubs isolate a group during its synthetic test; they never enter a deployed site.
TEST_STUB = """function mountNode(el,n,c){if(n.type==='tpl'){el.textContent=n.tpl;}
else if(n.type==='input-text'){let x=document.createElement('input');x.name=n.name;el.append(x);}
else if(n.type==='submit'){let x=document.createElement('button');x.type='submit';x.textContent=n.label;el.append(x);}}"""
def html(config, parts, *, unit=False):
    handlers = []
    for group, types in pages.GROUPS.items():
        func = parts.get(group, TEST_STUB if unit else '')
        if func:
            handlers.extend(json.dumps(t) + ':(' + func + ')' for t in types)
    script=(HERE/'mount.js').read_text().replace('HANDLERS','{'+','.join(handlers)+'}')
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>App</title><style>'+
            pages.BASE_CSS+'</style></head><body><main id="app"></main><script>const schema='+
            json.dumps(config,ensure_ascii=False).replace('<',r'\u003c')+';\n'+script+'</script></body></html>')

def probe(group,source):
    from playwright.sync_api import sync_playwright
    tabset=schema.SAMPLE['body'][0]
    records,button,form=tabset['tabs'][1]['body']
    configs={'layout':schema.SAMPLE,'records':records|{'data':schema.SAMPLE['data']},'actions':button,'input':form['body'][0],'form':form}
    with sync_playwright() as pw,pw.chromium.launch(env=browser.browser_env()) as eng,pages.local_tab(eng,html(configs[group],{group:source},unit=True)) as tab:
        errors=[];tab.on('pageerror',lambda e:errors.append(str(e)[:140]))
        def visible(text):return tab.get_by_text(text,exact=True).first.is_visible()
        try:
            if group=='layout':
                start=visible('Local notices');tab.get_by_text('Workshop',exact=True).first.click()
                passed=start and not visible('Local notices') and visible('Workshop')
            elif group=='records':passed=visible('Book') and visible('Local guide')
            elif group=='actions':
                tab.get_by_text('Read details',exact=True).first.click();passed=visible('Shelf amber')
            elif group=='input':
                box=tab.locator('input[name=nickname]');box.fill('Ada');passed=box.input_value()=='Ada' and box.evaluate('e=>e.required')
            else:
                tab.locator('input[name=nickname]').fill('Ada');tab.get_by_text('Save entry',exact=True).first.click();passed=visible('Entry saved')
        except Exception as exc:passed=False;errors.append(str(exc).splitlines()[0])
        return dict(passed=passed,errors=errors,visible=tab.locator('body').inner_text()[:280])

def check(mode,path,group=''):
    with browser.browser_slot():
        try:
            ret=subprocess.run([sys.executable,'-m',MODULE,mode,str(path),group],capture_output=True,text=True,timeout=32,check=True)
            return json.loads(ret.stdout)
        except (subprocess.TimeoutExpired,subprocess.CalledProcessError) as exc:
            return dict(passed=False,checks={},errors=[type(exc).__name__])

def build(tag,briefs,ledger):
    folder=OUT/'build'/tag;dest=folder/'library.json'
    if dest.exists():return read(dest)
    def component(group):
        history=[]
        msg=core.messages(ABI,dict(role=ROLES[group],types={t:schema.FIELDS[t] for t in pages.GROUPS[group]},public_websites=briefs,public_example=schema.SAMPLE))
        for i in range(2):
            work=folder/group/str(i);raw=''
            try:
                raw=gen.call(ledger,tag,work/'call',msg,'build',4000)
                code=gen.BASE.uncode(raw).strip()
                fence=re.search(r'```(?:javascript|js)?\s*\n([\s\S]*?)```',code,re.I)
                fn=gen.transport.build.modules
                r=subprocess.run(['node',str(fn.HERE/'function.cjs'),str(fn.ACORN)],input=json.dumps(dict(name='mountNode',arity=3,text=fence[1] if fence else code)),capture_output=True,text=True,timeout=8)
                if r.returncode or not r.stdout:raise ValueError('Return the complete named three-argument function.')
                path=work/'function.js';path.write_text(r.stdout);obs=check('unit',path,group)
                history.append(obs)
                if obs['passed']:return r.stdout,history
            except gen.MISSING as e:history.append(dict(error=str(e)));break
            except (ValueError,subprocess.TimeoutExpired) as e:obs=dict(error=str(e));history.append(obs)
            msg += [dict(role='assistant',content=raw),dict(role='user',content='Correct the complete function using this independent public browser observation: '+json.dumps(obs))]
        return '',history
    with ThreadPoolExecutor(max_workers=3) as pool:
        fs={k:pool.submit(component,k) for k in ROLES}
        values={k:v.result() for k,v in fs.items()}
    parts={k:fn for k,(fn,_) in values.items() if fn}
    rec=pages.write_html(folder/'sample',html(schema.SAMPLE,parts))
    obs=check('integration',ROOT/rec['file'])
    status='valid' if len(parts)==len(ROLES) and len(obs['checks'])==5 and all(obs['checks'].values()) else 'build_failed'
    core.save(dest,dict(status=status,parts=parts,units={k:v[1] for k,v in values.items()},integration=obs))
    return read(dest)

def generate():
    doc=native.HERE/'candidates.json';prev=read(doc)
    src=[Path(__file__),HERE/'PROTOCOL.md',HERE/'mount.js',doc,Path(pages.__file__),Path(gen.__file__),gen.OUT/'generation-input.json',native.OUT/'seal.json']
    hashes={str(p.relative_to(ROOT)):sha(p) for p in src}
    reg=OUT/'registration.json'
    if not reg.exists():
        b=check_credits(CAP);assert b['sufficient']
        core.save(reg,dict(utc=now(),cap=CAP,balance=b,sources=hashes,deadline=gen.END.isoformat()))
    assert read(reg)['sources']==hashes
    if (HERE/'candidates.json').exists():return
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP);rows=prev['rows'];libs={}
    tags=[t for t in gen.TAGS if prev['libraries'][t]['status']=='build_failed']
    with patch.multiple(gen.BASE,OUT=OUT,END=gen.END,template=gen.settings),ThreadPoolExecutor(max_workers=2) as pool:
        fs={t:pool.submit(build,t,read(gen.OUT/'generation-input.json'),ledger) for t in tags}
        for t,f in fs.items():
            lib=f.result();libs[t]={k:v for k,v in lib.items() if k!='parts'}
            for site,arms in rows[t].items():
                plan=read(native.OUT/'plans'/t/site/'record.json')
                if lib['status']!='valid':v=dict(status=lib['status'])
                elif plan['status']!='valid':v={k:a for k,a in plan.items() if k!='config'}
                else:v=pages.write_html(OUT/'sites'/t/site/'self',html(plan['config'],lib['parts']))
                arms['self']=v
    core.save(OUT/'seal.json',dict(sources=hashes,rows=rows,libraries={t:sha(OUT/'build'/t/'library.json') for t in tags}))
    core.save(HERE/'candidates.json',dict(registration=sha(reg),seal=sha(OUT/'seal.json'),previous=sha(doc),libraries=prev['libraries']|libs,rows=rows,cost=ledger_read.totals(OUT/'budget.sqlite3')))

if __name__=='__main__':
    if sys.argv[1:2]==['unit']:print(json.dumps(probe(sys.argv[3],Path(sys.argv[2]).read_text())))
    elif sys.argv[1:2]==['integration']:
        with patch.object(browser,'browser_slot',nullcontext):print(json.dumps(pages.check(Path(sys.argv[2]).read_text())))
    else:
        with browser.lock(OUT/'run.lock'):generate()
