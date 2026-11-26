"""Compare independently generated calculator documents, reference keys, and frozen external libraries."""
from concurrent.futures import ThreadPoolExecutor
from itertools import product
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit
import json
import re

from playwright.sync_api import sync_playwright
from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,UPSTREAM,read,sha,now
from studies.webbench.file_explorer.document_library.run import parse_document
from studies.webbench.file_explorer.library_sources import run as files
from studies.webbench.form.survey_workflow import run as survey
from studies.webbench_expand import core as expansion

HERE = Path(__file__).resolve().parent
OUT = ROOT/'artifacts/calculator-key-groups-20261126'
CAP = 2.50
PROJECT = 'calculator'
TAGS = ('qwen9','deepseek-flash')
REPS = ('a','b')
ARMS = ('direct','human','gpt5-library','self-a','self-b','astra-a','astra-b')
ORIGINAL = UPSTREAM/'projects/calculator'
GPT = ROOT/'artifacts/webbench-expand-build/libraries/calculator/openai__gpt-5'
ASTRA = {r:core.OUT/'builds/calculator'/('codex-'+str(i+1))/'package.json' for i,r in enumerate(REPS)}
GROUPS = {'powers':['√','^2','1/x'],'constant':['π'],'trigonometry':['sin','cos','tan'],
          'hyperbolic':['sinh','cosh'],'memory':['MR','M+','M-','MC']}
BASIC = set('0123456789.+-*/=')|{'Clear','C','AC','×','÷'}
base=files.base
action=files.action


def register():
    pub=core.public_input(PROJECT)
    core.save(OUT/'public.json',pub)
    source=[Path(__file__),HERE/'PROTOCOL.md',ORIGINAL/'src/index.html',ORIGINAL/'src-init/index.html',OUT/'public.json',GPT/'record.json',GPT/'package.json',*ASTRA.values(),Path(expansion.__file__)]
    source.extend(sorted(GPT.glob('call-*/response.json')))
    sums={str(p.relative_to(ROOT)):sha(p) for p in source}
    f=OUT/'registration.json'
    if not f.exists():
        b=check_credits(CAP)
        assert b['sufficient']
        cost=sum(float(read(p)['usage']['cost']) for p in GPT.glob('call-*/response.json'))
        core.save(f,dict(utc=now(),sources=sums,balance=b,cap=CAP,deadline=action.END.isoformat(),
            models={t:action.settings('table',t,'plan')['model'] for t in TAGS},source_costs=dict(gpt5_receipts_usd=cost,
            human='Upstream reference HTML plus five researcher-labelled key groups; original hours unrecorded.',
            astra='Two separately frozen subscription libraries; per-library dollar allocation unavailable.'),
            harness=browser.verify_contract(PROJECT),targets=list(range(1,21))))
    assert read(f)['sources']==sums
    return read(f)


def document(raw):
    try:return parse_document(raw)
    except ValueError:
        parsed=survey.receiver.first_object(raw)
        entries=parsed['files']
        mapping=core.files_map(entries) if isinstance(entries,list) else entries
        if set(mapping)!={'index.html'}:raise ValueError('Expected a single complete HTML document')
        return parse_document(mapping['index.html'])


def page(html,groups,enabled,path):
    inactive=[item for name,keys in groups.items() if name not in enabled for item in keys]
    if inactive:
        literal=json.dumps(inactive,ensure_ascii=True).replace('<','\\u003c')
        binding='<script>window.addEventListener("load",()=>{const omitted=new Set('+literal+');for(const el of document.querySelectorAll("button,[role=button],input[type=button]")){if(omitted.has((el.textContent||el.value||"").trim()))el.remove();}});</script>'
        html=re.sub(r'</body\s*>',lambda m:binding+m[0],html,count=1,flags=re.I)
    return files.emit(path,core.emit(PROJECT,{'index.html':html},path))


