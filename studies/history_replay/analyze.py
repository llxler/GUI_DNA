"""Recompute history outcomes from immutable Playwright reports, never old summaries."""
from collections import Counter, defaultdict
from .run import ROOT, OUT, read, dump, digest, sha, cases_by_file, verify, harness_name


def summarize(require_complete=True):
    inputs = verify()
    from .reference import verify as verify_reference
    extension = verify_reference()
    extension_done = read(OUT/"reference-extension-complete.json")
    assert extension_done["extension_sha256"] == digest(extension) and extension_done["all_passed"]
    if require_complete:
        assert read(OUT/'evaluation-complete.json')['inputs_sha256'] == digest(inputs)
    cache, missing = {}, []
    for key, job in inputs['jobs'].items():
        target = OUT/'scores'/key
        if not (target/'score.json').exists():
            missing.append(key)
            continue
        receipt = read(target/'score.json')
        assert sha(target/'report.json') == receipt['report_sha256']
        cases = cases_by_file(read(target/'report.json'))
        assert cases == receipt['tests']
        passed = set(cases)==set(job['specs']) and all(values and all(c['passed'] for c in values) for values in cases.values())
        assert passed == receipt['all_passed']
        assert passed or any(s in ('failed','timedOut') for values in cases.values() for c in values for s in c['statuses'])
        cache[key] = {'passed':passed,'failures':[{'spec':name,'title':c['title'],'statuses':c['statuses']}
                      for name, values in cases.items() for c in values if any(s in ('failed','timedOut') for s in c['statuses'])]}
    if require_complete:
        assert not missing
    rows = []
    for source in inputs['rows']:
        key = source['score_key']
        outcome = cache.get(key) if key else {'passed':False,'failures':[{'spec':None,'title':'No executable version','statuses':[]}]}
        rows.append({**source,'history_passed':outcome['passed'] if outcome else None,'failures':outcome['failures'] if outcome else []})
    groups = []
    for dimensions in [('cohort','project','method','label'), ('cohort','project','builder','model','method','label')]:
        grouped = defaultdict(list)
        for row in rows:
            grouped[tuple(row[d] for d in dimensions)].append(row)
        for key, values in grouped.items():
            complete = [r for r in values if r['history_passed'] is not None]
            old = [r for r in complete if r['old_current_passed'] is not None]
            groups.append({**dict(zip(dimensions,key)), 'level':'overall' if len(dimensions)==4 else 'stratum',
                'n':len(values),'scored':len(complete),'history_passed':sum(r['history_passed'] for r in complete),
                'old_current_available':len(old),'old_current_passed':sum(r['old_current_passed'] for r in old),
                'old_current_pass_history_fail':sum(r['old_current_passed'] and not r['history_passed'] for r in old),
                'old_current_fail_history_pass':sum(not r['old_current_passed'] and r['history_passed'] for r in old)})
    calibration = []
    calibration_jobs={**inputs['calibration'], 'expert-dom1/positive-reference':extension['job']}
    for key, job in calibration_jobs.items():
        folder = OUT/'calibration'/key
        receipt=read(folder/'score.json')
        assert sha(folder/'report.json') == receipt['report_sha256']
        cases=cases_by_file(read(folder/'report.json'))
        assert cases==receipt['tests']
        calibration.append({'name':('expert-dom1/legacy-rule-task20' if key=='expert-dom1/reference' else key),'passed':receipt['all_passed'],
            'passed_specs':[n for n,v in cases.items() if v and all(c['passed'] for c in v)],
            'failed_specs':[n for n,v in cases.items() if not all(c['passed'] for c in v)],
            'assertions':sum(len(v) for v in cases.values()),'passed_assertions':sum(c['passed'] for v in cases.values() for c in v)})
    result = {'scope':inputs['scope'],'complete':not missing,'comparisons':len(rows),
        'candidate_comparisons':sum(not r['method'].startswith('control/') for r in rows),
        'fixed_control_comparisons':sum(r['method'].startswith('control/') for r in rows),
        'unique_jobs':len(inputs['jobs']),'finished_jobs':len(cache),'missing_jobs':len(missing),
        'calibration':calibration,'groups':groups,'rows':rows,
        'calibration_correction':extension['correction'],
        'limitations':['First means first executable, matching the original cohorts, not first model response.',
            'Current-task values are retained historical observations; no assumption of zero timing/environment noise across dates.',
            'Raw init-plus-prefix assertions on the same page; no posthoc assertion exclusions.',
            'Final reference calibration is a compatibility witness, not calibration of every intermediate reference page.',
            'Correlated task prefixes, models and builders are not independent projects. The two model-built protocols remain separate.']}
    return result


def main():
    result=summarize()
    dump(ROOT/'test/results/history-replay.json',result)
    lines=['# 既有页面的完整历史复验','',result['scope'],'',
           '| 阶段 | 项目 | 做法 | 首次/最终 | n | 旧当前通过 | 新历史通过 | 当前过/历史不过 | 反向差异 |',
           '|---|---|---|---|---:|---:|---:|---:|---:|']
    for g in result['groups']:
        if g['level']=='overall':
            lines.append(f"| {g['cohort']} | {g['project']} | {g['method']} | {g['label']} | {g['n']} | {g['old_current_passed'] if g['old_current_available'] else '未测'} | {g['history_passed']} | {g['old_current_pass_history_fail']} | {g['old_current_fail_history_pass']} |")
    lines += ['', '参考校准：', '', *[f"- {r['name']}: {len(r['passed_specs'])}项文件全过；失败文件 {r['failed_specs']}。" for r in result['calibration']], '', *['- '+v for v in result['limitations']]]
    (ROOT/'test/results/history-replay.md').write_text('\n'.join(lines)+'\n')
    print('comparisons',result['comparisons'],'raw history jobs',result['unique_jobs'])


if __name__=='__main__':
    main()
