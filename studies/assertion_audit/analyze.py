"""Recompute diagnostic counts from unchanged raw Playwright reports."""
from collections import defaultdict
import json
from test.history_replay.run import read, dump, sha, cases_by_file, ROOT
from .run import OUT


def analyze():
    inputs=read(OUT/'inputs.json')
    assert read(OUT/'evaluation-complete.json')['inputs_sha256']==sha(OUT/'inputs.json')
    for name,checksum in read(OUT/'snapshot.json')['sha256'].items():
        assert sha(ROOT/name)==checksum,name
    rows=[]
    for key,job in inputs['jobs'].items():
        folder=OUT/'scores'/key
        score=read(folder/'score.json')
        assert sha(folder/'report.json')==score['report_sha256']
        cases=cases_by_file(read(folder/'report.json'))
        assert cases==score['tests'] and set(cases)==set(job['specs'])
        flat=[c for values in cases.values() for c in values]
        assert all(c['statuses'] and all(s in ('passed','failed','timedOut') for s in c['statuses']) for c in flat)
        passed=all(c['passed'] for c in flat)
        assert passed==score['all_passed']
        version,control,task=key.split('/')
        rows.append({'version':version,'control':control,'task':task,'passed':passed,
            'passed_cases':sum(c['passed'] for c in flat),'cases':len(flat),'detail':flat})
    groups=defaultdict(list)
    for row in rows:groups[row['version']+'/'+row['control']].append(row)
    summary={key:{'files_passed':sum(r['passed'] for r in values),'files':len(values),
        'cases_passed':sum(r['passed_cases'] for r in values),'cases':sum(r['cases'] for r in values)} for key,values in groups.items()}
    inventory=read(OUT/'static-inventory.json')
    # Conservative, post-hoc exclusion of all six statically flagged files,
    # including task-9, whose independent assertions can still reject a blank.
    source=ROOT/'test/results/webbench-expand.json'
    previous=read(source)
    excluded=set(inputs['replacements'])
    retained=[r for r in previous['rows'] if r['project']!='bom' or r['task'] not in excluded]
    sensitivity={method:{'passed':sum(r['final'] for r in retained if r['method']==method),
        'total':sum(r['method']==method for r in retained)} for method in ('plan','free_lib','free')}
    result={'static_files':len(inventory['files']),'replacements':inputs['replacements'],
        'groups':summary,'rows':rows,'api_usd':0,'scope':'Post-hoc diagnostic only; original official scores unchanged. Text screening does not prove all remaining tests sound.'}
    result['six_file_sensitivity']={'excluded_bom_tasks':sorted(excluded),
        'source':str(source.relative_to(ROOT)),'source_sha256':sha(source),'methods':sensitivity,
        'policy':'Conservatively exclude all six pattern-flagged BOM files from all three methods; original scores unchanged. Not a corrected-score evaluation.'}
    dump(ROOT/'test/results/assertion-audit-20261117.json',result)
    lines=['# 2026-11-17 官方断言空过诊断','','| 断言/页面 | 通过文件 | 通过测试 |','|---|---|---|']
    for key,g in summary.items():lines.append(f"| {key} | {g['files_passed']}/{g['files']} | {g['cases_passed']}/{g['cases']} |")
    lines+=['','六文件统一排除的事后敏感性（不回写官方成绩）：',
        *[f"- {method}: {value['passed']}/{value['total']}" for method,value in sensitivity.items()],
        '',result['scope']]
    (ROOT/'test/results/assertion-audit-20261117.md').write_text('\n'.join(lines)+'\n')
    return result


if __name__=='__main__':
    result=analyze()
    print(json.dumps({k:result[k] for k in ('static_files','replacements','groups')},indent=2))
