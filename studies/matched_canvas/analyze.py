"""Audit saved canvas pilot evidence and reconstruct the portable result."""
import argparse
from decimal import Decimal, ROUND_CEILING
from datetime import datetime
from pathlib import Path
from gui_dna.provider import parse_json
from studies.study_io import ROOT, read, dump, sha, cases_by_file
from studies.ledger_read import calls, totals
from studies.webbench_expand.core import compile_plan
from .browser import OUT, TASKS
from .evaluate import verify
from .run import GROUPS, MODEL, CONFIG, LIMIT, messages

RESULT = ROOT/'studies/results/matched-canvas-20261118.json'


def audit_report(path, task, expected_hash):
    assert sha(path) == expected_hash
    raw = read(path)
    cases = cases_by_file(raw)
    assert set(cases) == {task} and cases[task]
    passed = all(c['passed'] for c in cases[task])
    if not passed:
        assert any(s in ('failed','timedOut') for c in cases[task] for s in c['statuses'])
    return passed, raw['stats']['startTime'], cases[task]


def audit_calls(group, arm, package):
    ledger = {r['id']:r for r in calls(group/'budget.sqlite3')}
    seen = set()
    receipts = {'prepare':Decimal(0), 'target':Decimal(0)}
    attempts = {}
    for path in sorted(group.rglob('request.json')):
        request = read(path)
        call_id = request['call_id']
        assert call_id in ledger and call_id not in seen
        seen.add(call_id)
        body = request['body']
        task = path.relative_to(group).parts[0]
        prepare = task == 'prepare'
        initial = messages(arm, None if prepare else task, None if prepare else package)
        assert initial == body['messages'][:2] == read(group/task/'messages.json')
        effort = CONFIG.get('reasoning_effort', {}).get(MODEL)
        assert body['model'] == MODEL and body['reasoning'] == ({'effort':effort} if effort else {'enabled':False})
        assert body['provider']['order'] == CONFIG['provider_order'][MODEL]
        assert body['max_tokens'] == CONFIG['max_tokens']
        if path.parent.parent.name == 'attempt-1':
            original = group/task/'attempt-0'
            first = read(original/'api/response.json')['choices'][0]['message']['content']
            import json
            feedback = json.dumps(read(original/'check.json'))
            assert body['messages'][2:] == [
                {'role':'assistant','content':first},
                {'role':'user','content':'Public format, compile or load feedback: '+feedback+'. Return a full corrected object.'}]
        else:
            assert len(body['messages']) == 2
        if ledger[call_id]['actual'] is not None:
            response = read(path.with_name('response.json'))
            amount = Decimal(str(response['usage']['cost']))
            assert int((amount*1000000).to_integral_value(rounding=ROUND_CEILING)) == ledger[call_id]['actual']
            receipts['prepare' if prepare else 'target'] += amount
            attempts[str(path.parent.parent.relative_to(group))] = {
                'response_sha256':sha(path.with_name('response.json')),
                'finish_reason':response['choices'][0]['finish_reason'],
                'completion_tokens':response['usage']['completion_tokens'],
                'cost_usd':float(amount)}
    assert seen == set(ledger)
    return {k:float(v) for k,v in receipts.items()}, attempts


