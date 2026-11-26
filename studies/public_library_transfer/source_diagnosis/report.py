"""Join source comparisons by target ID while retaining build, delivery and fixed controls."""
from argparse import ArgumentParser
from collections import Counter
from pathlib import Path

from studies.study_io import ROOT, dump, read, sha
from studies.webgen_bench import report as functional


HERE=Path(__file__).resolve().parent
INITIAL=HERE/'initial-comparisons.json'
TRIAL=HERE/'result.json'
FORM=ROOT/'studies/webbench/form/survey_workflow/qwen_comparison/result.json'
MENU=ROOT/'studies/webbench/table/menu_propagation/result.json'
DONORS=ROOT/'studies/public_library_transfer/duo_donor_library/result.json'
DYNAMIC=ROOT/'studies/public_library_transfer/duo_react_callbacks/result.json'
OUTPUT=ROOT/'studies/results/library-source-diagnosis-20261126.json'
FILES=ROOT/'studies/webbench/file_explorer/interaction_contracts/result.json'
IDENTITY=FILES.parent/'entry_identity/result.json'
VISIBLE=HERE/'visible_choices/result.json'
CORE_PROFILES=VISIBLE.parent/'core_profiles/result.json'
CHOICES=CORE_PROFILES.with_name('configurations.json')
FUNCTIONS=VISIBLE.with_name('function-choices.json')
SVG=ROOT/'studies/webbench/typed_components/svg_public_geometry/attribute_contracts/result.json'
DIRECT_SOURCES={'qwen9':('qwen/qwen3.5-9b','backbone-extension-20261124.json'),
                'mistral':('mistralai/mistral-small-3.2-24b-instruct','backbone-matrix-20261124.json')}
SOURCES=(INITIAL,TRIAL,FORM,MENU,DONORS,DYNAMIC,FILES,IDENTITY,SVG,VISIBLE,CORE_PROFILES,CHOICES,FUNCTIONS,functional.RESULT,*(ROOT/'studies/results'/p for m,p in DIRECT_SOURCES.values()))


FOLLOWUP_LEDGERS={
    TRIAL:'library-source-diagnosis',FORM:'form-qwen-source-comparison',FILES:'file-explorer-interactions',
    IDENTITY:'file-explorer-entry-identity',SVG:'svg-attribute-contracts',VISIBLE:'todo-visible-choices',CORE_PROFILES:'todo-core-profiles',
}

def round_budget():
    first=read(functional.RESULT)['budget']['total']
    total=Counter(first)
    for file in FOLLOWUP_LEDGERS:
        cost=read(file)['cost']
        total.update(calls=cost['calls'],unsettled_calls=cost['unsettled_calls'],
                     settled_micro_usd=round(cost['settled_usd']*1e6),exposure_micro_usd=round(cost['exposure_usd']*1e6))
    assert total['exposure_micro_usd']<=20_000_000
    return dict(total)

def verify_ledgers():
    from studies import ledger_read
    first=read(functional.RESULT)['budget']
    assert first==functional.accounting()
    for file,folder in FOLLOWUP_LEDGERS.items():
        ledger=ROOT/'artifacts'/(folder+'-20261126pm')/'budget.sqlite3'
        assert read(file)['cost']==ledger_read.totals(ledger)

def arm(rows,name):
    selected=[r for r in rows if r['arm']==name]
    grouped={str(r['task']):r for r in selected}
    assert len(grouped)==len(selected)
    return grouped


def paired(rows,names,targets=None):
    groups={k:arm(rows,k) for k in names}
    known = {k:{t for t,r in v.items() if type(r.get('passed')) is bool} for k,v in groups.items()}
    if targets is None:
        targets=sorted(set.intersection(*known.values())) if known else []
    targets=[str(t) for t in targets]
    if not all(set(targets)<=s for s in known.values()):raise ValueError('Unmatched target enters comparison')
    result={}
    for k,rs in groups.items():
        status=Counter(rs[t]['status'] for t in targets)
        result[k]=dict(passes=sorted(t for t in targets if rs[t]['passed']),observed=len(known[k]),
                       observed_passes=sorted(t for t in known[k] if rs[t]['passed']),
                       statuses=dict(sorted(status.items())))
    return dict(n=len(targets),targets=targets,arms=result)


