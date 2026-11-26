"""Build project-specific component libraries, then replay the original matched targets."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
import json
import os
import re
import subprocess
import sys

from gui_dna.budget import BudgetStop, Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.interface_blind.core import compile_plan
from studies.public_library_transfer import browser, core
from studies.public_library_transfer.self_refinement.form_components import run as form
from studies.public_library_transfer.self_refinement.svg_renderers.confirmation import run as charts
from studies.study_io import ROOT, now, read, sha
from studies.webbench.compact_planning import run as compact
from studies.webbench.self_build_modules import run as base
from studies.webbench.table.controller_build import build as table

HERE = Path(__file__).resolve().parent
OUT = ROOT/'artifacts/typed-components-20261125'
CAP = 2.50
CASES = [('table', t) for t in ('gpt5','qwen','mistral')] + [
    (p,t) for p in ('form','svg-chart') for t in compact.CELLS[p]['self']]
MISSING = (BudgetStop, base.original.Unavailable)
ALL_TAGS = ['gemma','qwen9','mistral','qwen','oss','deepseek-flash','deepseek-pro']


def register():
    path = OUT/'registration.json'
    if path.exists():
        reg = read(path)
        assert all(sha(ROOT/f)==h for f,h in reg['sources'].items())
        return reg
    from studies.paper_performance import current_group
    old = read(compact.MATRIX)
    cases = []
    files = [Path(__file__), HERE/'PROTOCOL.md', Path(base.__file__), Path(table.__file__), Path(form.__file__),
             form.COMPILER, form.registry.HERE/'probe.js', Path(charts.base.__file__), Path(charts.comp.__file__),
             Path(charts.links.__file__), charts.links.HERE/'link.cjs', Path(charts.dom.__file__),
             charts.dom.HERE/'arguments.cjs', Path(charts.observe.__file__), Path(browser.__file__),
             compact.OUT/'registration.json']
    for p,t in CASES:
        arm = 'gpt5-library' if t=='gpt5' else 'self'
        deploy = {}
        for tag in ALL_TAGS if t=='gpt5' else [t]:
            model = base.template(p,tag,'plan')['model']
            group = current_group(old[model],p)
            deploy[tag] = dict(model=model,targets=group['targets'],previous=group['passed'][arm],
                               direct=group['passed']['direct'])
        pub = base.old_root(p,'qwen')/'inputs'/p/'public.json'
        assert read(pub)==core.public_input(p)
        files += [pub,base.old_root(p,'qwen')/'inputs'/p/'browser.json']
        cases.append(dict(project=p,builder=t,public=str(pub.relative_to(ROOT)),arm=arm,deploy=deploy))
    balance=check_credits(CAP)
    assert balance['sufficient']
    core.save(path,dict(utc=now(),deadline=compact.END.isoformat(),cap=CAP,balance=balance,cases=cases,
                        sources={str(f.relative_to(ROOT)):sha(f) for f in files}))
    return read(path)


def table_build(ledger,case,public,folder):
    tag=case['builder']
    messages=core.messages(table.PROMPT+' Share one model-owned selection state across cell clicks, keyboard, menu actions and dragging. Enforce the public menu names and CSS selectors wherever explicitly requested. Return one JSON object.',
                           dict(public=public,output_schema=table.SCHEMA))
    previous=[]
    for attempt in range(2):
        raw=base.request(ledger,('table',tag,'a'),folder/'build'/str(attempt),messages,'build',14000)
        try:
            pkg=table.package(base.parse_json(raw),public)
            # The registered public right-click action must work on the first configuration.
            path=folder/'public-probe'
            files=core.emit('table',compile_plan(pkg,pkg['examples'][0]['plan']),path)
            served=browser.served_page(OUT,'table',path,files)
            from playwright.sync_api import sync_playwright
            with browser.serve('table',served) as url, sync_playwright() as pw:
                engine=pw.chromium.launch(env=browser.browser_env())
                try:
                    tab=engine.new_page(service_workers='block')
                    from urllib.parse import urlsplit
                    tab.route('**/*',lambda r:r.continue_() if urlsplit(r.request.url).netloc==urlsplit(url).netloc else r.abort())
                    errors=[];tab.on('pageerror',lambda e:errors.append(str(e)))
                    tab.goto(url+'/index.html',wait_until='load')
                    active=tab.evaluate(base.PROBES['table'])
                finally: engine.close()
            if errors or not active: raise ValueError('Public context menu probe: '+str([active,errors])[:650])
            core.save(folder/'package.json',pkg)
            return 'valid',pkg,previous
        except (ValueError,KeyError,TypeError,AttributeError) as exc:
            why=str(exc)[:750];previous.append(why)
            messages=messages+[dict(role='assistant',content=raw),dict(role='user',content='Correct the entire library according to this public feedback: '+why)]
    return 'build_failed',None,previous


def table_deploy(ledger,tag,targets,pub,pkg,folder):
    opts=compact.choices(pkg,'self','table')
    def page(plan,path):
        files=core.emit('table',compile_plan(pkg,plan),path)
        return dict(status='valid',page=str(path.relative_to(ROOT)),files=files)
    fixed=page(opts[0],folder/'fixed')
    def one(n):
        try:
            msg=compact.make_messages(pub,n,pkg,opts,False)
            raw=base.request(ledger,('table',tag,'a'),folder/str(n)/'call',msg,'plan',8192)
            value=base.uncode(raw).strip()
            if not re.fullmatch(r'[0-9]{1,4}',value) or int(value)>=len(opts): raise ValueError('Invalid selection')
            return page(opts[int(value)],folder/str(n)/'page')
        except MISSING as exc: return dict(status='missing',reason=str(exc))
        except base.ERRORS as exc: return dict(status='invalid',reason=str(exc)[:300])
    with ThreadPoolExecutor(max_workers=3) as pool: return fixed,list(pool.map(one,targets))


def form_deploy(ledger,tag,targets,pub,folder):
    def ask(dest,ledger,system,prompt,purpose,seed,limit,previous=None):
        msg=[dict(role='system',content=system),dict(role='user',content=prompt)]
        if previous:
            msg.extend([dict(role='assistant',content=previous[0]),dict(role='user',content='Public feedback: '+str(previous[1])[:3000]+'. Return the corrected file.')])
        stage='build' if purpose.startswith('prepare') else 'plan'
        try:
            text=base.request(ledger,('form',tag,'a'),dest,msg,stage,8192)
            return text,dict(status='returned')
        except MISSING as exc: return '',dict(status='missing',reason=str(exc))
    rep='build-a'
    def page(result,kind,n):
        if result['status']!='valid':return {k:v for k,v in result.items() if k in ('status','reason')}
        path=folder/rep/kind/str(n)/'page'
        return dict(status='valid',page=str(path.relative_to(ROOT)),files=browser.tree(path))
    with patch.multiple(form, OUT=folder, ask=ask),ThreadPoolExecutor(max_workers=3) as pool:
        def write(name,deps):
            return form.module_code((rep,name,pub,ledger,deps))
        states=[write('Question',{})]
        deps=form.module_files(rep)
        states.extend(pool.map(lambda name:write(name,deps),(*form.TYPES[1:],'Contents','style')))
        states.append(write('Survey',{k:v for k,v in form.module_files(rep).items() if k in ('common/Question.js','common/Contents.js')}))
        if any(s['status']!='valid' for s in states):
            status='missing' if any(s['status']=='missing' for s in states) else 'build_failed'
            return status,{},[]
        modules=form.module_files(rep)
        neutral=dict(questions=[dict(type='SingleSelectionQuestion',args=['Choose','sample',['North','East','West']],position='append')],surveyTitle=None,exportData=False)
        files=compile_plan(dict(files=pub['starter']|modules,compiler=form.COMPILER.read_text()),neutral)
        obs=form.observe(files,['SingleSelectionQuestion'],True)
        core.save(folder/'admission.json',obs)
        if form.problem(obs):return 'build_failed',{},[]
        fixed=page(form.make_plan((rep,20,'fixed',pub,ledger)),'fixed',20)
        plans=list(pool.map(lambda n:page(form.make_plan((rep,n,'selected',pub,ledger)),'selected',n),targets))
        return 'valid',fixed,plans


def svg_deploy(ledger,tag,targets,pub,folder):
    svg=charts.base
    def ask(ledger,name,messages,limit,schema=None):
        if schema is not None:
            messages=messages+[dict(role='user',content='Return only the JSON object. Required fields: '+json.dumps(schema['required']))]
        stage='plan' if '/plan/' in name else 'build'
        return base.request(ledger,('svg-chart',tag,'a'),folder/'calls'/name,messages,stage,8192)
    with patch.multiple(svg,OUT=folder,ask=ask,MISSING=MISSING),patch.object(charts.links,'OUT',folder/'linked'),patch.object(charts.dom,'OUT',folder/'tokens'):
        built=svg.prepare(ledger,'A',pub)
        if built['status']!='valid': return built['status'],{},[]
        modules=read(folder/'A/modules.json')
        linked=charts.links.link(built['selected'])
        first=dict(built['selected'],page=linked['page'],files=linked['files'])
        observation=charts.observe.public(folder,ROOT/first['page'],first['files'])
        chosen,edits=charts.dom.correct(first,charts.dom.witnessed(observation))
        modules={k:(ROOT/chosen['page']/k).read_text() for k in modules}
        fixed=svg.endpoint(folder/'A/corrected',pub,modules,svg.ALL,True)
        core.save(folder/'admission.json',dict(public=fixed['public'],links=linked['edits'],tokens=edits))
        if not svg.positive(fixed['public']): return 'build_failed',{},[]
        built['selected']=fixed
        with ThreadPoolExecutor(max_workers=3) as pool:
            return 'valid',fixed,list(pool.map(lambda n:svg.choose(ledger,'A',n,pub,built,modules),targets))


def generate(case):
    p,t=case['project'],case['builder']
    folder=OUT/p/t
    if (folder/'seal.json').exists():return
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    pub=read(ROOT/case['public'])
    orig=base.template
    def template(project,tag,stage):
        if tag=='gpt5':
            return dict(model='openai/gpt-5',provider=dict(sort='price',allow_fallbacks=True,
                        max_price={'prompt':1.50,'completion':12,'request':0}),reasoning={'effort':'low'})
        params=orig(project,tag,stage)
        if tag in ('deepseek-flash','deepseek-pro','qwen9'):params['reasoning']={'enabled':False}
        return params
    rows=[]
    with patch.multiple(base, OUT=OUT, END=compact.END, template=template):
        try:
            if p=='table': status,pkg,reasons=table_build(ledger,case,pub,folder)
            else:status='valid';reasons=[]
            for tag,group in case['deploy'].items():
                if status!='valid':break
                targets=group['targets']
                if p=='table':fixed,plans=table_deploy(ledger,tag,targets,pub,pkg,folder/tag)
                elif p=='form':status,fixed,plans=form_deploy(ledger,tag,targets,pub,folder)
                else:status,fixed,plans=svg_deploy(ledger,tag,targets,pub,folder)
                if status=='valid':
                    for n,plan in zip(targets,plans,strict=True):
                        for arm,val in (('planned',plan),('fixed',fixed)):
                            rows.append(dict(project=p,tag=tag,task=n,arm=arm,**{k:v for k,v in val.items() if k in ('status','reason','page','files')}))
        except MISSING as exc: status='missing';reasons=[str(exc)]
    core.save(folder/'seal.json',dict(case=case,registration=sha(OUT/'registration.json'),status=status,reasons=reasons,rows=rows))
    print(p,t,status,len(rows),flush=True)


def score(case):
    folder=OUT/case['project']/case['builder']
    if (folder/'result.json').exists(): return
    seal=read(folder/'seal.json')
    assert seal['registration']==sha(OUT/'registration.json') and seal['case']==case
    p=case['project']
    protocol=browser.verify_contract(p)
    assert protocol==read(base.old_root(p,'qwen')/'inputs'/p/'browser.json')
    rows=browser.evaluate(seal['rows'],OUT,{p:protocol},4)
    official=[]
    for r in rows:
        val={k:v for k,v in r.items() if k in ('tag','arm','task','status','passed','report_sha256','reason')}
        if val['status']=='invalid':val['passed']=False
        official.append(val)
    core.save(folder/'result.json',dict(**case,status=seal['status'],reasons=seal['reasons'],rows=official,seal_sha256=sha(folder/'seal.json')))
    print('scored',p,case['builder'],seal['status'],flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('register','generate','case','score','publish'))
    parser.add_argument('index',nargs='?',type=int)
    args=parser.parse_args()
    reg=register()
    if args.action=='generate':
        def child(i):
            subprocess.run([sys.executable,'-m','studies.webbench.typed_components.run','case',str(i)],check=True)
        with ThreadPoolExecutor(max_workers=3) as pool: list(pool.map(child,range(len(reg['cases']))))
    elif args.action=='case':generate(reg['cases'][args.index])
    elif args.action=='score':
        import time
        from datetime import datetime,timezone
        for k in tuple(os.environ):
            if k.endswith(('_API_KEY','_AUTH_TOKEN','_ACCESS_TOKEN')):os.environ.pop(k)
        browser.OUT=OUT
        while datetime.now(timezone.utc)<compact.END:
            pending=[]
            for c in reg['cases']:
                folder=OUT/c['project']/c['builder']
                if not (folder/'result.json').exists():
                    if (folder/'seal.json').exists():score(c)
                    else:pending.append(c)
            if not pending:break
            time.sleep(2)
    elif args.action=='publish':
        core.save(HERE/'result.json',dict(registration_sha256=sha(OUT/'registration.json'),cost=ledger_read.totals(OUT/'budget.sqlite3'),
                cases=[read(OUT/c['project']/c['builder']/'result.json') for c in reg['cases']]))
