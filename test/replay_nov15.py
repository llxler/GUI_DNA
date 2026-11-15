"""Independently reconstruct November 15 tables from raw reports and dated ledgers.

Original manifests attest original bytes. Anonymous archives separately validate
REPLAY-MANIFEST.json; this module checks outcomes after path/identity rewriting.
"""
from collections import Counter,defaultdict
import json
import hashlib
from pathlib import Path
from test.ledger_read import totals

ROOT=Path(__file__).resolve().parents[1]


def read(path):return json.loads((ROOT/path).read_text())


def browser_cases(report):
    result={}
    stack=list(report.get('suites',[]))
    while stack:
        suite=stack.pop(0)
        for spec in suite.get('specs',[]):
            filename=Path(spec['file']).name.removesuffix('.spec.js')
            for test in spec.get('tests',[]):
                statuses=[r['status'] for r in test.get('results',[])]
                result.setdefault(filename,[]).append({'title':spec['title'],'statuses':statuses,
                    'passed':bool(statuses) and all(s=='passed' for s in statuses)})
        stack[0:0]=suite.get('suites',[])
    return result


def replay_history():
    stage=Path('artifacts/history-replay-20261115');inputs=read(stage/'inputs.json');expected=read('test/results/history-replay.json')
    outcomes={}
    for key,job in inputs['jobs'].items():
        report=read(stage/'scores'/key/'report.json')
        cases=browser_cases(report)
        passed=set(cases)==set(job['specs']) and all(cases.values()) and all(c['passed'] for values in cases.values() for c in values)
        assert passed==read(stage/'scores'/key/'score.json')['all_passed']
        failures=[{'spec':name,'title':c['title'],'statuses':c['statuses']} for name,values in cases.items() for c in values if any(s in ('failed','timedOut') for s in c['statuses'])]
        assert passed or failures
        outcomes[key]=(passed,failures)
    old_controls=read('artifacts/webbench-expand-controls/results.json')['rows']
    rows=[]
    for source in inputs['rows']:
        key=source['score_key']
        passed,failures=outcomes[key] if key else (False,[{'spec':None,'title':'No executable version','statuses':[]}])
        if not source['method'].startswith('control/'):
            folder=Path(source['record']).parent;record=read(source['record']);hidden=read(folder/'hidden.json')
            assert hidden[source['label']]['all_passed']==source['old_current_passed']
            version=record['versions'][0 if source['label']=='first' else -1] if record['versions'] else None
            assert (str(folder/version) if version else None)==source['page']
        elif source['old_current_passed'] is not None:
            original=next(r for r in old_controls if all(r[f]==source[f] for f in ('project','builder','model','task')) and 'control/'+r['control']==source['method'])
            assert original['passed']==source['old_current_passed']
        rows.append({**source,'history_passed':passed,'failures':failures})
    assert rows==expected['rows']
    for group in expected['groups']:
        dimensions=('cohort','project','builder','model','method','label')
        selected=[r for r in rows if all(r[k]==group[k] for k in dimensions if k in group)]
        old=[r for r in selected if r['old_current_passed'] is not None]
        metrics={'n':len(selected),'scored':len(selected),'history_passed':sum(r['history_passed'] for r in selected),
            'old_current_available':len(old),'old_current_passed':sum(r['old_current_passed'] for r in old),
            'old_current_pass_history_fail':sum(r['old_current_passed'] and not r['history_passed'] for r in old),
            'old_current_fail_history_pass':sum(not r['old_current_passed'] and r['history_passed'] for r in old)}
        assert all(group[k]==v for k,v in metrics.items()),group
    for calibration in expected['calibration']:
        name='expert-dom1/reference' if calibration['name']=='expert-dom1/legacy-rule-task20' else calibration['name']
        cases=browser_cases(read(stage/'calibration'/name/'report.json'))
        assert calibration['passed_specs']==[n for n,v in cases.items() if v and all(c['passed'] for c in v)]
        assert calibration['failed_specs']==[n for n,v in cases.items() if not all(c['passed'] for c in v)]
        assert calibration['passed_assertions']==sum(c['passed'] for v in cases.values() for c in v)
    diagnostic=read('test/results/history-replay-diagnostics.json')
    discordances=[];counts=Counter();pages=defaultdict(set)
    finals=[r for r in rows if r['label']=='final' and not r['method'].startswith('control/')]
    def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    for row in finals:
        if not row['old_current_passed'] or row['history_passed']:continue
        sequence=[r for r in finals if all(r[k]==row[k] for k in ('cohort','project','builder','model','method'))]
        k=int(row['task'].split('-')[1])
        for failure in row['failures']:
            spec=failure['spec'];i=0 if spec=='init' else int(spec.split('-')[1]) if spec else None
            witnesses=[r['task'] for r in sequence if r['history_passed'] and i is not None and i<=int(r['task'].split('-')[1])<k]
            item={key:row[key] for key in ('cohort','project','builder','model','method','task')}
            item.update(failure=failure,earlier_assertion=i is not None and i<k,earlier_page_history_pass_witnesses=witnesses)
            discordances.append(item)
            fk=(row['cohort'],row['project'],row['method'],spec,failure['title']);counts[fk]+=1
            pages[fk].add(digest(inputs['jobs'][row['score_key']]['files']) if row['score_key'] else 'none')
    # Source iteration order differs from the descriptive grouping; compare identities.
    key=lambda r:json.dumps(r,sort_keys=True)
    assert sorted(discordances,key=key)==sorted(diagnostic['discordances'],key=key)
    assert diagnostic['discordant_final_observations']==len(discordances)
    assert diagnostic['with_initial_file_failure']==sum(r['failure']['spec']=='init' for r in discordances)
    assert diagnostic['with_earlier_assertion_failure']==sum(r['earlier_assertion'] for r in discordances)
    assert diagnostic['with_same_sequence_earlier_page_history_pass_witness']==sum(bool(r['earlier_page_history_pass_witnesses']) for r in discordances)
    failure_rows=[dict(zip(('cohort','project','method','spec','title'),k),observations=v,distinct_source_maps=len(pages[k])) for k,v in sorted(counts.items(),key=lambda x:(-x[1],str(x[0])))]
    assert failure_rows==diagnostic['failures']
    variants=Counter()
    for row in finals:
        if row['cohort']!='expert' or row['method'] not in ('dna','dna_unchecked') or not row['page']:continue
        record=read(row['record']);number=int(row['page'].split('/')[-1].removeprefix('v'))
        plan=next(a for a in record['attempts'] if a['attempt']==number).get('plan')
        if not isinstance(plan,dict):continue
        for field in ('select','insert','delete','drag','menuLabel'):variants[row['method'],field,str(plan.get(field)),row['history_passed']]+=1
    assert diagnostic['expert_variants']==[{'method':m,'field':f,'value':v,'history_passed':p,'observations':n} for (m,f,v,p),n in sorted(variants.items())]
    return {'comparisons':len(rows),'raw_reports':len(outcomes),'groups':expected['groups'],'calibration':expected['calibration'],
        'diagnostics_counts':{k:diagnostic[k] for k in ('discordant_final_observations','with_earlier_assertion_failure','with_same_sequence_earlier_page_history_pass_witness')},
        'scope':'Same-page init-plus-prefix; retained historical current-task observations; no posthoc assertion exclusions.'}


