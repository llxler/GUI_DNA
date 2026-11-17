"""Reconstruct matched outcomes and actual compute from raw reports/receipts."""
from collections import Counter, defaultdict
from .core import ROOT, OUT, read, dump, sha, digest, jobs, messages, package_path
from test.history_replay.run import cases_by_file, source_files
from test.replay_hashes import verify_report_hash
from test.ledger_read import calls, totals
from gui_dna.provider import parse_json
from test.webbench_expand.generate import output_files
from test.interface_blind.core import validate_files
import hashlib


def raw_outcome(folder, specs):
    saved = read(folder / 'score.json')
    verify_report_hash(folder / 'report.json', saved['report_sha256'])
    raw = read(folder / 'report.json')
    assert not [e for e in raw.get('errors',[]) if 'maximum allowed failures' not in e.get('message','')]
    cases = cases_by_file(raw)
    assert set(cases).issubset(specs)
    passed = set(cases) == set(specs) and all(v and all(c['passed'] for c in v) for v in cases.values())
    failures = [{'file': name, 'title': c['title']} for name, values in cases.items() for c in values
                if any(s in ('failed','timedOut') for s in c['statuses'])]
    assert passed or failures
    assert passed == saved['all_passed']
    return passed, failures


def reconstruct():
    assert (OUT / 'evaluation-complete.json').exists()
    inputs = read(OUT / 'evaluation-inputs.json')
    complete = read(OUT / 'evaluation-complete.json')
    verify_report_hash(OUT / 'evaluation-inputs.json', complete['inputs_sha256'])
    outcomes, failures = {}, {}
    for key, job in inputs['jobs'].items():
        assert source_files(ROOT / job['page']) == job['files']
        outcomes[key], failures[key] = raw_outcome(OUT / 'scores/heldout' / key, job['specs'])
    rows = [{**r, 'passed': outcomes[r['score_key']] if r['score_key'] else False,
        'failures': failures.get(r['score_key'], [])} for r in inputs['rows']]
    assert len(rows) == len(jobs()) * 6 + 12 * 3
    groups = defaultdict(lambda: {'passed':0, 'total':0})
    project_groups = defaultdict(lambda: {'passed':0, 'total':0})
    for row in rows:
        key = '/'.join((row['method'],row['label'],row['endpoint']))
        groups[key]['total'] += 1; groups[key]['passed'] += row['passed']
        k = '/'.join((row['project'], row.get('builder') or 'no_library',key))
        project_groups[k]['total'] += 1; project_groups[k]['passed'] += row['passed']
    records = []
    ledger_paths=[OUT/'budget.sqlite3']
    continuation=OUT/'continuation.json'
    if continuation.exists():ledger_paths += [ROOT/p for p in read(continuation)['prior_ledgers']]
    all_calls=[r for path in ledger_paths for r in calls(path)]
    ledger_rows = {r['id']:r for r in all_calls}
    assert len(ledger_rows)==len(all_calls),'Copied requests must not duplicate charges'
    usage = defaultdict(lambda: Counter())
    sent_seed_values, public_raw_reports = set(), 0
    for job in jobs():
        folder = ROOT / job['folder']; record = read(folder / 'record.json')
        package = read(package_path(job['project'],job['builder'])) if job['builder'] else None
        assert read(folder / 'messages.json') == messages(job['project'],job['method'],package)
        assert record['status'] == 'complete'
        for attempt in record['attempts']:
            if attempt['version']:
                parsed = parse_json(read(folder / f'output-{attempt["attempt"]}.json')['text'])
                files = validate_files(output_files(job['method'], package, parsed))
                assert {n:hashlib.sha256(v.encode()).hexdigest() for n,v in files.items()} == source_files(folder/attempt['version'])
                key = 'public/' + str(folder.relative_to(OUT / 'runs')) + '/' + attempt['version']
                passes = 0
                for spec in read(OUT / 'inputs.json')['public']:
                    passes += raw_outcome(OUT / 'scores' / key / spec, [spec])[0]
                    public_raw_reports += 1
                assert passes == attempt['public_passes']
        for request_path in folder.rglob('request.json'):
            request = read(request_path); ledger = ledger_rows.pop(request['call_id'])
            method = job['method']; usage[method]['requests'] += 1
            usage[method]['cost_micro_usd'] += ledger['actual'] or 0
            usage[method]['unsettled'] += ledger['actual'] is None
            sent_seed_values.add(request['body'].get('seed'))
            response_path = request_path.with_name('response.json')
            if response_path.exists():
                payload = read(response_path); u = payload['usage']
                usage[method]['length_terminated_responses'] += payload['choices'][0]['finish_reason'] == 'length'
                for k in ('prompt_tokens','completion_tokens'): usage[method][k] += u.get(k,0) or 0
                usage[method]['cached_prompt_tokens'] += (u.get('prompt_tokens_details') or {}).get('cached_tokens',0) or 0
                usage[method]['reasoning_tokens'] += (u.get('completion_tokens_details') or {}).get('reasoning_tokens',0) or 0
                usage[method]['cached_tokens_reported'] += isinstance((u.get('prompt_tokens_details') or {}).get('cached_tokens'),int)
                usage[method]['reasoning_tokens_reported'] += isinstance((u.get('completion_tokens_details') or {}).get('reasoning_tokens'),int)
        records.append({**job, 'responses': len(record['attempts']),
            'first_public_passes': record['attempts'][0]['public_passes'],
            'final_public_passes': record['attempts'][-1]['public_passes'],
            'first_executable': bool(record['attempts'][0]['version']),
            'final_executable': bool(record['attempts'][-1]['version'])})
        for label, attempt in [('first',record['attempts'][0]),('final',record['attempts'][-1])]:
            selected_rows = [r for r in rows if r.get('folder') == job['folder'] and r['label']==label]
            assert {r['endpoint'] for r in selected_rows} == {'current','withheld','history'}
            for row in selected_rows:
                if attempt['version']:
                    scored = inputs['jobs'][row['score_key']]
                    assert source_files(folder/attempt['version']) == scored['files']
                else:
                    assert row['score_key'] is None and not row['passed']
    assert not ledger_rows, 'All requests must be attributed'
    public_summary = {}
    transitions = {}
    method_pairs = {}
    for label in ('first','final'):
        for endpoint in ('current','withheld','history'):
            pairs = defaultdict(dict)
            for row in rows:
                if row['method'] in ('plan','free_lib') and row['label']==label and row['endpoint']==endpoint:
                    key=(row['project'],row['builder'],row['model'],row['seed'])
                    pairs[key][row['method']]=row['passed']
            assert all(set(pair)=={'plan','free_lib'} for pair in pairs.values())
            counts=Counter('both' if p['plan'] and p['free_lib'] else
                'plan_only' if p['plan'] else 'code_only' if p['free_lib'] else 'neither' for p in pairs.values())
            method_pairs[label+'/'+endpoint]={'total':len(pairs),
                **{name:counts[name] for name in ('both','plan_only','code_only','neither')}}
    for method in ('free','free_lib','plan'):
        selected = [r for r in records if r['method'] == method]
        public_summary[method] = {'total':len(selected),
            'first_all_passed':sum(r['first_public_passes']==5 for r in selected),
            'final_all_passed':sum(r['final_public_passes']==5 for r in selected),
            'first_executable':sum(r['first_executable'] for r in selected),
            'final_executable':sum(r['final_executable'] for r in selected),
            'responses':sum(r['responses'] for r in selected),
            'repair_responses':sum(r['responses']-1 for r in selected)}
        for endpoint in ('current','withheld','history'):
            pairs = {}
            for r in rows:
                if r['method']==method and r['endpoint']==endpoint:
                    pairs.setdefault(r['folder'],{})[r['label']]=r['passed']
            transitions[method+'/'+endpoint] = {'improved':sum(not p['first'] and p['final'] for p in pairs.values()),
                'regressed':sum(p['first'] and not p['final'] for p in pairs.values()), 'total':len(pairs)}
    cost=totals(OUT/'budget.sqlite3')
    if len(ledger_paths)>1:
        ledgers={str(p.relative_to(ROOT)):totals(p) for p in ledger_paths}
        assert all(v['stop_usd']==0 for v in ledgers.values())
        cost={'calls':len(all_calls),'settled_usd':sum(r['actual'] or 0 for r in all_calls)/1e6,
            'exposure_usd':sum(r['actual'] if r['actual'] is not None else r['reserved'] for r in all_calls)/1e6,
            'unsettled_calls':sum(r['actual'] is None for r in all_calls),'all_ledgers_closed':True,'ledgers':ledgers}
    return {'posthoc':True,'candidates':len(records),'controls':12,'comparisons':len(rows),
        'unique_hidden_reports':len(outcomes),'public_feedback_reports':public_raw_reports,
        'groups':dict(sorted(groups.items())),'by_project_builder':dict(sorted(project_groups.items())),
        'public_summary':public_summary,'first_final_transitions':transitions,'method_pairs':method_pairs,
        'usage':{m:{**dict(u),'cost_usd':u['cost_micro_usd']/1e6} for m,u in usage.items()},
        'actually_sent_seeds':sorted(sent_seed_values,key=lambda x:str(x)),
        'cost':cost,'records':records,'rows':rows,
        'scope':'Exploratory three-project full-target comparison, one model and two repeated requests. Equal output cap/repair opportunities/public tests, not equal realized compute. Free denominator is 6; same-library denominators are 12. Original libraries saw all public requirements. No novel-source transfer, pure feedback causal estimate, browser-tool agent, or library upper bound.'}


if __name__ == '__main__':
    result = reconstruct(); dump(ROOT/'test/results/matched-feedback.json',result)
    print(result['groups']); print(result['cost'])
