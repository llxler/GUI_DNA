"""Reconstruct historical library-building targets and their original controls, offline."""
from __future__ import annotations

import argparse
from collections import defaultdict

from studies.study_io import ROOT, UPSTREAM, dump, read, sha
from studies.todomvc_dna.domain import tasks as todo_tasks

RESULTS = ROOT / 'studies/results'
OUTPUT = RESULTS / 'public-library-transfer-history-20261123.json'
GPT = 'openai/gpt-5'
MISTRAL = 'mistralai/mistral-small-3.2-24b-instruct'
ALL = list(range(1, 21))
FIVE = [4, 8, 12, 16, 20]


def number(task):
    return int(str(task).removeprefix('task-'))


def outcomes(values):
    return {'planned': len(values), 'observed': sum(v is not None for v in values.values()),
            'passed': sum(v is True for v in values.values()),
            'pass_targets': sorted(k for k, v in values.items() if v is True),
            'missing_targets': sorted(k for k, v in values.items() if v is None)}


def manifest(folder):
    return {p.relative_to(folder).as_posix(): sha(p) for p in sorted(folder.rglob('*')) if p.is_file()}


def reconstruct():
    source_hashes = {}
    cohorts, controls, costs = [], {}, {}
    def load(name, outside=False):
        path = (ROOT if outside else RESULTS) / name
        source_hashes[str(path.relative_to(ROOT))] = sha(path)
        return read(path)
    def control(key, values, label, source):
        assert key not in controls
        controls[key] = {'kind': label, 'source': source, 'outcomes': outcomes(values)}
    def add(study, project, builder, planner, rep, values, key, source, **extra):
        assert key is None or key in controls
        cohorts.append(dict(study=study, project=project, builder=builder, planner=planner,
                            repetition=rep, targets=sorted(values), historical_outcomes=outcomes(values),
                            direct_control_id=key, source=source, **extra))

    base_file = 'end_to_end.json'
    base = load(base_file)
    groups = defaultdict(dict)
    for row in base['records']:
        group=(row['cohort'],row['project'],row['builder'],row['model'],row['method'])
        n=number(row['task'])
        assert n not in groups[group]
        groups[group][n]=row['current']
    for (study,p,b,m,arm), vals in groups.items():
        if arm=='free':
            control(f'{study}/{p}/{m}',vals,'historical_no_library',base_file)
    for (study,p,b,m,arm), vals in groups.items():
        if arm=='plan':
            assert set(vals) == set(groups[study,p,None,m,'free'])
            add(study,p,b,m,1,vals,f'{study}/{p}/{m}',base_file,
                preparation_input='All project requirements, project-independent runtime constraints; no upstream starter or implementation in the build prompt.',
                endpoint='final saved candidate on the current official task',
                construction_cost_pointer=f'end_to_end.json#/costs/construction_by_builder/{study}',
                generation_cost_pointer='end_to_end.json#/costs')
    costs[base_file] = base['costs']['construction_by_builder']
    for study,c in list(base['canvas_pilots'].items())+[('matched_flex',base['matched_flex'])]:
        for rep in (1,2):
            def observed(arm):
                return {number(n):c['rows'][f'{arm}-{rep}/{n}']['passed'] for n in c['milestones']}
            key=f'{c["project"]}/{study}/notes-{rep}'
            control(key,observed('free'),'independently prepared no-library notes followed by direct code',base_file)
            info=c['groups'][f'plan-{rep}']
            add(study,c['project'],c['builder'],c['generator'],rep,observed('plan'),key,base_file,
                preparation_input='Full public requirements and mounted asset names; both workflows prepared separately.',
                max_tokens=c['config']['max_tokens'], prepare_status=info['prepare_status'],
                deployed_targets=[] if info['prepare_status']!='accepted' else list(FIVE),
                pipeline_scoring='A failed preparation was recorded as a workflow failure on each planned target.',
                plan_stage_cost=info['cost'], direct_stage_cost=c['groups'][f'free-{rep}']['cost'])
    f='webbench-expand-frontier.json'
    d=load(f)
    for g in d['groups']:
        vals={number(r['task']):r['final'] for r in d['rows'] if r['builder']==g['builder']
              and r['project']==g['project'] and r['method']=='plan'}
        assert set(vals)==set(FIVE)
        add('expansion_frontier',g['project'],g['builder'],d['model'],1,vals,None,f,
            endpoint='final after up to two repairs; five prespecified targets; 12000-token GPT-5 deployment',
            baseline_note='Only the same-library free-code arm and fixed controls were run.',
            cost_pointer=f+'#/costs_by_stage')
    f='library-sources-20261121.json'
    initial=load(f)
    for p,c in initial.items():
        key=f'library_sources/{p}/direct'
        def cells(arm):
            return {int(n):v['passed'] for n,v in c['cells'][arm].items()}
        control(key,cells('direct'),'current target from scratch',f)
        add('library_sources',p,c['ai_builder'],c['generator'],1,cells('ai'),key,f,
            cost_pointer=f+f'#/{p}/by_purpose')
    f='form-public-repair-20261121.json'
    d=load(f)
    key='form_repair/direct'
    def repaired(arm):
        return {number(r['task']):r['after'] for r in d['rows'] if r['arm']==arm}
    control(key,repaired('direct'),'same initial outputs plus public-format repair',f)
    add('form_public_repair','form',GPT,MISTRAL,1,repaired('ai'),key,f,
        shares_build_and_initial_samples_with='library_sources/form',cost_pointer=f+'#/by_arm')
    f='svg-chart-interfaces-20261123.json'
    d=load(f)
    def chart(arm):
        return {int(n):v['passed'] for n,v in d['cells'][arm].items()}
    key='chart_interface/direct'
    control(key,chart('direct'),'current target from scratch',f)
    add('svg_chart_interfaces','svg-chart',d['builder'],d['generator'],1,chart('ai'),key,f,
        deployment_note='Twenty new targets per deployed arm; the earlier five-target package was reused. Compare within this deployment protocol.',
        cost_pointer=f+'#/billing')
    for name in ('table-library-sources','expression-editor-sources','expression-editor-window','expression-editor-unseen'):
        f=f'{name}-20261123.json'
        d=load(f)
        p='table' if name.startswith('table') else 'expression-editor'
        b=d['provenance']['ai']['construction']['model'] if p=='table' else d.get('preparation_model', d.get('builder'))
        m=d.get('model', d.get('generator'))
        def phase(arm,when):
            return {number(n):v[arm][when]['passed'] for n,v in d['targets'].items()}
        for stage in (('first','after_public_repair') if name.endswith('sources') else ('first','final')):
            key=f'{name}/{stage}/direct'
            direct_label='from scratch without project-wide notes' if p=='table' else 'no-library code with separately prepared public notes'
            control(key,phase('direct',stage),direct_label,f)
            vals=phase('ai',stage)
            meta={'endpoint':stage,
                  'preparation_public_tasks':list(range(1,11)) if name.endswith('unseen') else ALL,
                  'cost_pointer':f+'#/'+('cost_by_arm' if name.endswith('sources') else 'ledger')}
            if name=='expression-editor-window':
                meta['preparation_max_tokens']=d['preparation_max_tokens']
            if p=='expression-editor':
                meta['deployed_ai_targets']=[]
                meta['preparation_outcome']='Original AI-side preparation invalid or missing; planned and deployed units differ.'
            add(name,p,b,m,1,vals,key,f,**meta)
    extra='expression-editor-unseen-notes-admission-20261123.json'
    d=load(extra)
    for stage in ('first','final'):
        key=f'editor_supplementary_notes/{stage}'
        vals={number(n):t['supplementary_notes'][stage]['passed'] for n,t in d['targets'].items()}
        control(key,vals,'supplementary notes comparison; original AI preparation retained',extra)
    f='blind-library.json'
    blind=load(f)
    ids=sorted(t['id'] for t in todo_tasks())
    for b,c in blind['builders'].items():
        for m,row in c['models'].items():
            key=f'todomvc/main_free/{m}'
            if key not in controls:
                controls[key]={'kind':'archived original no-library code','source':f,
                               'outcomes':{'planned':2*len(ids),'passed_final':row['main_free']}}
            else:
                assert controls[key]['outcomes']['passed_final']==row['main_free']
            assert row['dna']['n']==2*len(ids)
            cohorts.append(dict(study='todomvc_blind_library',project='TodoMVC',builder=b,planner=m,
                repetition=1,samples_per_target=2,sample_ids=[0,1],targets=ids,historical_outcomes={k:row['dna'][k] for k in ('n','first','final','transport_failures')},
                direct_control_id=key,source=f,preparation_input='Public TodoMVC specification with study-defined shell and slots.',
                construction_cost_usd=c['library']['build_cost_usd'],deployment_cost_usd=row['dna']['cost_usd']))
    original_registration=load('artifacts/todomvc-blind-2/review-manifest.json',True)
    assert original_registration['protocol']['samples']==2
    blind_unreported=[]
    for builder,c in blind['builders'].items():
        for model in original_registration['config']['models']:
            if model in blind['builders'] or model in c['models']:
                continue
            folder=ROOT/'artifacts/todomvc-blind-2/runs'/builder.replace('/','__')/model.replace('/','__')/'dna'
            samples=[]
            for record in sorted(folder.glob('*/s*/record.json')):
                r=load(str(record.relative_to(ROOT)),True)
                h=record.parent/'hidden.json'
                summary=load(str(h.relative_to(ROOT)),True) if h.is_file() else {}
                samples.append({'target':r['task'],'sample':r['sample'],
                                'first':summary.get('first',{}).get('all_passed'),
                                'final':summary.get('final',{}).get('all_passed'),
                                'record':str(record.relative_to(ROOT))})
            blind_unreported.append({'builder':builder,'planner':model,'planned_target_samples':2*len(ids),
                                     'archived_records':samples,'reported_in_blind_library_summary':False})
    f='studies/webapp1k_dna/results/summary.json'
    duo=load(f,True)
    replay='studies/webapp1k_dna/results/summary-replay.json'
    load(replay,True)
    for m in duo['models']:
        key='webapp1k_duo/direct/'+m['model']
        controls[key]={'kind':'direct code with the public Duo Jest file','source':f,'outcomes':m['arms']['free']}
        origins=sorted({v['origin'] for variants in duo['library'].values() for v in variants})
        cohorts.append(dict(study='webapp1k_duo',project='WebApp1K-Duo', builder=origins, planner=m['model'],repetition=1,
                            targets=[r['category']+'/'+r['name'] for r in duo['duos']], historical_outcomes=m['arms']['dna'],
                            direct_control_id=key,source=f,distinct_single_atoms=len(duo['library']),
                            construction_input='Public single-feature tests, variants from both origins jointly available.',
                            compiler_replay_same_outputs=replay,cost_pointer=f+'#/accounting'))

    supplement={}
    for stem,scope in {
        'contract-library-table':'Two independent preparations with GPT-5 design and Mistral component generation; neither design passed admission.',
        'compatible-library-rebuild':'Four Codex table rebuilds against a historical interface; two archived Mistral plan cohorts, no fresh Mistral planning.',
        'compatible-table-local-plans':'Fresh local Qwen planning on historical and compatible table packages.',
        'public-controller-table':'Two independent public-only Codex table builders; fresh local Qwen plans.',
        'schema-constrained-table':'Constrained Qwen on the two public-only Codex libraries and original GPT-5 library; shares builds, not a new construction.',
        'compatible-chart-rebuild':'Two Codex SVG builds retaining an old interface; archived local Qwen planning, no fresh provider replication.',
        'svg-chart-compact-local':'Compact local planner diagnostic on the historical GPT-5 SVG package.',
        'library-refinement-table':'Deterministic table implementation/refinement diagnostic on archived plans.',
        'svg-chart-library-refinement':'Same frozen SVG package with archived and newly requested compact/full Mistral planning; incomplete arms retained.',
        'svg-chart-local-prompt-comparison':'Local Qwen compact versus full prompt with the same frozen SVG library.',
    }.items():
        file=stem+'-20261123.json'
        d=load(file)
        meta={'scope':scope, 'project':d['project'].split('/')[-1], 'scheduled_targets':ALL,
              'planner':d.get('planner',d.get('model',MISTRAL))}
        if stem=='contract-library-table':
            meta.update(builder={'design':GPT,'components':MISTRAL}, repeats={k:r['build'] for k,r in d['repeats'].items()},
                        frozen_direct='table-library-sources-20261123.json', cost=d['ledger'])
        elif stem=='compatible-library-rebuild':
            meta.update(builder=d['new_library_builder'],repeats=d['build_statuses'], archived_planner_cohorts=list(d['cohorts']),
                        compute=d['build_compute'])
        elif stem=='compatible-table-local-plans':
            meta.update(backends=list(d['totals']),remote_planning_calls=d['remote_planning_calls'])
        elif stem=='compatible-chart-rebuild':
            meta.update(builder=d['model'],repeats=d['independent_builds'],cost_usd=d['additional_openrouter_cost_usd'])
        elif stem=='public-controller-table':
            meta.update(builder=d['library_builder'],repetitions=list(d['repeats']),remote_calls=d['verification']['remote_api_requests'])
        elif stem=='schema-constrained-table':
            meta.update(builders=d['builder_by_arm'],remote_api_usd=d['verification']['additional_api_cost_usd'])
        elif stem=='svg-chart-library-refinement':
            meta.update(builder=d['builder'], arms={key:{'seed_requested':a['seed'],'outcomes':a['summary']}
                                                   for key,a in d['arms'].items()},deployment_ledger=d['generation_ledger'])
        elif stem=='library-refinement-table':
            meta.update(builder=d['library_builder'],archived_planner_cohorts=list(d['cohorts']),api_usd=d['additional_api_cost_usd'])
        else:
            meta['builder']=GPT
        supplement[file]=meta
    file='library-repair-full.json'
    fix=load(file)
    source_pairs=[{'project':p['project'],'builder':p['builder']} for p in fix['selected_pairs']]
    supplement[file]={'scope':'Post hoc review versus development-feedback library repair; two variants per original package; old planner outputs replayed.',
                      'six_original_packages':source_pairs, 'development_targets':[2,6,10,14,18],
                      'evaluation_targets':FIVE,'recorded_planners':sorted({r['model'] for r in fix['rows'] if r['method']=='plan'}),
                      'preparation_cost_in_original_stage':fix['prior_generation_cost'],'continuation_cost':fix['cost']}
    for file in ('matched-feedback.json','matched-feedback-frontier.json'):
        d=load(file)
        rows=[r for r in d['rows'] if r['method']=='plan' and r['endpoint']=='current']
        supplement[file]={'scope':'Matched public feedback with existing AI libraries, direct baseline and possible repairs. Current task only.',
                          'projects':sorted({r['project'] for r in rows}), 'original_builders':sorted({r['builder'] for r in rows}),
                          'planners':sorted({r['model'] for r in rows}), 'requested_seeds':sorted({r['seed'] for r in rows}),
                          'targets':[20], 'deployment_cost':d['cost']}
    file='behavior-feedback.json'
    d=load(file); split='behavior-feedback-split.json'
    load(split)
    supplement[file]={'scope':'Extra development feedback on existing dom1/form AI libraries; historical split-specific protocol.',
                      'groups':[{'project':g['project'],'original_builder':g['builder'],'planner':g['model'],
                                 'observed_deployments':g['methods']['plan']['n']} for g in d['groups']],
                      'feedback_split':split, 'deployment_cost':d['cost']}
    sources={}
    for p in ('dom1','form','calculator','table','bom','draw','canvas','flex','svg-chart','expression-editor'):
        src=UPSTREAM/'projects'/p
        filename='tasks.yml' if (src/'tasks.yml').exists() else 'tasks.jsonl'
        req=src/filename
        historical_loader=next(value for group,value in [
            (('dom1','form'),'studies.interface_blind.core.requirements'),
            (('calculator','table','bom'),'studies.webbench_expand.core.requirements'),
            (('draw',),'studies.webbench_draw.core.requirements'),
            (('canvas',),'studies.matched_canvas.run.messages'),
            (('flex',),'studies.matched_flex.run.configure + studies.matched_canvas.run.messages'),
            (('svg-chart',),'studies.svg_chart_sources.run.inputs'),
            (('expression-editor',),'studies.expression_editor_sources.core.requirements')] if p in group)
        sources[p]={'public_requirements':str(req.relative_to(ROOT)),'requirements_sha256':sha(req),
                    'historical_public_loader':historical_loader,'includes_init':filename=='tasks.jsonl',
                    'starter_manifest':manifest(src/'src-init'),'asset_manifest':manifest(src/'assets')}
    coverage=load('webbench-coverage-20261123.json')
    return {'study':'historical AI-library rerun register','scope':'Prior public-benchmark preparations and original comparison units only. New protocol measurements are separate.',
            'upstream_commit':coverage['upstream_commit'], 'public_input_inventory_note':'Paths identify public materials in the upstream snapshot. Individual historical protocols differed in which materials were included in model prompts.', 'historical_public_inputs':sources,
            'historical_cohorts':cohorts, 'originally_configured_unreported_todomvc':blind_unreported, 'original_controls':controls,'original_construction_costs_by_builder':costs,
            'supplementary_existing_builds_or_replays':supplement,
            'replication_rule':'Match project, preparation scope, target list, build and deployment model, repetitions and original endpoint. A new-model project transfer alone does not complete that historical cohort. Baseline reuse requires identical generation input and endpoint; never sum shared controls.',
            'excluded_scope':{'withdrawn_webapp1k_quartet':'User withdrew the exploratory cohort, no published result.', 'synthetic_studies':'Archived and outside current public-benchmark evidence.', 'react_blog':'Only calibration was run in the prior study.'},
            'artifacts_sha256':source_hashes,'offline_reconstruction_api_usd':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--write',action='store_true')
    mode.add_argument('--check',action='store_true')
    args=parser.parse_args()
    data=reconstruct()
    if args.write:
        dump(OUTPUT,data)
    elif read(OUTPUT)!=data:
        raise SystemExit('Historical register differs from its frozen sources')
    print(f'{len(data["historical_cohorts"])} original cohort/endpoints, {len(data["original_controls"])} unique control groups.')
