"""Match each historical endpoint to actual new-method targets without relabelling protocols."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict

from studies.study_io import ROOT, dump, read, sha

RESULTS=ROOT/'studies/results'
BASE='public-library-transfer'
DAY='20261123'
ASTRA='gpt-6.2-astra'
OUTPUT=RESULTS/f'{BASE}-retest-crosswalk-{DAY}.json'


def artifact(stem, path):
    return ROOT/'artifacts'/f'{BASE}{stem}-{DAY}'/path


def endpoint(c):
    if 'endpoint' in c: return c['endpoint']
    if c['study'] in ('todomvc_blind_library','webapp1k_duo'):return 'reported first and final responses'
    return {'form_public_repair':'after public-format repair',
            'library_sources':'first response','svg_chart_interfaces':'first response'}.get(c['study'],'original final workflow')


def reasons(c):
    if c['project']=='TodoMVC':
        return ['Historical builders wrote variants for study-defined slots with a fixed shell. New builders choose their own controls.',
                'Historical workflows allowed repairs; new target deployments take one response.']
    if c['project']=='WebApp1K-Duo':
        return ['The old library combined single-task variants from both origin models. The new method builds one menu per category and source.',
                'Old deployments could select variants, order and relabel; new deployments select up to two components.']
    if c['study']=='expression-editor-unseen':
        return ['The ten-task preparation cutoff is matched only by the separately sealed editor holdout.',
                'Both methods changed the preparation implementation and interface. The old direct comparator prepared notes.']
    if c['project'] in ('canvas','flex'):
        return ['The historical preparation and deployment used the same GPT-5 or Claude model and allowed project-wide notes for direct code.',
                'The newer five-target supplement uses a public starter, separate subscription builders and one-shot deployers; output windows differ.']
    if c['study'] in ('expansion','interface','draw','expansion_frontier'):
        return ['Historical builders saw the public requirements without the upstream starter and designed their own compiler.',
                'New builders receive starter and assets and use the fixed finite-control assembler. New deployments use one response.']
    if c['project']=='expression-editor':
        return ['Historical direct code used independently prepared notes. This round uses the public prefix and starter directly.',
                'New library shape, compilation and output admission differ; the historical public-repair endpoint is not rerun.']
    return ['The new package interface, preparation and target-generation protocol differ. New deployments use one schema-constrained response.']


def reconstruct():
    sources={}
    pending=[]
    def use(path):
        sources[str(path.relative_to(ROOT))]=sha(path)
        return read(path)
    history_path=RESULTS/f'{BASE}-history-{DAY}.json'
    prior=use(history_path)['historical_cohorts']
    groups={}
    grouped=defaultdict(dict)
    meta={}
    def record(stage,project,builder,planner,rep,task,sample,status,path,boundary='whole-project'):
        group=(stage,project,builder,planner,rep)
        key=(task,sample)
        if key in grouped[group]:raise ValueError(f'Duplicate plan registration {group}/{key}')
        grouped[group][key]=status
        meta[group]=(str(path.relative_to(ROOT)),boundary)
    def web(stem,seal,boundary='whole-project'):
        path=artifact(stem,seal)
        if not path.is_file():
            pending.append(str(path.relative_to(ROOT)))
            return
        d=use(path)
        for r in d['rows']:
            if r['arm']=='plan':
                record(stem.lstrip('-') or 'primary',r['project'],r['builder'],r['planner'],r['rep'],r['task'],0,r['status'],path,boundary)
    web('','generation-sealed.json')
    web('-remote','generation-sealed.json')
    web('-remote-milestones','generation-sealed.json')
    web('-holdout','sealed.json','prepare-1-10/test-11-20')

    def nonweb_task(group,task):
        return ('TodoMVC',task) if group=='todomvc' else ('WebApp1K-Duo',f'{group}/{task}')
    path=RESULTS/f'{BASE}-extra-{DAY}.json'
    extra=use(path)
    target_groups={t:r['group'] for t,r in extra['rows'].items()}
    for t,r in extra['rows'].items():
        project,task=nonweb_task(r['group'],t)
        for rep,arm in enumerate(('dna-a','dna-b'),1):
            outcome=r['arms'][arm]
            status='valid' if outcome.get('candidate_sha256') else 'invalid' if outcome.get('passed') is not None else 'missing'
            record('extra-subscription',project,ASTRA,extra['model'],rep,task,0,status,path,'public-task-benchmark')
    registration_path=artifact('-extra-remote','registered.json')
    registration=use(registration_path)
    aliases={k:v[0] for k,v in registration['prices_and_models'].items()}
    final=RESULTS/f'{BASE}-historical-models-{DAY}.json'
    other=use(final) if final.is_file() else None
    if other is None:pending.append(str(final.relative_to(ROOT)))
    for key,r in registration['requests'].items():
        if r['arm'] not in ('dna-a','dna-b'):continue
        project,task=nonweb_task(r['group'],r['task'])
        if other is None:
            state='registered_pending_final_report'
        else:
            outcome=other['rows'][key.rsplit('/',1)[0]]['arms'][r['arm']]
            state=outcome.get('status','missing')
        record('extra-original-deployers',project,ASTRA,aliases[r['alias']],1 if r['arm']=='dna-a' else 2,
               task,r['sample'],state,final if other else registration_path,'public-task-benchmark')
    duo_reg_path=artifact('-extra-remote','duo-original-sources/registered.json')
    if duo_reg_path.is_file():
        duo_reg=use(duo_reg_path)
        final=RESULTS/f'{BASE}-duo-original-sources-{DAY}.json'
        result=use(final) if final.is_file() else None
        if result is None:pending.append(str(final.relative_to(ROOT)))
        for r in duo_reg['planned']:
            b,m,t=r['builder'],r['deployer'],r['task']
            status=result['rows'][f'{b}/{m}/{t}']['dna']['status'] if result else 'registered_pending_final_report'
            project,task=nonweb_task(target_groups[t],t)
            record('duo-separate-original-builders',project,aliases[b],aliases[m],1,task,0,status,
                   final if result else duo_reg_path,'category-library/single-source')
    else:
        pending.append(str(duo_reg_path.relative_to(ROOT)))
    work={}
    for key,states in sorted(grouped.items()):
        stage,p,b,m,rep=key
        identifier=f'{stage}|{p}|{b}|{m}|{rep}'
        path,boundary=meta[key]
        groups[identifier]={'stage':stage,'project':p,'builder':b,'planner':m,'library_repetition':rep,
                            'inputs':boundary,'source':path,'source_sha256':sources[path],
                            'targets':sorted({k[0] for k in states}),'sample_ids':sorted({k[1] for k in states}),
                            'target_sample_outcomes':dict(sorted(Counter(states.values()).items()))}
        work[identifier]=states

    rows=[]
    def match(c):
        old_builders=c['builder'] if isinstance(c['builder'],list) else [c['builder']]
        target_ids=set(c['targets'])
        original_samples=set(c.get('sample_ids',[0]))
        matched=[]
        for gid,g in groups.items():
            if g['project']!=c['project']:continue
            # Prevent full-brief results from being credited as withheld preparation and vice versa.
            if (c['study']=='expression-editor-unseen') != (g['inputs']=='prepare-1-10/test-11-20'):continue
            scope=set(g['targets'])
            common=target_ids & scope
            if not common:continue
            builder=('original' if len(old_builders)==1 and old_builders[0]==g['builder'] else
                     'one_original_component_source' if g['builder'] in old_builders else 'changed')
            planner='original' if g['planner']==c['planner'] else 'changed'
            observed=[s for (task,sample),s in work[gid].items() if task in common and sample in original_samples]
            counted=Counter(observed)
            # Count valid physical plans only. Rejected outputs and no response retain their own buckets.
            matched.append({'group':gid,'builder_identity':builder,'planner_identity':planner,
                            'target_scope':'same' if target_ids==scope else 'new_superset' if common==target_ids else 'partial_overlap',
                            'overlap_distinct_targets':len(common), 'old_sample_ids_covered':sorted(original_samples & set(g['sample_ids'])),
                            'matched_target_sample_slots':len(observed),'valid_plans_on_matched_slots':counted.get('valid',0),
                            'statuses_on_matched_slots':dict(sorted(counted.items()))})
        return matched
    for i,c in enumerate(prior,1):
        matched=match(c)
        exact=[m for m in matched if m['builder_identity']=='original' and m['planner_identity']=='original']
        planner=[m for m in matched if m['planner_identity']=='original' and m['builder_identity']!='original']
        if any(m['valid_plans_on_matched_slots'] for m in exact): identity='same_builder_and_deployer_new_protocol_observed'
        elif exact:identity='same_builder_and_deployer_without_valid_new_plans'
        elif isinstance(c['builder'],list):identity='pooled_original_builder_mix_not_rebuilt'
        elif c['project']=='TodoMVC':identity='historical_todomvc_builders_not_rerun'
        elif c['study']=='expression-editor-unseen':identity='new_holdout_builders_only'
        else:identity='historical_deployer_not_run_with_original_builder'
        if any(m['valid_plans_on_matched_slots'] for m in planner): pstatus='valid_new_plans'
        elif planner and all(m['statuses_on_matched_slots'].get('registered_pending_final_report')==m['matched_target_sample_slots'] for m in planner):
            pstatus='registered_waiting_for_final_report'
        elif planner:pstatus='no_valid_new_plans_on_matched_slots'
        else:pstatus='no_same_deployer_transfer'
        origin=c['source'] if c['source'].startswith('studies/') else 'studies/results/'+c['source']
        row={'historical_row':i,'study':c['study'],'project':c['project'],'original_builder':c['builder'],
             'original_planner':c['planner'],'original_library_repetition':c['repetition'],'original_endpoint':endpoint(c),
             'original_targets':c['targets'],'original_samples_per_target':c.get('samples_per_target',1),
             'original_source':origin,
             'original_observations':{k:v for k,v in c['historical_outcomes'].items() if k in ('planned','observed','passed','n','first','final','first_pass','final_pass')},
             'exact_original_protocol_replication':False,
             'original_model_pair_under_new_method':identity,'original_deployer_with_changed_or_partial_builder':pstatus,
             'protocol_differences':reasons(c),'new_groups':matched}
        if exact and not any(x['valid_plans_on_matched_slots'] for x in exact) and c['project'] not in ('TodoMVC','WebApp1K-Duo'):
            row['preparation_outcome']='Remote historical-builder preparation unavailable; see per-project status retained in the new generation seal.'
        if c['study']=='library_sources' and c['project']=='svg-chart':
            row['coverage_note']='Five old milestones recur in a new twenty-target deployment, not as a rerun of the original five-target stage.'
        if c['project'] in ('canvas','flex'):
            row['coverage_note']='Five new remote targets match the milestone IDs; historical model, preparation notes, response cap and repetition pairing are different.'
        if c['study']=='webapp1k_duo':
            row['coverage_note']='Each new original-source library is single-source. A matched old component supplier and planner cannot reproduce old cross-source variant selection.'
        rows.append(row)
    assert len(rows)==60 and len({(r['study'],r['project'],str(r['original_builder']),r['original_planner'],
                                  r['original_library_repetition'],r['original_endpoint']) for r in rows})==len(rows)
    return {'scope':'One row per previously indexed historical group/endpoint, with candidate-level evidence of new-method coverage; no retired test endpoints.',
            'unit':'Matched slots intersect the actual target IDs and original sampling indices; each new library is independently sampled. Equal sample indices do not establish equal seeds or identical model draws.',
            'definition':'A valid plan means valid materialization. Behavioral passes are reported in the endpoint reports, not inferred from admission. Repeated references to a group are coverage links, not additional observations.',
            'counts':{'historical_rows':len(rows),'strict_protocol_replicates':sum(r['exact_original_protocol_replication'] for r in rows),
                      'new_method_identity_match':dict(sorted(Counter(r['original_model_pair_under_new_method'] for r in rows).items()))},
            'pending_sources':pending,'historical_index_sha256':sources[str(history_path.relative_to(ROOT))],
            'new_groups':groups,'historical_rows':rows,'sources_sha256':sources}


if __name__=='__main__':
    p=argparse.ArgumentParser();mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--write',action='store_true');mode.add_argument('--check',action='store_true')
    args=p.parse_args();d=reconstruct()
    if args.write: dump(OUTPUT,d)
    elif read(OUTPUT)!=d:raise SystemExit('Crosswalk differs from the current frozen sources')
    print(d['counts'],'pending',d['pending_sources'])