def replay_transfer():
    stage=Path('artifacts/interaction-transfer-run-20261115');inputs=read(stage/'scoring-inputs.json');expected=read('test/results/interaction-transfer.json')
    outcomes={}
    for key,job in inputs['jobs'].items():
        report=read(stage/'scores'/key/'report.json')
        assert [c['id'] for c in report['cases']]==[f'heldout-{i:02d}' for i in range(1,13)]
        passed=sum(c['passed'] for c in report['cases'])
        assert report['passed']==passed and report['all_passed']==(passed==12)
        outcomes[key]={'all_passed':passed==12,'passed_cases':passed,'total_cases':12,'case_outcomes':{c['id']:c['passed'] for c in report['cases']}}
    rows=[{**source,**(outcomes[source['score_key']] if source['score_key'] else {'all_passed':False,'passed_cases':0,'total_cases':12,'case_outcomes':{}})} for source in inputs['rows']]
    assert rows==expected['rows']
    for group in expected['groups']:
        fields=('project','builder','condition','model','method','label')
        selected=[r for r in rows if r['kind']=='candidate' and all(r[f]==group[f] for f in fields if f in group)]
        metrics={'n':len(selected),'all_passed':sum(r['all_passed'] for r in selected),'passed_cases':sum(r['passed_cases'] for r in selected),
            'total_cases':sum(r['total_cases'] for r in selected),'unavailable_libraries':sum(r.get('unavailable_library',False) for r in selected)}
        assert all(group[k]==v for k,v in metrics.items())
    from test.interaction_transfer.controls import merge
    for library in expected['libraries']:
        folder=Path('artifacts/interaction-transfer-build-20261115/libraries')/library['project']/library['builder'].replace('/','__')/library['condition']
        record=read(folder/'record.json');assert record['status']==library['status']
        selected=[r for r in rows if r['kind']=='control' and all(r[f]==library[f] for f in ('project','builder','condition'))]
        assert library['finite_subset_witness']==any(r['all_passed'] for r in selected)
        assert library['finite_casewise_witnesses']==sum(any(r['case_outcomes'].get(f'heldout-{i:02d}',False) for r in selected) for i in range(1,13))
        if record['status']=='failed':continue
        package=read(folder/'package.json')
        assert library['schema_properties']==list(package['plan_schema']['properties']) and library['schema']==package['plan_schema']
        assert library['source_bytes']==sum(len(v.encode()) for v in package['files'].values())
        assert library['compiler_bytes']==len(package['compiler'].encode()) and library['design']==package['design']
        passes=0
        for i in range(3):
            report=read(folder/f'validation-{record["selected_attempt"]}'/f'dev-{i}'/'public-report.json')
            assert report['all_passed']==all(c['passed'] for c in report['cases'])
            passes+=report['all_passed']
        assert passes==library['development_passes']
        for control in selected:
            plans=[next(e['plan'] for e in package['examples'] if e['id']==f'dev-{i}') for i in control['subset']]
            try:
                plan=plans[0]
                for value in plans[1:]:plan=merge(plan,value)
            except ValueError as error:
                assert control['page'] is None and control['error']==str(error)
                continue
            # Even a merge rejected by the schema retains its proposed plan.
            plan_path=Path('artifacts/interaction-transfer-controls-20261115/pages')/library['project']/library['builder'].replace('/','__')/library['condition']/control['control']/'plan.json'
            assert read(plan_path)==plan
    finish=Counter();truncated=[];providers=Counter();usage=defaultdict(Counter)
    for kind,name in [('build','interaction-transfer-build-20261115'),('generation','interaction-transfer-run-20261115')]:
        for p in (ROOT/'artifacts'/name).rglob('response.json'):
            response=read(p)
            if response.get('usage',{}).get('cost') is None:continue
            reason=response.get('choices',[{}])[0].get('finish_reason','unknown')
            finish[kind+'/'+response.get('model','unknown')+'/'+reason]+=1
            providers[kind+'/'+response.get('model','unknown')+'/'+response.get('provider','unknown')]+=1
            if reason=='length':truncated.append(str(p.relative_to(ROOT)))
            for key in ('prompt_tokens','completion_tokens','cost'):usage[kind][key]+=response['usage'].get(key,0) or 0
            usage[kind]['reasoning_tokens']+=response['usage'].get('completion_tokens_details',{}).get('reasoning_tokens',0) or 0
        assert totals(ROOT/'artifacts'/name/'budget.sqlite3')==expected['costs'][kind]
    assert dict(finish)==expected['finish_reasons'] and sorted(truncated)==sorted(expected['truncated_responses'])
    assert dict(providers)==expected['providers']
    for kind,values in usage.items():
        for key,value in values.items():assert abs(value-expected['usage'][kind][key])<1e-8
    for pair in expected['pairs']:
        selected=[r for r in rows if r['kind']=='candidate' and r['label']=='final' and all(r[f]==pair[f] for f in ('project','condition'))]
        lookup={(r['builder'],r['model'],r['method']):r for r in selected}
        plans=[r for r in selected if r['method']=='plan']
        metrics=Counter()
        for plan in plans:
            code=lookup[plan['builder'],plan['model'],'free_lib']
            metrics['plan_wins']+=plan['all_passed'] and not code['all_passed']
            metrics['code_wins']+=code['all_passed'] and not plan['all_passed']
            metrics['ties']+=plan['all_passed']==code['all_passed']
        assert pair['n']==len(plans) and all(pair[k]==metrics[k] for k in ('plan_wins','code_wins','ties'))
    calibration=read('artifacts/interaction-transfer-calibration-20261115/calibration.json')['rows']
    for row in calibration:
        report=read(row['report'])
        assert row['passed']==report['passed']==sum(c['passed'] for c in report['cases'])
        assert row['total']==report['total']==len(report['cases'])
        assert row['all_passed']==report['all_passed']==all(c['passed'] for c in report['cases'])
        assert row['all_passed']==row['expected_all']
    assert read('artifacts/interaction-transfer-calibration-20261115/complete.json')['all_expectations_met']
    return {'distinct_candidates':expected['distinct_candidates'],'comparisons':len(rows),'raw_reports':len(outcomes),'calibration':calibration,
        'groups':expected['groups'],'pairs':expected['pairs'],
        'library_development':[{'project':r['project'],'builder':r['builder'],'condition':r['condition'],'status':r['status'],
            'passed':r.get('development_passes'), 'finite_subset_witness':r['finite_subset_witness']} for r in expected['libraries']]}