def probe(candidate):
    dest=ROOT/candidate['page']
    with browser.serve(PROJECT,dest) as url,sync_playwright() as pw,pw.chromium.launch(env=browser.browser_env()) as engine:
        tab=engine.new_page(service_workers='block')
        tab.route('**/*',lambda r:r.continue_() if urlsplit(r.request.url).netloc==urlsplit(url).netloc else r.abort())
        tab.set_default_timeout(2200)
        try:
            tab.goto(url)
            return tab.evaluate("""() => {
              const buttons=Array.from(document.querySelectorAll('button,[role=button],input[type=button]')).filter(el=>el.getClientRects().length);
              const label=b=>(b.textContent||b.value||'').trim(), click=s=>buttons.find(b=>label(b)===s)?.click();
              const output=()=>Array.from(document.querySelectorAll('input:not([type=button]),output,#display,.display,[role=status]')).map(el=>(el.value||el.textContent||'').trim());
              const reset=()=>{const c=['Clear','C','AC'].find(s=>buttons.some(b=>label(b)===s));if(c)click(c);};
              reset();['2','+','3','='].forEach(click);
              const arithmetic=output().some(s=>Number(s)===5);
              const functional=[];
              const cases=[['√','9',3],['^2','3',9],['1/x','2',.5],['π','',Math.PI],['sin','0',0]];
              for (const [key,input,want] of cases) {
                if(!buttons.some(b=>label(b)===key))continue;
                reset();if(input)click(input);
                const before=output();click(key);
                if(output().some(s=>s && Math.abs(Number(s)-want)<.0001)&&JSON.stringify(output())!==JSON.stringify(before))functional.push(key);
              }
              return {arithmetic,buttons:buttons.map(label),functional};
            }""")
        except Exception as exc:
            from playwright.sync_api import Error
            if not isinstance(exc,Error):raise
            return dict(arithmetic=False,buttons=[],functional=[],error=str(exc).splitlines()[0][:180])


def prepare(tag,rep,pub,ledger):
    folder=OUT/tag/'build'/rep
    final=folder/'library.json'
    if final.exists():return read(final)
    history=[]
    previous=''
    for turn in range(2):
        try:
            msg=core.messages('Build a reusable single-document calculator implementation for all public requirements. Return a complete self-contained index.html, real arithmetic and DOM controls. Use actual button text for keyboard groups; handle clear, scientific operations, memory, theme and history as requested. All selectors and functions must work in a standard browser. No external services.',dict(project=pub,previous=previous,public_feedback=history[-1:] if turn else []))
            raw=base.request(ledger,('table',tag,rep),folder/str(turn)/'document',msg,'build',12500)
            html=document(raw)
            previous=html
            full=probe(page(html,{},[],folder/str(turn)/'full'))
            desc=core.messages('Describe up to six optional key groups in YOUR calculator using their actual exact button captions. Return a JSON object mapping each short semantic group name to a nonempty array of distinct strings. Exclude digits, operators, equals and clear. Do not write JS.',dict(buttons=full['buttons'],source=html[-12000:]))
            obj=survey.receiver.first_object(base.request(ledger,('table',tag,rep),folder/str(turn)/'groups',desc,'build',1700))
            if not isinstance(obj,dict) or not 1<=len(obj)<=6:raise ValueError('Expected 1 to 6 optional key groups')
            if not all(isinstance(k,str) and isinstance(v,list) and v and all(isinstance(s,str) and s.strip() and s not in BASIC for s in v) for k,v in obj.items()):raise ValueError('Invalid optional group names or basic key')
            labels=[s for keys in obj.values() for s in keys]
            if len(labels)!=len(set(labels)):raise ValueError('Keys overlap across groups')
            off=probe(page(html,obj,[],folder/str(turn)/'off'))
            working=set(full['functional'])&set(labels)
            passed=full['arithmetic'] and off['arithmetic'] and bool(working-set(off['buttons']))
            history.append(dict(full=full,off=off,admitted=passed))
            if passed:
                core.save(final,dict(status='valid',html=html,groups=obj,public=history))
                return read(final)
        except action.typed.MISSING as exc:
            core.save(final,dict(status='missing',public=history,reason=str(exc)))
            return read(final)
        except base.ERRORS as exc:history.append(dict(reason=str(exc)[:260]))
    core.save(final,dict(status='build_failed',public=history))
    return read(final)


