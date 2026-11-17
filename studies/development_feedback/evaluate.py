"""Freeze first/final code before hidden evaluation; no feedback into generation."""
import argparse
from .run import ROOT,OUT,HERE,verify_transfer,dump,digest,now
from test.interaction_transfer.evaluate import read,sha
from test.interaction_transfer.fixtures import heldout
from test.interaction_transfer.browser import evaluate

def prepare():
 verify_transfer();assert not (OUT/'inputs.json').exists()
 barrier=read(OUT/'generation-complete.json');assert barrier['candidates']==4
 jobs={};rows=[]
 for path in sorted((OUT/'runs').rglob('record.json')):
  r=read(path);assert r['status']=='complete'
  for label in ('first','final'):
   version=('version-0' if 'version-0' in r['versions'] else None) if label=='first' else (r['versions'][-1] if r['versions'] else None)
   row={k:r[k] for k in ('project','model')};row.update(label=label,page=None,score_key=None,record=str(path.relative_to(ROOT)))
   if version:
    page=path.parent/version;files=read(page/'source-manifest.json')['files_sha256']
    assert all(sha(page/n)==v for n,v in files.items())
    key=digest({'project':r['project'],'files':files,'cases':heldout(r['project'])})
    row.update(page=str(page.relative_to(ROOT)),score_key=key);jobs.setdefault(key,{'project':r['project'],'page':row['page'],'files_sha256':files})
   rows.append(row)
 dump(OUT/'inputs.json',{'rows':rows,'jobs':jobs,'generation_sha256':sha(OUT/'generation-complete.json')})
 sources={str(p.relative_to(ROOT)):sha(p) for base in (HERE,OUT/'runs') for p in base.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
 sources[str((OUT/'inputs.json').relative_to(ROOT))]=sha(OUT/'inputs.json')
 dump(OUT/'scoring-snapshot.json',{'frozen_utc':now(),'files':sources})

def verify():
 verify_transfer()
 for p,v in read(OUT/'review-manifest.json')['sha256'].items():assert sha(ROOT/p)==v,p
 for p,v in read(OUT/'scoring-snapshot.json')['files'].items():assert sha(ROOT/p)==v,p
 inputs=read(OUT/'inputs.json');assert inputs['generation_sha256']==sha(OUT/'generation-complete.json');return inputs

def score():
 inputs=verify()
 if not (OUT/'grading-started.json').exists():dump(OUT/'grading-started.json',{'started_utc':now()})
 assert read(OUT/'generation-complete.json')['finished_utc']<=read(OUT/'scoring-snapshot.json')['frozen_utc']<=read(OUT/'grading-started.json')['started_utc']
 for key,job in inputs['jobs'].items():
  folder=OUT/'scores'/key
  if (folder/'receipt.json').exists():assert sha(folder/'report.json')==read(folder/'receipt.json')['report_sha256'];continue
  assert not (folder/'report.json').exists()
  dump(folder/'report.json',evaluate(ROOT/job['page'],job['project'],heldout(job['project'])))
  dump(folder/'receipt.json',{'report_sha256':sha(folder/'report.json')});print(job['project'],read(folder/'report.json')['passed'],'/12',flush=True)
 dump(OUT/'evaluation-complete.json',{'inputs_sha256':digest(inputs),'finished_utc':now()})

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','score']);a=p.parse_args();globals()[a.action]()