def replay_history_witnesses():
    from test.webbench_expand.core import compile_plan
    from gui_dna.provider import parse_json
    expected=read('test/results/history-replay-witnesses.json');history=read('test/results/history-replay.json')['rows']
    inputs=read('artifacts/history-replay-20261115/inputs.json');evidence=defaultdict(list)
    for row in history:
        if row['cohort'] not in ('expansion','frontier') or not row['history_passed']:continue
        if row['method']!='plan' and not row['method'].startswith('control/'):continue
        evidence[row['project'],row['builder'],row['task']].append({k:row[k] for k in ('cohort','method','model','label','page','score_key')})
    assert expected['witnesses']==[{'project':p,'builder':b,'task':t,'observations':v} for (p,b,t),v in sorted(evidence.items()) if v]
    for page,proof in expected['compiled_page_proofs'].items():
        row=next(r for r in history if r['page']==page and r['history_passed'] and r['cohort'] in ('expansion','frontier'))
        package=read(Path('artifacts/webbench-expand-build/libraries')/row['project']/row['builder'].replace('/','__')/'package.json')
        folder=Path(page)
        if folder.name.startswith('example-'):plan=package['examples'][int(folder.name[-1])]['plan']
        else:plan=parse_json(read(folder.parent/('output-'+folder.name.removeprefix('version-')+'.json'))['text'])
        assert plan==proof['plan'];files=compile_plan(package,plan)
        assert set(files)==set(inputs['jobs'][row['score_key']]['files'])
        assert all((ROOT/folder/name).read_text()==text for name,text in files.items())
    counts=Counter();outcomes=[]
    for row in history:
        if row['cohort']!='expansion' or row['method']!='plan' or row['label']!='final':continue
        category='passed' if row['history_passed'] else ('failed_with_legal_history_witness' if evidence[row['project'],row['builder'],row['task']] else 'failed_without_observed_history_witness')
        counts[category]+=1;outcomes.append({k:row[k] for k in ('project','builder','model','task','page','history_passed')}|{'category':category})
    assert outcomes==expected['main_plan_outcomes'] and dict(counts)==expected['main_plan_categories']
    for library in expected['libraries']:
        tasks=[f'task-{k}' for k in range(1,21) if evidence[library['project'],library['builder'],f'task-{k}']]
        assert tasks==library['witness_tasks'] and len(tasks)==library['with_observed_witness']
    assert expected['with_observed_witness']==sum(r['with_observed_witness'] for r in expected['libraries'])
    return {'library_task_pairs':120,'with_observed_witness':expected['with_observed_witness'],'main_plan_categories':dict(counts),'source_pages_recompiled':len(expected['compiled_page_proofs'])}


