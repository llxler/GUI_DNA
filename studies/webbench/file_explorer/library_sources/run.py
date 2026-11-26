"""Run the four matched full-project file-explorer workflows and fixed-page controls."""
from concurrent.futures import ThreadPoolExecutor
from itertools import product
from pathlib import Path
import json
import os
import re
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.interface_blind import core as blind
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,now,read,sha
from studies.webbench.table.action_library import run as action
from studies.webbench_dna import domain
from . import library

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/file-explorer-sources-20261126'
CAP=2.50
TAGS=('deepseek-flash','qwen9')
REPS=('a','b')
GPT=ROOT/'artifacts/interface-blind-build/libraries/dom1/openai__gpt-5'
SHELL=ROOT/'studies/webbench_dna/shell.html'
ASTRA={rep:core.OUT/'builds/dom1'/('codex-'+str(i+1))/'package.json' for i,rep in enumerate(REPS)}
base=action.compact.base


def register():
    target=OUT/'registration.json'
    pub=core.public_input('dom1')
    assert pub==read(core.OUT/'inputs/dom1.json')
    assert all(a['description']==b['description'] for a,b in zip(pub['requirements'],[r for r in blind.requirements('dom1') if r['id'].startswith('task-')],strict=True))
    core.save(OUT/'public.json',pub)
    browser_contract=browser.verify_contract('dom1')
    core.save(OUT/'browser.json',browser_contract)
    record=read(GPT/'record.json')
    assert record['status']=='frozen' and record['builder']=='openai/gpt-5' and record['selected_attempt']==0
    req=read(GPT/'call-0/request.json')
    charge=next(r for r in ledger_read.calls(ROOT/'artifacts/interface-blind-build/budget.sqlite3') if r['id']==req['call_id'])
    assert charge['model']=='openai/gpt-5' and charge['actual'] is not None
    files=[Path(__file__),Path(library.__file__),HERE/'PROTOCOL.md',GPT/'record.json',GPT/'package.json',GPT/'call-0/response.json',
           Path(blind.__file__),blind.HERE/'compile.cjs',Path(browser.__file__),Path(core.__file__),Path(domain.__file__),
           Path(domain.library.__code__.co_filename),domain.TASKS_FILE,SHELL,OUT/'public.json',OUT/'browser.json',*ASTRA.values()]
    hashes={str(p.relative_to(ROOT)):sha(p) for p in files}
    if not target.exists():
        b=check_credits(CAP)
        assert b['sufficient']
        core.save(target,dict(utc=now(),deadline=action.END.isoformat(),cap=CAP,balance=b,targets=list(range(1,21)),
            sources=hashes,models={t:action.settings('table',t,'plan')['model'] for t in TAGS},
            source_costs=dict(gpt5=charge['actual']/1e6,astra='subscription; dollar allocation unavailable',
                              human='reference-decomposed, preparation time unrecorded')))
    assert read(target)['sources']==hashes
    return read(target)


def configs(lib,own):
    if own:
        d=lib['design']
        return list(d['controls']),{k:k in d['first'] for k in d['controls']},{k:[False,True] for k in d['controls']},d['controls']
    props=lib['plan_schema']['properties']
    return list(props),lib['examples'][0]['plan'],{k:([False,True] if v['type']=='boolean' else v['enum']) for k,v in props.items()},lib['plan_documentation']


def emit(page,files):
    return dict(status='valid',page=str(page.relative_to(ROOT)),files=files)