def file_comparisons(files):
    groups={}
    for tag,model in [('qwen9','qwen/qwen3.5-9b'),('deepseek-flash','deepseek/deepseek-v4-flash')]:
        control=[r for r in files['controls'] if r['tag']==tag]
        replicas={}
        for rep in ('a','b'):
            rows=[r for r in files['rows'] if r['tag']==tag and r['rep']==rep]
            result=paired(control+rows,['direct','human','gpt5-library','planned','old-fixed','fixed','core'])
            lib=files['libraries'][tag][rep]
            result['public_sequences']={k:sorted(n for n,v in lib[k]['checks'].items() if v) for k in ('before','after')}
            result['retained_edits']=[r['group'] for r in lib['history'] if r['retained']]
            a,b=(set(result['arms'][k]['passes']) for k in ('planned','fixed'))
            result.update(planned_only=sorted(a-b),fixed_only=sorted(b-a))
            replicas[rep]=result
        groups[model]=replicas
    return groups


def reconstruct():
    data=read(TRIAL);initial=read(INITIAL);form=read(FORM);menu=read(MENU);donors=read(DONORS);react=read(DYNAMIC)
    assert data['initial']==sha(INITIAL)
    assert len(initial['rows'])==len({(r['project'],r['model']) for r in initial['rows']})
    out={'web':{},'todo':{},'form':{},'files':{}}
    for c in data['web']:
        names=['direct','before','gpt5-library',*sorted({r['arm'] for r in c['examples']})]
        rows=[*c['original_rows']['direct'],*[{**r,'arm':'before'} for r in c['original_rows']['gpt5-library']],
              *[r for r in c['rows'] if r['arm']=='gpt5-library'],*c['examples']]
        g=paired(rows,names)
        sets=[set(g['arms'][a]['passes']) for a in names if a.startswith('example-')]
        g['example_union']=sorted(set.union(*sets))
        out['web'][c['project']]=dict(model=c['model'],**g)
    for model,d in data['todomvc'].items():
        existing={r['arm'] for r in d['rows']}
        rows=list(d['rows'])
        if 'gpt5-library' in existing:
            rows.extend({**r,'arm':'before-gpt5'} for r in d['original_gpt5'])
            existing.add('before-gpt5')
        result=paired(rows,sorted(existing))
        result['libraries']=d.get('builds',{})
        out['todo'][model]=result
    for model,rows in form['models'].items():
        tag='qwen9';libs=form['libraries'][tag]
        result=paired(rows,sorted({r['arm'] for r in rows}))
        result['public']={k:v['after']['checks'] for k,v in libs.items()}
        result['public_errors']={k:v['after']['errors'] for k,v in libs.items()}
        result['library_controls']=form['public']
        out['form'][model]=result
    files=read(FILES)
    identity=read(IDENTITY)
    assert files['control_source']==identity['control_source'] and files['controls']==identity['controls']
    out['files_initial']=file_comparisons(files)
    out['files']=file_comparisons(identity)
    svg=read(SVG)
    out['svg_attributes']={}
    for tag,(model,filename) in DIRECT_SOURCES.items():
        controls=[r for r in read(ROOT/'studies/results'/filename)['models'][model]['rows'] if r['project']=='svg-chart' and r['arm'] in ('direct','human','gpt5-library')]
        candidates=[r for r in svg['rows'] if r['tag']==tag]
        groups=paired(controls+candidates,['direct','human','gpt5-library','planned','fixed','planned-no-new-functions','fixed-no-new-functions'])
        lib=svg['libraries'][tag]
        groups['retained']=lib['retained']
        groups['development_checks']=[len(lib[k]['passed']) for k in ('initial','final')]
        groups['new_input_checks']={k:len(v['passed']) for k,v in lib['unseen'].items()}
        a,b=(set(groups['arms'][k]['passes']) for k in ('planned','fixed'))
        groups.update(planned_only=sorted(a-b),fixed_only=sorted(b-a))
        out['svg_attributes'][model]=groups
    decoded=read(VISIBLE)
    out['visible_choices']={}
    for model,record in decoded['models'].items():
        g=paired(record['rows'],['direct','human','gpt5-library','self','fixed-human','fixed-gpt5-library','fixed-self'])
        traces={}
        for phase in ('old_delivery','new_delivery'):
            traces[phase]={}
            for method,entries in record[phase].items():
                bins=Counter()
                for item in entries:bins[f"{item['step']}/{item['finish']}/"+('visible' if item['visible'] else 'empty')]+=item['count']
                traces[phase][method]=dict(sorted(bins.items()))
        g['delivery']=traces
        changes=read(FUNCTIONS)[model]
        assert set(changes)==set(g['targets'])
        for t,r in changes.items():
            assert r['fixed_passed']==(t in g['arms']['fixed-gpt5-library']['passes'])
            assert r['planned_passed']==(t in g['arms']['gpt5-library']['passes'])
        g['single_function_losses']={t:r for t,r in changes.items()
            if r['fixed_passed'] and not r['planned_passed'] and len(r['fixed_unique'])==len(r['planned_unique'])==1 and not r['changed_lines_by_kind'].get('other')}
        out['visible_choices'][model]=g
    core_profiles=read(CORE_PROFILES)
    out['core_profiles']={}
    for model,r in core_profiles['models'].items():
        rows=r['rows'];profiles=r['profiles']
        names=['direct','human','gpt5-library','fixed-self','unfiltered']
        if profiles['eligible']:names+=['self','fixed-core','projected']
        g=paired(rows,names)
        g['eligible']=len(profiles['eligible']);g['enumerated']=len(profiles['enumerated'])
        g['universal']=sorted(k for k in profiles['default'] if profiles['eligible'] and all(p[k] for p in profiles['eligible']))
        admitted={tuple(sorted(p.items())) for p in profiles['eligible']}
        assert admitted=={tuple(sorted(e['choices'].items())) for e in profiles['enumerated'] if all(e['checks'].values()) and not e['error']}
        selections=read(CHOICES)[model]
        assert selections['seal']==r['seal'] and set(selections['targets'])==set(g['targets'])
        invalid_prior=[]
        for target,plan in selections['targets'].items():
            if plan['before'] is not None:
                inside=tuple(sorted(plan['before'].items())) in admitted
                assert inside==(plan['failed_common_before']==[])
                if not inside:invalid_prior.append(target)
            if plan['model'] is not None:assert tuple(sorted(plan['model'].items())) in admitted
        g['previous_choices_violating_core']=sorted(invalid_prior)
        if profiles['eligible']:
            model_pass=set(g['arms']['self']['passes'])
            fixed=set(g['arms']['fixed-core']['passes'])
            g['planned_only']=sorted(model_pass-fixed)
            g['fixed_only']=sorted(fixed-model_pass)
        old=out['visible_choices'][model]
        for k in ('direct','human','gpt5-library','fixed-self','unfiltered'):
            prev=old['arms']['self' if k=='unfiltered' else k]
            assert g['arms'][k]['passes']==prev['passes'] and g['arms'][k]['observed']==prev['observed']
        out['core_profiles'][model]=g
    reversals=[]
    for r in initial['rows']:
        scores=r['cells'];g,s=scores['gpt5-library'],scores['self']
        if not g or not s or g[0]>=s[0]:continue
        p,m=r['project'],r['model']
        item=dict(model=m,project=p,previous_gpt5=g,previous_self=s)
        if p in ('table','svg-chart') and out['web'].get(p,{}).get('model')==m:
            item['diagnostic']='fixed_library_numbered_examples'
        elif p=='table':
            tags={'deepseek/deepseek-v4-flash':'deepseek-flash','deepseek/deepseek-v4-pro-0813':'deepseek-pro',
                  'qwen/qwen3-coder-30b-a3b-instruct':'qwen','openai/gpt-oss-120b':'oss'}
            filtered=[x for x in menu['rows'] if x['arm']=='corrected-plan' and x['tag']==tags[m]]
            assert len(filtered)==g[1] and sum(x['before'] is True for x in filtered)==g[0]
            item.update(diagnostic='document_listener_closes_context_menu',same_plans_after=sum(x['passed'] for x in filtered),
                        fixed_after=[sum(x['passed'] for x in menu['rows'] if x['tag']==str(i) and x['arm']=='corrected-fixed') for i in range(4)])
        elif p=='todomvc':
            item['diagnostic']='same_functions_with_typed_slots'
        elif p=='form':
            item['diagnostic']='shared_survey_configuration'
        elif p=='duo':
            d=paired(donors['models'][m],['planned','fixed','names'])
            item.update(diagnostic='published_cross_pair_donors',donor_controls=d,covered_features=sum(len(v['owners']) for v in donors['libraries'].values()))
            if m in react['models']:item['self_controls']=paired(react['models'][m],['direct','a','fixed-a','b','fixed-b'])
        new_counts={'gpt5-library':g,'self':s}
        protocol=None
        if p in out['web'] and out['web'][p]['model']==m:
            protocol=out['web'][p]
            new_counts['gpt5-library']=[len(protocol['arms']['gpt5-library']['passes']),protocol['n']]
        if p=='svg-chart' and m in out['svg_attributes']:
            shape=out['svg_attributes'][m]
            new_counts['self']=[len(shape['arms']['planned']['passes']),shape['n']]
        if p=='form' and m in out['form']:
            protocol=out['form'][m]
            new_counts['gpt5-library']=[len(protocol['arms']['gpt5-library']['passes']),protocol['n']]
            accepted=all(protocol['public']['a'].values()) and not protocol['public_errors']['a']
            new_counts['self']=[len(protocol['arms']['self-a']['passes']),protocol['n']] if accepted else None
        if p=='todomvc':
            protocol=out['visible_choices'].get(m,out['todo'][m])
            for name,src in [('gpt5-library','gpt5-library'),('self','self' if m in out['visible_choices'] else 'a')]:
                if src in protocol['arms']:new_counts[name]=[len(protocol['arms'][src]['passes']),protocol['n']]
        if p=='todomvc' and m in out['core_profiles'] and out['core_profiles'][m]['eligible']:
            audited=out['core_profiles'][m]
            new_counts['self']=[len(audited['arms']['self']['passes']),audited['n']]
        assert all(v is None or v[1]==g[1] for v in new_counts.values())
        item['displayed_after']=new_counts
        if protocol:item['configuration_status']=protocol['arms']['gpt5-library']['statuses']
        reversals.append(item)
    displayed=[r['cells']['self'] for r in initial['rows'] if r['cells']['self'] is not None]
    first_distribution={'observed':len(displayed),'zero':sum(k==0 for k,n in displayed),'at_most_one_quarter':sum(4*k<=n for k,n in displayed)}
    return dict(**out,initial_self_distribution=first_distribution,initial_visible_reversals=reversals,round_budget=round_budget(),
                costs={'source_diagnosis':data['cost'],'source_cost_by_model_and_phase':data['cost_by_model_and_phase'],'survey':form['cost'],'file_explorer_interactions':files['cost'],'file_explorer_model_and_phase':files['calls_settled_exposure_micro_usd'],
                       'core_profiles':core_profiles['cost'],'core_profiles_by_model':core_profiles['by_planner'],
                       'visible_choices':decoded['cost'],'visible_choices_by_model_arm':decoded['costs_by_model_and_arm'],
                       'svg_attributes':svg['cost'],'svg_by_builder':svg['cost_by_builder'],
                       'file_entry_identity':identity['cost'],'entry_identity_model_and_phase':identity['calls_settled_exposure_micro_usd']},
                sources={str(p.relative_to(ROOT)):sha(p) for p in SOURCES})


