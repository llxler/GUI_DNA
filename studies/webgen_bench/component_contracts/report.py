"""Reconstruct the two website cohorts and the paired TodoMVC state-example study."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
from pathlib import Path

from studies.public_library_transfer.source_diagnosis import report as previous
from studies.study_io import ROOT, dump, read, sha
from studies.webgen_bench import report as pilot

HERE = Path(__file__).resolve().parent
TYPED = HERE/'typed_inputs'
FLASH = HERE.parent/'heldout_transfer'
NATIVE_HTML = FLASH/'incomplete_html'
NATIVE_TRANSPORT = NATIVE_HTML/'transport.json'
TODO = ROOT/'studies/public_library_transfer/compact_todomvc/state_examples/result.json'
RESULT = ROOT/'studies/results/component-validation-20261127.json'
TABLE = ROOT/'studies/webbench/table/action_sequences/single_slot'
SELECTION = TABLE.parent/'selection_mode'
ACCOUNTING = HERE/'accounting.json'
DEFAULTS = TODO.with_name('default-result.json')
EVIDENCE = TODO.with_name('evidence-result.json')
DECISIONS = TODO.with_name('evidence-decisions.json')
STAGES = (
    ('components', HERE/'candidates.json', HERE/'judgments.json'),
    ('function_bodies', HERE/'function_bodies/candidates.json', HERE/'function_bodies/judgments.json'),
    ('named_inputs', TYPED/'candidates.json', TYPED/'judgments.json'),
    ('fragment_replay', TYPED/'replay-candidates.json', TYPED/'replay-judgments.json'),
    ('local_edits', TYPED/'edit-candidates.json', TYPED/'edit-judgments.json'),
    ('dom_inputs', TYPED/'dom-candidates.json', TYPED/'dom-judgments.json'),
    ('native_visibility', TYPED/'visibility-candidates.json', TYPED/'visibility-judgments.json'),
)
RECEIPTS = (TODO,DEFAULTS,EVIDENCE,DECISIONS,previous.TRIAL,TABLE/'result.json',TABLE/'heldout-result.json',TABLE/'interrupted.json',ACCOUNTING,pilot.STAGES['binding']/'judgments.json',pilot.STAGES['binding']/'candidates.json',
            FLASH/'candidates.json',FLASH/'judgments.json',FLASH/'secondary.json',FLASH/'secondary-completion.json',
            SELECTION/'result.json',SELECTION/'validation.json',SELECTION/'function-hashes.json',NATIVE_HTML/'candidates.json',NATIVE_HTML/'judgments.json',
            NATIVE_HTML/'functional-confirmation.json',NATIVE_HTML/'browser.json',NATIVE_TRANSPORT,
            *(f for _,c,j in STAGES for f in (c,j)))


def relative(path):
    return str(path.relative_to(ROOT))


def website_groups():
    basec = pilot.STAGES['binding']/'candidates.json'
    basej = pilot.STAGES['binding']/'judgments.json'
    initial = read(basec)['rows']
    controls = ('direct','human','gpt5-library')
    registered = read(pilot.RESULT)
    old_cases = {(r['model'],r['site'],r['check'],r['arm']):r for r in read(basej)['rows']}
    before_c,before_j = basec,basej
    w = {}
    origins = {}
    basejudge = read(basej)['route']['model']
    for stage,c,j in STAGES:
        candidates,judgments = read(c),read(j)
        assert candidates['previous'] == sha(before_c)
        assert judgments['original_judgments'] == sha(before_j) and judgments['candidates'] == sha(c)
        route = judgments['route']
        assert route['primary']['model']==basejudge and route['primary']['qualified']
        for tag,sites in initial.items():
            for site,arms in sites.items():
                new = candidates['development'][tag][site]
                assert all(arms[a]==new[a] for a in controls)
        before = read(before_c)
        for tag in pilot.TAGS:
            for batch in ('development','holdout'):
                sites = candidates[batch].get(tag,{})
                if not sites:continue
                if stage=='components':
                    origins[tag,batch,'self']=(c,j)
                    continue
                for s,arms in sites.items():
                    assert all(arms[a]==before[batch][tag][s][a] for a in controls)
                if any(before[batch][tag][s]['self']!=arms['self'] for s,arms in sites.items()):
                    origins[tag,batch,'self']=(c,j)
        w[stage]={}
        for tag,lib in candidates['libraries'].items():
            checks=lib.get('final',{}).get('checks',{})
            if not isinstance(checks,dict):checks={}
            w[stage][tag]={'status':lib['status'],'public':checks,'changed':lib.get('changed',[])}
            if 'reason' in lib:w[stage][tag]['reason']=lib['reason']
            empty=lib.get('empty_replacements',lib.get('empty',{}))
            if empty:w[stage][tag]['empty']=empty['checks']
        before_c,before_j=c,j
    extra = read(FLASH/'judgments.json')
    assert extra['candidates']==sha(FLASH/'candidates.json') and extra['route']==route
    final_rows = judgments['rows']+extra['rows']
    for r in judgments['rows']:
        if r['batch']=='development' and (r['arm']!='self' or r['model']=='deepseek-flash'):
            old=old_cases[r['model'],r['site'],r['check'],r['arm']]
            assert all(r.get(k)==old.get(k) for k in ('status','verdict','source'))
    groups={}
    for batch in ('development','holdout'):
        groups[batch]={}
        for tag, model in registered['registered_models'].items():
            rows=[r for r in final_rows if r['batch']==batch and r['model']==tag]
            group=pilot.matched(rows)
            sites=sorted({r['site'] for r in rows})
            sources={}
            for arm in pilot.ARMS:
                if batch=='holdout' and tag=='deepseek-flash':c,j=FLASH/'candidates.json',FLASH/'judgments.json'
                elif batch=='development' and (arm!='self' or tag=='deepseek-flash'):c,j=basec,basej
                elif arm=='self':c,j=origins[tag,batch,'self']
                else:_,c,j=STAGES[0]
                evidence=read(j)['rows']
                expected={(r['site'],r['check']):(r['status'],r['verdict'],r.get('source')) for r in rows if r['arm']==arm}
                actual={(r['site'],r['check']):(r['status'],r['verdict'],r.get('source')) for r in evidence if r['arm']==arm and r['model']==tag and r.get('batch',batch)==batch}
                assert expected==actual
                sources[arm]=dict(candidates=relative(c),judgments=relative(j))
            by_site={}
            for site in sites:
                items=pilot.matched([r for r in rows if r['site']==site])
                by_site[site]={'n':items['n'],'points':{a:v['points'] for a,v in items['methods'].items() if 'points' in v}}
            observed_arms=[a for a,record in group['methods'].items() if 'points' in record]
            comparable=set(group['targets'])
            for a in observed_arms:
                comparable &= {r['site']+'/'+str(r['check']) for r in rows if r['arm']==a and r['status']=='judged'}
            runnable={a:sum(pilot.POINTS[r['verdict']] for r in rows if r['arm']==a and r['site']+'/'+str(r['check']) in comparable)
                      for a in observed_arms}
            groups[batch][model]=group|{'sites':sites,'sources':sources,'by_site':by_site,
                                        'jointly_runnable':{'targets':sorted(comparable),'n':len(comparable),'points':runnable}}
    development = groups['development']
    holdout = groups['holdout']
    for model in development:
        assert len(development[model]['sites'])==6 and len(holdout[model]['sites'])==3
        assert set(development[model]['sites']).isdisjoint(holdout[model]['sites'])
        assert development[model]['registered']==43 and holdout[model]['registered']==21
    for cohort in groups.values():
        assert len({tuple(g['sites']) for g in cohort.values()})==1
    primary=dict(cohorts=groups,admission=w,judge=basejudge,official=route['official'],weights=pilot.POINTS)
    return primary,final_rows


def second_agreement(final_rows):
    first_second=read(FLASH/'secondary.json')
    second=read(FLASH/'secondary-completion.json')
    assert len(second['rows'])==39 and second['previous']==sha(FLASH/'secondary.json')
    assert second['subset']==first_second['subset'] and second['calibration']==first_second['calibration']
    def identity(row):
        return tuple(row[k] for k in ('batch','model','site','check','arm'))

    original = {identity(row): row for row in first_second['rows']}
    assert len(original) == len(second['rows'])
    assert {identity(row) for row in second['rows']} == set(original)
    for r in second['rows']:
        old = original[identity(r)]
        assert r['page'] == old['page']
        if old['status'] == 'judged':
            assert r['reused'] and r['verdict'] == old['verdict'] and r['receipt'] == old['receipt']
    final = {identity(r):r for r in final_rows}
    assert len(final)==len(final_rows)
    agreement={}
    for batch in ('development','holdout'):
        subset=[r for r in second['rows'] if r['batch']==batch]
        for r in subset:
            key=identity(r)
            assert r['check']==second['subset'][r['site']] and r['primary']==final[key]['verdict']
        pairs=[r for r in subset if r['status']==r['primary_status']=='judged']
        differences=[pilot.POINTS[r['verdict']]-pilot.POINTS[r['primary']] for r in pairs]
        agreement[batch]=dict(scheduled=len(subset),runnable=sum(r['page_status']=='valid' for r in subset),paired=len(pairs),
                              exact=sum(v==0 for v in differences),second_higher=sum(v>0 for v in differences),
                              second_lower=sum(v<0 for v in differences),both_yes=sum(r['primary']==r['verdict']=='YES' for r in pairs))
    return dict(model=second['model'],qualified=second['qualified'],paced_endpoint_qualified=second['endpoint_qualified'],
                cohorts=agreement,controls={k:v['verdict'] for k,v in second['calibration'].items()})


def native_direct_scores(web, rows, judgment_file='judgments.json'):
    """Replace only registered start failures and compare exact IDs even when judgments are unavailable."""
    candidates = read(NATIVE_HTML/'candidates.json')
    judged = read(NATIVE_HTML/judgment_file)
    browser = read(NATIVE_HTML/'browser.json')
    assert judged['candidates'] == sha(NATIVE_HTML/'candidates.json') and judged['model'] == web['judge']
    assert browser['candidates'] == judged['candidates']
    output = {}
    for batch, record in candidates['records'].items():
        group = web['cohorts'][batch]['qwen/qwen3.5-9b']
        site = record['site']
        sample = [r for r in rows if r['batch'] == batch and r['model'] == 'qwen9' and r['arm'] == 'direct']
        failed = {(r['site'], r['check']) for r in sample if r['status'] == 'start_failed'}
        graded = [r for r in judged['rows'] if r['batch'] == batch]
        assert len(graded) == len(failed) and {(r['site'], r['check']) for r in graded} == failed
        assert all(r['site'] == site for r in graded)
        observed = {r['check'] for r in graded if r['status'] == 'judged'}
        points = sum(pilot.POINTS[r['verdict']] for r in graded if r['check'] in observed)
        missing = len(graded) - len(observed)
        paired = [r for r in rows if r['batch'] == batch and r['model'] == 'qwen9' and r['arm'] == 'self'
                  and (r['site'] != site or r['check'] in observed)]
        assert len(paired) == group['n'] - missing and all(r['status'] == 'judged' for r in paired)
        direct = group['methods']['direct']['points'] + points
        output[batch] = dict(site=site, original=group['methods']['direct']['points'], scheduled=len(graded),
                             observed=len(observed), new_site_points=points, matched_n=len(paired),
                             direct=direct, self=sum(pilot.POINTS[r['verdict']] for r in paired),
                             direct_bounds=[direct, direct+missing], full_n=group['n'],
                             browser_first_reply=browser['observations'][batch][0])
    return output


def todo_groups():
    original=read(previous.TRIAL)['todomvc']
    data=read(TODO)
    defaults=read(DEFAULTS)
    deployments=read(EVIDENCE)
    assert defaults['prior']==deployments['prior']==sha(TODO)
    assert read(DECISIONS)['seal']==deployments['seal']
    results={}
    for model,g in data['models'].items():
        rows=g['rows']
        names=sorted({r['arm'] for r in rows})
        primary=['direct','human','gpt5-library','a']
        main=previous.paired(rows,primary)
        diagnostics={a:previous.paired(rows,[a]) for a in names}
        for original_arm,arm in [('direct','direct'),('human','human'),('gpt5-library','gpt5-library'),
                                 ('a','original-a'),('b','original-b'),('fixed-a','original-fixed-a'),('fixed-b','original-fixed-b')]:
            old=previous.arm(original[model]['rows'],original_arm)
            replay=previous.arm(rows,arm)
            assert set(old)==set(replay)
            for t,r in old.items():
                assert r.get('files_sha256')==replay[t].get('files_sha256') and r['status']==replay[t]['status']
        replicas={}
        for r,lib in g['replicas'].items():
            assert lib['status']==g['libraries'][r] and set(lib['initial'])<=set(lib['public'])
            measures={}
            for a in (r,'original-'+r,'fixed-'+r,'original-fixed-'+r,'old-choice-'+r,'envelope-'+r):
                if a in diagnostics:
                    arm=diagnostics[a]['arms'][a]
                    measures[a]=dict(passes=arm['passes'],n=diagnostics[a]['n'])
            joint=previous.paired(rows,[r,'fixed-'+r])
            planned=set(joint['arms'][r]['passes'])
            fixed=set(joint['arms']['fixed-'+r]['passes'])
            replicas[r]=dict(status=lib['status'],changed=lib['changed'],public_before=lib['initial'],public_after=lib['public'],
                             unseen=lib['unseen'],measurements=measures,planned_only=sorted(planned-fixed),
                             fixed_only=sorted(fixed-planned),matched=joint['targets'])
        strict=defaults['models'][model]
        new=deployments['models'][model]
        for a in ('direct','human','gpt5-library','fixed-a','fixed-b'):
            assert previous.arm(new['rows'],a)==previous.arm(strict['rows'],a)==previous.arm(rows,a)
        newer=previous.paired(new['rows'],primary)
        for rep,lib in replicas.items():
            followup=previous.paired(new['rows'],[rep,'fixed-'+rep])
            plan=set(followup['arms'][rep]['passes']);fixed=set(followup['arms']['fixed-'+rep]['passes'])
            lib['default_policy']=dict(n=followup['n'],passes=sorted(plan),fixed=sorted(fixed),planned_only=sorted(plan-fixed),
                  fixed_only=sorted(fixed-plan),counterfactual=new['counterfactual'][rep],
                  decisions=new['choices'][rep])
        results[model]=dict(state_examples=main,uncited_defaults=previous.paired(strict['rows'],primary),primary=newer,replicas=replicas)
    return results


# The named-input evaluator writes cumulative costs at both seals on one ledger.
# Only the final seal for that ledger contributes to the round total.
def costs():
    receipts={'components_generation':(STAGES[0][1],'cost'),'components_judge':(STAGES[0][2],'cost'),
              'bodies_generation':(STAGES[1][1],'cost'),'bodies_judge':(STAGES[1][2],'cost'),
              'typed_generation':(STAGES[2][1],'cost'),'typed_judge':(STAGES[3][2],'cumulative_stage_cost'),
              'edits_generation':(STAGES[4][1],'cost'),'edits_judge':(STAGES[4][2],'cost'),
              'dom_generation':(STAGES[5][1],'cost'),'dom_judge':(STAGES[5][2],'cost'),
              'visibility_generation':(STAGES[6][1],'cost'),'visibility_judge':(STAGES[6][2],'cost'),'native_html_judge':(NATIVE_HTML/'judgments.json','cost'),
              'html_confirmation':(NATIVE_HTML/'functional-confirmation.json','cost'),
              'flash_generation':(FLASH/'candidates.json','cost'),'flash_judge':(FLASH/'judgments.json','cost'),'secondary_judge':(FLASH/'secondary.json','cost'),'paced_judge':(FLASH/'secondary-completion.json','cost'),
              'todo_generation':(TODO,'cost'),'todo_defaults':(DEFAULTS,'cost'),'todo_evidence':(EVIDENCE,'cost'),'table_generation':(TABLE/'result.json','cost'),
              'initial_table_generation':(TABLE/'interrupted.json','cost'),'selection_generation':(SELECTION/'result.json','cost')}
    phases={k:read(f)[field] for k,(f,field) in receipts.items()}
    counts=Counter()
    for g in phases.values():
        counts.update(calls=g['calls'],unsettled_calls=g['unsettled_calls'],settled_micro_usd=round(g['settled_usd']*1e6),
                      exposure_micro_usd=round(g['exposure_usd']*1e6))
    # Table construction shares the website generation allocation. TodoMVC has
    # its own allocation for all three phases, including both planning stages.
    caps = {'generation': 1_600_000, 'judge': 5_750_000, 'todo': 650_000, 'confirmation': 500_000}
    exposure = Counter()
    for stage, phase in phases.items():
        bucket = 'todo' if stage.startswith('todo_') else stage.rsplit('_', 1)[-1]
        exposure[bucket] += round(phase['exposure_usd'] * 1e6)
    assert set(exposure) == set(caps)
    assert all(exposure[bucket] <= limit for bucket, limit in caps.items())
    assert sum(exposure.values()) == counts['exposure_micro_usd']
    assert counts['exposure_micro_usd'] <= 8_000_000
    detailed=read(ACCOUNTING)
    assert set(detailed)==set(phases)
    for stage,groups in detailed.items():
        sums=Counter()
        for g in groups.values():sums.update(g)
        assert sums['calls']==phases[stage]['calls'] and sums['unsettled_calls']==phases[stage]['unsettled_calls']
        for prop in ('exposure','settled'):
            assert sums[prop+'_micro_usd']==round(phases[stage][prop+'_usd']*1e6)
    return dict(phases=phases,by_model_and_phase=detailed,total=dict(counts))


LEDGERS = {
    'components_generation':'webgen-component-contracts','components_judge':'webgen-contract-judge',
    'bodies_generation':'webgen-function-bodies','bodies_judge':'webgen-body-judge',
    'typed_generation':'webgen-typed-inputs','typed_judge':'webgen-typed-judge',
    'edits_generation':'webgen-local-edits','edits_judge':'webgen-edits-judge',
    'dom_generation':'webgen-dom-inputs','dom_judge':'webgen-dom-judge',
    'visibility_generation':'webgen-visibility','visibility_judge':'webgen-visibility-judge',
    'flash_generation':'webgen-flash-transfer','flash_judge':'webgen-flash-judge','secondary_judge':'webgen-holdout-second','paced_judge':'webgen-paced-second',
    'todo_generation':'todo-state-examples','todo_defaults':'todo-frozen-defaults','todo_evidence':'todo-evidence-choices','table_generation':'table-single-slot','initial_table_generation':'table-action-sequences',
    'selection_generation':'table-selection-mode',
    'native_html_judge':'webgen-native-html',
    'html_confirmation':'webgen-html-confirmation',
}


def accounting():
    from studies import ledger_read
    stages={}
    for stage,name in LEDGERS.items():
        db=ROOT/'artifacts'/(name+'-20261127')/'budget.sqlite3'
        groups=defaultdict(Counter)
        for row in ledger_read.calls(db):
            parts=row['purpose'].split('/')
            phase=parts[0]
            if phase=='plan' and 'direct' in parts:phase='direct'
            by=groups[row['model']+' / '+phase]
            by.update(calls=1,unsettled_calls=int(row['actual'] is None),settled_micro_usd=row['actual'] or 0,
                      exposure_micro_usd=row['reserved'] if row['actual'] is None else row['actual'])
        stages[stage]=dict(sorted(groups.items()))
    return stages


def native_transport():
    root = ROOT/'artifacts/webgen-native-html-20261127'
    registrations = root/'price-registration.json', root/'judge-registration.json'
    pricing, run = map(read, registrations)
    scored = read(NATIVE_HTML/'judgments.json')
    assert scored['registration'] == sha(registrations[1]) and scored['model'] == pricing['model']
    providers = Counter()
    for file in root.rglob('settled.json'):
        response = file.with_name('response.json')
        assert read(file)['sha256'] == sha(response)
        providers[read(response).get('provider') or 'unreported'] += 1
    return dict(registrations=[sha(p) for p in registrations], protocol=pricing['protocol'], source=pricing['source'],
                candidates=pricing['candidates'], cap_usd=run['cap'], earlier_judge_exposure=run['previous_exposure'],
                priced_endpoints=[{'provider':e['provider_name'],'context_tokens':e['context_length'],
                                  'prompt_per_token':e['pricing']['prompt'],'completion_per_token':e['pricing']['completion']}
                                  for e in pricing['endpoints']], settled_by_provider=dict(providers))


def table_groups():
    source=TABLE/'result.json'
    official=read(source)
    trace=read(TABLE/'heldout-result.json')
    assert trace['official']==sha(source) and trace['cases']==sha(TABLE/'heldout.json')
    result=pilot.table_summary(official)
    result['release_checks']=trace['calibrated']
    result['action_sequences']={}
    for arm,observations in trace['rows'].items():
        result['action_sequences'][arm]={}
        for name,record in observations.items():
            if record['status']=='observed':
                first=next((s['action'] for s in record['steps'] if not s['passed']),None)
                assert (first is None)==record['passed']
                result['action_sequences'][arm][name]=dict(passed=record['passed'],first_failure=first)
            else:result['action_sequences'][arm][name]=dict(status=record['status'])
    revised = read(SELECTION/'result.json')
    controls = read(SELECTION/'validation.json')
    fingerprints = read(SELECTION/'function-hashes.json')
    assert controls['score'] == sha(SELECTION/'result.json')
    assert controls['validation'] == sha(SELECTION/'validate.py')
    assert revised['direct_source'] == official['direct_source']
    methods = {}
    for rep, lib in revised['libraries'].items():
        assert lib['origin'] == fingerprints['before'][rep]['library_sha256']
        before_hashes = fingerprints['before'][rep]['functions_sha256']
        after_hashes = fingerprints['after'][rep]['functions_sha256']
        assert {k for k in before_hashes if before_hashes[k] != after_hashes[k]} == set(lib['changed'])
        history = lib['history']
        first = {k for k,v in history[0]['checks'].items() if v}
        final = {k for k,v in history[-1]['checks'].items() if v} if lib['changed'] else first
        assert first <= final
        methods[rep] = lib | {'checks': sorted(final)}
    replay = pilot.table_summary(revised | {'libraries': methods})
    for rep, lib in methods.items():
        replay['libraries'][rep]['changed'] = lib['changed']
        assert replay['libraries'][rep]['matched'] == result['libraries'][rep]['matched']
    assert replay['arms']['direct'] == result['arms']['direct']
    replay['calibrated'] = controls['calibrated']
    initial = fingerprints['before']
    replay['identical_initial_handlers'] = sorted(k for k,v in initial['a']['functions_sha256'].items()
                                                 if v == initial['b']['functions_sha256'][k])
    replay['sequences'] = {label: {case: obs['passed'] for case, obs in cases.items()}
                           for label,cases in controls['observations'].items()}
    result['same_plans_repaired_handlers'] = replay
    return result


def reconstruct():
    web,rows=website_groups()
    web['secondary']=second_agreement(rows)
    web['native_direct']=native_direct_scores(web,rows,'functional-confirmation.json')
    transport = read(NATIVE_TRANSPORT)
    native = read(NATIVE_HTML/'judgments.json')
    confirmation = read(NATIVE_HTML/'functional-confirmation.json')
    assert confirmation['earlier_judgments'] == sha(NATIVE_HTML/'judgments.json') and native['cost']['calls'] == 0
    assert all(r['status'] == 'missing' for r in native['rows'])
    assert {(r['site'], r['check']) for r in native['rows']} == {(r['site'],r['check']) for r in confirmation['rows']}
    assert round((confirmation['previous_exposure_usd'] + confirmation['cost']['cap_usd']) * 1e6) <= 8_000_000
    assert transport['registrations'][1] == native['registration'] and transport['candidates'] == native['candidates']
    assert transport['source'] == sha(NATIVE_HTML/'route.py') and transport['protocol'] == sha(NATIVE_HTML/'PRICE.md')
    assert round((transport['earlier_judge_exposure'] + transport['cap_usd']) * 1e6) <= 5_750_000
    assert sum(transport['settled_by_provider'].values()) == native['cost']['calls'] - native['cost']['unsettled_calls']
    return dict(webgen=web,todomvc=todo_groups(),table=table_groups(),budget=costs(),
                sources={relative(p):sha(p) for p in RECEIPTS})


def matrix_group(group,judge):
    return dict(n=group['n'],targets=group['targets'],registered=group['registered'],sites=group['sites'],judge=judge,
                measure='functional points',passed={a:r['points'] for a,r in group['methods'].items() if 'points' in r},
                excluded_build_arms=[a for a,r in group['methods'].items() if r['status']=={'build_failed':group['registered']}],
                implementation_sources={a:src['judgments'] for a,src in group['sources'].items()},
                candidate_sources={a:src['candidates'] for a,src in group['sources'].items()},
                start_failures={a:r['start_failed_in_common'] for a,r in group['methods'].items()},
                jointly_runnable=group['jointly_runnable'])


def attach(matrix):
    doc=read(RESULT)
    for batch,cohort in doc['webgen']['cohorts'].items():
        field='webgen_functional' if batch=='development' else 'webgen_holdout'
        for model,group in cohort.items():
            if batch=='development':
                old=matrix[model][field]
                assert set(old['targets'])==set(group['targets']) and old['n']==group['registered']
                for arm in ('direct','human'):
                    assert group['methods'][arm]['points']==old['passed'][arm]
            matrix[model][field]=matrix_group(group,doc['webgen']['judge'])
    for model,g in doc['todomvc'].items():
        orig=matrix[model]['source_diagnosis']['todomvc']
        official=g['primary']
        if g['replicas']['a']['status']!='valid' or set(official['targets'])!=set(orig['targets']):
            continue
        counts={a:len(official['arms'][name]['passes']) for a,name in [('direct','direct'),('human','human'),('gpt5-library','gpt5-library'),('self','a')]}
        matrix[model]['state_examples']={'todomvc':orig|dict(passed=counts,source=relative(RESULT),
              implementation_sources={a:relative(EVIDENCE if a=='self' else TODO) for a in counts},markers=orig['markers']|{'self':'quoted-exclusions'})}


if __name__=='__main__':
    parser=ArgumentParser(description=__doc__)
    parser.add_argument('--write',action='store_true')
    parser.add_argument('--ledgers', action='store_true', help='Verify cost attribution using the original read-only ledgers')
    args=parser.parse_args()
    if args.write:
        for receipt in RECEIPTS:
            if receipt not in (ACCOUNTING, NATIVE_TRANSPORT) and not receipt.is_file():
                raise FileNotFoundError(f'Awaiting sealed receipt: {relative(receipt)}')
        for dest, record in [(ACCOUNTING, accounting()), (NATIVE_TRANSPORT, native_transport())]:
            if dest.exists():
                assert read(dest) == record
            else:
                dump(dest, record)
    if args.ledgers:
        assert read(ACCOUNTING) == accounting() and read(NATIVE_TRANSPORT) == native_transport()
    new=reconstruct()
    if args.write and not RESULT.exists():
        dump(RESULT,new)
    assert new==read(RESULT),'Published comparison differs from the paired receipts.'
    print('Verified both website cohorts, TodoMVC control replays, and the two fresh table libraries.')
