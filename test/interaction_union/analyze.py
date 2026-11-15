"""Reconstruct exploratory Boolean-union outcomes; keep the original control intact."""
from .run import ROOT,OUT,verify,read,sha,dump,digest

def main():
 inputs=verify();assert read(OUT/'evaluation-complete.json')['inputs_sha256']==digest(inputs)
 rows=[]
 for row in inputs['rows']:
  if row['score_key']:
   folder=OUT/'scores'/row['score_key'];r=read(folder/'report.json')
   assert sha(folder/'report.json')==read(folder/'receipt.json')['report_sha256']
   assert r['total']==12 and r['passed']==sum(c['passed'] for c in r['cases'])
   assert r['all_passed']==all(c['passed'] for c in r['cases'])
  else:r={'passed':0,'all_passed':False}
  rows.append({**row,'passed_cases':r['passed'],'all_passed':r['all_passed']})
 result={'posthoc':True,'rows':rows,'passed':sum(r['all_passed'] for r in rows),'total':len(rows),
  'reused_reports':sum(bool(j['reuse_key']) for j in inputs['jobs'].values()),'new_reports':sum(not j['reuse_key'] for j in inputs['jobs'].values()),
  'scope':'Exploratory all-three-example Boolean OR, proposed after seeing strict merge errors; no target/hidden access by algorithm. Not a general planner or confirmation study.'}
 dump(ROOT/'test/results/interaction-union.json',result);print(result['passed'],'/',result['total'])
if __name__=='__main__':main()
