"""Build a minimal file-tree core, then compose independently verified DOM capabilities."""
from concurrent.futures import ThreadPoolExecutor
from itertools import combinations
from pathlib import Path
import re
from urllib.parse import urlsplit
from unittest.mock import patch

from gui_dna.budget import Ledger
from playwright.sync_api import sync_playwright
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,now,read,sha
from ..library_sources import run as original

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/file-explorer-dom-20261126'
CAP=1.50
action=original.action
MODULES={'core':(1,2,3,4,5),'menu':(7,8,9,10,20),'exchange':(11,12),'autosave':(13,),
         'resize':(17,18),'generate':(16,),'filter':(19,),'keys':(14,15),'drag':(6,)}
DESCRIPTION={'core':'Toolbar and file tree; create, select, open, delete entries. Supply real styles and working nested directories.',
             'menu':'Context menus and commands for file, directory and background.',
             'exchange':'Import and export document data through the requested controls.',
             'autosave':'Update the selected file content when the user edits the textarea.',
             'resize':'A visible drag handle changes leftbar width.',
             'generate':'Generate requested numbers of actual file and directory nodes.',
             'filter':'A prompt filters the visible entries by name.',
             'keys':'Keyboard shortcuts and menu command labels.',
             'drag':'Allow actual files and folders to move by drag and drop.'}


def register():
    f=OUT/'registration.json'
    parent=read(original.OUT/'registration.json')
    files=[Path(__file__),HERE/'PROTOCOL.md',Path(original.library.__file__),original.OUT/'registration.json',
           original.OUT/'public.json',original.OUT/'browser.json',Path(browser.__file__)]
    files += [original.OUT/t/r/'library.json' for t in original.TAGS for r in original.REPS]
    sums={str(p.relative_to(ROOT)):sha(p) for p in files}
    if not f.exists():
        b=check_credits(CAP)
        assert b['sufficient']
        core.save(f,dict(utc=now(),cap=CAP,deadline=action.END.isoformat(),balance=b,models=parent['models'],targets=parent['targets'],sources=sums))
    assert read(f)['sources']==sums
    return read(f)


def emit(pub,modules,dest):
    # Each script has its own lexical scope. UI effects and their semantics come from the model's source.
    scripts=''.join('<script src="./'+n+'.js"></script>' for n in modules)
    html=pub['starter']['index.html'].replace('</body>',scripts+'</body>')
    files={'index.html':html,**{n+'.js':f'(function(){{\n{src}\n}})();' for n,src in modules.items()}}
    return original.emit(dest,core.emit('dom1',files,dest))


def exercise(candidate,extensions):
    root=ROOT/candidate['page']
    base=original.library.observe(OUT,root,candidate['files'])
    if not base['admitted'] or not extensions:return base
    stage=browser.served_page(OUT,'dom1',root,candidate['files'])
    with browser.browser_slot(),browser.serve('dom1',stage) as url,sync_playwright() as pw,pw.chromium.launch(env=browser.browser_env()) as engine:
        tab=engine.new_page(service_workers='block')
        tab.route('**/*',lambda r:r.continue_() if urlsplit(r.request.url).netloc==urlsplit(url).netloc else r.abort())
        tab.set_default_timeout(1600)
        tab.on('pageerror',lambda e:base['errors'].append(str(e).splitlines()[0][:220]))
        dialogs=[]
        def accept(d):
            dialogs.append(d.type)
            d.accept('unmatched-search-text' if d.type=='prompt' else None)
        tab.on('dialog',accept)
        def button(name):return tab.locator('.tools button').filter(has_text=re.compile(r'^\s*'+name+r'\s*$',re.I)).first
        def probe(n):
            tab.goto(url+'/index.html',wait_until='load')
            button('file').click()
            file=tab.locator('.entries .entry.file').first
            if n=='menu':
                file.click(button='right')
                return tab.locator('.menu:visible .menu-item-delete:visible').count()>0
            if n=='exchange':return button('exp').count()>0 and button('imp').count()>0
            if n=='autosave':
                file.click()
                tab.locator('.editor').fill('A public edit')
                tab.locator('.editor').dispatch_event('change')
                return file.get_attribute('data-content')=='A public edit'
            if n=='resize':
                bar=tab.locator('.leftbar').first
                x=bar.bounding_box()
                bar.hover()
                tab.mouse.move(x['x']+x['width']-2,x['y']+60)
                tab.mouse.down();tab.mouse.move(x['x']+x['width']+42,x['y']+60,steps=6);tab.mouse.up()
                return bar.bounding_box()['width']>x['width']+10
            if n=='generate':
                button('gen').click()
                return tab.locator('.entries > .entry').count()>=90
            if n=='filter':
                dialogs.clear();button('filter').click()
                return 'prompt' in dialogs and not file.is_visible()
            if n=='keys':
                before=tab.locator('.entries .entry.file').count()
                tab.keyboard.press('Control+j')
                return tab.locator('.entries .entry.file').count()>before
            if n=='drag':
                button('dir').click();directory=tab.locator('.entries .entry.dir').first
                file.drag_to(directory)
                return directory.locator('.dir-content .entry.file').count()>0
            raise ValueError(n)
        for name in extensions:
            try:base['checks'][name]=bool(probe(name))
            except Exception as e:
                base['checks'][name]=False
                base.setdefault('interaction_failures',{})[name]=str(e).splitlines()[0][:180]
    base['admitted']=all(base['checks'].values()) and not base['errors']
    return base