def replay_union():
    from test.interaction_union.run import merge
    stage=Path('artifacts/interaction-union-20261115');inputs=read(stage/'inputs.json');expected=read('test/results/interaction-union.json')
    rows=[]
    for row in inputs['rows']:
        folder=Path('artifacts/interaction-transfer-build-20261115/libraries')/row['project']/row['builder'].replace('/','__')/row['condition']
        package=read(folder/'package.json');plans=[next(e['plan'] for e in package['examples'] if e['id']==f'dev-{i}') for i in range(3)]
        try:
            plan=merge(merge(plans[0],plans[1]),plans[2]);assert read(Path(row['page'])/'plan.json')==plan
        except ValueError as e:assert row['page'] is None and row['error']==str(e)
        if row['score_key']:
            job=inputs['jobs'][row['score_key']];report=read(stage/'scores'/row['score_key']/'report.json')
            assert len(report['cases'])==12 and report['passed']==sum(c['passed'] for c in report['cases'])
            assert report['all_passed']==all(c['passed'] for c in report['cases'])
            if job['reuse_key']:assert report==read(Path('artifacts/interaction-transfer-run-20261115/scores')/job['reuse_key']/'report.json')
        else:report={'passed':0,'all_passed':False}
        rows.append({**row,'passed_cases':report['passed'],'all_passed':report['all_passed']})
    assert rows==expected['rows'] and expected['passed']==sum(r['all_passed'] for r in rows)
    assert expected['reused_reports']==sum(bool(j['reuse_key']) for j in inputs['jobs'].values())
    assert expected['new_reports']==sum(not j['reuse_key'] for j in inputs['jobs'].values())
    return expected


