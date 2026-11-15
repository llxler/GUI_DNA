"""Reconstruct application-level and trajectory-level results without pooling sources."""
from collections import defaultdict,Counter
from pathlib import Path
import json
from .core import ROOT,BUILD,RUN,PROJECTS,BUILDERS,CONDITIONS,dump,digest,slug
from .evaluate import verify_scoring,read,sha
from test.ledger_read import totals


def summarize():
    inputs=verify_scoring()
    assert read(RUN/'evaluation-complete.json')['inputs_sha256']==digest(inputs)
    scores={}
    for key,job in inputs['jobs'].items():
        folder=RUN/'scores'/key
        report=read(folder/'report.json')
        assert read(folder/'receipt.json')['report_sha256']==sha(folder/'report.json')
        assert len(report['cases'])==12 and report['passed']==sum(c['passed'] for c in report['cases'])
        assert report['all_passed']==all(c['passed'] for c in report['cases'])
        scores[key]=report
    rows=[]
    for source in inputs['rows']:
        value=scores[source['score_key']] if source['score_key'] else {'all_passed':False,'passed':0,'total':12,'cases':[]}
        rows.append({**source,'all_passed':value['all_passed'],'passed_cases':value['passed'],'total_cases':value['total'],
                     'case_outcomes':{c['id']:c['passed'] for c in value['cases']}})
    groups=[]
    for dimensions in [('project','condition','method','label'),('project','builder','condition','model','method','label')]:
        grouped=defaultdict(list)
        for row in rows:
            if row['kind']=='candidate':grouped[tuple(row[d] for d in dimensions)].append(row)
        for key,values in grouped.items():
            groups.append({**dict(zip(dimensions,key)),'level':'aggregate' if len(dimensions)==4 else 'stratum',
                'n':len(values),'all_passed':sum(r['all_passed'] for r in values),'passed_cases':sum(r['passed_cases'] for r in values),
                'total_cases':sum(r['total_cases'] for r in values),'unavailable_libraries':sum(r.get('unavailable_library',False) for r in values)})
    libraries=[]
    for project in PROJECTS:
        for builder in BUILDERS:
            for condition in CONDITIONS:
                folder=BUILD/'libraries'/project/slug(builder)/condition;record=read(folder/'record.json')
                package=read(folder/'package.json') if record['status']!='failed' else None
                info={k:record[k] for k in ('project','builder','condition','status','attempts')}
                if package is not None:
                    assert digest(package)==record['package_sha256']
                    info.update(development_passes=record['development_passes'],development_total=record['development_total'],
                        selected_attempt=record['selected_attempt'],schema_properties=list(package['plan_schema']['properties']),
                        schema=package['plan_schema'],file_count=len(package['files']),source_bytes=sum(len(x.encode()) for x in package['files'].values()),
                        compiler_bytes=len(package['compiler'].encode()),design=package['design'])
                selected=[r for r in rows if r['kind']=='control' and all(r[k]==info[k] for k in ('project','builder','condition'))]
                info['controls']=[{k:r[k] for k in ('control','subset','deployed_control','fixed_example','all_passed','passed_cases','total_cases','error')} for r in selected]
                info['finite_subset_witness']=any(r['all_passed'] for r in selected)
                info['finite_casewise_witnesses']=sum(any(r['case_outcomes'].get(f'heldout-{i:02d}',False) for r in selected) for i in range(1,13))
                libraries.append(info)
    pairs=[]
    finals=[r for r in rows if r['kind']=='candidate' and r['label']=='final']
    for project in PROJECTS:
        for condition in CONDITIONS:
            selected=[r for r in finals if r['project']==project and r['condition']==condition]
            index={(r['builder'],r['model'],r['method']):r for r in selected}
            values=[(r,index[(r['builder'],r['model'],'free_lib')]) for r in selected if r['method']=='plan']
            pairs.append({'project':project,'condition':condition,'n':len(values),
                'plan_wins':sum(a['all_passed'] and not b['all_passed'] for a,b in values),
                'code_wins':sum(b['all_passed'] and not a['all_passed'] for a,b in values),
                'ties':sum(a['all_passed']==b['all_passed'] for a,b in values)})
    providers=Counter();usage=defaultdict(lambda:Counter());finish_reasons=Counter();truncated=[]
    for stage,kind in [(BUILD,'build'),(RUN,'generation')]:
        for p in stage.rglob('response.json'):
            response=read(p)
            if response.get('usage',{}).get('cost') is None:continue
            providers[kind+'/'+response.get('model','unknown')+'/'+response.get('provider','unknown')]+=1
            for key in ('prompt_tokens','completion_tokens','cost'):usage[kind][key]+=response['usage'].get(key,0) or 0
            usage[kind]['reasoning_tokens']+=response['usage'].get('completion_tokens_details',{}).get('reasoning_tokens',0) or 0
            reason=response.get('choices',[{}])[0].get('finish_reason','unknown')
            finish_reasons[kind+'/'+response.get('model','unknown')+'/'+reason]+=1
            if reason=='length':truncated.append(str(p.relative_to(ROOT)))
    return {'scope':'Two specification-derived applications, development-only library construction, one full target per app and 12 heldout interaction sequences. Not official benchmark scores or 24 independent tasks.',
        'distinct_candidates':len(finals),'comparisons':len(rows),'raw_reports':len(scores),'libraries':libraries,
        'groups':groups,'pairs':pairs,'rows':rows,'providers':dict(providers),'usage':{k:dict(v) for k,v in usage.items()},
        'finish_reasons':dict(finish_reasons),'truncated_responses':truncated,
        'costs':{'build':totals(BUILD/'budget.sqlite3'),'generation':totals(RUN/'budget.sqlite3')},
        'first_definition':'Raw initial response; version-0 compilation failure is a failure, not replaced by first executable repair.',
        'limitations':['Two familiar source applications, one seed per builder/planner; no independent-project significance claim.',
            'Construction comparison is a prompt-level process contrast, not a new learned abstraction algorithm.',
            'Development exposes primitive semantics and UI selectors; heldout trajectories are unseen, not all semantic information.',
            'Full-merge is a deterministic deployable control; success of any subset merge is only a finite-set reachable witness.',
            'Extra unrequested working features were allowed; fixed development examples may already implement the full target.']}


def main():
    result=summarize();dump(ROOT/'test/results/interaction-transfer.json',result)
    lines=['# 开发原语到完整交互序列','',result['scope'],'',
        '| 来源应用 | 建库提示 | 做法 | 首次/最终 | 应用全过 | 轨迹通过（相关） |','|---|---|---|---|---:|---:|']
    for g in result['groups']:
        if g['level']=='aggregate':lines.append(f"| {g['project']} | {g['condition']} | {g['method']} | {g['label']} | {g['all_passed']}/{g['n']} | {g['passed_cases']}/{g['total_cases']} |")
    lines+=['','固定控制：','']
    for lib in result['libraries']:
        deployed=next(r for r in lib['controls'] if r['deployed_control'])
        lines.append(f"- {lib['project']}/{lib['builder']}/{lib['condition']}: 三例合并 {deployed['passed_cases']}/12；有限子集合并存在完整见证={lib['finite_subset_witness']}。")
    lines+=['',*['- '+x for x in result['limitations']]]
    (ROOT/'test/results/interaction-transfer.md').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines))


if __name__=='__main__':main()