def reconstruct():
    verify(OUT/'protocol-freeze.json')
    verify(OUT/'generated.json')
    calibration = read(OUT/'calibration.json')
    reference_cases = {}
    for key,v in calibration.items():
        kind, task = key.split('/')
        passed,_,cases = audit_report(OUT/'calibration'/key/'report.json',task,v['report_sha256'])
        assert passed == v['passed']
        if kind == 'reference' and passed:
            reference_cases[task] = [c['title'] for c in cases]
    eligible = [task for task in TASKS if calibration['reference/'+task]['passed'] and not calibration['blank/'+task]['passed']]
    completed = datetime.fromisoformat(read(OUT/'generated.json')['utc'])
    eval_data = read(OUT/'evaluation.json')
    assert eval_data['generated_sha256'] == sha(OUT/'generated.json')
    results = eval_data['results']
    assert set(results) == {f'{arm}-{rep}/{task}' for arm,rep in GROUPS for task in TASKS}
    groups = {}
    for arm,rep in GROUPS:
        name = f'{arm}-{rep}'
        group = OUT/name
        package = read(group/'prepare/frozen.json') if (group/'prepare/frozen.json').exists() else None
        preparation = read(group/'prepare/result.json')
        if preparation['status'] == 'accepted':
            final = group/f"prepare/attempt-{preparation['attempt']}/api/response.json"
            assert package == parse_json(read(final)['choices'][0]['message']['content'])
        cost = totals(group/'budget.sqlite3')
        assert cost['cap_usd'] == LIMIT and cost['stop_usd'] == 0 and cost['exposure_usd'] <= LIMIT
        receipts, attempts = audit_calls(group,arm,package)
        for task in TASKS:
            key = name+'/'+task
            row = results[key]
            record = read(group/task/'result.json')
            assert row['status'] == record['status'] and row['page'] == record.get('page')
            if row['page']:
                passed,start,cases = audit_report(OUT/'scores'/key/'report.json',task,row['report_sha256'])
                assert datetime.fromisoformat(start) >= completed and passed == row['passed']
                if passed and task in reference_cases:
                    assert [c['title'] for c in cases] == reference_cases[task]
                row['first_failed_case'] = next((c['title'] for c in cases if any(
                    status in ('failed','timedOut') for status in c['statuses'])),None)
                page = ROOT/row['page']
                raw = read(page.parent/'api/response.json')['choices'][0]['message']['content']
                value = parse_json(raw)
                files = compile_plan(package,value) if arm == 'plan' else value['files']
                assert set(files) == {p.relative_to(page).as_posix() for p in page.rglob('*') if p.is_file() and 'assets' not in p.relative_to(page).parts}
                assert all((page/n).read_bytes()==v.encode() for n,v in files.items())
            else:
                assert row['passed'] is (None if row['status']=='missing' else False)
        values = [results[name+'/'+task]['passed'] for task in TASKS]
        groups[name] = {'arm':arm,'repetition':rep, 'prepare_status':preparation['status'],
            'prepare_sha256':sha(group/'prepare/frozen.json') if package is not None else None,
            'planned':len(TASKS),'observed':sum(v is not None for v in values),'passed':values.count(True),
            'calibrated_passes':sum(results[name+'/'+task]['passed'] is True for task in eligible),
            'cost':cost,'receipts_usd':receipts,'settled_attempts':attempts}
    paired = {}
    for rep in (1,2):
        pairs = [(results[f'free-{rep}/{task}']['passed'],results[f'plan-{rep}/{task}']['passed']) for task in TASKS]
        paired[str(rep)] = {label:pairs.count(key) for label,key in [
            ('direct_only',(True,False)),('plan_only',(False,True)),('both_pass',(True,True)),('both_fail',(False,False))]}
    return {'project':'canvas','model':MODEL,'builder':MODEL,'generator':MODEL,'milestones':TASKS,
            'calibrated_milestones':eligible,'config':CONFIG,'cap_per_repetition_arm_usd':LIMIT,
            'calibration':calibration,'groups':groups,'paired':paired,'rows':results,
            'source_sha256':{n:sha(OUT/n) for n in ('protocol-freeze.json','calibration.json','generated.json','evaluation.json')},
            'scope':'Prospective matched full-public-scope, spending-cap pilot on one project. Two independent preparations per workflow. Passage refers to the official current task file.'}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    data=reconstruct()
    if args.check:
        import json
        assert read(RESULT)==json.loads(json.dumps(data))
    else:
        dump(RESULT,data)
    print({k:(v['passed'],v['observed'],v['cost']['settled_usd']) for k,v in data['groups'].items()})