def replay_development_feedback():
    stage=Path('artifacts/development-feedback-20261115');inputs=read(stage/'inputs.json');expected=read('test/results/development-feedback.json')
    rows=[]
    for row in inputs['rows']:
        r=read(row['record']);label=row['label']
        version=('version-0' if 'version-0' in r['versions'] else None) if label=='first' else (r['versions'][-1] if r['versions'] else None)
        assert row['page']==(str(Path(row['record']).parent/version) if version else None)
        report=read(stage/'scores'/row['score_key']/'report.json') if row['score_key'] else {'passed':0,'all_passed':False,'cases':[]}
        if row['score_key']:
            assert len(report['cases'])==12 and report['passed']==sum(c['passed'] for c in report['cases'])
            assert report['all_passed']==all(c['passed'] for c in report['cases'])
        if r['versions']:
            number=int(r['versions'][-1].removeprefix('version-'))
            development=[read(Path(row['record']).parent/f'validation-{number}'/f'dev-{i}.json') for i in range(3)]
            assert r['development_passes']==sum(d['all_passed'] for d in development)
        rows.append({**row,'all_passed':report['all_passed'],'passed_cases':report['passed'],'attempts':len(r['attempts']),
            'development_passes':r.get('development_passes',0),'development_total':3})
    assert rows==expected['rows'];assert totals(ROOT/stage/'budget.sqlite3')==expected['costs']
    usage=Counter();finish=Counter();providers=Counter()
    for p in (ROOT/stage/'runs').rglob('response.json'):
        r=read(p);finish[r['model']+'/'+r['choices'][0]['finish_reason']]+=1;providers[r['model']+'/'+r.get('provider','unknown')]+=1
        for k in ('prompt_tokens','completion_tokens','cost'):usage[k]+=r.get('usage',{}).get(k,0) or 0
        usage['reasoning_tokens']+=r.get('usage',{}).get('completion_tokens_details',{}).get('reasoning_tokens',0) or 0
    assert dict(finish)==expected['finish_reasons'] and dict(providers)==expected['providers']
    assert all(abs(value-expected['usage'][k])<1e-8 for k,value in usage.items())
    return expected