def generate(reg):
    if (OUT/'seal.json').exists():return
    pub=read(OUT/'public.json')
    human=(ORIGINAL/'src/index.html').read_text()
    gpt=read(GPT/'package.json')
    external={'astra-'+r:read(p) for r,p in ASTRA.items()}
    def frozen(arm,config,path):
        if arm=='gpt5-library':
            return files.emit(path,core.emit(PROJECT,expansion.compile_plan(gpt,config),path))
        return files.emit(path,core.materialize(PROJECT,external[arm],config,path))
    fixed={'starter':page(pub['starter']['index.html'],{},[],OUT/'fixed/starter'),
           'fixed-human':page(human,GROUPS,GROUPS,OUT/'fixed/human-on'),
           'minimum-human':page(human,GROUPS,[],OUT/'fixed/human-off')}
    for arm,pkg in [('gpt5-library',gpt),*external.items()]:
        fixed['fixed-'+arm]=frozen(arm,pkg['examples'][0]['plan'],OUT/'fixed'/arm)
    checks={k:probe(v) for k,v in fixed.items()}
    assert checks['fixed-human']['arithmetic'] and checks['minimum-human']['arithmetic'] and set(checks['fixed-human']['functional'])-set(checks['minimum-human']['buttons'])
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    with patch.multiple(base,OUT=OUT,END=action.END,template=action.settings):
        with ThreadPoolExecutor(max_workers=3) as pool:
            libs=dict(zip(product(TAGS,REPS),pool.map(lambda t:prepare(*t,pub,ledger),product(TAGS,REPS)),strict=True))
        def one(job):
            tag,n,arm=job
            folder=OUT/tag/'targets'/str(n)/arm
            f=folder/'record.json'
            if f.exists():return read(f)
            def ask(msg,limit):return base.request(ledger,('table',tag,'a'),folder/'call',msg,'plan',limit)
            try:
                dest=folder/'page'
                if arm=='direct':
                    prompt=core.messages('Implement the current public calculator requirement using the starter and preceding requirements. Return one complete index.html including all needed CSS and JS. Use no external services.',core.prefix(pub,n))
                    value=page(document(ask(prompt,12500)),{},[],dest)
                elif arm=='gpt5-library' or arm in external:
                    if not checks['fixed-'+arm]['arithmetic']:value=dict(status='build_failed')
                    else:
                        pkg=gpt if arm=='gpt5-library' else external[arm]
                        plan=survey.receiver.first_object(ask(core.plan_messages(pub,n,pkg),3800))
                        value=frozen(arm,plan,dest)
                else:
                    obj=libs[tag,arm[-1]] if arm.startswith('self') else dict(status='valid',html=human,groups=GROUPS)
                    if obj['status']!='valid':value=dict(status=obj['status'])
                    else:
                        groups=obj['groups']
                        msg=core.messages('Choose which optional calculator key groups to expose for the current requirement. Return one JSON array of group names. Basic arithmetic stays enabled.',dict(public=core.prefix(pub,n),available=groups))
                        raw=base.uncode(ask(msg,1500)).strip()
                        selected=json.loads(raw)
                        if not isinstance(selected,list) or not all(isinstance(k,str) and k in groups for k in selected):raise ValueError('Unknown calculator key group')
                        value=page(obj['html'],groups,selected,dest)
            except action.typed.MISSING as exc:value=dict(status='missing',reason=str(exc))
            except base.ERRORS as exc:value=dict(status='invalid',reason=str(exc)[:200])
            core.save(f,dict(project=PROJECT,tag=tag,task=n,arm=arm,**value))
            return read(f)
        with ThreadPoolExecutor(max_workers=5) as pool:
            rows=list(pool.map(one,product(TAGS,reg['targets'],ARMS)))
    for tag in TAGS:
        controls=dict(fixed)
        for rep in REPS:
            obj=libs[tag,rep]
            for mode in ('fixed','minimum'):
                arm=mode+'-self-'+rep
                controls[arm]=(page(obj['html'],obj['groups'],obj['groups'] if mode=='fixed' else [],OUT/tag/arm) if obj['status']=='valid' else dict(status=obj['status']))
        rows.extend(dict(project=PROJECT,tag=tag,task=n,arm=arm,**candidate) for arm,candidate in controls.items() for n in reg['targets'])
    core.save(OUT/'seal.json',dict(registration=sha(OUT/'registration.json'),rows=rows,public=checks,libraries={
        t:{r:{k:v for k,v in libs[t,r].items() if k!='html'} for r in REPS} for t in TAGS}))


def score(reg):
    seal=read(OUT/'seal.json')
    assert seal['registration']==sha(OUT/'registration.json') and reg['harness']==browser.verify_contract(PROJECT)
    rows=browser.evaluate(seal['rows'],OUT,{PROJECT:reg['harness']},4)
    core.save(HERE/'result.json',dict(registration=sha(OUT/'registration.json'),seal=sha(OUT/'seal.json'),cost=ledger_read.totals(OUT/'budget.sqlite3'),
        source_costs=reg['source_costs'],libraries=seal['libraries'],public=seal['public'],models={reg['models'][t]:[dict(arm=r['arm'],task=r['task'],status=r['status'],
        passed=False if r['status']=='invalid' else r['passed'],report_sha256=r.get('report_sha256')) for r in rows if r['tag']==t] for t in TAGS}))


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('phase',choices=('generate','score'))
    phase=p.parse_args().phase
    with browser.lock(OUT/(phase+'.lock')):
        reg=register()
        (generate if phase=='generate' else score)(reg)
