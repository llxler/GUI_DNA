"""Recompute the prepared three-workflow comparison from individual task files and receipts."""
import argparse
from collections import Counter
from itertools import combinations

from studies.ledger_read import calls, totals
from studies.study_io import ROOT, digest, dump, read, sha, source_files
from studies.table_library_sources.report import paired
from .core import (
    ARMS, BUILDER, CONTROLLERS, HERE, MODEL, MODULES, OUT, RUNTIME, SOURCE, TASKS, TOOLBAR, target_prompt,
)
from .run import BASE_CONTROLS, CAP, EXAMPLES, frozen, with_error

DESTINATION = ROOT/'studies/results/expression-editor-sources-20261123.json'
STAGES = ('first','after_public_repair')
CONTROL_NAMES = BASE_CONTROLS+EXAMPLES


def summary(targets, stage):
    score = {a:{t:targets[t][a][stage]['passed'] for t in TASKS} for a in ARMS}
    common = [t for t in TASKS if all(score[a][t] is not None for a in ARMS)]
    controls = {c:{t:targets[t]['fixed_pages'][c]['passed'] for t in TASKS} for c in CONTROL_NAMES}
    calibrated = [t for t in common if controls['upstream_final'][t] and not controls['blank'][t] and not controls['starter'][t]]
    def by_arm(visible):
        return {a:{'passed':sum(score[a][t] is True for t in visible[a]),
                   'valid_artifacts':sum(targets[t][a][stage]['valid'] for t in visible[a]),
                   'observed':len(visible[a])} for a in ARMS}
    return {'shared_observed_targets':common,
            'by_arm_common':by_arm(dict.fromkeys(ARMS,common)),
            'by_arm_available':by_arm({a:[t for t in TASKS if score[a][t] is not None] for a in ARMS}),
            'paired':{a+'_vs_'+b:paired(score[a],score[b],TASKS) for a,b in combinations(ARMS,2)},
            'calibrated_shared_targets':calibrated,'by_arm_calibrated_common':by_arm(dict.fromkeys(ARMS,calibrated)),
            'task_plan_vs_fixed_library_example':{a:paired(score[a],controls[c],TASKS)
                                for a,c in [('reference','reference_full'),('ai','ai_example2')]}}


def receipt_check():
    actual = {r['id']:r for r in calls(OUT/'budget.sqlite3')}
    found = set()
    cost = {'preparation':{},'planning':{}}
    for kind,arms,top in [('preparation',('ai','direct'),'preparation'),('planning',ARMS,'candidates')]:
        for arm in arms:
            amounts=Counter()
            providers=Counter()
            finishes=Counter()
            for path in sorted((OUT/top/arm).rglob('request.json')):
                req=read(path)
                row=actual[req['call_id']]
                assert row['id'] not in found
                found.add(row['id'])
                assert row['model']==req['body']['model']==(BUILDER if kind=='preparation' else MODEL)
                assert req['body']['max_tokens']==(16000 if kind=='preparation' else 8192)
                stage_dir=path.parent.parent
                stage=stage_dir.name
                assert row['purpose']==('prepare-' if kind=='preparation' else '')+arm+'-'+stage
                rec=read(stage_dir/'record.json')
                prompt=req['body']['messages']
                assert rec['prompt_sha256']==digest(prompt)
                if stage=='first':
                    origin=(OUT/'prep-prompts'/(arm+'.json') if kind=='preparation'
                            else OUT/'inputs'/arm/(stage_dir.parent.name+'.json'))
                    assert prompt==read(origin)
                else:
                    first=stage_dir.parent/'first'
                    expected=with_error(read(first/'call/request.json')['body']['messages'],
                              read(first/'call/response.json')['choices'][0]['message']['content'],
                              read(first/'record.json')['error'])
                    assert prompt==expected
                amounts['requests']+=1
                amounts['settled']+=row['actual'] or 0
                amounts['exposure']+=row['actual'] if row['actual'] is not None else row['reserved']
                amounts['unsettled']+=row['actual'] is None
                resp_path=path.with_name('response.json')
                if resp_path.exists():
                    resp=read(resp_path)
                    assert row['actual'] is not None
                    providers[resp.get('provider','unspecified')]+=1
                    finishes[resp['choices'][0]['finish_reason']]+=1
                    for key in ('prompt_tokens','completion_tokens'):
                        amounts[key]+=resp['usage'][key]
                    amounts['reasoning_tokens']+=(resp['usage'].get('completion_tokens_details') or {}).get('reasoning_tokens') or 0
            cost[kind][arm]={'requests':amounts['requests'],'settled_usd':amounts['settled']/1e6,
                              'exposure_usd':amounts['exposure']/1e6,'unsettled_calls':amounts['unsettled'],
                              'billed_tokens':{k:amounts[k] for k in ('prompt_tokens','completion_tokens','reasoning_tokens')},
                              'providers':dict(providers),'finish_reasons':dict(finishes)}
    assert set(actual)==found
    return cost


