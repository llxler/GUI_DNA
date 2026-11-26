"""Build a model-owned file explorer behind a shared namespace and finite switches."""
from pathlib import Path
import json
import re
import subprocess
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
from studies.public_library_transfer import browser,core
from studies.public_library_transfer.self_refinement.todomvc.event_modules import modules
from studies.study_io import ROOT,read
from studies.webbench.self_build_modules import run as base

FILES={
    'state.js':'Define the shared data model, initial state, selection and persistence helpers.',
    'entries.js':'Create, nest, edit, select, delete, move, copy and rename entries and synchronize editor content.',
    'menu.js':'Build context menus, keyboard shortcuts and clipboard commands; call existing entry operations.',
    'tools.js':'Mount toolbar commands, import/export, generation, filter, resize. Create all visible UI required.',
    'index.js':'Initialize the file explorer on the public starter, connect the modules and bind listeners after mounting.',
    'style.css':'Style the layout, selected entries, toolbar, context menu, drop indicators, resizer and filter.'
}
INTERFACE=('Classic scripts execute in listed order at body end. globalThis.Explorer is initially an empty object. '
    'Put shared helpers/state on that object; reuse exact names. Do not redeclare top-level variables across scripts. '
    'APP_CONFIG is injected beforehand; respect the declared Boolean controls. No imports or network. '
    'All app behaviors and event handlers must be implemented in your files.')


def assemble(pub,lib,plan,dest):
    files=dict(lib['files'])
    html=pub['starter']['index.html']
    boot='<script>globalThis.Explorer={};globalThis.APP_CONFIG='+json.dumps(plan)+';</script>'
    scripts=''.join('<script src="./'+file+'"></script>' for file in FILES if file.endswith('.js') and file in files)
    html=html.replace('</head>','<link rel="stylesheet" href="./style.css"></head>').replace('</body>',boot+scripts+'</body>')
    return core.emit('dom1',{**pub['starter'],**files,'index.html':html},dest)


def observe(root,dest,files):
    page=browser.served_page(root,'dom1',dest,files)
    checks={}
    errors=[]
    with browser.browser_slot(),browser.serve('dom1',page) as url,sync_playwright() as pw,pw.chromium.launch(env=browser.browser_env()) as engine:
        tab=engine.new_page(service_workers='block')
        tab.route('**/*',lambda r:r.continue_() if urlsplit(r.request.url).netloc==urlsplit(url).netloc else r.abort())
        tab.set_default_timeout(1800)
        tab.on('pageerror',lambda e:errors.append(str(e.stack or e).splitlines()[:3]))
        tab.on('dialog',lambda d:d.accept('example') if d.type=='prompt' else d.accept())
        try:
            tab.goto(url+'/index.html',wait_until='load')
            checks['panels']=bool(tab.locator('.tools').count() and tab.locator('.entries').count())
            for kind in ('file','dir'):
                before=tab.locator('.entries .entry.'+kind).count()
                button=tab.locator('.tools button').filter(has_text=re.compile(r'^\s*'+kind+r'\s*$',re.I))
                if button.count():button.first.click()
                checks[kind]=tab.locator('.entries .entry.'+kind).count()>before
        except Exception as exc:errors.append([str(exc).splitlines()[0][:180]])
    return dict(checks=checks,errors=errors,admitted=all(checks.get(k) for k in ('panels','file','dir')) and not errors)


def source(raw,name):
    if name.endswith('.css'):
        fenced=re.search(r'```css\s*\n(.*?)\n\s*```',raw,re.S|re.I)
        value=fenced[1] if fenced else base.uncode(raw)
        if not value.strip():raise ValueError('Empty CSS')
        return value
    value=modules.js_block(raw).strip()
    test=subprocess.run(['node','--check'],input=value,capture_output=True,text=True,timeout=10)
    if test.returncode:raise ValueError('\n'.join(test.stderr.splitlines()[:5]))
    return value


def make(root,tag,rep,pub,ledger,missing):
    folder=root/tag/rep
    saved=folder/'library.json'
    if saved.exists():return read(saved)
    def ask(label,messages,size):
        return base.request(ledger,('table',tag,rep),folder/'calls'/label,messages,'build',size)
    history=[]
    lib={}
    try:
        msgs=core.messages(base.DESIGN,dict(public=pub,module_roles=FILES,shared=INTERFACE))
        for i in range(2):
            raw=ask('design-'+str(i),msgs,3800)
            try:
                design=base.manifest(raw)
                break
            except (ValueError,KeyError,TypeError) as exc:
                if i:raise
                msgs=msgs+[dict(role='assistant',content=raw),dict(role='user',content='Correct the JSON design: '+str(exc))]
        lib=dict(design=design,files={})
        def implement(name,phase,feedback=None):
            input_data=dict(file=name,role=FILES[name],interface=INTERFACE,design=design,
                public_requirements=pub['requirements'],starter=pub['starter'],already_delivered={
                k:v[:6500] for k,v in lib['files'].items() if k!='style.css' and k!=name},
                previous=lib['files'].get(name),public_browser_feedback=feedback)
            msg=core.messages('Return only complete raw source for the ONE requested file. '
                'Use an IIFE for each classic JavaScript file and share through globalThis.Explorer. '+INTERFACE,input_data)
            for attempt in range(2):
                raw=ask(phase+'/'+name+'/'+str(attempt),msg,7000)
                try:return source(raw,name)
                except ValueError as exc:
                    if attempt:raise
                    msg=msg+[dict(role='assistant',content=raw),dict(role='user',content='Fix the parse error; return the complete single file. '+str(exc))]
        for name in FILES:lib['files'][name]=implement(name,'original')
        config={k:k in design['first'] for k in design['controls']}
        def probe(which):
            dest=folder/'public'/which
            return observe(root,dest,assemble(pub,lib,config,dest))
        observation=probe('initial')
        history.append(observation)
        tried=set()
        for turn in range(2):
            if observation['admitted']:break
            trace=' '.join(str(e) for e in observation['errors'])
            named=next((k for k in FILES if k in trace and k not in tried),None)
            fallback=['tools.js','index.js','entries.js'] if not observation['checks'].get('panels') else ['entries.js','tools.js','index.js']
            name=named or next(k for k in fallback if k not in tried)
            tried.add(name)
            old=lib['files'][name]
            lib['files'][name]=implement(name,'integration-'+str(turn),observation)
            trial=probe('repair-'+str(turn))
            old_pass={k for k,v in observation['checks'].items() if v}
            new_pass={k for k,v in trial['checks'].items() if v}
            if old_pass<=new_pass and len(trial['errors'])<=len(observation['errors']):observation=trial
            else:lib['files'][name]=old
            history.append(dict(owner=name,**trial))
        status='valid' if observation['admitted'] else 'build_failed'
        reason='' if status=='valid' else 'Incomplete public add-file or add-directory operation'
    except missing as exc:status,reason='missing',str(exc)
    except (ValueError,TypeError,KeyError,IndexError) as exc:status,reason='build_failed',str(exc)[:300]
    core.save(saved,dict(status=status,reason=reason,library=lib,public=history))
    print('file explorer preparation',tag,rep,status,flush=True)
    return read(saved)