def attach(matrix):
    report=read(OUTPUT)
    initial={(r['model'],r['project']):r['cells'] for r in read(INITIAL)['rows']}

    def publish(model,project,g,mapping,failed=()):
        expected=next((v[1] for v in initial[model,project].values() if v),None)
        if not g['n'] or g['n']!=expected:return
        cache=matrix[model]
        previous=cache.get('source_diagnosis',{}).get(project)
        frozen_group=cache.get('library_capabilities',{}).get(project,{})
        universe=([f'todo-{i:02d}' for i in range(1,9)] if project=='todomvc' else [str(i) for i in range(1,21)])
        if project!='todomvc' and frozen_group.get('targets'):
            universe=[str(t) for t in frozen_group['targets']]
        if set(g['targets'])!=set(universe):raise ValueError(f'Unknown target set for {model} / {project}')
        counts={k:v[0] for k,v in initial[model,project].items() if v}
        markers={}
        for field in ('library_capabilities','extended_targets','component_followup'):
            if project in cache.get(field,{}):
                markers=dict(cache[field][project].get('markers',{}));break
        if previous:
            assert set(previous['targets'])==set(g['targets'])
            counts.update(previous['passed']);markers.update(previous['markers'])
        for method,origin in mapping.items():
            counts[method]=len(g['arms'][origin]['passes'])
            if method!='direct':markers[method]='source-plans' if method!='self' else 'self-sequences'
        for method in failed:
            counts.pop(method,None);markers.pop(method,None)
        cache.setdefault('source_diagnosis',{})[project]=dict(n=g['n'],targets=g['targets'],passed=counts,
             markers=markers,excluded_build_arms=list(failed),source=str(OUTPUT.relative_to(ROOT)))
    for project,g in report['web'].items():publish(g['model'],project,g,{'gpt5-library':'gpt5-library'})
    for model,g in report['todo'].items():
        slots={k:k for k in ('direct','human','gpt5-library') if k in g['arms']}
        if 'a' in g['arms']:slots['self']='a'
        publish(model,'todomvc',g,slots)
    for model,g in report['visible_choices'].items():
        publish(model,'todomvc',g,{'direct':'direct','human':'human','gpt5-library':'gpt5-library','self':'self'})
        group=matrix[model]['source_diagnosis']['todomvc']
        group['markers']={k:'visible-choices' for k in group['passed']}
    for model,g in report['core_profiles'].items():
        if g['eligible']:
            publish(model,'todomvc',g,{'self':'self'})
            matrix[model]['source_diagnosis']['todomvc']['markers']['self']='core-profile'
    for model,g in report['form'].items():
        slots={'direct':'direct','human':'human','gpt5-library':'gpt5-library'}
        accepted=len(g['public']['a'])==5 and all(g['public']['a'].values()) and not g['public_errors']['a']
        if accepted:slots['self']='self-a'
        publish(model,'form',g,slots,[] if accepted else ['self'])

    for model,g in report['svg_attributes'].items():
        publish(model,'svg-chart',g,{'self':'planned'})
    for model,replicas in report['files'].items():
        publish(model,'dom1',replicas['a'],{'self':'planned'})


if __name__=='__main__':
    parser=ArgumentParser(description=__doc__);parser.add_argument('--write',action='store_true')
    parser.add_argument('--ledgers',action='store_true',help='Verify the complete round against local read-only API ledgers')
    args=parser.parse_args();result=reconstruct()
    if args.ledgers:verify_ledgers()
    if args.write:dump(OUTPUT,result)
    assert read(OUTPUT)==result
    print('Verified',len(result['initial_visible_reversals']),'initial, visible GPT-5 / Self reversals.')