def aggregate_cost(rows):
    vals=list(rows)
    return {k:(round(sum(v[k] for v in vals),6) if k.endswith('_usd') else sum(v[k] for v in vals))
            for k in ('requests','settled_usd','exposure_usd','unsettled_calls')}


def report():
    initial=frozen('freeze.json')
    prep=frozen('planning-freeze.json')
    gen=frozen('generation-complete.json')
    assert gen['planning_freeze_sha256']==sha(OUT/'planning-freeze.json')
    assert gen['freeze_sha256']==prep['freeze_sha256']==sha(OUT/'freeze.json')
    assert prep['controls_sha256']==sha(OUT/'controls-complete.json')
    assert read(OUT/'prep-prompts/ai.json')[1]==read(OUT/'prep-prompts/direct.json')[1]
    packages={'reference':read(OUT/'reference.json')}
    for a in ('ai','direct'):
        if a in prep['available_arms']:
            packages[a]=read(OUT/'preparation'/a/'artifact.json')
    for a,pkg in packages.items():
        for t in TASKS:
            assert target_prompt(a,t,pkg)==read(OUT/'inputs'/a/(t+'.json'))

    records={(r['arm'],r['task'],r['stage']):r for r in gen['rows']}
    assert len(records)==len(gen['rows'])
    assert {(a,t) for a,t,s in records if s=='first'}=={(a,t) for a in ARMS for t in TASKS}
    assert {(a,t) for a,t,s in records if s=='repair'}=={(a,t) for (a,t,s),r in records.items() if s=='first' and r['generated'] and not r['valid']}
    scores=read(OUT/'scores-complete.json')['rows']
    controls=read(OUT/'controls-complete.json')['rows']|read(OUT/'ai-control-complete.json')['rows']
    assert set(scores)=={'/'.join(k) for k,r in records.items() if r['valid']}
    available_controls=BASE_CONTROLS+(EXAMPLES if 'ai' in packages else ())
    assert set(controls)=={c+'/'+t for t in TASKS for c in available_controls}
    def verify_score(location,all_scores,key,task):
        data=all_scores[key]
        path=OUT/location/key
        raw=read(path/'score.json')
        assert sha(path/'report.json')==raw['report_sha256']==data['report_sha256']
        assert raw['all_passed']==data['passed'] and set(raw['tests'])=={task}
        return data
    targets={}
    for t in TASKS:
        targets[t]={}
        for a in ARMS:
            first=records[a,t,'first']
            final=records.get((a,t,'repair'),first)
            outcome={}
            for stage,row in zip(STAGES,(first,final)):
                key='/'.join((a,t,row['stage']))
                score_info=verify_score('scores',scores,key,t) if row['valid'] else {}
                outcome[stage]={'response':row['generated'],'valid':row['valid'],
                    'passed':score_info.get('passed',False if row['generated'] else None),'artifact_stage':row['stage'],
                    'page_manifest_sha256':digest(row['files_sha256']) if row['valid'] else None,
                    'official_report_sha256':score_info.get('report_sha256')}
            targets[t][a]=outcome
        targets[t]['fixed_pages']={}
        for c in CONTROL_NAMES:
            data=verify_score('calibration',controls,c+'/'+t,t) if c in available_controls else {}
            targets[t]['fixed_pages'][c]={'passed':data.get('passed'),'official_report_sha256':data.get('report_sha256')}

    costs=receipt_check()
    ledger=totals(OUT/'budget.sqlite3')
    summaries={s:summary(targets,s) for s in STAGES}
    statuses={a:{st:{'scheduled_positions':sum(r['arm']==a and r['stage']==st for r in gen['rows']),
                      'attempted_positions':sum((OUT/'candidates'/a/t/st/'call/request.json').is_file() for t in TASKS),
                      'received':sum(r['arm']==a and r['stage']==st and r['generated'] for r in gen['rows']),
                      'valid':sum(r['arm']==a and r['stage']==st and r['valid'] for r in gen['rows'])}
                 for st in ('first','repair')} for a in ARMS}
    stages={'reference':{'inputs':'Six upstream production modules and study binding informed by the published reference entry, plus the public starter and requirement prefix.',
            'production_modules':list(MODULES),'production_module_utf8_bytes':sum((SOURCE/('src/'+n+'.js')).stat().st_size for n in MODULES),
            'reference_files_sha256':{n+'.js':sha(SOURCE/('src/'+n+'.js')) for n in MODULES},
            'binding_sha256':sha(HERE/'binding.js'),'binding_utf8_bytes':(HERE/'binding.js').stat().st_size,
            'controls':{'toolbar':list(TOOLBAR),'controllers':list(CONTROLLERS)},
            'upstream_human_person_hours':None,'observed_agent_preparation_wall_seconds_including_runner_protocol':initial['agent_preparation_elapsed_seconds']}}
    for a in ('ai','direct'):
        attempts=prep['preparation'][a]
        if a in packages:
            preparation_status='valid_artifact_frozen'
        elif not attempts[-1]['received']:
            preparation_status='preparation_unobserved_or_interrupted'
        else:
            preparation_status='returned_artifacts_failed_public_validation'
        stages[a]={'preparation_status':preparation_status,'deployment_positions_planned':len(TASKS),
                   'deployment_first_responses':statuses[a]['first']['received'],'preparation_model':BUILDER,'preparation_user_message_sha256':digest(read(OUT/'prep-prompts'/(a+'.json'))[1]),
                   'preparation_inputs':'Complete public requirements and public starter; no official assertions or reference assets.',
                   'deployment_inputs':'Prefix and starter, plus own '+('complete frozen package' if a=='ai' else 'frozen non-executed technical memo'),
                   'artifact_sha256':sha(OUT/'preparation'/a/'artifact.json') if a in packages else None,
                   'artifact_utf8_bytes':(OUT/'preparation'/a/'artifact.json').stat().st_size if a in packages else None,
                   'preparation_attempts':[{'stage':r['stage'],'received':r['received'],'valid':r['valid'],
                        'public_failure':r.get('error')} for r in attempts],
                   'construction':costs['preparation'][a]}
    return {'study':'expression-editor-sources-20261123','project':'expression-editor','upstream_revision':initial['upstream_revision'],
        'planned_unique_targets':20,'model':MODEL,'preparation_model':BUILDER,'primary_endpoint':'first',
        'task_unit':'individual current official file','protocol':'Project-wide public preparation for both AI workflows; independent requirement-prefix deployments and a single optional public format repair.',
        'freeze_utc':initial['frozen_utc'],'preparations_frozen_utc':prep['frozen_utc'],'generation_closed_utc':gen['frozen_utc'],
        'provenance':stages,'public_starter_sha256':source_files(SOURCE/'src-init'),'summaries':summaries,'responses':statuses,
        'fixed_page_controls':{c:{'observed':sum(targets[t]['fixed_pages'][c]['passed'] is not None for t in TASKS),
                  'passed':sum(targets[t]['fixed_pages'][c]['passed'] is True for t in TASKS),
                  'page_manifest_sha256':digest(source_files(OUT/'control-pages'/c)) if c in available_controls else None} for c in CONTROL_NAMES},
        'stage_ledger':ledger,'preparation_cost_by_arm':costs['preparation'],'cost_by_arm':costs['planning'],
        'planning_ledger':aggregate_cost(costs['planning'].values()),'preparation_ledger':aggregate_cost(costs['preparation'].values()),
        'evaluation_runtime':{'playwright':'1.57.0','tinycolor2':'1.6.0','runtime_lock_sha256':sha(RUNTIME/'package-lock.json'),
               'utility_sha256':source_files(RUNTIME/'test-util')},'targets':targets,
        'audit_sha256':{n:sha(OUT/n) for n in ('freeze.json','planning-freeze.json','generation-complete.json',
                                          'controls-complete.json','ai-control-complete.json','scores-complete.json')}}


