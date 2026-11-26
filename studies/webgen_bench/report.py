"""Recompute the six-site functional comparison and the paired table diagnostics."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
from pathlib import Path

from studies import ledger_read
from studies.study_io import ROOT, dump, read, sha

HERE = Path(__file__).resolve().parent
PILOT = HERE / 'functional_pilot'
RESULT = ROOT / 'studies/results/webgen-functional-20261126.json'
TABLE = ROOT / 'studies/webbench/table'
ARMS = ('direct', 'human', 'gpt5-library', 'self')
TAGS = ('gemma', 'qwen9', 'deepseek-flash')
STAGES = {
    'schema': PILOT,
    'native': PILOT / 'native_plans',
    'mounted': PILOT / 'mounted_components',
    'functions': PILOT / 'component_functions',
    'binding': PILOT / 'function_binding',
}
TABLE_STAGES = {
    'installers': TABLE / 'interaction_modules',
    'state_contract': TABLE / 'interaction_modules/state_contract',
    'module_paths': TABLE / 'interaction_modules/module_paths',
    'reducers': TABLE / 'state_reducers',
    'typed_events': TABLE / 'state_reducers/typed_events',
    'interaction_repairs': TABLE / 'selection_binding/interaction_repairs',
}
POINTS = {'YES': 1, 'PARTIAL': .5, 'NO': 0}
CONTROLS = PILOT / 'judge_controls/result.json'
SECOND_REPLAY = PILOT / 'judge_controls/recovery/result.json'
SECOND_COMPLETE = PILOT / 'judge_controls/remaining/result.json'
SOURCES = [HERE/'protocol.json', CONTROLS, SECOND_REPLAY, SECOND_COMPLETE, *(p/'result.json' for p in TABLE_STAGES.values()),
           *(p/name for p in STAGES.values() for name in ('candidates.json','judgments.json'))]
LEDGERS = {
    'table/initial':'table-interaction-modules','table/contract':'table-state-contract',
    'table/reducers':'table-pure-state','table/typed':'table-typed-events',
    'webgen/initial_generation':'webgen-sites','webgen/initial_judge':'webgen-browser-judge',
    'webgen/native_generation':'webgen-native-plans','webgen/native_judge':'webgen-native-judge',
    'webgen/mounted_generation':'webgen-mounted-components','webgen/mounted_judge':'webgen-mounted-judge',
    'webgen/function_generation':'webgen-component-functions','webgen/function_judge':'webgen-function-judge',
    'webgen/judge_controls':'webgen-judge-controls',
    'webgen/second_recovery':'webgen-second-rater-recovery','webgen/secondary_remaining':'webgen-secondary-remaining',
    'webgen/output_binding':'webgen-function-binding','webgen/binding_judge':'webgen-binding-judge',
    'table/interaction_repairs':'table-interaction-repair',
}

def points(row):
    if row['status']=='judged':
        return POINTS[row['verdict']]
    if row['status']=='start_failed':
        assert row['verdict'] is None
        return 0
    assert row['status'] in ('missing','build_failed') and row['verdict'] is None
    return None

def matched(rows):
    by_arm = {a:{} for a in ARMS}
    for r in rows:
        key = r['site']+'/'+str(r['check'])
        group = by_arm[r['arm']]
        if key in group:raise ValueError(f'Duplicate case {key} in {r["arm"]}')
        group[key] = r
    universe = set(by_arm['direct'])
    assert all(set(g)==universe for g in by_arm.values())
    known = {a:{k:points(r) for k,r in g.items() if points(r) is not None} for a,g in by_arm.items()}
    evaluated = {a:g for a,g in known.items() if g}
    common = sorted(set.intersection(*(set(g) for g in evaluated.values()))) if 'direct' in evaluated else []
    totals = {}
    for arm, group in by_arm.items():
        rows_common = [group[key] for key in common] if arm in evaluated else []
        totals[arm] = {
            'observed':len(known[arm]), 'status':dict(sorted(Counter(r['status'] for r in group.values()).items())),
            'verdicts':dict(sorted(Counter(r['verdict'] for r in rows_common if r['status']=='judged').items())),
            'start_failed_in_common':sum(r['status']=='start_failed' for r in rows_common),
        }
        if rows_common:
            totals[arm]['points'] = sum(points(r) for r in rows_common)
    return dict(registered=len(universe), n=len(common), targets=common, methods=totals)

def table_summary(data):
    all_targets=set(range(1,21))
    rows=defaultdict(dict)
    for row in data['rows']:
        task=row['task'];arm=row['arm']
        assert task in all_targets and task not in rows[arm]
        if row['passed'] is not None:assert type(row['passed']) is bool
        rows[arm][task]=row['passed']
    output={}
    for arm,targets in rows.items():
        assert set(targets)==all_targets
        output[arm]=dict(observed=sum(x is not None for x in targets.values()),
                         passes=sorted(t for t,v in targets.items() if v))
    libs={}
    for rep,library in data['libraries'].items():
        lib={'status':library['status'],'checks':library['checks']}
        planned, fixed = ('self-'+rep, 'fixed-'+rep)
        if lib['status']=='valid':
            assert planned in rows and fixed in rows
            joint={t for t in all_targets if all(rows[k][t] is not None for k in (planned,fixed,'direct'))}
            lib['matched']=sorted(joint)
            lib['planned_only']=sorted(t for t in joint if rows[planned][t] and not rows[fixed][t])
            lib['fixed_only']=sorted(t for t in joint if rows[fixed][t] and not rows[planned][t])
        libs[rep]=lib
    return dict(libraries=libs,arms=output)

def compare_judges(native,controls):
    rows={(r['model'],r['site'],r['check'],r['arm']):r for r in native}
    pairs=Counter()
    identifiers={(r['model'],r['site'],r['check'],r['arm']) for r in controls['second']}
    assert len(identifiers)==len(controls['second'])==3*6*4
    eligible=sum(rows[key]['status']=='judged' for key in identifiers)
    for second in controls['second']:
        if second['status']!='judged':continue
        first=rows[second['model'],second['site'],second['check'],second['arm']]
        if first['status']=='judged':pairs[first['verdict']+' / '+second['verdict']]+=1
    blanks=controls['blank']
    assert len({(r['site'],r['check']) for r in blanks})==43
    return dict(blank_status=dict(Counter(r['status'] for r in blanks)),
                blank_verdicts=dict(Counter(r['verdict'] for r in blanks if r['status']=='judged')),
                primary_partial=controls['controls']['partial']['verdict'],
                second_model=controls['controls']['second'],qualified=controls['controls']['qualified'],
                second_status=dict(Counter(r['status'] for r in controls['second'])),
                eligible=eligible,unpaired_eligible=eligible-sum(pairs.values()),paired=sum(pairs.values()),exact=sum(n for k,n in pairs.items() if len(set(k.split(' / ')))==1),
                pairs=dict(sorted(pairs.items())))

def accounting():
    stages={}
    total=Counter()
    for name,folder in LEDGERS.items():
        file=ROOT/'artifacts'/(folder+'-20261126pm')/'budget.sqlite3'
        groups=defaultdict(Counter)
        for r in ledger_read.calls(file):
            kind=r['purpose'].split('/')[0]
            if kind=='judge':kind += '/'+r['purpose'].split('/')[1]
            group=groups[r['model']+' / '+kind]
            for target in (group,total):
                target['calls']+=1
                target['unsettled_calls']+=int(r['actual'] is None)
                target['settled_micro_usd']+=r['actual'] or 0
                target['exposure_micro_usd']+=r['reserved'] if r['actual'] is None else r['actual']
        stages[name]=dict(totals=ledger_read.totals(file),by_model_and_phase=dict(sorted(groups.items())))
    return dict(total=dict(total),stages=stages)

def reconstruct(published_costs=None):
    spec=read(HERE/'protocol.json')
    allsites={s for sites in spec['pilot_sites'].values() for s in sites}
    assert len(allsites)==6
    stages={}
    for name,folder in STAGES.items():
        cand=read(folder/'candidates.json');judges=read(folder/'judgments.json')
        assert judges['candidates']==sha(folder/'candidates.json') and judges['calibration']['qualified']
        if name!='schema':
            assert cand['previous']==sha(STAGES[list(STAGES)[list(STAGES).index(name)-1]]/'candidates.json')
        assert set(cand['rows'])==set(TAGS)
        groups={}
        for t in TAGS:
            sites=cand['rows'][t]
            assert set(sites)==allsites and all(set(v)==set(ARMS) for v in sites.values())
            rows=[r for r in judges['rows'] if r['model']==t]
            group=matched(rows)
            assert group['registered']==43 and len(rows)==43*len(ARMS)
            for r in rows:
                status=sites[r['site']][r['arm']]['status']
                assert (status=='valid' and r['status'] in ('judged','missing') or
                        status=='invalid' and r['status']=='start_failed' or
                        status in ('missing','build_failed') and r['status']==status)
            group['sites']={s:matched([r for r in rows if r['site']==s]) for s in sorted(allsites)}
            working_direct={(r['site'],r['check']) for r in rows if r['arm']=='direct' and r['status']=='judged'}
            comparable=matched([r for r in rows if (r['site'],r['check']) in working_direct])
            group['on_judged_direct_pages']={'n':comparable['n'],'targets':comparable['targets'],
                                             'points':{a:v['points'] for a,v in comparable['methods'].items() if 'points' in v}}
            group['delivered_sites']={a:sum(s[a]['status']=='valid' for s in sites.values()) for a in ARMS}
            groups[t]=group
        stages[name]=dict(models=groups,route=judges['route'],
                          preparation={k:v['status'] for k,v in cand['libraries'].items()})
    # The independent rater used the shorter-plan pages. Match their actual bytes
    # to the final displayed pages before attributing agreement to Panel C.
    rated_pages = read(STAGES['native'] / 'candidates.json')['rows']
    final_pages = read(STAGES['binding'] / 'candidates.json')['rows']
    for model, sites in final_pages.items():
        for site, methods in sites.items():
            for method, final_page in methods.items():
                rated = rated_pages[model][site][method]
                assert rated['status'] == final_page['status']
                if rated['status'] == 'valid':
                    assert rated['sha256'] == final_page['sha256']
    primary_rows = read(STAGES['binding'] / 'judgments.json')['rows']
    for first,second in ((CONTROLS,SECOND_REPLAY),(SECOND_REPLAY,SECOND_COMPLETE)):
        original,latest=read(first),read(second)
        assert latest['previous']==sha(first) and latest['subset']==original['subset']
        def known(data):
            return {(r['model'],r['site'],r['check'],r['arm']):r['verdict'] for r in data['second'] if r['status']=='judged'}
        assert known(original).items()<=known(latest).items()
    return dict(dataset=spec['dataset'],registered_models=dict(zip(TAGS,spec['models'],strict=True)),
                pilot_sites=spec['pilot_sites'],metric=POINTS,primary_stage='binding',stages=stages,
                judge_controls=compare_judges(primary_rows,read(SECOND_COMPLETE)),
                secondary_recovery=compare_judges(primary_rows,read(SECOND_REPLAY)),
                initial_controls=compare_judges(primary_rows,read(CONTROLS)),
                table={name:table_summary(read(folder/'result.json')) for name,folder in TABLE_STAGES.items()},
                budget=accounting() if published_costs is None else published_costs,sources={str(p.relative_to(ROOT)):sha(p) for p in SOURCES})

if __name__=='__main__':
    parser=ArgumentParser(description=__doc__)
    parser.add_argument('--write',action='store_true')
    parser.add_argument('--portable', action='store_true', help='Verify results against versioned per-check and stage receipts, without local ledgers.')
    args=parser.parse_args()
    if args.portable and args.write:parser.error('Use --write with the actual ledgers')
    costs = read(RESULT)['budget'] if args.portable else None
    if costs:
        artifacts = {
            'table/initial':TABLE_STAGES['installers']/'result.json','table/contract':TABLE_STAGES['state_contract']/'result.json',
            'table/reducers':TABLE_STAGES['reducers']/'result.json','table/typed':TABLE_STAGES['typed_events']/'result.json',
            'table/interaction_repairs':TABLE_STAGES['interaction_repairs']/'result.json','webgen/judge_controls':CONTROLS,'webgen/second_recovery':SECOND_REPLAY,'webgen/secondary_remaining':SECOND_COMPLETE,
        }
        for stage,prep,score in [('schema','initial_generation','initial_judge'),('native','native_generation','native_judge'),
                           ('mounted','mounted_generation','mounted_judge'),('functions','function_generation','function_judge'),
                           ('binding','output_binding','binding_judge')]:
            artifacts['webgen/'+prep] = STAGES[stage]/'candidates.json'
            artifacts['webgen/'+score] = STAGES[stage]/'judgments.json'
        for name,path in artifacts.items():
            assert costs['stages'][name]['totals'] == read(path)['cost']
        totals = Counter()
        for stage in costs['stages'].values():
            groups=Counter()
            for group in stage['by_model_and_phase'].values():groups.update(group)
            raw=stage['totals']
            assert groups['calls']==raw['calls'] and groups['unsettled_calls']==raw['unsettled_calls']
            assert groups['settled_micro_usd']==round(raw['settled_usd']*1e6)
            assert groups['exposure_micro_usd']==round(raw['exposure_usd']*1e6)
            totals.update(groups)
        assert totals==costs['total']
    result=reconstruct(costs)
    if args.write:dump(RESULT,result)
    assert read(RESULT)==result, 'Published functional report differs from source records'
    print('Verified 3 backbones × 4 workflows × 43 checks in each generation stage.')
