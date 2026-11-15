"""Posthoc legal-plan reachability witnesses for the new complete-history endpoint."""
from collections import defaultdict,Counter
import json
from .run import ROOT,OUT,read,dump,digest,sha
from .analyze import summarize
from test.webbench_expand.saved_witnesses import package,compile_cached,plan_page


def main():
 h=summarize();inputs=read(OUT/'inputs.json');evidence=defaultdict(list);proofs={}
 for row in h['rows']:
  if row['cohort'] not in ('expansion','frontier') or not row['history_passed']:continue
  if row['method']!='plan' and not row['method'].startswith('control/'):continue
  project,builder,page=row['project'],row['builder'],ROOT/row['page']
  if row['page'] not in proofs:
   if row['method'].startswith('control/example-'):
    plan=package(project,builder)['examples'][int(row['method'][-1])]['plan']
    files=compile_cached(project,builder,json.dumps(plan));mapping=inputs['jobs'][row['score_key']]['files']
    assert set(files)==set(mapping)
    import hashlib
    assert all(hashlib.sha256(v.encode()).hexdigest()==mapping[n] and (page/n).read_text()==v for n,v in files.items())
    output_hash=digest(files)
   else:plan,_,output_hash=plan_page(page.parent,page.name,project,builder)
   proofs[row['page']]={'plan':plan,'output_sha256':output_hash}
  evidence[project,builder,row['task']].append({k:row[k] for k in ('cohort','method','model','label','page','score_key')})
 libraries=[]
 for project in ('calculator','table','bom'):
  for builder in ('openai/gpt-5','anthropic/claude-sonnet-4.5'):
   present=[f'task-{k}' for k in range(1,21) if evidence[project,builder,f'task-{k}']]
   libraries.append({'project':project,'builder':builder,'n':20,'with_observed_witness':len(present),'witness_tasks':present})
 outcomes=[];counts=Counter()
 for row in h['rows']:
  if row['cohort']!='expansion' or row['method']!='plan' or row['label']!='final':continue
  witnesses=evidence[row['project'],row['builder'],row['task']]
  category='passed' if row['history_passed'] else ('failed_with_legal_history_witness' if witnesses else 'failed_without_observed_history_witness')
  counts[category]+=1;outcomes.append({k:row[k] for k in ('project','builder','model','task','page','history_passed')}|{'category':category})
 result={'scope':'Posthoc union of saved legal plans and fixed controls under same-page complete history. Positive pages are recompiled byte-for-byte against the original frozen package. No new search, model call or browser run; absence is not impossibility. Separate from the older current-file 53/120 bound.',
  'library_task_pairs':120,'with_observed_witness':sum(r['with_observed_witness'] for r in libraries),'libraries':libraries,
  'witnesses':[{'project':p,'builder':b,'task':t,'observations':v} for (p,b,t),v in sorted(evidence.items()) if v],
  'compiled_page_proofs':proofs,'main_plan_categories':dict(counts),'main_plan_outcomes':outcomes}
 dump(ROOT/'test/results/history-replay-witnesses.json',result)
 print('Full-history witnessed pairs',result['with_observed_witness'],'/120;',dict(counts))

if __name__=='__main__':main()
