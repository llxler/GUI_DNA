"""Replay the first delivered state programs, keeping citation faults as metadata."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,now,read,sha
from . import action_plan as source

build=source.build
GEN=ROOT/'artifacts/webgen-state-program-replay-20261128'
OUT=ROOT/'artifacts/webgen-state-program-judge-20261128'
PAGES=build.HERE/'program-candidates.json'
RESULT=build.HERE/'program-judgments.json'
CAP=1.30


def literal(value):
    if not isinstance(value,str) or not 1<=len(value)<=120 or any(c in value for c in '<>{}'):
        raise ValueError('Expected plain literal text')
    return value


def replay(spec, brief, cfg):
    spec=deepcopy(spec)
    citations=[{'quote':entry.get('quote'),'exact':isinstance(entry.get('quote'),str) and
                entry['quote'].strip()!='' and entry['quote'].casefold() in brief.casefold()} for entry in spec['coverage']]
    removed=[]
    for section in spec['sections']:
        for action in section['actions']:
            gate=action.get('requires') or {}
            if type(spec['initial'].get(gate.get('field'))) is bool and type(gate.get('min')) is int and gate['min']<=0:
                removed.append(dict(action=action['label'],guard=action.pop('requires')))
    with patch.object(build,'plain',literal):
        variants={a:build.pages.page(build.compile_updates(cfg,spec,a=='active'),'human') for a in ('active','inert')}
    return variants,spec,{'citations':citations,'tautological_guards':removed}


def generate():
    if PAGES.exists():
        return
    files=[Path(__file__),build.HERE/'PROGRAM_REPLAY.md',source.PAGES,Path(build.__file__)]
    replies={s:source.GEN/'plans'/s/'0/transmission-1/response.json' for s in source.SITES}
    reg=GEN/'registration.json'
    hashes={str(p.relative_to(ROOT)):sha(p) for p in (*files,*replies.values())}
    if not reg.exists():
        core.save(reg,dict(utc=now(),sources=hashes,sites=source.SITES))
    assert hashes==read(reg)['sources']
    briefs=read(build.main.OUT/'briefs.json')|read(build.main.gen.OUT/'generation-input.json')
    rows={};audits={};observations={};specs={}
    for site,f in replies.items():
        assert sha(f)==read(f.with_name('settled.json'))['response_sha256']
        original=build.main.native.OUT/'plans'/build.TAG/site/'record.json' if site==source.sdk_audit.SITE else build.main.OUT/'jobs'/build.TAG/site/'plan/record.json'
        try:
            raw=build.main.gen.parse(read(f)['choices'][0]['message']['content'])
            variants,spec,audits[site]=replay(raw,briefs[site],read(original)['config'])
            specs[site]=spec
            rows[site]={a:build.pages.write_html(GEN/'sites'/site/a,html) for a,html in variants.items()}
        except (AttributeError,*build.main.gen.ERRORS) as exc:
            rows[site]={a:dict(status='invalid',reason=str(exc)[:180]) for a in ('active','inert')}
    seal=dict(registration=sha(reg),rows=rows,first_replies={s:sha(p) for s,p in replies.items()},validation=audits,programs=specs)
    core.save(GEN/'seal.json',seal)
    for site,spec in specs.items():
        observations[site]={}
        for arm,item in rows[site].items():
            html=(ROOT/item['file']).read_text()
            observations[site][arm]=build.evaluate.browser_job(lambda e:source.observe(e,html,spec))
            if site==source.sdk_audit.SITE:
                upgrades=deepcopy(spec)
                upgrades['sections']=[s for s in upgrades['sections'] if s['tab']=='Upgrades']
                observations[site][arm]={'first_action':observations[site][arm],
                    'upgrade':build.evaluate.browser_job(lambda e:source.observe(e,html,upgrades))}
    core.save(PAGES,seal|dict(seal=sha(GEN/'seal.json'),observations=observations))


def score():
    import duckdb
    candidates=read(PAGES)
    assert candidates['seal']==sha(GEN/'seal.json')
    reg=OUT/'registration.json'
    sources={str(p.relative_to(ROOT)):sha(p) for p in (Path(__file__),build.HERE/'PROGRAM_REPLAY.md',PAGES,build.main.gen.SRC,
        source.earlier.primary.OUT/'calibration.json')}
    costs=sum(ledger_read.totals(p/'budget.sqlite3')['exposure_usd'] for p in (build.main.OUT,build.OUT,source.GEN,source.JUDGE))
    if not reg.exists():
        assert costs+source.earlier.CAP+source.earlier.primary.CAP+CAP<=20
        bal=check_credits(CAP)
        assert bal['sufficient'] and datetime.now(timezone.utc)<build.main.END
        core.save(reg,dict(utc=now(),sources=sources,cap=CAP,balance=bal,deadline=build.main.END.isoformat(),previous_closed_exposure=costs))
    assert read(reg)['sources']==sources
    if RESULT.exists():
        return
    calibration=read(source.earlier.primary.OUT/'calibration.json')
    assert calibration['qualified']
    rows=duckdb.sql('select id,ui_instruct from read_parquet(?) where id in (select unnest(?))',
                    params=[str(build.main.gen.SRC),list(build.SITES)]).fetchall()
    tasks={(s,i):{k:c[k] for k in ('task','expected_result')} for s,cs in rows for i,c in enumerate(cs)}
    jobs=[(site,i,a) for site,i in tasks for a in ('active','inert')]
    jobs.sort(key=lambda j:source.hashlib.sha256('/'.join(map(str,j)).encode()).digest())
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    def grade(job):
        site,i,arm=job
        item=candidates['rows'][site][arm]
        base=dict(site=site,check=i,arm=arm,verdict=None)
        if item['status']=='invalid':
            return base|dict(status='start_failed')
        f=ROOT/item['file']
        assert sha(f)==item['sha256']
        dest=OUT/'checks'/site/str(i)/arm
        val=build.evaluate.browser_job(lambda e:build.evaluate.journey(ledger,calibration['model'],f.read_text(),True,tasks[site,i],dest,e))
        return base|dict(status=val['status'],verdict=val['verdict'],reason=val.get('reason'),source=sha(dest/'judgment.json'))
    api=source.earlier.primary.api
    with patch.multiple(api,OUT=OUT,END=build.main.END),patch.dict(api.PRICES,{api.ALTERNATE:(.15,.6)}),ThreadPoolExecutor(max_workers=2) as workers:
        judgments=list(workers.map(grade,jobs))
    core.save(RESULT,dict(registration=sha(reg),candidates=sha(PAGES),judge=calibration['model'],rows=judgments,cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=('generate','evaluate'))
    phase=parser.parse_args().phase
    with browser.lock((GEN if phase=='generate' else OUT)/'run.lock'):
        (generate if phase=='generate' else score)()
