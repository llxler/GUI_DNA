"""Test whether explicit, observable SVG contracts fix the original builders' drawings."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
from unittest.mock import patch
from urllib.parse import urlsplit

from gui_dna.budget import Ledger
from playwright.sync_api import sync_playwright,Error
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,now,read,sha
from ..decoration import run as previous

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/svg-attribute-contracts-20261126pm'
CAP=.65
END=datetime(2026,11,26,13,55,tzinfo=timezone.utc)
TAGS=('qwen9','mistral')
PROJECT=previous.PROJECT
GEOM=previous.geometry
ENTRY='common/AttributeContracts.js'
GOALS={
    'rootAttributes':(['frame'],[2], 'On the root svg itself, id equals config.id; its two CSS classes identify chart and config.type. The actual SVG viewBox is 0 0 100 70. This describes the root element; apply no decorative border.'),
    'plotLines':(['series','scale','points','values'],[3,4,8,9], 'For line charts, one .datasets polyline.dataset per config.data.datasets item. Its points follow the labels and dataset.data in original order. Map the global min/max across all series to the same y scale; x increases across the plotting area. Honor axes, pointStyle and dataLabels. Repair the existing dataset group without creating duplicates.'),
    'plotBars':(['bars'],[15,16,17], 'For bar charts the .datasets group must contain one SVG rect per label and series, with positive numeric width and finite nonnegative height. Values are in dataset.data. Respect enabled chart options.'),
    'axisText':(['labels','axes','grids'],[4,5,6], 'Use the actual supplied axis labels and coordinates. For enabled axes place those labels inside .axes-x; both .axes-x .axis-x and .axes-y .axis-y are SVG lines. Enabled .grids .grid matches tick positions; omit disabled features.'),
    'seriesLegend':(['legends'],[7], 'When enabled, each dataset label belongs in a .legends text element. When disabled, remove this group. Retain the data curves and axes.'),
}
UNSEEN=[dict(labels=['Cedar','Linden','Pine','Ash','Yew'],values=[[7,3,11,5,8],[2,12,3,9,4]]),
        dict(labels=['North','South','West'],values=[[18,4,13],[9,16,7]])]

def register():
    dest=OUT/'registration.json'
    files=[Path(__file__),HERE/'PROTOCOL.md',Path(previous.__file__),previous.HERE/'source.cjs',GEOM.HERE/'geometry.js',
           previous.OUT/'seal.json',previous.HERE/'result.json',GEOM.OUT/'registration.json']
    for t in TAGS:files.extend([previous.OUT/t/'library.json',GEOM.old.OUT/PROJECT/t/'seal.json'])
    sums={str(p.relative_to(ROOT)):sha(p) for p in files}
    if not dest.exists():
        b=check_credits(CAP);assert b['sufficient']
        core.save(dest,dict(utc=now(),deadline=END.isoformat(),cap=CAP,sources=sums,balance=b,targets=list(range(1,21)),models=list(TAGS),unseen=UNSEEN))
    assert read(dest)['sources']==sums
    return read(dest)

def emit(original,functions,dest):
    src=ROOT/original['page']
    browser.verify_page(src,original['files'],PROJECT)
    data={n:(src/n).read_text() for n in original['files'] if not n.startswith('assets/')}
    assert ENTRY not in data and data['index.js'].count('instance.draw();')==1
    pre='beforeDraw(instance.svg,{...supplied,id});'
    post='afterDraw(instance.svg,{...supplied,id});'
    js=data['index.js']
    end=previous.CALL if previous.ENTRY in data else 'instance.draw();'
    js=js.replace(end,end+'\n'+post).replace('instance.draw();',pre+'\ninstance.draw();')
    data['index.js']="import {beforeDraw,afterDraw} from './"+ENTRY+"';\n"+js
    frame='rootAttributes(svg,config);' if 'rootAttributes' in functions else ''
    body='\n'.join(f+'(svg,config);' for f in functions)
    data[ENTRY]='\n'.join(functions.values())+'\nexport function beforeDraw(svg,config){'+frame+'}\nexport function afterDraw(svg,config){'+body+'}'
    return dict(status='valid',page=str(dest.relative_to(ROOT)),files=core.emit(PROJECT,data,dest))

def inspect(candidate,unseen=False):
    folder=ROOT/candidate['page'];stage=browser.served_page(OUT,PROJECT,folder,candidate['files'])
    mounted=GEOM.old.typed.charts.observe.observe(OUT,folder,candidate['files'])
    src=(GEOM.HERE/'geometry.js').read_text()
    if unseen:
        i=src.index('const fixtures = ');j=src.index('  for (const [group',i)
        src=src[:i]+'const fixtures = '+json.dumps(UNSEEN)+';\n'+src[j:]
    deco=previous.ENTRY in candidate['files']
    old=f"const old=await import('/{previous.ENTRY}');old.finishChart(svg,configuration);" if deco else ''
    hook="const configuration={id,type:kind,data,options};const h=await import('/"+ENTRY+"');h.beforeDraw(svg,configuration);chart.draw();"+old+"h.afterDraw(svg,configuration);"
    assert src.count('chart.draw();')==1
    with browser.serve(PROJECT,stage) as url,sync_playwright() as pw,pw.chromium.launch(env=browser.browser_env()) as eng:
        tab=eng.new_page(service_workers='block')
        tab.route('**/*',lambda r:r.continue_() if urlsplit(r.request.url).netloc in ('',urlsplit(url).netloc) else r.abort())
        tab.goto(url,wait_until='networkidle',timeout=20000)
        checks=tab.evaluate(src.replace('chart.draw();',hook))
        dom=tab.evaluate('''()=>Array.from(document.querySelectorAll('.root svg')).slice(0,4).map(s=>({id:s.id,classes:s.getAttribute('class'),box:s.getAttribute('viewBox'),groups:Array.from(s.querySelectorAll('g')).slice(0,12).map(n=>n.getAttribute('class')),firstPolyline:s.querySelector('polyline')?.outerHTML.slice(0,240)}))''')
    return dict(observed=mounted,public=checks,dom=dom,passed=sorted(f'{g}/{k}' for g,v in checks.items() for k,x in v.items() if x is True))

def build(tag,ledger):
    folder=OUT/tag;dest=folder/'library.json'
    if dest.exists():return read(dest)
    old=read(previous.OUT/'seal.json')
    fixed=next(r for r in old['rows'] if r['arm']=='fixed' and r['tag']==tag and r['status']=='valid')
    settings=read(GEOM.old.OUT/PROJECT/tag/'seal.json')['case']
    pub=read(ROOT/settings['public']);func={};history=[]
    initial=best=inspect(emit(fixed,{},folder/'public/initial'))
    assert best['passed']==read(previous.OUT/tag/'library.json')['final']['passed']
    for name,(fields,indices,meaning) in GOALS.items():
        for attempt in range(2):
            missing={case:[k for k in fields if v.get(k) is False] for case,v in best['public'].items()}
            if not any(missing.values()):break
            msg=core.messages('Implement precisely one short JavaScript DOM function named '+name+'(svg, config). '
                    'Use the SVG namespace and actual incoming data. Preserve the already drawn content and public behaviors. '
                    'Never branch on id or dataset literals. Output only the named function. Use no outside helpers.',
                dict(required_invariants=meaning,failed=missing,current_live_DOM=best['dom'],existing_hook=func.get(name),
                     public_requirements=[pub['requirements'][k-1]['description'] for k in indices],
                     argument_example={'id':'demo','type':'line','data':{'labels':['Alpha','Beta','Gamma'],'datasets':[{'label':'north','data':[2,6,4]},{'label':'south','data':[3,1,5]}]},
                                       'options':{'axes':True,'grids':True,'legends':True,'pointStyle':'circle','dataLabels':True}},
                     previous_feedback=history[-1].get('feedback') if attempt else None))
            try:
                raw=GEOM.admission.compact.base.request(ledger,(PROJECT,tag,'a'),folder/'calls'/name/str(attempt),msg,'build',4000)
                raw=GEOM.admission.compact.base.uncode(raw).strip()
                proc=subprocess.run(['node',str(previous.HERE/'source.cjs')],input=json.dumps(dict(raw=raw,name=name)),text=True,capture_output=True,timeout=10)
                if proc.returncode:raise ValueError('Expected one function declaration with two arguments')
                trial=func|{name:proc.stdout}
                after=inspect(emit(fixed,trial,folder/'public'/(name+'-'+str(attempt))))
                added=set(after['passed'])-set(best['passed'])
                keep=GEOM.accept(best,after) and any(k.split('/')[-1] in fields for k in added)
                history.append(dict(name=name,attempt=attempt,retained=keep,feedback=dict(dom=after['dom'],checks=after['public'])))
                if keep:func=trial;best=after
            except GEOM.old.typed.MISSING as e:
                history.append(dict(name=name,retained=False,missing=str(e)));break
            except (ValueError,Error) as e:history.append(dict(name=name,retained=False,feedback=str(e).splitlines()[0][:180]))
    core.save(dest,dict(initial=initial,final=best,functions=func,history=history))
    print('svg attribute changes',tag,len(initial['passed']),len(best['passed']),list(func),flush=True)
    return read(dest)

def generate():
    register();dest=OUT/'seal.json'
    if dest.exists():return
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    with patch.multiple(GEOM.admission.compact.base,OUT=OUT,END=END,template=GEOM.admission.settings),ThreadPoolExecutor(max_workers=2) as pool:
        libs=dict(zip(TAGS,pool.map(lambda t:build(t,ledger),TAGS),strict=True))
    rows=[]
    for r in read(previous.OUT/'seal.json')['rows']:
        if r['tag'] not in TAGS:continue
        for suffix,hooks in [('',libs[r['tag']]['functions']),('-no-new-functions',{})]:
            arm=r['arm']+suffix
            candidate=emit(r,hooks,OUT/r['tag']/arm/str(r['task'])) if r['status']=='valid' else r
            rows.append(r|candidate|{'arm':arm})
    core.save(dest,dict(registration=sha(OUT/'registration.json'),rows=rows,libraries={t:sha(OUT/t/'library.json') for t in TAGS}))

def score():
    sealed=read(OUT/'seal.json');harness=browser.verify_contract(PROJECT)
    assert sealed['registration']==sha(OUT/'registration.json') and harness==read(GEOM.OUT/'registration.json')['harness']
    libs={}
    for t,hashval in sealed['libraries'].items():
        assert sha(OUT/t/'library.json')==hashval
        v=read(OUT/t/'library.json')
        unseen={}
        for arm in ('fixed','fixed-no-new-functions'):
            sample=next(r for r in sealed['rows'] if r['tag']==t and r['arm']==arm and r['status']=='valid')
            unseen[arm]=inspect(sample,unseen=True)
        libs[t]=dict(initial=v['initial'],final=v['final'],retained=list(v['functions']),unseen=unseen)
    graded=browser.evaluate(sealed['rows'],OUT,{PROJECT:harness},3)
    rs=[{k:r.get(k) for k in ('task','tag','arm','status','passed','report_sha256')}|
        {'passed':False if r['status']=='invalid' else r['passed']} for r in graded]
    groups={}
    for v in ledger_read.calls(OUT/'budget.sqlite3'):
        g=groups.setdefault(v['model'],dict(calls=0,settled_micro_usd=0,exposure_micro_usd=0));g['calls']+=1
        g['settled_micro_usd']+=v['actual'] or 0;g['exposure_micro_usd']+=v['reserved'] if v['actual'] is None else v['actual']
    core.save(HERE/'result.json',dict(registration=sha(OUT/'registration.json'),seal=sha(OUT/'seal.json'),libraries=libs,rows=rs,cost_by_builder=groups,cost=ledger_read.totals(OUT/'budget.sqlite3')))

if __name__=='__main__':
    with browser.lock(OUT/'run.lock'):
        generate();score()