def generate(reg):
    pub=read(OUT/'public.json')
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    lib_human=domain.library()
    assert len(lib_human['functions'])==44
    gpt=read(GPT/'package.json')
    controls={}
    def fixed(key,files,dest):
        probe=library.observe(OUT,dest,files)
        controls[key]=dict(candidate=emit(dest,files),public=probe)
    dest=OUT/'fixed/gpt5-library'
    fixed('gpt5-library',core.emit('dom1',blind.compile_plan(gpt,gpt['examples'][0]['plan']),dest),dest)
    for rep,source in ASTRA.items():
        pkg=read(source)
        dest=OUT/'fixed'/('astra-'+rep)
        fixed('astra-'+rep,core.materialize('dom1',pkg,pkg['examples'][0]['plan'],dest),dest)
    with patch.multiple(base,OUT=OUT,END=action.END,template=action.settings):
        def build(job):
            tag,rep=job
            return (tag,rep),library.make(OUT,tag,rep,pub,ledger,action.typed.MISSING)
        with ThreadPoolExecutor(max_workers=3) as pool:
            libs=dict(pool.map(build,((tag,rep) for tag in TAGS for rep in REPS)))
        tasks={r['k']:r for r in domain.tasks()}
        def one(job):
            tag,n,arm=job
            folder=OUT/tag/'deploy'/arm/str(n)
            record=folder/'record.json'
            if record.exists():return read(record)
            def ask(msg,max_tokens):
                return base.request(ledger,('table',tag,'a'),folder/'call',msg,'plan',max_tokens)
            page=folder/'page'
            rows=[]
            try:
                if arm=='direct':
                    raw=ask(core.direct_messages(pub,n),11000)
                    files=core.materialize_direct('dom1',pub,base.parse_json(raw),page)
                elif arm=='human':
                    msg=domain.messages_for(tasks[n],'dna',lib_human)
                    msg=msg+[dict(role='user',content='Public starter layout:\n'+pub['starter']['index.html'])]
                    plan=base.parse_json(ask(msg,6000))
                    js=domain.compile_plan(plan,tasks[n]['features'],lib_human)
                    files=core.emit('dom1',{'index.html':SHELL.read_text().replace('/*__CANDIDATE__*/',js)},page)
                elif arm=='gpt5-library':
                    if not controls[arm]['public']['admitted']:raise LookupError('Frozen first page failed public admission')
                    msg=core.messages('Return only a data-only JSON plan for this existing file explorer. Match the documented plan language.',
                        dict(public=core.prefix(pub,n),schema=gpt['plan_schema'],design=gpt['design'],examples=gpt['examples']))
                    plan=base.parse_json(ask(msg,6000))
                    files=core.emit('dom1',blind.compile_plan(gpt,plan),page)
                else:
                    own=arm.startswith('self')
                    rep=arm[-1]
                    if own and libs[tag,rep]['status']!='valid':raise LookupError(libs[tag,rep]['status'])
                    if not own and not controls[arm]['public']['admitted']:raise LookupError('Frozen first page failed public admission')
                    pkg=libs[tag,rep]['library'] if own else read(ASTRA[rep])
                    keys,first,options,doc=configs(pkg,own)
                    choices=[dict(zip(keys,c,strict=True)) for c in product(*(options[k] for k in keys))]
                    assert first in choices
                    msg=action.compact.make_messages(pub,n,dict(plan_documentation=doc),choices,False)
                    raw=base.uncode(ask(msg,2300)).strip()
                    if not re.fullmatch('[0-9]+',raw) or int(raw)>=len(choices):raise ValueError('Expected one available configuration number')
                    plan=choices[int(raw)]
                    files=library.assemble(pub,pkg,plan,page) if own else core.materialize('dom1',pkg,plan,page)
                value=emit(page,files)
            except action.typed.MISSING as e:value=dict(status='missing',reason=str(e))
            except LookupError as e:
                if isinstance(e,(KeyError,IndexError)):value=dict(status='invalid',reason=str(e)[:180])
                else:value=dict(status='missing' if str(e)=='missing' else 'build_failed',reason=str(e))
            except (ValueError,TypeError,AttributeError) as e:value=dict(status='invalid',reason=str(e)[:180])
            rows.append(dict(project='dom1',task=n,arm=arm,**value))
            if arm.startswith('self'):
                rep=arm[-1]
                if libs[tag,rep]['status']=='valid':
                    pkg=libs[tag,rep]['library']
                    _,first,_,_=configs(pkg,True)
                    dest=OUT/tag/rep/'fixed'
                    with browser.lock(OUT/tag/rep/'fixed.lock'):
                        fixed_page=emit(dest,library.assemble(pub,pkg,first,dest))
                else:fixed_page=dict(status=libs[tag,rep]['status'])
            elif arm in controls:
                fixed_page=controls[arm]['candidate'] if controls[arm]['public']['admitted'] else dict(status='build_failed')
            else:fixed_page=None
            if fixed_page:rows.append(dict(project='dom1',task=n,arm='fixed-'+arm,**fixed_page))
            core.save(record,rows)
            return rows
        jobs=[(t,n,a) for n in reg['targets'] for t in TAGS for a in ('direct','human','gpt5-library','self-a','self-b','astra-a','astra-b')]
        with ThreadPoolExecutor(max_workers=7) as pool:list(pool.map(one,jobs))
    files=[*OUT.glob('*/*/library.json'),*OUT.glob('*/deploy/*/*/record.json')]
    core.save(OUT/'seal.json',dict(registration=sha(OUT/'registration.json'),sources={str(p.relative_to(OUT)):sha(p) for p in sorted(files)},
              references=controls))


def score(reg):
    seal=read(OUT/'seal.json')
    assert seal['registration']==sha(OUT/'registration.json') and all(sha(OUT/p)==v for p,v in seal['sources'].items())
    for key in tuple(os.environ):
        if key.endswith(('_API_KEY','_ACCESS_TOKEN','_AUTH_TOKEN')):os.environ.pop(key)
    browser.OUT=OUT
    protocol=browser.verify_contract('dom1')
    assert protocol==read(OUT/'browser.json')
    browser.controls(OUT,('dom1',),[1,10,20],3)
    rows=[]
    for tag in TAGS:
        for file in sorted((OUT/tag/'deploy').glob('*/*/record.json')):
            rows.extend(dict(tag=tag,**r) for r in read(file))
    rows=browser.evaluate(rows,OUT,{'dom1':protocol},4)
    models={m:[dict(task=r['task'],arm=r['arm'],status=r['status'],
            passed=False if r['status']=='invalid' else r['passed'],report_sha256=r.get('report_sha256')) for r in rows if r['tag']==t]
            for t,m in reg['models'].items()}
    core.save(HERE/'result.json',dict(registration=sha(OUT/'registration.json'),seal=sha(OUT/'seal.json'),cost=ledger_read.totals(OUT/'budget.sqlite3'),
        source_costs=reg['source_costs'],models=models,
        public={t:{r:{k:v for k,v in read(OUT/t/r/'library.json').items() if k!='library'} for r in REPS} for t in TAGS},
        frozen_public={arm:entry['public'] for arm,entry in seal['references'].items()},
        calibration=browser.calibration_evidence(OUT,('dom1',))))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('generate','score'))
    phase=parser.parse_args().action
    with browser.lock(OUT/(phase+'.lock')):
        reg=register()
        (generate if phase=='generate' else score)(reg)
