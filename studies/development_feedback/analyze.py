"""Read the exploratory whole-page baseline without pooling earlier protocols."""
from collections import Counter
from .evaluate import ROOT,OUT,verify,read,sha,dump,digest
from test.ledger_read import totals

def main():
 inputs=verify();assert read(OUT/'evaluation-complete.json')['inputs_sha256']==digest(inputs)
 rows=[]
 for row in inputs['rows']:
  report=read(OUT/'scores'/row['score_key']/'report.json') if row['score_key'] else {'cases':[],'all_passed':False,'passed':0}
  if row['score_key']:
   assert len(report['cases'])==12 and report['passed']==sum(c['passed'] for c in report['cases'])
   assert report['all_passed']==all(c['passed'] for c in report['cases'])
   assert sha(OUT/'scores'/row['score_key']/'report.json')==read(OUT/'scores'/row['score_key']/'receipt.json')['report_sha256']
  record=read(ROOT/row['record'])
  rows.append({**row,'all_passed':report['all_passed'],'passed_cases':report['passed'],'attempts':len(record['attempts']),
   'development_passes':record.get('development_passes',0),'development_total':3})
 usage=Counter();finish=Counter();providers=Counter()
 for p in (OUT/'runs').rglob('response.json'):
  r=read(p);finish[r['model']+'/'+r['choices'][0]['finish_reason']]+=1;providers[r['model']+'/'+r.get('provider','unknown')]+=1
  for k in ('prompt_tokens','completion_tokens','cost'):usage[k]+=r.get('usage',{}).get(k,0) or 0
  usage['reasoning_tokens']+=r.get('usage',{}).get('completion_tokens_details',{}).get('reasoning_tokens',0) or 0
 result={'posthoc':True,'rows':rows,'costs':totals(OUT/'budget.sqlite3'),'usage':dict(usage),'finish_reasons':dict(finish),'providers':dict(providers),
  'raw_reports':len(inputs['jobs']),'scope':'4 no-library full pages with construction-scale public feedback and 20000 output tokens/response; different information/feedback/cost from original 8000-token no-library candidates; no tool agent or pure feedback effect.'}
 dump(ROOT/'test/results/development-feedback.json',result)
 for r in rows:print(r['project'],r['model'],r['label'],r['passed_cases'],'/12')
if __name__=='__main__':main()