def replay_task_history():
    path = ROOT / 'test/results/history-tasks-only.json'
    if not path.exists():
        return None
    stage = Path('artifacts/history-tasks-only-20261115')
    inputs = read(stage / 'inputs.json')
    expected = read(path)
    outcomes = {}
    def infer(cases, specs):
        if any(status in ('failed', 'timedOut') for name in specs for case in cases.get(name, []) for status in case['statuses']):
            return False, 'observed_task_failure'
        if all(cases.get(name) and all(case['passed'] for case in cases[name]) for name in specs):
            return True, 'all_task_files_observed_passed'
        return None, 'task_files_unresolved_after_init_failure'
    for key, decision in inputs['decisions'].items():
        passed, reason = infer(browser_cases(read(decision['old_report'])), decision['specs'])
        assert (passed, reason) == (decision['observed'], decision['reason'])
        assert (key in inputs['jobs']) == (passed is None)
        if passed is None:
            job = inputs['jobs'][key]
            assert job['specs'] == decision['specs'] and 'init' not in job['specs']
            passed, _ = infer(browser_cases(read(stage / 'scores' / key / 'report.json')), job['specs'])
            assert passed is not None
        outcomes[key] = passed
    rows = []
    for row in read('test/results/history-replay.json')['rows']:
        passed = outcomes[row['score_key']] if row['score_key'] else False
        assert not row['history_passed'] or passed
        rows.append({**row, 'task_history_passed': passed, 'new_report_used': row['score_key'] in inputs['jobs']})
    assert rows == expected['rows']
    for group in expected['groups']:
        fields = ('cohort', 'project', 'method', 'label')
        selected = [r for r in rows if all(r[k] == group[k] for k in fields if k in group)]
        metrics = {'n': len(selected), 'old_current_available': sum(r['old_current_passed'] is not None for r in selected),
                   'old_current_passed': sum(bool(r['old_current_passed']) for r in selected),
                   'history_passed': sum(r['history_passed'] for r in selected),
                   'task_history_passed': sum(r['task_history_passed'] for r in selected),
                   'old_current_pass_task_history_fail': sum(r['old_current_passed'] is True and not r['task_history_passed'] for r in selected),
                   'old_current_fail_task_history_pass': sum(r['old_current_passed'] is False and r['task_history_passed'] for r in selected),
                   'new_report_endpoints': sum(r['new_report_used'] for r in selected)}
        assert all(group[k] == v for k, v in metrics.items())
    assert expected['new_reports'] == len(inputs['jobs'])
    assert expected['reused_decisive_reports'] == len(inputs['decisions']) - len(inputs['jobs'])
    return {'scope': expected['scope'], 'posthoc': True, 'comparisons': len(rows),
            'new_reports': expected['new_reports'], 'reused_decisive_reports': expected['reused_decisive_reports'],
            'groups': expected['groups']}


def replay_container():
    result_path=ROOT/'test/results/container-replay.json'
    if not result_path.exists():return None
    expected=read(result_path)
    stage=Path(expected.get('stage', 'artifacts/container-replay-20261115'))
    inputs=read(stage/'inputs/inputs.json')
    rows=[]
    for job in inputs['jobs']:
        cases=browser_cases(read(stage/'outputs/scores'/job['id']/'report.json'))
        passed=set(cases)==set(job['specs']) and all(cases.values()) and all(c['passed'] for group in cases.values() for c in group)
        prior=read(Path('artifacts/history-replay-20261115/scores')/job['history_key']/'score.json')['all_passed'] if job['comparison']=='history' else job['expected']
        rows.append({**job,'passed':passed,'expected_observation':prior,'matches':passed==prior,'tests':cases})
    assert rows==expected['rows'] and expected['matched']==sum(r['matches'] for r in rows)
    assert expected['environment']==read(stage/'outputs/environment.json')
    return expected


def replay_finite_schema():
    result_path = ROOT / 'test/results/finite-schema-audit.json'
    if not result_path.exists():
        return None
    from test.finite_schema_audit.analyze import reconstruct
    from test.webbench_expand.generate import output_files
    observed = reconstruct()
    assert observed == read(result_path)
    inputs = read('artifacts/finite-schema-audit-20261115/inputs.json')
    package = read(inputs['package'])
    for row in inputs['rows']:
        files = output_files('plan', package, row['plan'])
        observed_files = {name: hashlib.sha256(content.encode()).hexdigest() for name, content in files.items()}
        assert observed_files == inputs['jobs'][row['score_key']]['files']
    return {**observed, 'complete_configurations_recompiled': len(inputs['rows'])}


