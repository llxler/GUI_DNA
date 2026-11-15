"""Whole-page generation with the public development checks, no frozen library."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import argparse,hashlib,json,subprocess
from pathlib import Path
from gui_dna.budget import Ledger,BudgetStop
from gui_dna.provider import parse_json,ProviderError
from test.streaming_provider_v2 import StreamingOpenRouter
from test.review_stage import freeze
from test.ledger_read import calls
from test.interaction_transfer.core import ROOT,PROJECTS,BUILDERS,CALIBRATION,config,messages_for,public_inputs,validate_files,write_files,dump,digest,slug
from test.interaction_transfer.browser import evaluate
from test.interaction_transfer.run import verify as verify_transfer,now

HERE=Path(__file__).resolve().parent;OUT=ROOT/'artifacts/development-feedback-20261115'

def messages(project):
 result=messages_for(project,'free',None)
 result[0]['content']+=' The same complete page will be checked against all three public development requirements. You may include additional working features. Public development behavior feedback is available for up to two repairs.'
 return result

def configuration():
 cfg=config(True);cfg.update(budget_usd=3,stop_new_requests_usd=2.7)
 return cfg

def public_validate(project,page,folder):
 feedback=[];reports={}
 for task in public_inputs(project):
  report=evaluate(page,project,task['public_cases']);dump(folder/(task['id']+'.json'),report);reports[task['id']]=report
  if not report['all_passed']:feedback.append(task['id']+': '+json.dumps(report['failures'][:2],ensure_ascii=False))
 return feedback,reports

def main():
 verify_transfer();assert not (OUT/'grading-started.json').exists()
 cfg=configuration();plan=json.loads((ROOT/'artifacts/review-20261115/budget-plan.json').read_text())
 assert plan['stages'][OUT.name]=={'cap':3,'stop':2.7}
 frozen=[str(p.relative_to(ROOT)) for p in HERE.iterdir() if p.suffix in ('.py','.md')]
 frozen+=['test/interaction_transfer/run.py','test/interaction_transfer/core.py','test/interaction_transfer/browser.py','test/interaction_transfer/domain.py',str((CALIBRATION/'frozen.json').relative_to(ROOT))]
 freeze(OUT,cfg,frozen,{'posthoc':True,'scope':'4 no-library complete pages, public-development feedback and 20000-token response limit; not a pure feedback factorial'})
 client=StreamingOpenRouter(cfg,Ledger(OUT/'budget.sqlite3',3,2.7))
 def one(job):
  project,model=job;folder=OUT/'runs'/project/slug(model);initial=messages(project)
  if (folder/'record.json').exists():
   saved=json.loads((folder/'record.json').read_text())
   if saved['status']=='complete':return saved
   raise RuntimeError('Preserve incomplete transport; do not silently issue duplicate requests')
  dump(folder/'messages.json',initial);thread=list(initial)
  record={'project':project,'model':model,'attempts':[],'versions':[],'status':'in_progress'}
  for attempt in range(3):
   if datetime.now(timezone.utc)>=datetime.fromisoformat('2026-11-15T06:40:00+00:00'):
    record['status']='time_incomplete';break
   try:raw=client.call(model,thread,folder/f'call-{attempt}','development-feedback-free',seed=20261115)
   except (BudgetStop,ProviderError) as e:
    record.update(status='transport_or_budget_incomplete',error=str(e));break
   dump(folder/f'output-{attempt}.json',{'text':raw})
   try:
    parsed=parse_json(raw)
    if not isinstance(parsed,dict) or set(parsed)!={'files'}:raise ValueError('Return exactly the files envelope')
    files=validate_files(parsed['files']);version=f'version-{attempt}';page=folder/version;write_files(page,files)
    dump(page/'source-manifest.json',{'files_sha256':{n:hashlib.sha256(v.encode()).hexdigest() for n,v in files.items()}})
    record['versions'].append(version)
    feedback,reports=public_validate(project,page,folder/f'validation-{attempt}')
    record.update(development_passes=sum(r['all_passed'] for r in reports.values()),development_total=3)
   except (ValueError,KeyError,TypeError,AttributeError,TimeoutError,subprocess.TimeoutExpired) as e:feedback=[f'{type(e).__name__}: {e}'[:2400]]
   record['attempts'].append({'attempt':attempt,'feedback':feedback});dump(folder/'record.json',record)
   if not feedback:break
   thread += [{'role':'assistant','content':raw},{'role':'user','content':'Public development/compiler feedback:\n'+'\n'.join(feedback)+'\nReturn the complete corrected JSON object.'}]
  if record['status']=='in_progress':record['status']='complete'
  dump(folder/'record.json',record);print(project,model,record['status'],'attempts',len(record['attempts']),flush=True);return record
 jobs=[(p,m) for p in PROJECTS for m in BUILDERS]
 with ThreadPoolExecutor(max_workers=2) as pool:records=list(pool.map(one,jobs))
 assert all(r['status']=='complete' for r in records),'Do not start hidden scoring'
 dump(OUT/'generation-complete.json',{'finished_utc':now(),'candidates':4,'records':records})

if __name__=='__main__':main()
