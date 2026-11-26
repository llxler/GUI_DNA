"""Replay sealed chart plans on same-model modules repaired from public data variations."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit
import json

from playwright.sync_api import sync_playwright
from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, read, sha, now
from studies.webbench.table.action_library import run as admission
from .. import svg_admission as old

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/svg-public-geometry-20261126'
CAP = .65
TAGS = tuple(old.TAGS)
CHART = 'svg-chart'
SVG = old.typed.charts.base
COMP = old.typed.charts.comp


def register():
    sources = [Path(__file__), HERE/'geometry.js', HERE/'PROTOCOL.md', Path(old.__file__),
               Path(COMP.__file__), Path(SVG.__file__), Path(admission.__file__), old.RESULT]
    for tag in TAGS:
        folder = old.OUT/CHART/tag
        sources.extend([folder/'A/modules.json', folder/'seal.json', ROOT/read(folder/'seal.json')['case']['public']])
    f = OUT/'registration.json'
    hashes = {str(p.relative_to(ROOT)):sha(p) for p in sources}
    if not f.exists():
        balance = check_credits(CAP)
        assert balance['sufficient']
        core.save(f, dict(utc=now(), sources=hashes, cap=CAP, balance=balance, models=list(TAGS),
                         deadline=admission.END.isoformat(), harness=browser.verify_contract(CHART)))
    assert read(f)['sources']==hashes
    return read(f)


def inspect_page(pub, mods, dest):
    page = SVG.endpoint(dest,pub,mods,SVG.ALL)
    served = browser.served_page(OUT,CHART,dest,page['files'])
    observed = old.typed.charts.observe.observe(OUT,dest,page['files'])
    with browser.serve(CHART,served) as url, sync_playwright() as pw:
        with pw.chromium.launch(env=browser.browser_env()) as engine:
            tab = engine.new_page(service_workers='block')
            tab.route('**/*',lambda r:r.continue_() if urlsplit(r.request.url).netloc in ('',urlsplit(url).netloc) else r.abort())
            tab.goto(url,wait_until='networkidle',timeout=18000)
            values = tab.evaluate((HERE/'geometry.js').read_text())
    keys = [f'{case}/{k}' for case,v in values.items() for k,passed in v.items() if passed is True]
    return dict(public=values,passed=sorted(keys),observed=observed)


def accept(before,after):
    left, right = before['observed'], after['observed']
    maintained = all(all(not n or right[k].get(chart,0)>0 for chart,n in left[k].items()) for k in ('mounted','drawn'))
    return maintained and len(right['errors'])<=len(left['errors']) and set(before['passed'])<set(after['passed'])


def build(tag,ledger):
    root=OUT/tag
    f=root/'library.json'
    if f.exists():return read(f)
    origin=old.OUT/CHART/tag
    recorded=read(origin/'seal.json')
    pub=read(ROOT/recorded['case']['public'])
    modules=read(origin/'A/modules.json')
    initial=before=inspect_page(pub,modules,root/'public'/'initial')
    attempts=[]
    for kind in ('base','line','bar'):
        name=COMP.path(kind)
        msg=core.messages('Repair only '+name+' and return its entire ES module as JavaScript. Keep compatibility with your other supplied real modules. Respect public axes, grids, legends, labels, data extents and disabled options with arbitrary input arrays. Do not branch on fixture ids or fixed values. Only public synthetic observations are supplied.',dict(requirements=pub['requirements'],modules=modules,observation=before['public']))
        attempt={'module':name,'retained':False}
        try:
            raw=admission.compact.base.request(ledger,(CHART,tag,'a'),root/'calls'/kind,msg,'build',10000)
            updated=COMP.source(raw,kind)
            trial={**modules,name:updated}
            after=inspect_page(pub,trial,root/'public'/kind)
        except (ValueError,*old.typed.MISSING) as exc:
            attempt['reason']=str(exc)[:420]
        except Exception as exc:
            from playwright.sync_api import Error
            if not isinstance(exc,Error):raise
            attempt['reason']=str(exc).splitlines()[0][:420]
        else:
            attempt.update(public=after,retained=accept(before,after))
            if attempt['retained']:modules,before=trial,after
        attempts.append(attempt)
    core.save(f,dict(status=recorded['status'],modules=modules,initial=initial,final=before,attempts=attempts))
    return read(f)


def main(phase):
    reg=register()
    seal=OUT/'seal.json'
    if phase=='generate':
        if seal.exists():return
        ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
        with patch.multiple(admission.compact.base,OUT=OUT,END=admission.END,template=admission.settings), ThreadPoolExecutor(max_workers=2) as pool:
            libs=dict(zip(TAGS,pool.map(lambda t:build(t,ledger),TAGS),strict=True))
        rows=[]
        for tag,lib in libs.items():
            orig=read(old.OUT/CHART/tag/'A/modules.json')
            changed={name:code for name,code in lib['modules'].items() if code!=orig[name]}
            for r in read(old.OUT/CHART/tag/'seal.json')['rows']:
                if r['status']!='valid' or not changed:
                    rows.append(r)
                    continue
                src=ROOT/r['page']
                browser.verify_page(src,r['files'],CHART)
                dest=OUT/tag/r['arm']/str(r['task'])
                inputs={name:(src/name).read_text() for name in r['files'] if not name.startswith('assets/')}
                assert all(inputs.get(name)==orig[name] for name in changed)
                fs=core.emit(CHART,inputs|changed,dest)
                assert r['files']['index.js']==fs['index.js']
                rows.append({**r,'files':fs,'page':str(dest.relative_to(ROOT))})
        core.save(seal,dict(registration=sha(OUT/'registration.json'),libraries={t:sha(OUT/t/'library.json') for t in TAGS},rows=rows))
        return
    saved=read(seal)
    assert saved['registration']==sha(OUT/'registration.json') and all(sha(OUT/t/'library.json')==v for t,v in saved['libraries'].items())
    assert reg['harness']==browser.verify_contract(CHART)
    graded=browser.evaluate(saved['rows'],OUT,{CHART:reg['harness']},3)
    core.save(HERE/'result.json',dict(registration=sha(OUT/'registration.json'),seal=sha(seal),cost=ledger_read.totals(OUT/'budget.sqlite3'),
               libraries={t:{k:v for k,v in read(OUT/t/'library.json').items() if k!='modules'} for t in TAGS},
               rows=[dict(tag=r['tag'],task=r['task'],arm=r['arm'],status=r['status'],passed=False if r['status']=='invalid' else r['passed'],report_sha256=r.get('report_sha256')) for r in graded]))


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('phase',choices=('generate','score'))
    phase=p.parse_args().phase
    with browser.lock(OUT/(phase+'.lock')):main(phase)
