"""Freeze and grade a posthoc all-example Boolean union without model calls."""
import argparse
from copy import deepcopy
from datetime import datetime,timezone
import hashlib,json,shutil
from pathlib import Path
from test.interaction_transfer.core import ROOT,BUILD,RUN,PROJECTS,BUILDERS,CONDITIONS,slug,compile_plan,write_files,dump,digest
from test.interaction_transfer.evaluate import verify_scoring,read,sha
from test.interaction_transfer.fixtures import heldout
from test.interaction_transfer.browser import evaluate

HERE=Path(__file__).resolve().parent;OUT=ROOT/'artifacts/interaction-union-20261115'

def merge(a,b):
 if type(a) is not type(b):raise ValueError('Conflicting types')
 if isinstance(a,bool):return a or b
 if isinstance(a,dict):
  result=deepcopy(a)
  for k,v in b.items():result[k]=merge(result[k],v) if k in result else deepcopy(v)
  return result
 if isinstance(a,list):
  result=deepcopy(a)
  for v in b:
   if v not in result:result.append(deepcopy(v))
  return result
 if a!=b:raise ValueError('Conflicting scalar values')
 return deepcopy(a)

def prepare():
 old=verify_scoring();assert (RUN/'evaluation-complete.json').exists()
 if OUT.exists():raise RuntimeError('Do not overwrite exploratory inputs')
 rows=[];jobs={}
 for project in PROJECTS:
  for builder in BUILDERS:
   for condition in CONDITIONS:
    folder=BUILD/'libraries'/project/slug(builder)/condition;package=read(folder/'package.json')
    row={'project':project,'builder':builder,'condition':condition,'error':None,'page':None,'score_key':None}
    target=OUT/'pages'/project/slug(builder)/condition
    try:
     plans=[next(e['plan'] for e in package['examples'] if e['id']==f'dev-{i}') for i in range(3)]
     plan=merge(merge(plans[0],plans[1]),plans[2]);dump(target/'plan.json',plan)
     files=compile_plan(package,plan);write_files(target,files)
     mapping={n:hashlib.sha256(v.encode()).hexdigest() for n,v in files.items()};dump(target/'source-manifest.json',{'files_sha256':mapping})
     key=digest({'project':project,'files':mapping,'cases':heldout(project)})
     row.update(page=str(target.relative_to(ROOT)),score_key=key)
     jobs.setdefault(key,{'project':project,'page':row['page'],'files_sha256':mapping,'reuse_key':key if key in old['jobs'] else None})
    except (ValueError,KeyError,TypeError) as e:row['error']=str(e)
    rows.append(row)
 dump(OUT/'inputs.json',{'rows':rows,'jobs':jobs,'posthoc':True,'prior_result_sha256':sha(ROOT/'test/results/interaction-transfer.json')})
 frozen={str(p.relative_to(ROOT)):sha(p) for base in (HERE,OUT) for p in base.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
 dump(OUT/'snapshot.json',{'frozen_utc':datetime.now(timezone.utc).isoformat(),'files':frozen})
 print('Frozen',len(rows),'controls;',sum(j['reuse_key'] is not None for j in jobs.values()),'exact source reuses')

def verify():
 verify_scoring()
 for p,v in read(OUT/'snapshot.json')['files'].items():assert sha(ROOT/p)==v,p
 return read(OUT/'inputs.json')

def score():
 inputs=verify()
 for key,job in inputs['jobs'].items():
  folder=OUT/'scores'/key
  if (folder/'receipt.json').exists():assert sha(folder/'report.json')==read(folder/'receipt.json')['report_sha256'];continue
  assert not (folder/'report.json').exists()
  if job['reuse_key']:
   old=RUN/'scores'/job['reuse_key'];assert sha(old/'report.json')==read(old/'receipt.json')['report_sha256']
   folder.mkdir(parents=True,exist_ok=True);shutil.copy2(old/'report.json',folder/'report.json')
  else:dump(folder/'report.json',evaluate(ROOT/job['page'],job['project'],heldout(job['project'])))
  dump(folder/'receipt.json',{'report_sha256':sha(folder/'report.json'),'reused':bool(job['reuse_key'])})
  print(job['project'],read(folder/'report.json')['passed'],'/12',flush=True)
 dump(OUT/'evaluation-complete.json',{'inputs_sha256':digest(inputs),'finished_utc':datetime.now(timezone.utc).isoformat()})

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','score']);a=p.parse_args();globals()[a.action]()