def library(tag,rep,pub,ledger):
    root=OUT/tag/rep
    f=root/'library.json'
    if f.exists():return read(f)
    sources={}
    history=[]
    missing_core=False
    for name,indices in MODULES.items():
        previous=None
        feedback=None
        for attempt in range(2):
            msg=core.messages('Write one compact, complete vanilla JavaScript file for an existing static file explorer. '
              'The script runs at the END of body, after the listed existing scripts. Use the real accessible DOM. '
              'Add CSS by appending a style element if needed. No imports, Markdown, bundler, placeholders or external assets. '
              'Implement only the stated feature; do not rewrite the page or invent another UI. Stay within 110 lines.',
              dict(feature=DESCRIPTION[name],public_requirements=[pub['requirements'][i-1]['description'] for i in indices],
                   original_html=pub['starter']['index.html'],existing_core=sources.get('core','')[:6500] if name!='core' else None,
                   previous=previous,public_observation=feedback))
            try:
                raw=original.base.request(ledger,('table',tag,rep),root/'calls'/name/str(attempt),msg,'build',5600)
                previous=original.library.source(raw,'module.js')
                trial={**sources,name:previous}
                page=emit(pub,trial,root/'public'/name/str(attempt))
                observation=exercise(page,[s for s in trial if s!='core'])
                history.append(dict(name=name,attempt=attempt,**observation))
                if observation['admitted']:
                    sources=trial
                    break
                feedback=observation
            except action.typed.MISSING as exc:
                history.append(dict(name=name,attempt=attempt,missing=str(exc)))
                if name=='core':missing_core=True
                break
            except ValueError as exc:
                feedback=str(exc);previous=raw[:5500]
                history.append(dict(name=name,attempt=attempt,invalid=feedback[:250]))
        if name=='core' and name not in sources:break
    status='valid' if 'core' in sources and len(sources)>1 else ('missing' if missing_core else 'build_failed')
    core.save(f,dict(status=status,source=sources,public=history))
    print('file explorer extensions',tag,rep,status,list(sources),flush=True)
    return read(f)


def main(phase):
    reg=register()
    targets=reg['targets']
    pub=read(original.OUT/'public.json')
    if phase=='generate':
        ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
        def build(pair):
            t,r=pair
            lib=library(t,r,pub,ledger)
            if lib['status']!='valid':return
            folder=OUT/t/r
            names=[k for k in lib['source'] if k!='core']
            choices=[tuple(p) for n in range(len(names)+1) for p in combinations(names,n)]
            def create(selected,dest):
                return emit(pub,{k:s for k,s in lib['source'].items() if k=='core' or k in selected},dest)
            control=create([],folder/'core-only')
            fixed=create(names,folder/'fixed')
            def pick(n):
                dest=folder/'targets'/str(n)
                msg=action.compact.make_messages(pub,n,dict(plan_documentation={k:DESCRIPTION[k] for k in names}),[dict(enabled=c) for c in choices],False)
                try:
                    raw=original.base.request(ledger,('table',t,r),dest/'call',msg,'plan',2300)
                    num=original.base.uncode(raw).strip()
                    if not re.fullmatch('[0-9]+',num) or int(num)>=len(choices):raise ValueError('Invalid index')
                    return create(choices[int(num)],dest/'page')
                except action.typed.MISSING as e:return dict(status='missing',reason=str(e))
                except ValueError as e:return dict(status='invalid',reason=str(e))
            rows=[]
            with ThreadPoolExecutor(max_workers=2) as pool:
                for n,val in zip(targets,pool.map(pick,targets),strict=True):
                    for arm,result in [('planned',val),('fixed',fixed),('core',control)]:
                        rows.append(dict(task=n,project='dom1',arm=arm,**result))
            core.save(folder/'deployment.json',dict(library=sha(folder/'library.json'),rows=rows))
        with patch.multiple(original.base,OUT=OUT,END=action.END,template=action.settings),ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(build,((t,r) for t in original.TAGS for r in original.REPS)))
        empty=emit(pub,{},OUT/'starter')
        files=[*OUT.glob('*/*/library.json'),*OUT.glob('*/*/deployment.json')]
        core.save(OUT/'seal.json',dict(registration=sha(OUT/'registration.json'),sources={str(p.relative_to(OUT)):sha(p) for p in files},empty=empty))
        return
    seal=read(OUT/'seal.json')
    assert seal['registration']==sha(OUT/'registration.json') and all(sha(OUT/p)==v for p,v in seal['sources'].items())
    protocol=browser.verify_contract('dom1')
    assert read(original.OUT/'browser.json')==protocol
    rows=[dict(task=n,project='dom1',tag='starter',rep='-',arm='host',**seal['empty']) for n in targets]
    libraries={}
    for t in original.TAGS:
        for r in original.REPS:
            f=OUT/t/r/'library.json';lib=read(f)
            libraries.setdefault(t,{})[r]=dict(status=lib['status'],source_sha256=sha(f),options=list(lib['source']),public=lib['public'])
            if lib['status']=='valid':
                deployed=read(f.with_name('deployment.json'))
                assert deployed['library']==sha(f)
                rows.extend(dict(tag=t,rep=r,**v) for v in deployed['rows'])
    graded=browser.evaluate(rows,OUT,{'dom1':protocol},3)
    values=[dict(tag=r['tag'],rep=r['rep'],task=r['task'],arm=r['arm'],status=r['status'],
                 passed=False if r['status']=='invalid' else r['passed'],report_sha256=r.get('report_sha256')) for r in graded]
    core.save(HERE/'result.json',dict(registration=sha(OUT/'registration.json'),seal=sha(OUT/'seal.json'),rows=values,libraries=libraries,
                                     cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('phase',choices=('generate','score'))
    phase=parser.parse_args().phase
    with browser.lock(OUT/(phase+'.lock')):main(phase)
