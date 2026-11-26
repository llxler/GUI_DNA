"""Freeze six instruction-only sites and generate each scheduled candidate exactly once."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
import argparse
import hashlib
import json
import re
import subprocess
import sys

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,now,read,sha
from studies.webbench.table.action_library import run as transport
from studies.webbench.file_explorer.document_library.run import parse_document
from . import pages,schema

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/webgen-sites-20261126pm'
CAP=1.80
END=datetime(2026,11,26,11,55,tzinfo=timezone.utc)
BASE=transport.compact.base
TAGS=('gemma','qwen9','deepseek-flash')
BUILDERS=('gpt5',*TAGS)
REG=HERE.parent/'protocol.json'
SRC=pages.UP/'test.parquet'
UPSTREAM=pages.UP/'evaluator'
DIST=pages.UP/'packages/amis-6.13.0.tgz'
SEED=2026112613
MISSING=transport.typed.MISSING
ERRORS=(TypeError,ValueError,KeyError,IndexError)
def model(t):return transport.settings('table',t,'plan')['model']

def register():
    import duckdb
    original=read(REG)
    assert sha(SRC)==original['sha256']
    assert subprocess.check_output(['git','-C',str(UPSTREAM),'rev-parse','HEAD'],text=True).strip()==original['evaluation'].split('/')[-1]
    records=duckdb.sql("select id, instruction, Category.primary_category as category from read_parquet(?)",params=[str(SRC)]).fetchall()
    assert len(records)==original['sites']
    sites={}
    for name,selected in original['pilot_sites'].items():
        candidates=[(a,b) for a,b,c in records if c==name]
        candidates.sort(key=lambda v:(hashlib.sha256(('gui-dna-webgen-v1:'+v[0]).encode()).hexdigest(),v[0]))
        assert sorted(k for k,_ in candidates[:2])==sorted(selected)
        for k,v in candidates[:2]:sites[k]=v
    core.save(OUT/'generation-input.json',sites)
    f=OUT/'registration.json'
    fs=[Path(__file__),HERE/'pages.py',HERE/'schema.py',HERE/'PROTOCOL.md',REG,SRC,DIST,OUT/'generation-input.json',
        pages.SDK/'sdk.js',pages.SDK/'sdk.css',Path(transport.__file__),Path(BASE.__file__),transport.build.modules.HERE/'function.cjs']
    hashes={str(p.relative_to(ROOT)):sha(p) for p in fs}
    if not f.exists():
        bal=check_credits(CAP);assert bal['sufficient']
        core.save(f,dict(utc=now(),deadline=END.isoformat(),balance=bal,cap=CAP,sources=hashes,models={t:model(t) for t in BUILDERS},original=original['evaluation'],
                         information='Only the six public instruction strings are passed to builders. Direct and target planning receive one.'))
    assert read(f)['sources']==hashes
    return read(f)

def parse(raw):
    text=BASE.uncode(raw).strip()
    block=re.search(r'```(?:json)?\s*\n([\s\S]*?)```',text,re.I)
    if block:text=block[1]
    return json.loads(text.strip())

def call(ledger,tag,dest,msg,phase,limit):
    return BASE.request(ledger,('webgen',tag,'a'),dest,msg,phase,limit)

def settings(proj,tag,phase):
    return transport.settings('table',tag,phase)|{'seed':SEED}

def function(raw):
    text=BASE.uncode(raw).strip()
    block=re.search(r'```(?:javascript|js)?\s*\n([\s\S]*?)```',text,re.I)
    text=re.sub(r'^\s*export\s+(?:default\s+)?','',block[1] if block else text)
    m=transport.build.modules
    r=subprocess.run(['node',str(m.HERE/'function.cjs'),str(m.ACORN)],input=json.dumps(dict(name='renderNode',arity=2,text=text)),capture_output=True,text=True,timeout=10)
    if r.returncode or not r.stdout:raise ValueError('A complete synchronous function renderNode(node, ctx) is required')
    return r.stdout

def public_replay(parts,folder):
    dest=folder/'public.json'
    if not dest.exists():
        html=pages.page(schema.SAMPLE,parts)
        local=pages.write_html(folder/'sample',html)
        try:
            r=subprocess.run([sys.executable,'-m','studies.webgen_bench.functional_pilot.generate','sample',str(ROOT/local['file'])],
                             text=True,capture_output=True,timeout=30,check=True)
            val=json.loads(r.stdout)
        except subprocess.TimeoutExpired:val=dict(checks={},errors=['Public scenario exceeded 30 seconds'])
        core.save(dest,val)
    return read(dest)

def build(tag,sites,ledger):
    folder=OUT/'build'/tag
    f=folder/'library.json'
    if f.exists():return read(f)
    parts={};history=[]
    def request(group,repair=None):
        msg=core.messages(pages.ABI,dict(public_site_briefs=sites,component_types={k:schema.FIELDS[k] for k in pages.GROUPS[group]},
            shared_grammar=schema.SPEC,public_example=schema.SAMPLE,output='Return just function renderNode(node,ctx){...} with all helpers inside. Implement all listed types and return a visible usable element.'))
        if repair:
            msg+=[dict(role='assistant',content=repair[0]),dict(role='user',content='Correct your complete local implementation: '+json.dumps(repair[1])+'. Return the complete named function only.')]
        raw=call(ledger,tag,folder/group/('repair' if repair else 'first'),msg,'build',5200)
        return function(raw)
    for g in pages.GROUPS:
        try:
            try:parts[g]=request(g)
            except ERRORS as e:parts[g]=request(g,('',str(e)))
        except MISSING as e:
            core.save(f,dict(status='missing',parts=parts,reason=str(e),history=history));return read(f)
        except ERRORS as e:history.append(dict(group=g,error=str(e)))
    check=public_replay(parts,folder/'initial')
    history.append(dict(phase='initial',observation=check))
    owners={'layout':('start','tabs'),'records':('record',),'actions':('details',),'input':('form',),'form':('form',)}
    for g,required in owners.items():
        if all(check['checks'].get(k) for k in required):continue
        # A syntax repair has already used this group's single allotted correction.
        if (folder/g/'repair/transmission-1/request.json').exists():continue
        try:src=request(g,(parts.get(g,''),check))
        except (MISSING+ERRORS) as e:history.append(dict(group=g,error=str(e)));continue
        trial=public_replay(parts|{g:src},folder/'revision'/g)
        before={k for k,v in check['checks'].items() if v};after={k for k,v in trial['checks'].items() if v}
        kept=after>before
        history.append(dict(group=g,observation=trial,retained=kept))
        if kept:parts[g]=src;check=trial
    ok=all(check['checks'].get(k) for k in ('start','tabs','record','details','form'))
    core.save(f,dict(status='valid' if ok else 'build_failed',parts=parts,final=check,history=history))
    return read(f)

def target(tag,site,kind,brief,ledger):
    folder=OUT/'jobs'/tag/site/kind
    f=folder/'record.json'
    if f.exists():return read(f)
    if kind=='direct':
        msg=core.messages('Create a complete locally working website from the user brief. Implement navigation, distinct sections, meaningful content and interactions with local browser state. All CSS and scripts inline. No external resources or backend. Return one complete HTML document only.',dict(website=brief))
        parse_value=parse_document
    else:
        msg=core.messages(schema.SPEC,dict(website=brief,component_manifest=schema.FIELDS,example=schema.SAMPLE,
            task='Write the complete configuration for this website. Include actionable views and realistic data for every requested area. Return only JSON.'))
        parse_value=lambda raw:schema.validate(parse(raw))
    for i in range(2):
        try:
            raw=call(ledger,tag,folder/str(i),msg,'plan',7500)
            v=parse_value(raw)
            result=pages.write_html(folder/'site',v) if kind=='direct' else dict(status='valid',config=v)
            break
        except MISSING as e:result=dict(status='missing',reason=str(e));break
        except ERRORS as e:
            result=dict(status='invalid',reason=str(e)[:210])
            msg+=[dict(role='assistant',content=raw),dict(role='user',content='Public format check: '+str(e)[:210]+'. Return the complete corrected output.')]
    core.save(f,result);return read(f)

def generate():
    reg=register()
    if (OUT/'seal.json').exists():return
    sites=read(OUT/'generation-input.json');ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    with patch.multiple(BASE,OUT=OUT,END=END,template=settings),ThreadPoolExecutor(max_workers=8) as pool:
        human=pages.check(pages.page(schema.SAMPLE,'human'),True)
        core.save(OUT/'human-public.json',human)
        assert all(human['checks'].values()),human
        libs={t:pool.submit(build,t,sites,ledger) for t in BUILDERS}
        jobs={(t,k,a):pool.submit(target,t,k,a,brief,ledger) for t in TAGS for k,brief in sites.items() for a in ('direct','plan')}
        libs={t:v.result() for t,v in libs.items()};batch={}
        for t in TAGS:
            batch[t]={}
            for site in sites:
                rows={'direct':jobs[t,site,'direct'].result()}
                plan=jobs[t,site,'plan'].result()
                for arm,lib in [('human','human'),('gpt5-library',libs['gpt5']),('self',libs[t])]:
                    if lib!='human' and lib['status']!='valid':v=dict(status=lib['status'])
                    elif plan['status']!='valid':v=plan
                    else:v=pages.write_html(OUT/'sites'/t/site/arm,pages.page(plan['config'],lib if lib=='human' else lib['parts']))
                    rows[arm]=v
                batch[t][site]=rows
    core.save(OUT/'seal.json',dict(registration=sha(OUT/'registration.json'),human_public=sha(OUT/'human-public.json'),
        builds={t:sha(OUT/'build'/t/'library.json') for t in BUILDERS},jobs={str(f.relative_to(OUT)):sha(f) for f in (OUT/'jobs').rglob('record.json')},rows=batch))
    core.save(HERE/'candidates.json',dict(registration=sha(OUT/'registration.json'),seal=sha(OUT/'seal.json'),cost=ledger_read.totals(OUT/'budget.sqlite3'),
        libraries={t:{k:v for k,v in z.items() if k!='parts'} for t,z in libs.items()},human_public=human,models=reg['models'],rows=batch))

if __name__=='__main__':
    if sys.argv[1:2]==['sample']:print(json.dumps(pages.check(Path(sys.argv[2]).read_text())))
    else:
        with browser.lock(OUT/'generation.lock'):generate()
