"""Project a model-declared collection onto the DOM and verify optional capabilities."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import re
from urllib.parse import urlsplit
from unittest.mock import patch

from gui_dna.budget import Ledger
from playwright.sync_api import sync_playwright
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,read,sha,now
from ..action_contracts import run as contracts
from ..action_library import run as parent

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/table-selection-binding-20261126'
CAP=.80
TAGS=contracts.TAGS
REPS=contracts.REPS
build,public=parent.build,parent.public
CHECKS={'keys':('arrow','delete'),'clipboard':('clipboard',),'range':('range',),'resize':('resize',),'reorder':('reorder',)}
RENDER='''
// Generic rendering of the model-declared Set. The event handlers own all changes to that Set.
const projection = BINDING;
function reflect(){
  const collection=ctx[projection.collection];
  if (!(collection instanceof Set)) return;
  for (const el of table.querySelectorAll(projection.selector)) el.classList.toggle(projection.className,collection.has(el));
}
for (const eventName of ['click','dblclick','contextmenu','keydown','mousedown','mousemove','mouseup','drop']){
  document.addEventListener(eventName,reflect);
}
reflect();
'''


def register():
    previous=read(contracts.OUT/'registration.json')
    files=[HERE/'PROTOCOL.md',Path(__file__),HERE/'state.py',HERE/'state.cjs',Path(build.__file__),build.HERE/'host.js',Path(public.__file__),Path(contracts.__file__),
           contracts.HERE/'units.cjs',contracts.OUT/'registration.json',contracts.OUT/'runtime-amendment.json']
    files.extend(contracts.OUT/t/r/'library.json' for t in TAGS for r in REPS[t])
    sums={str(f.relative_to(ROOT)):sha(f) for f in files}
    f=OUT/'registration.json'
    if not f.exists():
        b=check_credits(CAP)
        assert b['sufficient']
        core.save(f,dict(utc=now(),cap=CAP,balance=b,deadline=parent.END.isoformat(),sources=sums,
                    public=previous['public'],targets=previous['targets']))
    assert read(f)['sources']==sums
    return read(f)


def page(pub,funcs,profile,binding,dest):
    # Build in a separate immutable directory before adding the renderer.
    original=dest.parent/(dest.name+'-unbound')
    first=build.page(pub,funcs,profile,original)
    files={k:(original/k).read_text() for k in first['files'] if not k.startswith('assets/')}
    files['index.js']+='\n'+RENDER.replace('BINDING',json.dumps(binding))
    return dict(status='valid',page=str(dest.relative_to(ROOT)),files=core.emit('table',files,dest))


def observe(candidate):
    out=public.measure(OUT,candidate)
    served=browser.served_page(OUT,'table',ROOT/candidate['page'],candidate['files'])
    try:
        with browser.serve('table',served) as url,sync_playwright() as pw,pw.chromium.launch(env=browser.browser_env()) as engine:
            tab=engine.new_page(service_workers='block')
            tab.route('**/*',lambda r:r.continue_() if urlsplit(r.request.url).netloc==urlsplit(url).netloc else r.abort())
            tab.set_default_timeout(1600)
            errors=[]
            tab.on('pageerror',lambda e:errors.append(str(e)[:160]))
            tab.goto(url+'/index.html')
            cells=tab.locator('tbody td')
            x,y=cells.first.bounding_box(),cells.nth(1).bounding_box()
            tab.mouse.move(x['x']+10,x['y']+10);tab.mouse.down()
            tab.mouse.move(y['x']+10,y['y']+10,steps=5);tab.mouse.up()
            out['checks']['range']=tab.locator('tbody td.selected').count()>=2
            out['errors']=sorted(set(out['errors']+errors))
    except Exception as exc:
        out['checks']['range']=False
        out['errors'].append(str(exc).splitlines()[0][:160])
    return out


def bind(ledger,tag,rep,pub):
    folder=OUT/tag/rep
    f=folder/'library.json'
    if f.exists():return read(f)
    old=read(contracts.OUT/tag/rep/'library.json')
    orig=old['functions']
    unit=old['unit_records']
    msg=core.messages('Declare one CSS class projection from the model-owned collection. Return only JSON with exactly these string fields: '
        'collection (existing Set property of ctx), selector (CSS selector for cells inside the table), className (class token required by the public click requirement). '
        'Do not return functions or styling rules.',dict(public=pub['requirements'][3]['description'],
          state='ctx={table,menu,selected:new Set(),active:null,anchor:null,target:null}',cellClick=orig['cellClick'][:2600]))
    try:
        raw=parent.compact.base.request(ledger,('table',tag,rep),folder/'binding-call',msg,'build',1000)
        b=parent.compact.base.parse_json(raw)
        if (not isinstance(b,dict) or set(b)!={'selector','collection','className'} or b['collection']!='selected'
            or not re.fullmatch('[a-zA-Z_][a-zA-Z0-9_-]{0,40}',b['className']) or not isinstance(b['selector'],str)
            or not re.fullmatch(r'[a-zA-Z., #>_-]{1,70}',b['selector'])):raise ValueError('Invalid declarative binding')
    except parent.typed.MISSING as exc:
        core.save(f,dict(status='missing',reason=str(exc),public=[]));return read(f)
    except (TypeError,KeyError,ValueError) as exc:
        core.save(f,dict(status='build_failed',reason=str(exc),public=[]));return read(f)
    def source(name,label):
        if label=='starting':return read(contracts.feedback.OUT/tag/rep/'library.json')['functions'][name]
        if label.startswith('fresh-'):
            loc=contracts.OUT/tag/rep/'calls'/name/label.split('-')[1]
            receipt=next(loc.glob('transmission-*/settled.json'))
            response=receipt.with_name('response.json')
            assert sha(response)==read(receipt)['response_sha256']
        else:
            response=ROOT/label
            assert sha(response)==read(response.with_name('settled.json'))['response_sha256']
        return build.extract(name,read(response)['choices'][0]['message']['content'])
    isolated={}
    for name,options in unit.items():
        # Prefer absence of exceptions among tied public outcomes.
        def rank(v):
            checks=v['checks'].values()
            return sum(x['passed'] for x in checks),-sum(isinstance(x['observed'],str) for x in checks)
        v=max(options,key=rank)
        isolated[name]=source(name,v['source'])
    # Pure state test: a collection / active update may be correct even without an assigned CSS class.
    from .state import logical_winner
    logic={**isolated}
    for name in ('cellClick','markSelection'):
        logic[name]=logical_winner(name,[source(name,v['source']) for v in unit[name]])
    history=[]
    choice=None
    for label,initial in [('parent',orig),('isolated',isolated),('logical',logic)]:
        basic=['menu']
        trial=observe(page(pub,initial,basic,b,folder/'public'/label))
        history.append(dict(stage=label,**trial))
        rank=(public.admitted(trial),sum(trial['checks'].values()),-len(trial['errors']))
        if choice is None or rank>choice[0]:choice=(rank,initial,trial,label)
    _,funcs,before,label=choice
    options=['menu']
    if public.admitted(before):
        for option,needs in CHECKS.items():
            trial=observe(page(pub,funcs,options+[option],b,folder/'public'/option))
            gained=all(trial['checks'][k] for k in needs)
            keep=public.admitted(trial) and gained and all(not v or trial['checks'][k] for k,v in before['checks'].items())
            history.append(dict(stage=option,retained=keep,**trial))
            if keep:options.append(option);before=trial
    status='valid' if public.admitted(before) else 'build_failed'
    core.save(f,dict(status=status,reason='' if status=='valid' else 'Core public checks failed',binding=b,functions=funcs,
                     options=options,chosen=label,public=history))
    print(tag,rep,status,options,flush=True)
    return read(f)


def generate(reg):
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    pub=read(ROOT/reg['public'])
    def one(case):
        tag,rep=case
        folder=OUT/tag/rep
        lib=bind(ledger,tag,rep,pub)
        if lib['status']!='valid':return
        opt=lib['options'];funcs=lib['functions'];binding=lib['binding']
        fixed=page(pub,funcs,opt,binding,folder/'fixed')
        profiles=list(dict.fromkeys([tuple(opt),(),*((n,) for n in opt),*(tuple(n for n in opt if n!=k) for k in opt)]))
        host=page(pub,{},[],binding,folder/'empty')
        def pick(n):
            dest=folder/'target'/str(n)
            msg=parent.compact.make_messages(pub,n,dict(plan_documentation='Each listed option enables the publicly verified behavior of its event family.'),[dict(enabled=list(s)) for s in profiles],False)
            try:
                raw=parent.compact.base.request(ledger,('table',tag,rep),dest/'call',msg,'plan',3000)
                value=parent.compact.base.uncode(raw).strip()
                if not re.fullmatch('[0-9]+',value) or int(value)>=len(profiles):raise ValueError('Invalid index')
                return page(pub,funcs,profiles[int(value)],binding,dest/'page')
            except parent.typed.MISSING as exc:return dict(status='missing',reason=str(exc))
            except ValueError as exc:return dict(status='invalid',reason=str(exc))
        with ThreadPoolExecutor(max_workers=2) as pool:plans=list(pool.map(pick,reg['targets']))
        rows=[]
        for n,plan in zip(reg['targets'],plans,strict=True):
            for arm,val in [('planned',plan),('fixed',fixed),('host',host)]:
                rows.append(dict(task=n,project='table',arm=arm,**val))
        core.save(folder/'deployment.json',dict(library=sha(folder/'library.json'),rows=rows))
    with patch.multiple(parent.compact.base,OUT=OUT,END=parent.END,template=parent.settings),ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(one,((t,r) for t in TAGS for r in REPS[t])))
    files=[*OUT.glob('*/*/library.json'),*OUT.glob('*/*/deployment.json')]
    core.save(OUT/'seal.json',dict(registration=sha(OUT/'registration.json'),sources={str(f.relative_to(OUT)):sha(f) for f in files}))


def score(reg):
    seal=read(OUT/'seal.json')
    assert seal['registration']==sha(OUT/'registration.json') and all(sha(OUT/p)==v for p,v in seal['sources'].items())
    protocol=browser.verify_contract('table')
    assert protocol==read((ROOT/reg['public']).with_name('browser.json'))
    result=[]
    for t in TAGS:
        for rep in REPS[t]:
            f=OUT/t/rep/'library.json';lib=read(f)
            case=dict(tag=t,rep=rep,status=lib['status'],public=lib['public'],options=lib.get('options',[]),library_sha256=sha(f),deployments={})
            if lib['status']=='valid':
                deployment=read(f.with_name('deployment.json'))
                assert deployment['library']==sha(f)
                graded=browser.evaluate(deployment['rows'],OUT,{'table':protocol},3)
                case['deployments'][t]=[dict(task=r['task'],arm=r['arm'],status=r['status'],passed=False if r['status']=='invalid' else r['passed'],
                        report_sha256=r.get('report_sha256')) for r in graded]
            result.append(case)
    core.save(HERE/'result.json',dict(registration=sha(OUT/'registration.json'),seal=sha(OUT/'seal.json'),cases=result,cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=('generate','score'))
    phase=p.parse_args().action
    with browser.lock(OUT/(phase+'.lock')):
        reg=register()
        generate(reg) if phase=='generate' else score(reg)