def replay_network_probe():
    path = ROOT / 'test/results/container-network-probe.json'
    if not path.exists(): return None
    expected = read(path)
    rows = []
    for mode in expected['network_modes']:
        raw = read(f'artifacts/container-network-probe-20261115/{mode}.json')
        assert raw['exit_code'] == 0
        rows.append({'network': mode, **json.loads(raw['stdout'])})
    assert rows == expected['observations'] and expected['benchmark_pages_reexecuted'] == 0
    return expected


def source_integrity():
    """Check original workspace bytes, never rewritten anonymous manifests."""
    names = [
        'history-replay-20261115/snapshot.json',
        'history-replay-20261115/reference-extension.json',
        'interaction-transfer-calibration-20261115/frozen.json',
        'interaction-transfer-build-20261115/review-manifest.json',
        'interaction-transfer-run-20261115/review-manifest.json',
        'interaction-transfer-run-20261115/scoring-snapshot.json',
        'interaction-union-20261115/snapshot.json',
        'development-feedback-20261115/review-manifest.json',
        'development-feedback-20261115/scoring-snapshot.json',
    ]
    if (ROOT / 'artifacts/container-replay-20261115/snapshot.json').exists():
        names.append('container-replay-20261115/snapshot.json')
    if (ROOT / 'artifacts/container-replay-20261115-uid/snapshot.json').exists():
        names.append('container-replay-20261115-uid/snapshot.json')
    if (ROOT / 'artifacts/history-tasks-only-20261115/snapshot.json').exists():
        names.append('history-tasks-only-20261115/snapshot.json')
    if (ROOT / 'artifacts/finite-schema-audit-20261115/snapshot.json').exists():
        names += ['finite-schema-audit-20261115/snapshot.json', 'finite-schema-audit-20261115/dependency-extension.json']
    if (ROOT / 'artifacts/container-network-probe-20261115/snapshot.json').exists():
        names.append('container-network-probe-20261115/snapshot.json')
    rows = []
    for name in names:
        manifest = Path('artifacts') / name
        snapshot = read(manifest)
        mapping = snapshot.get('sha256', snapshot.get('files'))
        assert isinstance(mapping, dict) and mapping
        for source, expected in mapping.items():
            assert hashlib.sha256((ROOT / source).read_bytes()).hexdigest() == expected, (name, source)
        rows.append({'manifest': str(manifest), 'files_verified': len(mapping), 'all_passed': True})
    result = {'scope': 'Original workspace source/input snapshots for November 15; exported copies use their own REPLAY-MANIFEST hashes. Does not resume generation.',
              'manifests': rows, 'all_passed': True}
    (ROOT / 'test/results/nov15-integrity.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Original source/input snapshots match:', len(rows), 'manifests.')


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-integrity', action='store_true',
                        help='Verify original workspace byte hashes only, not anonymous copies')
    args = parser.parse_args()
    if args.source_integrity:
        source_integrity()
        return
    from test.authorized_costs import summarize
    daily=summarize('20261115')
    assert daily==read('test/results/review-20261115-costs.json')
    from test.replay_table_details import reconstruct
    table_details = reconstruct()
    assert table_details == read('test/results/table-details-replay.json')
    from test.replay_pilot_tables import reconstruct as reconstruct_pilots
    pilot_tables = reconstruct_pilots()
    assert pilot_tables == read('test/results/pilot-tables-replay.json')
    from test.replay_review_tables import reconstruct as reconstruct_review
    review_tables = reconstruct_review()
    assert review_tables == read('test/results/review-tables-replay.json')
    result={'all_passed':True,'history_replay':replay_history(),'history_witnesses':replay_history_witnesses(),'task_file_history':replay_task_history(),'interaction_transfer':replay_transfer(),'interaction_union':replay_union(),'development_feedback':replay_development_feedback(),'container':replay_container(),'daily_cost':daily,
            'table_details': table_details,
            'pilot_tables': pilot_tables,
            'review_tables': review_tables,
            'finite_schema': replay_finite_schema(),
            'container_network_probe': replay_network_probe(),
            'scope':'Independent recomputation from retained raw reports, source records, deterministic control proposals and read-only ledgers; no fresh API or browser execution.'}
    (ROOT/'test/results/nov15-replay.json').write_text(json.dumps(result,indent=2)+'\n')
    print('November 15 raw-report reconstruction matches core studies, exploratory controls and dated ledgers.')


if __name__=='__main__':main()
