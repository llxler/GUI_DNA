"""Calibrate blank and partial UIs and reproduce six blind checks with a second VLM."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib
import time
from pathlib import Path
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,now,read,sha
from .. import evaluate as ev,generate as g,judge_api as api
from ..native_plans import run as native

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/webgen-judge-controls-20261126pm'
CAP=2.
SECOND='qwen/qwen2.5-vl-72b-instruct'
def register(checks):
    files=[Path(__file__),HERE/'PROTOCOL.md',g.REG,g.SRC,Path(ev.__file__),Path(api.__file__),ev.OUT/'calibration.json',
           g.HERE/'candidates.json',native.HERE/'PROTOCOL.md']
    sums={str(f.relative_to(ROOT)):sha(f) for f in files};f=OUT/'registration.json'
    selected={s:min(range(len(cs)),key=lambda i:hashlib.sha256(f'webgen-rater-v1:{s}:{i}'.encode()).digest()) for s,cs in checks.items()}
    if not f.exists():
        b=check_credits(CAP);assert b['sufficient']
        core.save(f,dict(utc=now(),balance=b,cap=CAP,deadline=g.END.isoformat(),primary=api.ALTERNATE,second=SECOND,selected=selected,sources=sums))
    assert read(f)['sources']==sums and read(f)['selected']==selected
    return selected
def run():
    import duckdb
    sites=read(g.OUT/'generation-input.json')
    checks={s:[dict(task=c['task'],expected_result=c['expected_result']) for c in cs] for s,cs in duckdb.sql('select id,ui_instruct from read_parquet(?)',params=[str(g.SRC)]).fetchall() if s in sites}
    subset=register(checks)
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    def judge(model,html,sdk,task,dest):
        f=dest/'judgment.json'
        if f.exists():return read(f)
        return ev.browser_job(lambda eng:ev.journey(ledger,model,html,sdk,task,dest,eng))
    with patch.multiple(api,OUT=OUT,PRICES=api.PRICES|{SECOND:(.90,1.20)}):
        def blank(job):
            site,i,task=job
            d=OUT/'blank'/site/str(i)
            v=judge(api.ALTERNATE,'<html><head><title>App</title></head><body></body></html>',False,task,d)
            return dict(site=site,check=i,verdict=v['verdict'],status=v['status'],receipt=sha(d/'judgment.json'))
        with ThreadPoolExecutor(max_workers=2) as pool:
            blanks=pool.submit(lambda:[blank((s,i,c)) for s,cs in sorted(checks.items()) for i,c in enumerate(cs)])
            cal={}
            for key,js in [('working',"document.querySelector('output').innerText='Amber Ready'"),('inert','void(0)')]:
                body='<html><body><h1>Switch check</h1><button onclick="'+js+'">Activate</button><output>Standby</output></body></html>'
                cal[key]=judge(SECOND,body,False,ev.TEST,OUT/'calibrate'/key)
            body='<html><body><button onclick="document.querySelector(\'output\').textContent=\'Amber Ready\'">Activate</button><output>Standby</output><button>Enable lamp</button><p>Lamp dark</p></body></html>'
            half=dict(task='Activate the status and enable the lamp using both buttons.',expected_result='Both independent outcomes occur: the status reads Amber Ready and the lamp reads Lamp green.')
            partial=judge(api.ALTERNATE,body,False,half,OUT/'partial')
            qualified=cal['working']['verdict']=='YES' and cal['inert']['verdict']=='NO'
            core.save(OUT/'controls.json',dict(second=SECOND,calibration=cal,qualified=qualified,partial=partial))
            while not (native.HERE/'candidates.json').exists():
                if datetime.now(timezone.utc)>=g.END:raise RuntimeError('New candidates still pending at deadline')
                time.sleep(5)
            candidates=read(native.HERE/'candidates.json');raters=[]
            for s,i in sorted(subset.items()):
                for t,sites in candidates['rows'].items():
                    for a,v in sites[s].items():
                        if v['status']=='valid' and qualified:
                            f=ROOT/v['file'];assert sha(f)==v['sha256']
                            d=OUT/'second'/s/str(i)/t/a;res=judge(SECOND,f.read_text(),a=='human',checks[s][i],d)
                            outcome=dict(status=res['status'],verdict=res['verdict'],receipt=sha(d/'judgment.json'))
                        else:outcome=dict(status=v['status'] if v['status']!='valid' else 'uncalibrated',verdict=None)
                        raters.append(dict(model=t,site=s,arm=a,check=i,**outcome))
            blankrows=blanks.result()
    core.save(HERE/'result.json',dict(registration=sha(OUT/'registration.json'),candidates=sha(native.HERE/'candidates.json'),controls=read(OUT/'controls.json'),blank=blankrows,
                                     second=raters,subset=subset,cost=ledger_read.totals(OUT/'budget.sqlite3')))
if __name__=='__main__':
    with browser.lock(OUT/'run.lock'):run()
