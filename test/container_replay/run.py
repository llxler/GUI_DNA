"""Prepare a deterministic saved-page sample and execute it in pinned Docker."""
import argparse
from datetime import datetime,timezone
import hashlib,json,shutil,subprocess
from pathlib import Path
from test.history_replay.run import source_files,cases_by_file

ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/container-replay-20261115'
IMAGE='mcr.microsoft.com/playwright:v1.57.0-noble'
TAG='gui-dna-replay:20261115'

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n')
def call(args,**kw):return subprocess.check_output(args,text=True,**kw).strip()

def prepare():
 if OUT.exists():raise RuntimeError('Use a new stage; no overwrite')
 image=read_json_output(['docker','image','inspect',IMAGE])[0]
 digest=next(x for x in image['RepoDigests'] if x.startswith('mcr.microsoft.com/playwright@sha256:'))
 history=read(ROOT/'artifacts/history-replay-20261115/inputs.json')
 jobs=[]
 def add(identifier,project,page,specs,comparison,expected=None):
  page=Path(page);files=source_files(page)
  job={'id':identifier,'project':project,'page':str(page.relative_to(ROOT)),'files':files,
       'specs':specs,'comparison':comparison,'expected':expected}
  if comparison=='history':
   matches=[(k,j) for k,j in history['jobs'].items() if j['project']==project and j['runtime']=='157' and j['files']==files and j['specs']==specs]
   assert len(matches)==1,(identifier,len(matches));job['history_key']=matches[0][0]
  for name in files:
   target=OUT/'inputs/pages'/identifier/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(page/name,target)
  jobs.append(job)
 saved=read(ROOT/'test/results/library-repair-mechanism.json')
 for row in saved['rows']:add('mechanism-'+row['name'],'table',ROOT/row['page'],['task-20'],'mechanism',row['all_passed'])
 add('table-reference','table',ROOT/'artifacts/web-bench/projects/table/src',['task-20'],'reference',True)
 specs=['init']+[f'task-{k}' for k in range(1,21)]
 for project in ('calculator','table','bom'):
  for builder in ('openai__gpt-5','anthropic__claude-sonnet-4.5'):
   for method in ('plan','free_lib'):
    folder=ROOT/'artifacts/webbench-expand-run/runs'/project/builder/'openai__gpt-oss-120b'/method/'task-20'
    record=read(folder/'record.json');assert record['versions'],'Preserve absent version explicitly before proceeding'
    add('-'.join((project,builder,method)),project,folder/record['versions'][-1],specs,'history')
 for project in ('calculator','bom'):
  add(project+'-reference',project,ROOT/'artifacts/web-bench/projects'/project/'src',specs,'reference',True)
 assert len(jobs)==19
 dump(OUT/'inputs/inputs.json',{'jobs':jobs,'selection':'Fixed before new container outcomes; 12 GPT-OSS final task-20 pages plus four mechanism pages and three references.'})
 context=OUT/'context';context.mkdir(parents=True)
 for source,target in [('runtime-package.json','package.json'),('runtime-lock.json','package-lock.json')]:shutil.copy2(ROOT/'test/webbench_expand'/source,context/target)
 shutil.copytree(ROOT/'test/webbench_dna/harness/test-util',context/'test-util')
 for project in ('calculator','table','bom'):
  old=ROOT/'artifacts/history-replay-20261115/harness'/('157-'+project)
  shutil.copytree(old/'test',context/'harness'/project/'test')
  for name in ('package.json','playwright.config.cjs'):shutil.copy2(old/name,context/'harness'/project/name)
 shutil.copy2(HERE/'runner.cjs',context/'runner.cjs')
 (context/'Dockerfile').write_text(f'FROM {digest}\nWORKDIR /opt/replay\nENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1\nCOPY package.json package-lock.json ./\nCOPY test-util ./test-util\nRUN npm ci --ignore-scripts --no-audit --no-fund\nCOPY harness ./harness\nRUN for p in calculator table bom; do ln -s /opt/replay/node_modules /opt/replay/harness/$p/node_modules; done\nCOPY runner.cjs ./runner.cjs\nCMD ["node", "/opt/replay/runner.cjs"]\n')
 sources={str(p.relative_to(ROOT)):sha(p) for base in (HERE,OUT/'inputs',context) for p in base.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
 dump(OUT/'snapshot.json',{'frozen_utc':datetime.now(timezone.utc).isoformat(),'base_image_digest':digest,'base_image_id':image['Id'],'files':sources})
 print('Frozen',len(jobs),'pages, digest',digest)

def read_json_output(args):return json.loads(call(args))

def verify():
 snapshot=read(OUT/'snapshot.json')
 for name,value in snapshot['files'].items():assert sha(ROOT/name)==value,name
 return snapshot

def build():
 verify();log=OUT/'build.log'
 if (OUT/'image.json').exists():raise RuntimeError('Image already built')
 with log.open('w') as f:subprocess.run(['docker','build','--tag',TAG,str(OUT/'context')],stdout=f,stderr=subprocess.STDOUT,check=True,timeout=900)
 dump(OUT/'image.json',read_json_output(['docker','image','inspect',TAG])[0]);print('Image ready')

def run():
 verify()
 assert (ROOT/'artifacts/history-replay-20261115/evaluation-complete.json').exists(),'Wait for BOM queue to finish'
 diagnostic=ROOT/'artifacts/history-tasks-only-20261115'
 assert not diagnostic.exists() or (diagnostic/'evaluation-complete.json').exists(),'Wait for the task-history BOM queue to finish'
 if (OUT/'outputs').exists():raise RuntimeError('Refuse to overwrite any container observations')
 (OUT/'outputs').mkdir();image=read(OUT/'image.json')
 container_name='gui-dna-replay-20261115'
 args=['docker','run','--name',container_name,'--rm','--init','--network','none','--cap-drop','ALL','--security-opt','no-new-privileges',
  '--shm-size','1g','--read-only','--tmpfs','/tmp:rw,nosuid,size=1g','-v',str(OUT/'inputs')+':/inputs:ro',
  '-v',str(OUT/'outputs')+':/outputs:rw',image['Id']]
 dump(OUT/'launch.json',{'command':args,'scope':'Container userspace, same host kernel; no host browser/npm/system-library mounts.'})
 try:subprocess.run(args,check=True,timeout=1800)
 except subprocess.TimeoutExpired:
  subprocess.run(['docker','stop','--time','10',container_name],check=False,timeout=30)
  raise

def analyze():
 verify();inputs=read(OUT/'inputs/inputs.json');done=read(OUT/'outputs/complete.json')
 assert done['inputs_sha256']==sha(OUT/'inputs/inputs.json') and done['jobs']==len(inputs['jobs'])
 rows=[]
 for job in inputs['jobs']:
  folder=OUT/'outputs/scores'/job['id'];report=read(folder/'report.json');receipt=read(folder/'receipt.json')
  assert sha(folder/'report.json')==receipt['report_sha256']
  errors=[e for e in report.get('errors',[]) if 'maximum allowed failures' not in e.get('message','')];assert not errors,errors
  cases=cases_by_file(report)
  passed=set(cases)==set(job['specs']) and all(cases.values()) and all(c['passed'] for group in cases.values() for c in group)
  assert passed or any(s in ('failed','timedOut') for group in cases.values() for c in group for s in c['statuses'])
  expected=read(ROOT/'artifacts/history-replay-20261115/scores'/job['history_key']/'score.json')['all_passed'] if job['comparison']=='history' else job['expected']
  rows.append({**job,'passed':passed,'expected_observation':expected,'matches':passed==expected,'tests':cases})
 result={'scope':'19 fixed saved pages; isolated container userspace/browser/npm/system libraries, same host kernel. Not all-history or cross-machine replay.',
  'rows':rows,'matched':sum(r['matches'] for r in rows),'total':len(rows),'environment':read(OUT/'outputs/environment.json'),
  'base_image_digest':read(OUT/'snapshot.json')['base_image_digest'],'image_id':read(OUT/'image.json')['Id']}
 dump(ROOT/'test/results/container-replay.json',result);print('Matched',result['matched'],'/',result['total'])

def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','build','run','analyze']);a=p.parse_args();globals()[a.action]()
if __name__=='__main__':main()
