"""Materialize sealed offline websites and bind the original, pinned AMIS package."""
from contextlib import contextmanager
from html import escape
import json
import mimetypes
from pathlib import Path
from urllib.parse import unquote,urlsplit

from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,sha
from .schema import SAMPLE

UP=ROOT/'artifacts/webgen-bench'
SDK=UP/'packages/amis-6.13.0/sdk'
ORIGIN='http://webgen.localhost'
GROUPS={
 'layout':['page','tabs','panel','container','tpl'],
 'records':['table'],
 'input':['input-text','input-number','textarea','select','checkbox'],
 'form':['form','submit'],
 'actions':['button','dialog'],
}
ABI="""Implement function renderNode(node, ctx) returning a newly created DOM element. No imports/fetch or external resources.
Your function handles ONLY the listed types. ctx.render(nodeOrArray) produces a DOM element/fragment for children.
ctx.data is the root page's mutable initial data (including literal arrays). ctx.text(value) interpolates simple ${field} references.
ctx.get(name) gets a field by its plain name. The form uses standard HTML controls with name and value. Submit buttons use type=submit.
Use DOM textContent for labels, values and data. Avoid re-invoking ctx.render on the same node/type. Tabs must actually switch their body,
tables read source using ctx.data, forms validate and support the declared submitSucc toast; implement actionType=dialog opening its body."""
BASE_CSS='body{font:16px system-ui,sans-serif;color:#233346;margin:0}main{max-width:76rem;margin:auto;padding:1.5rem}button,input,select,textarea{font:inherit;margin:.3rem;padding:.4rem}table{border-collapse:collapse}th,td{border:1px solid #bbc5d0;padding:.4rem}button{cursor:pointer}'
def page(config, library, title='App'):
    data=json.dumps(config,ensure_ascii=False).replace('<',r'\u003c')
    if library=='human':
        body='<link rel="stylesheet" href="/sdk/sdk.css"><script src="/sdk/sdk.js"></script>'
        run="amisRequire('amis/embed').embed('#app',schema,{locale:'en-US'},{locale:'en-US'});"
    else:
        body='<style>'+BASE_CSS+'</style>'
        declarations='\n'.join('const mod'+str(i)+'=('+src+');' for i,src in enumerate(library.values()))
        calls=','.join(json.dumps(t)+':mod'+str(i) for i,k in enumerate(library) for t in GROUPS[k])
        run=declarations+'\nconst handlers={'+calls+"};const state=schema.data||{};const ctx={data:state,get:k=>state[k],text:s=>String(s??'').replace(/\\$\\{([\\w.]+)\\}/g,(_,k)=>String(state[k]??'')),render:function(n){if(Array.isArray(n)){let f=document.createDocumentFragment();for(const child of n)f.append(this.render(child));return f;}if(!n||!handlers[n.type])return document.createTextNode('');return handlers[n.type](n,this);}};document.querySelector('#app').append(ctx.render(schema));"
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>'+escape(title)+'</title>'+body+'</head><body><main id="app"></main><script>const schema='+data+';\n'+run+'</script></body></html>'

def write_html(folder,html):
    f=folder/'index.html';folder.mkdir(parents=True,exist_ok=True)
    if f.exists():assert f.read_text()==html
    else:f.write_text(html)
    return dict(status='valid',file=str(f.relative_to(ROOT)),sha256=sha(f))

@contextmanager
def local_tab(engine,html,*,sdk=False):
    ctx=engine.new_context(viewport={'width':1024,'height':768},device_scale_factor=1,service_workers='block',accept_downloads=False)
    def route(req):
        u=urlsplit(req.request.url)
        if u.scheme!='http' or u.netloc!='webgen.localhost' or req.request.method!='GET':return req.abort()
        loc=unquote(u.path)
        if loc in ('','/','/index.html'):return req.fulfill(status=200,content_type='text/html; charset=utf-8',body=html,
             headers={'Content-Security-Policy':"default-src 'self' data: blob:; script-src 'self' 'unsafe-inline' 'unsafe-eval' blob:; style-src 'self' 'unsafe-inline'; connect-src 'none'; object-src 'none'; frame-src 'none'; base-uri 'none'; form-action 'none'"})
        if sdk and loc.startswith('/sdk/'):
            f=(SDK/loc[5:]).resolve()
            if f.is_relative_to(SDK.resolve()) and f.is_file():
                return req.fulfill(path=f,content_type=mimetypes.guess_type(str(f))[0] or 'application/octet-stream')
        return req.fulfill(status=404,body='')
    ctx.route('**/*',route)
    tab=ctx.new_page()
    try:
        tab.set_default_timeout(1800)
        tab.goto(ORIGIN+'/',wait_until='load',timeout=12000)
        yield tab
    finally:ctx.close()

def check(html,sdk=False):
    from playwright.sync_api import sync_playwright, Error
    checks={k:False for k in ('start','tabs','record','details','form')}
    errors=[]
    with browser.browser_slot(),sync_playwright() as pw,pw.chromium.launch(env=browser.browser_env()) as eng,local_tab(eng,html,sdk=sdk) as tab:
        try:
            tab.get_by_text('Local notices',exact=True).first.wait_for();checks['start']=True
            tab.get_by_text('Workshop',exact=True).first.click()
            tab.get_by_text('Read details',exact=True).first.wait_for();checks['tabs']=True
            checks['record']=tab.get_by_text('Local guide',exact=True).first.is_visible()
            tab.get_by_text('Read details',exact=True).first.click()
            tab.get_by_text('Shelf amber',exact=True).first.wait_for();checks['details']=True
        except Error as e:errors.append(str(e).splitlines()[0])
        try:
            tab.reload(wait_until='load')
            tab.get_by_text('Workshop',exact=True).first.click()
            box=tab.locator('input[name=nickname],input[type=text],input:not([type])').first
            box.fill('Ada')
            tab.get_by_text('Save entry',exact=True).first.click()
            tab.get_by_text('Entry saved',exact=True).first.wait_for()
            checks['form']=True
        except Error as e:errors.append(str(e).splitlines()[0])
    return dict(checks=checks,errors=errors)
