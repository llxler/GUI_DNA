"""Describe retained-history failures without treating repeated prefixes as defects."""
from collections import defaultdict,Counter
from .run import ROOT,OUT,read,dump,digest


def main():
    summary=read(ROOT/'test/results/history-replay.json')
    inputs=read(OUT/'inputs.json')
    finals=[r for r in summary['rows'] if r['label']=='final' and not r['method'].startswith('control/')]
    grouped=defaultdict(list)
    for row in finals:
        grouped[tuple(row[k] for k in ('cohort','project','builder','model','method'))].append(row)
    discordances=[];failure_counts=Counter();failure_pages=defaultdict(set)
    for key,rows in grouped.items():
        for row in rows:
            k=int(row['task'].split('-')[1])
            if not row['old_current_passed'] or row['history_passed']:continue
            for failure in row['failures']:
                spec=failure['spec'];i=0 if spec=='init' else int(spec.split('-')[1]) if spec else None
                witnesses=[r['task'] for r in rows if r['history_passed'] and i is not None and i<=int(r['task'].split('-')[1])<k]
                item={k2:row[k2] for k2 in ('cohort','project','builder','model','method','task')}
                item.update(failure=failure,earlier_assertion=i is not None and i<k,
                            earlier_page_history_pass_witnesses=witnesses)
                discordances.append(item)
                fk=(row['cohort'],row['project'],row['method'],spec,failure['title'])
                failure_counts[fk]+=1
                failure_pages[fk].add(digest(inputs['jobs'][row['score_key']]['files']) if row['score_key'] else 'none')
    groups=[dict(zip(('cohort','project','method','spec','title'),key),observations=value,
                 distinct_source_maps=len(failure_pages[key])) for key,value in sorted(failure_counts.items(),key=lambda x:(-x[1],str(x[0])))]
    variant_counts=Counter()
    for row in finals:
        if row['cohort']!='expert' or row['method'] not in ('dna','dna_unchecked') or not row['page']:continue
        record=read(ROOT/row['record'])
        number=int(row['page'].split('/')[-1].removeprefix('v'))
        attempt=next(a for a in record['attempts'] if a['attempt']==number)
        plan=attempt.get('plan')
        if not isinstance(plan,dict):continue
        for field in ('select','insert','delete','drag','menuLabel'):
            variant_counts[row['method'],field,str(plan.get(field)),row['history_passed']]+=1
    result={'discordant_final_observations':len(discordances),
        'with_initial_file_failure':sum(r['failure']['spec']=='init' for r in discordances),
        'with_earlier_assertion_failure':sum(r['earlier_assertion'] for r in discordances),
        'with_same_sequence_earlier_page_history_pass_witness':sum(bool(r['earlier_page_history_pass_witnesses']) for r in discordances),
        'failures':groups,'discordances':discordances,
        'expert_variants':[{'method':m,'field':f,'value':v,'history_passed':p,'observations':n} for (m,f,v,p),n in sorted(variant_counts.items())],
        'scope':'Only historical-current-pass/new-history-fail endpoints. First observed failure follows Playwright file order, not chronological requirement order. Repeated prefixes and source maps are not independent defects. Earlier-page witnesses use new full-history scores on unchanged pages, not a causal decomposition.'}
    dump(ROOT/'test/results/history-replay-diagnostics.json',result)
    print({k:v for k,v in result.items() if k not in ('failures','discordances','expert_variants')})


if __name__=='__main__':main()
