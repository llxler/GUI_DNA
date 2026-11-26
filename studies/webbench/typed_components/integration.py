"""Repair public integration failures in the five completed table and form builds."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
import posixpath
import re
import os
from unittest.mock import patch
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

from scripts.check_openrouter_credits import check_credits
from gui_dna.budget import Ledger
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.public_library_transfer.compact_todomvc.event_functions import run as events
from studies.study_io import ROOT,now,read,sha
from studies.webbench.transport_completion import run as restore
from . import run as typed
from .unavailable import run as absent

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/public-integration-20261125'
CAP=1
CASES=[('table','mistral'),('table','gemma'),('table','qwen9'),('form','mistral'),('form','gemma')]
IMPORT=re.compile(r"""((?:\bfrom\s*|\bimport\s*(?:\(\s*)?)['"])(\.[^'"]+)(['"])""")


def register():
    path=OUT/'registration.json'
    if path.exists():
        r=read(path)
        assert all(sha(ROOT/f)==h for f,h in r['sources'].items())
        return r
    prev=restore.register()
    bound=sum(prev['closed_exposure'].values())+typed.CAP+absent.CAP+restore.CAP+CAP+read(events.HERE/'result.json')['cost']['exposure_usd']
    balance=check_credits(CAP)
    assert bound<=10 and balance['sufficient']
    files=[Path(__file__),HERE/'integration.md',Path(typed.__file__),typed.form.COMPILER]
    cases=[]
    for p,t in CASES:
        f=next(root/p/t/'seal.json' for root in (typed.OUT,absent.OUT) if (root/p/t/'seal.json').is_file())
        s=read(f)
        assert s['status']=='build_failed'
        if p=='table':
            folder=f.parent/'build/1'
            source=next(x for x in sorted(folder.glob('transmission-*/response.json')) if read(x)['choices'][0].get('finish_reason')!='error')
            files.append(source)
        else:
            source=f.parent
            for state in (source/'build-a/modules').glob('*/status.json'):
                info=read(state)
                assert info['status']=='valid'
                code=state.parent/str(info['use'])/'code.json'
                assert sha(code)==info['source_sha256']
                files.extend([state,code])
            files.append(source/'admission.json')
        files.append(f)
        cases.append(dict(case=s['case'],source=str(source.relative_to(ROOT))))
    core.save(path,dict(utc=now(),deadline=typed.compact.END.isoformat(),cap=CAP,combined_bound=bound,balance=balance,
                      cases=cases,sources={str(f.relative_to(ROOT)):sha(f) for f in files}))
    return read(path)


def corrected_imports(files):
    edits=[]
    out=dict(files)
    for name,code in files.items():
        if not name.endswith('.js'):continue
        def resolve(m):
            original=m[2]
            expected=posixpath.normpath(posixpath.join(posixpath.dirname(name),original))
            if expected in files:return m[0]
            choices=[k for k in files if posixpath.basename(k)==posixpath.basename(original)]
            if len(choices)!=1:return m[0]
            rel=posixpath.relpath(choices[0],posixpath.dirname(name))
            rel=rel if rel.startswith('.') else './'+rel
            edits.append([name,original,rel])
            return m[1]+rel+m[3]
        out[name]=IMPORT.sub(resolve,code)
    return out,edits


def check_table(pub,source,path):
    value=deepcopy(source)
    value['files']=[f for f in value['files'] if f['path']!='index.html']
    pkg=typed.table.package(value,pub)
    files=core.emit('table',typed.compile_plan(pkg,pkg['examples'][0]['plan']),path)
    served=browser.served_page(OUT,'table',path,files)
    with browser.serve('table',served) as url,sync_playwright() as pw:
        with pw.chromium.launch(env=browser.browser_env()) as engine:
            tab=engine.new_page(service_workers='block')
            tab.route('**/*',lambda r:r.continue_() if urlsplit(r.request.url).netloc==urlsplit(url).netloc else r.abort())
            errors=[]
            tab.on('pageerror',lambda e:errors.append(str(e)))
            tab.goto(url+'/index.html',wait_until='load')
            active=tab.evaluate(typed.base.PROBES['table'])
    if errors or not active:raise ValueError(str(dict(context_menu=active,errors=errors)))
    return pkg


def check_form(pub,files):
    neutral=dict(questions=[dict(type='SingleSelectionQuestion',args=['Choose','sample',['North','East','West']],position='append')],surveyTitle=None,exportData=False)
    content=typed.compile_plan(dict(files=pub['starter']|files,compiler=typed.form.COMPILER.read_text()),neutral)
    observed=typed.form.observe(content,['SingleSelectionQuestion'],True)
    if typed.form.problem(observed):raise ValueError(str(observed)[:1600])
    return files


def build(entry,root,pub,ledger):
    case=entry['case']
    p,t=case['project'],case['builder']
    src=ROOT/entry['source']
    edits=[]
    if p=='table':
        source=typed.base.parse_json(read(src)['choices'][0]['message']['content'])
        before={v['path']:v['content'] for v in source['files']}
    else:
        with patch.object(typed.form,'OUT',src):source=typed.form.module_files('build-a')
        before=source
    files,edits=corrected_imports(before)
    if p=='table':source['files']=[dict(path=k,content=v) for k,v in files.items()]
    else:source=files
    attempts=[]
    for i in range(2):
        try:
            pkg=check_table(pub,source,root/f'public-{i}') if p=='table' else check_form(pub,source)
            core.save(root/'library.json',pkg)
            return 'valid',pkg,attempts,edits
        except typed.base.ERRORS as exc:attempts.append(str(exc)[:1600])
        if i:break
        request=core.messages('You are the original library maintainer. Repair the public integration error in your own delivered files. Return just a JSON object with a files array of {path,content}. Include the complete contents of each file you change. Preserve existing API and requested public behavior; no example app or auto-start in a reusable module. The host creates the app. Never change index.html, public assets or the app contract.',
                 dict(public_requirements=pub['requirements'],starter=pub['starter'],own_files=files,public_error=attempts[-1]))
        raw=typed.base.request(ledger,(p,t,'a'),root/'repair',request,'build',14000)
        try:
            changes=typed.base.parse_json(raw)['files']
            patchmap=core.files_map(changes)
            if not patchmap or set(patchmap)-set(files) or 'index.html' in patchmap:raise ValueError('Only existing non-HTML files may change')
            files=files|patchmap
            if p=='table':source['files']=[dict(path=k,content=v) for k,v in files.items()]
            else:source=files
        except typed.base.ERRORS as exc:
            attempts.append(str(exc)[:500])
            break
    return 'build_failed',None,attempts,edits


def form_plans(ledger,t,pub,files,targets,root):
    # Preserve the same native instance compiler, task messages and response cap as typed_components.
    def ask(dest,ledger,system,prompt,purpose,seed,limit,previous=None):
        try:
            raw=typed.base.request(ledger,('form',t,'a'),dest,[dict(role='system',content=system),dict(role='user',content=prompt)],'plan',8192)
            return raw,dict(status='returned')
        except typed.MISSING as exc:return '',dict(status='missing',reason=str(exc))
    def one(n,kind):
        result=typed.form.make_plan(('build-a',n,kind,pub,ledger))
        if result['status']!='valid':return {k:v for k,v in result.items() if k in ('status','reason')}
        page=root/'build-a'/kind/str(n)/'page'
        return dict(status='valid',page=str(page.relative_to(ROOT)),files=browser.tree(page))
    with patch.multiple(typed.form,OUT=root,ask=ask,module_files=lambda rep:files):
        fixed=one(20,'fixed')
        with ThreadPoolExecutor(max_workers=3) as pool:return fixed,list(pool.map(lambda n:one(n,'selected'),targets))


def generate(entry):
    case=entry['case']
    p,t=case['project'],case['builder']
    root=OUT/p/t
    if (root/'seal.json').exists():return
    pub=read(ROOT/case['public'])
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    targets=case['deploy'][t]['targets']
    orig=typed.base.template
    def template(project,tag,stage):
        settings=orig(project,tag,stage)
        if tag=='qwen9':settings['reasoning']={'enabled':False}
        return settings
    rows=[]
    edits=[]
    with patch.multiple(typed.base,OUT=OUT,END=typed.compact.END,template=template):
        try:
            status,pkg,reasons,edits=build(entry,root,pub,ledger)
            if status=='valid':
                if p=='table':fixed,plans=typed.table_deploy(ledger,t,targets,pub,pkg,root/'deployment')
                else:fixed,plans=form_plans(ledger,t,pub,pkg,targets,root/'deployment')
                for n,plan in zip(targets,plans,strict=True):
                    for a,d in (('fixed',fixed),('planned',plan)):rows.append(dict(project=p,tag=t,arm=a,task=n,**d))
        except typed.MISSING as exc:status='missing';reasons=[str(exc)]
    core.save(root/'seal.json',dict(case=case,registration=sha(OUT/'registration.json'),status=status,reasons=reasons,edits=edits,rows=rows))
    print(p,t,status,len(rows),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('register','generate','score','publish'))
    args=parser.parse_args()
    reg=register()
    if args.action=='generate':
        # The original typed-family functions bind their output root for one model at a time.
        for e in reg['cases']:generate(e)
    elif args.action=='score':
        import time
        from datetime import datetime, timezone
        for k in tuple(os.environ):
            if k.endswith(('_API_KEY','_AUTH_TOKEN','_ACCESS_TOKEN')):os.environ.pop(k)
        browser.OUT=OUT
        with patch.object(typed,'OUT',OUT):
            for e in reg['cases']:
                c=e['case']
                while not (OUT/c['project']/c['builder']/'seal.json').exists():
                    if datetime.now(timezone.utc)>=typed.compact.END:raise SystemExit('deadline')
                    time.sleep(2)
                typed.score(c)
    elif args.action=='publish':
        cases=[e['case'] for e in reg['cases']]
        core.save(HERE/'integration-result.json',dict(registration_sha256=sha(OUT/'registration.json'),cost=ledger_read.totals(OUT/'budget.sqlite3'),cases=[read(OUT/c['project']/c['builder']/'result.json') for c in cases]))
