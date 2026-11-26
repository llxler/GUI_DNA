"""Attach only original-model post-draw behavior supported by paired public chart variations."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
from unittest.mock import patch
from urllib.parse import urlsplit

from playwright.sync_api import Error, sync_playwright
from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,read,sha,now
from .. import run as geometry

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/svg-public-decorations-20261126'
CAP=.60
PROJECT=geometry.CHART
ACTIONS={'setFrame':['frame'],'drawAxes':['axes','labels'],'drawGrids':['grids'],'drawLegends':['legends'],
         'drawLineDetails':['series','scale','points','values'],'drawBars':['bars']}
ENTRY='common/AdditionalDrawing.js'
CALL='finishChart(instance.svg,{...supplied,id});'


def register():
    files=[Path(__file__),HERE/'source.cjs',HERE/'PROTOCOL.md',Path(geometry.__file__),geometry.HERE/'geometry.js',
           geometry.OUT/'registration.json',geometry.OUT/'seal.json']
    files += [geometry.OUT/t/'library.json' for t in geometry.TAGS]
    sums={str(p.relative_to(ROOT)):sha(p) for p in files}
    f=OUT/'registration.json'
    if not f.exists():
        b=check_credits(CAP)
        assert b['sufficient']
        core.save(f,dict(utc=now(),sources=sums,cap=CAP,balance=b,deadline=geometry.admission.END.isoformat(),models=list(geometry.TAGS)))
    assert read(f)['sources']==sums
    return read(f)


def emit(original,functions,dest):
    source=ROOT/original['page']
    browser.verify_page(source,original['files'],PROJECT)
    inputs={k:(source/k).read_text() for k in original['files'] if not k.startswith('assets/')}
    js=inputs['index.js']
    assert js.count('instance.draw();')==1
    inputs['index.js']="import {finishChart} from './"+ENTRY+"';\n"+js.replace('instance.draw();','instance.draw();\n'+CALL)
    assert ENTRY not in inputs
    inputs[ENTRY]='\n'.join(functions.values())+'\nexport function finishChart(svg,config){\n'+'\n'.join(k+'(svg,config);' for k in functions)+'\n}'
    return dict(status='valid',page=str(dest.relative_to(ROOT)),files=core.emit(PROJECT,inputs,dest))


def observe(candidate):
    dest=ROOT/candidate['page']
    served=browser.served_page(OUT,PROJECT,dest,candidate['files'])
    summary=geometry.old.typed.charts.observe.observe(OUT,dest,candidate['files'])
    script=(geometry.HERE/'geometry.js').read_text()
    assert script.count('chart.draw();')==1
    script=script.replace('chart.draw();',"chart.draw(); const {finishChart}=await import('/"+ENTRY+"');finishChart(svg,{id,type:kind,data,options});")
    with browser.serve(PROJECT,served) as url,sync_playwright() as pw,pw.chromium.launch(env=browser.browser_env()) as engine:
        tab=engine.new_page(service_workers='block')
        tab.route('**/*',lambda r:r.continue_() if urlsplit(r.request.url).netloc in ('',urlsplit(url).netloc) else r.abort())
        tab.goto(url,wait_until='networkidle',timeout=18000)
        values=tab.evaluate(script)
    return dict(observed=summary,public=values,passed=sorted(f'{case}/{k}' for case,r in values.items() for k,v in r.items() if v is True))


def prepare(tag,ledger):
    root=OUT/tag
    f=root/'library.json'
    if f.exists():return read(f)
    parent=read(geometry.OUT/tag/'library.json')
    old=read(geometry.old.OUT/PROJECT/tag/'seal.json')
    fixed=next(r for r in old['rows'] if r['arm']=='fixed')
    pub=read(ROOT/old['case']['public'])
    hooks={}
    initial=before=observe(emit(fixed,hooks,root/'public/no-functions'))
    assert before['passed']==parent['final']['passed']
    attempts=[]
    for name,fields in ACTIONS.items():
        missing={case:{k:v for k,v in row.items() if k in fields and v is False} for case,row in before['public'].items()}
        missing={case:v for case,v in missing.items() if v}
        if not missing:continue
        msg=core.messages('Write exactly one ordinary JavaScript function named '+name+'(svg, config). It runs after an existing SVG chart is drawn, on that same SVG element. Correct only the specified public condition(s). Inspect the original chart modules; preserve existing drawing and enabled/disabled options, process arbitrary series and labels, and use SVG namespace where needed. Do not branch on particular input values or fixture IDs. Return only the complete function, no imports.',dict(focus=fields,public_requirements=pub['requirements'],existing_sources=parent['modules'],prior_post_draw=hooks,public_observation=before['public']))
        event=dict(module=name,retained=False)
        try:
            raw=geometry.admission.compact.base.request(ledger,(PROJECT,tag,'a'),root/'calls'/name,msg,'build',6000)
            proc=subprocess.run(['node',str(HERE/'source.cjs')],input=json.dumps(dict(name=name,raw=raw)),text=True,capture_output=True,timeout=12)
            if proc.returncode:raise ValueError('Expected just the declared two-argument function')
            trial={**hooks,name:proc.stdout}
            after=observe(emit(fixed,trial,root/'public'/name))
            gained=set(after['passed'])-set(before['passed'])
            keep=geometry.accept(before,after) and any(s.split('/')[-1] in fields for s in gained)
            event.update(public=after,retained=keep)
            if keep:hooks,before=trial,after
        except (Error,ValueError,*geometry.old.typed.MISSING) as exc:event['reason']=str(exc)[:350]
        attempts.append(event)
    core.save(f,dict(initial=initial,final=before,attempts=attempts,functions=hooks,status=parent['status']))
    return read(f)


def main(phase):
    register()
    seal=OUT/'seal.json'
    if phase=='generate':
        if seal.exists():return
        ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
        api=geometry.admission
        with patch.multiple(api.compact.base,OUT=OUT,END=api.END,template=api.settings),ThreadPoolExecutor(max_workers=2) as pool:
            libs=dict(zip(geometry.TAGS,pool.map(lambda t:prepare(t,ledger),geometry.TAGS),strict=True))
        rows=[]
        for r in read(geometry.OUT/'seal.json')['rows']:
            hooks=libs[r['tag']]['functions']
            if hooks and r['status']=='valid':
                candidate=emit(r,hooks,OUT/r['tag']/r['arm']/str(r['task']))
                rows.append({**r,**candidate})
            else:rows.append(r)
        core.save(seal,dict(registration=sha(OUT/'registration.json'),rows=rows,libraries={t:sha(OUT/t/'library.json') for t in geometry.TAGS}))
        return
    stored=read(seal)
    assert stored['registration']==sha(OUT/'registration.json') and all(sha(OUT/t/'library.json')==v for t,v in stored['libraries'].items())
    harness=browser.verify_contract(PROJECT)
    assert harness==read(geometry.OUT/'registration.json')['harness']
    graded=browser.evaluate(stored['rows'],OUT,{PROJECT:harness},3)
    core.save(HERE/'result.json',dict(registration=sha(OUT/'registration.json'),seal=sha(seal),cost=ledger_read.totals(OUT/'budget.sqlite3'),
        libraries={t:{k:v for k,v in read(OUT/t/'library.json').items() if k!='functions'} for t in geometry.TAGS},
        rows=[dict(arm=r['arm'],tag=r['tag'],task=r['task'],status=r['status'],passed=False if r['status']=='invalid' else r['passed'],report_sha256=r.get('report_sha256')) for r in graded]))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('phase',choices=('generate','score'))
    phase=p.parse_args().phase
    with browser.lock(OUT/(phase+'.lock')):main(phase)
