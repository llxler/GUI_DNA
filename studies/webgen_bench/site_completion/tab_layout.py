"""Measure native tab visibility without modifying any frozen page or its contents."""
from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,now,read,sha
from . import evaluate as main, sdk_audit

OUT=ROOT/'artifacts/webgen-native-tabs-20261128'
PAGES=main.gen.HERE/'tab-layout.json'
RESULT=main.gen.HERE/'tab-layout-judgments.json'
CAP=.40


def variants(config):
    changed=deepcopy(config)
    tabs=changed['body'][0]
    assert tabs['type']=='tabs' and 'tabsMode' not in tabs
    tabs['tabsMode']='vertical'
    return {name:main.gen.pages.page(cfg,'human') for name,cfg in [('horizontal',config),('vertical',changed)]}


def visible(engine, html, names):
    with main.gen.pages.local_tab(engine,html,sdk=True) as page:
        page.get_by_text(names[0],exact=True).first.wait_for(state='attached')
        page.wait_for_timeout(400)
        labels=main.evaluator.v.Labels(page)
        labels.observe()
        return page.evaluate("""names => {
             const nav=[...document.querySelectorAll('[role="tab"], .cxd-Tabs-link')];
             const labelled=window.__wgItems;
             return names.map((name,i)=>{
               const el=nav.find(x=>x.textContent.trim()===name);
               if(!el) return {index:i,name,found:false,labelled:false};
               return {index:i,name,found:true,labelled:labelled.some(x=>
                 (x===el || x.contains(el) || el.contains(x)) && x.textContent.trim()===name)};
             });
        }""",names)


def generate():
    if PAGES.exists():
        return
    source=read(main.gen.CANDIDATES)
    files=[Path(__file__),main.gen.HERE/'TAB_LAYOUT.md',main.gen.CANDIDATES,main.gen.HERE/'navigation-audit.json',
           Path(main.evaluator.v.__file__),main.gen.gen.DIST]
    hashes={str(p.relative_to(ROOT)):sha(p) for p in files}
    reg=OUT/'registration.json'
    if not reg.exists():
        core.save(reg,dict(utc=now(),deadline=main.gen.END.isoformat(),sources=hashes))
    assert read(reg)['sources']==hashes
    result={};candidates={}
    sources=[(tag,s,main.gen.OUT/'jobs'/tag/s/'plan/record.json',v['human']) for tag,sites in source['rows'].items() for s,v in sites.items()]
    old=read(sdk_audit.RESULT)
    sources.append(('archived-flash',old['site'],main.gen.native.OUT/'plans'/sdk_audit.MODEL/old['site']/'record.json',old['native_replay']['human']['candidate']))
    def replay(engine):
        for tag,site,p,record in sources:
            if record['status']!='valid':
                result.setdefault(tag,{})[site]={'status':record['status']}
                continue
            cfg=read(p)['config']
            names=[t['title'] for t in cfg['body'][0]['tabs']]
            outputs=variants(cfg)
            assert outputs['horizontal'].encode()==(ROOT/record['file']).read_bytes()
            candidates.setdefault(tag,{})[site]={k:main.gen.pages.write_html(OUT/'pages'/tag/site/k,v) for k,v in outputs.items()}
            result.setdefault(tag,{})[site]={k:visible(engine,html,names) for k,html in outputs.items()}
    main.evaluator.browser_job(replay)
    core.save(PAGES,dict(registration=sha(reg),original=sha(main.gen.CANDIDATES),candidates=candidates,labels=result))


def evaluate():
    import duckdb
    if RESULT.exists():
        return
    layout=read(PAGES)
    reg=OUT/'judge-registration.json'
    hashes={str(p.relative_to(ROOT)):sha(p) for p in (PAGES,Path(__file__),main.gen.HERE/'TAB_LAYOUT.md',main.OUT/'calibration.json',main.gen.gen.SRC)}
    if not reg.exists():
        # Generation, optional-program and rejected-program judgments have already closed.
        used=sum(ledger_read.totals(ROOT/'artifacts'/(n+'-20261128')/'budget.sqlite3')['exposure_usd'] for n in
                 ('webgen-site-completion','webgen-native-state','webgen-native-state-judge','webgen-grounded-actions','webgen-grounded-actions-judge'))
        assert used+11.5+1.30+1.+.20+.20+CAP<=20
        balance=check_credits(CAP)
        assert balance['sufficient'] and datetime.now(timezone.utc)<main.gen.END
        core.save(reg,dict(utc=now(),sources=hashes,balance=balance,cap=CAP,deadline=main.gen.END.isoformat()))
    assert read(reg)['sources']==hashes
    cal=read(main.OUT/'calibration.json')
    assert cal['qualified']
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    site=sdk_audit.SITE
    row=duckdb.sql('select ui_instruct from read_parquet(?) where id=?',params=[str(main.gen.gen.SRC),site]).fetchall()[0][0][2]
    task={k:row[k] for k in ('task','expected_result')}
    def grade(arm):
        record=layout['candidates']['archived-flash'][site][arm]
        f=ROOT/record['file'];assert sha(f)==record['sha256']
        dest=OUT/'checks'/arm
        value=main.evaluator.browser_job(lambda e:main.evaluator.journey(ledger,cal['model'],f.read_text(),True,task,dest,e))
        return {k:value[k] for k in ('status','verdict','reason')}|dict(steps=len(value['trail']),source=sha(dest/'judgment.json'))
    with patch.multiple(main.api,OUT=OUT,END=main.gen.END),patch.dict(main.api.PRICES,{main.api.ALTERNATE:(.15,.6)}),ThreadPoolExecutor(max_workers=2) as workers:
        rows=dict(zip(('horizontal','vertical'),workers.map(grade,('horizontal','vertical')),strict=True))
    core.save(RESULT,dict(registration=sha(reg),candidates=sha(PAGES),site=site,check=2,judge=cal['model'],rows=rows,cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__=='__main__':
    parser=ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=('generate','evaluate'))
    phase=parser.parse_args().phase
    with browser.lock(OUT/'run.lock'):
        (generate if phase=='generate' else evaluate)()