def check_public(value):
    assert tuple(value['targets'])==TASKS and value['model']==MODEL and value['preparation_model']==BUILDER
    assert value['provenance']['ai']['preparation_user_message_sha256']==value['provenance']['direct']['preparation_user_message_sha256']
    for s in STAGES:
        assert summary(value['targets'],s)==value['summaries'][s]
    for c,r in value['fixed_page_controls'].items():
        vals=[x['fixed_pages'][c]['passed'] for x in value['targets'].values()]
        assert r['observed']==sum(v is not None for v in vals) and r['passed']==sum(v is True for v in vals)
    merge=aggregate_cost([*value['preparation_cost_by_arm'].values(),*value['cost_by_arm'].values()])
    for k in ('settled_usd','exposure_usd','unsettled_calls'):
        assert merge[k]==value['stage_ledger'][k]
    assert merge['requests']==value['stage_ledger']['calls']
    assert merge['exposure_usd']<=value['stage_ledger']['cap_usd']==CAP


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    for mode in ('write','check','check-public'):
        group.add_argument('--'+mode,action='store_true')
    args=parser.parse_args()
    value=read(DESTINATION) if args.check_public else report()
    check_public(value)
    if args.write:
        if DESTINATION.exists() and read(DESTINATION)!=value:
            raise SystemExit('Different existing result; preserve prior evidence')
        dump(DESTINATION,value)
    elif not args.check_public:
        assert value==read(DESTINATION)
    print({s:p['by_arm_common'] for s,p in value['summaries'].items()})
    print(value['stage_ledger'])
