"""Reconcile one sealed model, website, method and functional check with its judge trail."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import time

from playwright.sync_api import Error,sync_playwright
from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,now,read,sha
from . import generate as gen,judge_api as api,pages,voyager as v

OUT=api.OUT
HERE=gen.HERE
TEST={'task':'Click the Activate switch. Read its resulting status.', 'expected_result':'The status changes from Standby to Amber Ready.'}
def register():
    f=OUT/'registration.json'
    files=[Path(__file__),HERE/'judge_api.py',HERE/'voyager.py',HERE/'pages.py',HERE/'PROTOCOL.md',gen.REG,gen.SRC,
           gen.OUT/'registration.json',v.UI,v.UTILS,v.OPERATOR,v.PROMPTS,gen.UPSTREAM/'src/ui_test_webgen/compute_acc.py']
    sums={str(p.relative_to(ROOT)):sha(p) for p in files}
    if not f.exists():
        bal=check_credits(api.CAP);assert bal['sufficient']
        core.save(f,dict(utc=now(),deadline=gen.END.isoformat(),sources=sums,balance=bal,cap=api.CAP,exact=api.EXACT,alternate=api.ALTERNATE,
            round='20261126pm',weight={'YES':1,'PARTIAL':.5,'NO':0}))
    assert read(f)['sources']==sums
    return read(f)

def journey(ledger,model,html,sdk,task,dest,engine):
    result=dest/'judgment.json'
    if result.exists():return read(result)
    msg=[{'role':'system','content':v.PROMPT}]
    ask=v.TEMPLATE.format(**task)
    init=f'Now given a task: {ask}  Please interact with {pages.ORIGIN}/ and get the answer.\nObservation: please analyze the attached screenshot and give the Thought and Action. '
    value=None;trail=[];failure='';reason=None
    try:
        with pages.local_tab(engine,html,sdk=sdk) as tab:
            op=v.Labels(tab);tab.wait_for_timeout(400)
            for step in range(1,16):
                folder=dest/f'step-{step:02d}';folder.mkdir(parents=True,exist_ok=True)
                if step==15:msg.append(dict(role='user',content=v.FORM['ui_limit_prompt_template'].format(expected_result=task['expected_result'])))
                elif failure:
                    msg.append(dict(role='user',content=failure));failure=''
                else:
                    labels=op.observe()
                    snap=folder/'screen.png'
                    if not snap.exists():tab.screenshot(path=str(snap),timeout=5500)
                    formatted=v.FORM['format_msg'](step,init,'','', '',labels)
                    formatted['content'][-1]=dict(type='local_image',file=str(snap.relative_to(ROOT)),sha256=sha(snap))
                    msg.append(formatted)
                # Official clipping expects image_url in each prompt's second position and only tests list vs string.
                msg=v.FUNCTIONS['clip_message_and_obs'](msg,3)
                answer=api.send(ledger,model,folder/'call',msg)
                msg.append(dict(role='assistant',content=answer))
                if step!=15:op.clear()
                segment=re.split(r'\bAction\s*:',answer,flags=re.I)
                action=segment[-1].strip()
                value=v.final_answer(action) if len(segment)>1 or step==15 else None
                if value:
                    trail.append(dict(step=step,verdict=value));break
                if step==15:
                    reason='Final response did not provide an unambiguous verdict';break
                key,info=v.FUNCTIONS['extract_information'](action)
                try:
                    if len(segment)<2:raise ValueError('Expected Thought and Action')
                    op.act(key,info);trail.append(dict(step=step,action=key,target=info))
                    tab.wait_for_timeout(350)
                except (ValueError,Error,KeyError,TypeError,IndexError) as e:
                    failure='The local action could not be executed. Please check the previous label and action format.'
                    trail.append(dict(step=step,action=key,error=str(e).splitlines()[0][:170]))
    except api.Undelivered as e:reason=str(e)
    except (Error,ValueError,TypeError,KeyError) as e:reason=str(e).splitlines()[0][:200]
    core.save(result,dict(status='judged' if value else 'missing',verdict=value,reason=reason,trail=trail))
    return read(result)

def browser_job(fn):
    with browser.browser_slot(),sync_playwright() as pw,pw.chromium.launch(env=browser.browser_env()) as eng:return fn(eng)

def calibrate(ledger):
    route=OUT/'route.json'
    if not route.exists():
        try:
            api.send(ledger,api.EXACT,OUT/'official-route',[dict(role='user',content='Reply with OK.')])
            model=api.EXACT;reason=None
        except api.Undelivered as e:model=api.ALTERNATE;reason=str(e)
        core.save(route,dict(model=model,exact_unavailable=reason))
    model=read(route)['model'];results={}
    for works in (True,False):
        code="document.querySelector('output').innerText='Amber Ready'" if works else "void(0)"
        html='<html><body><h1>Switch check</h1><button onclick="'+code+'">Activate</button><output>Standby</output></body></html>'
        label='working' if works else 'inert'
        results[label]=browser_job(lambda eng:journey(ledger,model,html,False,TEST,OUT/'calibration'/label,eng))
    core.save(OUT/'calibration.json',dict(model=model,results=results,qualified=results['working']['verdict']=='YES' and results['inert']['verdict']=='NO'))
    return read(OUT/'calibration.json')

def score():
    import duckdb
    register();ledger=Ledger(OUT/'budget.sqlite3',api.CAP,api.CAP)
    cal=calibrate(ledger)
    if 'calibrate' in sys.argv:return
    while not (gen.HERE/'candidates.json').exists():
        if datetime.now(timezone.utc)>=gen.END:raise RuntimeError('No sealed candidates at deadline')
        time.sleep(5)
    source=read(gen.HERE/'candidates.json');assert source['seal']==sha(gen.OUT/'seal.json')
    chosen=read(gen.OUT/'generation-input.json')
    data=duckdb.sql('select id, ui_instruct from read_parquet(?)',params=[str(gen.SRC)]).fetchall()
    cases=[(site,i,dict(task=c['task'],expected_result=c['expected_result'])) for site,cs in sorted(data) if site in chosen for i,c in enumerate(cs)]
    assert len(cases)==read(gen.REG)['pilot_checks']
    jobs=[]
    for site,i,check in cases:
        for tag,by_site in source['rows'].items():
            for arm,row in by_site[site].items():
                jobs.append((tag,site,i,arm,check,row))
    # Stable interleaving across methods, sites and models for a bounded evaluation.
    def jobid(j):return '/'.join(map(str,j[:4]))
    jobs.sort(key=lambda x:hashlib.sha256(jobid(x).encode()).digest())
    def one(args):
        tag,site,i,arm,check,row=args
        dest=OUT/'checks'/tag/site/str(i)/arm
        if row['status']=='valid' and cal['qualified']:
            f=ROOT/row['file'];assert sha(f)==row['sha256']
            res=browser_job(lambda eng:journey(ledger,cal['model'],f.read_text(),arm=='human',check,dest,eng)) if not (dest/'judgment.json').exists() else read(dest/'judgment.json')
            value=dict(status=res['status'],verdict=res['verdict'],source=sha(dest/'judgment.json'),reason=res.get('reason'))
        elif row['status']=='invalid':value=dict(status='start_failed',verdict=None)
        else:value=dict(status=row['status'] if row['status']!='valid' else 'uncalibrated',verdict=None)
        return dict(model=tag,site=site,check=i,arm=arm,**value)
    with ThreadPoolExecutor(max_workers=5) as pool:rows=list(pool.map(one,jobs))
    core.save(HERE/'judgments.json',dict(registration=sha(OUT/'registration.json'),candidates=sha(gen.HERE/'candidates.json'),route=read(OUT/'route.json'),calibration=cal,
        cost=ledger_read.totals(OUT/'budget.sqlite3'),rows=rows))

if __name__=='__main__':
    with browser.lock(OUT/'evaluate.lock'):score()
