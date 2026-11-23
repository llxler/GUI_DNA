"""Verify the frozen trial, summarize target-matched results and write its public JSON."""
import argparse
from collections import Counter
from itertools import combinations

from studies.ledger_read import calls, totals
from studies.study_io import ROOT, digest, dump, read, sha, source_files
from studies.table_library_sources.core import AI, ARMS, CONTROLLERS, HERE, MODEL, MODULES, OUT, SOURCE, TASKS
from studies.table_library_sources.run import CAP, CONTROLS, verify

DESTINATION = ROOT / 'studies/results/table-library-sources-20261123.json'


def paired(left, right, tasks):
    both = [t for t in tasks if left[t] is not None and right[t] is not None]
    return {'observed': len(both), 'left_pass': sum(left[t] for t in both),
            'right_pass': sum(right[t] for t in both),
            'both_pass': sum(left[t] and right[t] for t in both),
            'left_only': [t for t in both if left[t] and not right[t]],
            'right_only': [t for t in both if not left[t] and right[t]],
            'both_fail': sum(not left[t] and not right[t] for t in both)}


def protocol_summary(scores, valid, controls):
    common = [t for t in TASKS if all(scores[a][t] is not None for a in ARMS)]
    calibrated = [t for t in common if controls['upstream_final'][t] and not controls['starter'][t]]
    return {'shared_observed_targets': common,
            'by_arm_common': {a: {'passed': sum(scores[a][t] for t in common),
                         'valid_artifacts': sum(valid[a][t] for t in common),
                         'observed': len(common)} for a in ARMS},
            'by_arm_available': {a: {'passed': sum(v is True for v in scores[a].values()),
                         'valid_artifacts': sum(valid[a].values()),
                         'observed': sum(v is not None for v in scores[a].values())} for a in ARMS},
            'paired': {f'{a}_vs_{b}': paired(scores[a], scores[b], TASKS) for a,b in combinations(ARMS, 2)},
            'calibrated_shared_targets': calibrated,
            'by_arm_calibrated_common': {a: {'passed': sum(scores[a][t] for t in calibrated),
                     'observed': len(calibrated)} for a in ARMS},
            'task_plan_vs_fixed_library_example': {a: paired(scores[a], controls[c], TASKS)
                    for a,c in [('reference','reference_full'), ('ai','ai_example2')]}}


def ledger_by_arm(rows, records):
    result = {}
    receipts = {}
    for rec in records:
        call = OUT / 'candidates' / rec['arm'] / rec['task'] / rec['stage'] / 'call'
        request = call / 'request.json'
        if request.exists():
            req = read(request)
            assert req['body']['model'] == MODEL and digest(req['body']['messages']) == rec['prompt_sha256']
            if rec['stage'] == 'first':
                assert req['body']['messages'] == read(OUT / 'inputs' / rec['arm'] / (rec['task'] + '.json'))
            resp = read(call / 'response.json') if rec['generated'] else None
            receipts[req['call_id']] = resp
    assert set(receipts) == {r['id'] for r in rows}
    for a in ARMS:
        selected = [r for r in rows if r['purpose'].startswith(a + '-')]
        amounts = [r['actual'] if r['actual'] is not None else r['reserved'] for r in selected]
        tokens = Counter()
        providers = Counter()
        finishes = Counter()
        for r in selected:
            resp = receipts[r['id']]
            if resp is None:
                assert r['actual'] is None
            else:
                assert r['actual'] is not None
                for key in ('prompt_tokens','completion_tokens'):
                    tokens[key] += resp['usage'][key]
                providers[resp.get('provider','unspecified')] += 1
                finishes[resp['choices'][0]['finish_reason']] += 1
        result[a] = {'requests': len(selected), 'settled_usd': sum(r['actual'] or 0 for r in selected) / 1e6,
                'exposure_usd': sum(amounts) / 1e6, 'unsettled_calls':sum(r['actual'] is None for r in selected),
                'billed_tokens': dict(tokens), 'providers': dict(providers), 'finish_reasons': dict(finishes)}
    return result


def historical_build_cost():
    base = AI.parents[3]
    ledger = {r['id']: r for r in calls(base / 'budget.sqlite3')}
    records = [ledger[read(p)['call_id']] for p in sorted(base.glob('**/table/openai__gpt-5/**/request.json'))]
    assert records and all(r['model'] == 'openai/gpt-5' for r in records)
    return {'model': 'openai/gpt-5', 'source': 'all public table requirements; no reference assets or official tests',
            'calls': len(records), 'settled_usd': sum(r['actual'] or 0 for r in records) / 1e6,
            'unsettled_calls': sum(r['actual'] is None for r in records),
            'exposure_usd': sum(r['actual'] if r['actual'] is not None else r['reserved'] for r in records) / 1e6}


def runtime_provenance():
    runtime = ROOT / 'artifacts/webbench-expand-runtime-157'
    historical_manifest = ROOT / 'artifacts/webbench-expand-harness-157/manifest.json'
    historical = read(historical_manifest)
    hashes = {n: sha(runtime / 'test-util' / n) for n in ('index.js', 'css.js')}
    version = read(runtime / 'node_modules/@playwright/test/package.json')['version']
    assert version == historical['playwright_version'] == '1.57.0'
    assert hashes == historical['utility_files_sha256']
    assert historical['runtime_lock_sha256'] == sha(runtime / 'package-lock.json')
    return {'playwright': version, 'browser': 'chromium', 'runtime_lock_sha256': historical['runtime_lock_sha256'],
            'test_utility_sha256':hashes,'prior_runtime_manifest_sha256':sha(historical_manifest)}


def report():
    freeze = read(OUT / 'freeze.json')
    generation = read(OUT / 'generation-complete.json')
    verify(freeze['inputs_sha256'])
    verify(generation['files_sha256'])
    assert sha(OUT / 'freeze.json') == generation['freeze_sha256']
    controls_saved = read(OUT / 'controls-complete.json')['rows']
    scored = read(OUT / 'scores-complete.json')['rows']
    record_list = generation['rows']
    assert len(record_list) == len({(r['arm'],r['task'],r['stage']) for r in record_list})
    indexed = {(r['arm'],r['task'],r['stage']):r for r in record_list}
    assert {(r['arm'],r['task']) for r in record_list if r['stage']=='first'} == {(a,t) for a in ARMS for t in TASKS}
    expected_repairs = {(r['arm'],r['task']) for r in record_list if r['stage']=='first' and r['generated'] and not r['valid']}
    assert expected_repairs == {(r['arm'],r['task']) for r in record_list if r['stage']=='repair'}
    assert set(scored) == {f"{r['arm']}/{r['task']}/{r['stage']}" for r in record_list if r['valid']}
    assert set(controls_saved) == {f'{c}/{t}' for c in CONTROLS for t in TASKS}

    def grade(folder, stored, key):
        value = stored[key]
        report_path = OUT / folder / key / 'report.json'
        assert sha(report_path) == value['report_sha256']
        score = read(report_path.with_name('score.json'))
        assert score['all_passed'] == value['passed'] and score['report_sha256'] == value['report_sha256']
        assert set(score['tests']) == {next(p for p in key.split('/') if p.startswith('task-'))}
        return value['passed']

    controls = {c:{t:grade('calibration', controls_saved, f'{c}/{t}') for t in TASKS} for c in CONTROLS}
    scores = {s:{a:{} for a in ARMS} for s in ('first','after_public_repair')}
    valid = {s:{a:{} for a in ARMS} for s in scores}
    targets = {}
    for task in TASKS:
        targets[task] = {}
        for arm in ARMS:
            initial = indexed[arm,task,'first']
            repair = indexed.get((arm,task,'repair'))
            info = {}
            for name,rec in [('first',initial), ('after_public_repair',repair or initial)]:
                exact = f"{arm}/{task}/{rec['stage']}"
                passed = grade('scores', scored, exact) if rec['valid'] else (False if rec['generated'] else None)
                scores[name][arm][task] = passed
                valid[name][arm][task] = rec['valid']
                info[name] = {'response': rec['generated'], 'valid': rec['valid'], 'passed': passed,
                    'artifact_stage': rec['stage'], 'page_manifest_sha256': digest(rec['files_sha256']) if rec['valid'] else None,
                    'official_report_sha256': scored[exact]['report_sha256'] if rec['valid'] else None}
            targets[task][arm] = info
        targets[task]['fixed_pages'] = {c:{'passed':controls[c][task],
                 'official_report_sha256': controls_saved[f'{c}/{task}']['report_sha256']} for c in CONTROLS}

    ledger = totals(OUT / 'budget.sqlite3')
    assert ledger['cap_usd'] == CAP and ledger['exposure_usd'] <= CAP
    return {'study': 'table-library-sources-20261123', 'project':'table', 'upstream_revision':freeze['upstream_revision'],
        'model': MODEL, 'task_unit':'individual current official file', 'planned_unique_targets':len(TASKS),
        'protocol': 'Frozen independent requirement-prefix generation on shared public starter; first response and at most one public format/compiler repair.',
        'primary_endpoint':'first', 'freeze_utc':freeze['frozen_utc'], 'generation_closed_utc':generation['frozen_utc'],
        'provenance': {'reference': {'description':'Upstream human-authored modules plus an agent-prepared binding from their reference entry point.',
             'public_starter_files':source_files(SOURCE / 'src-init'), 'production_modules':list(MODULES),
             'production_module_utf8_bytes':sum((SOURCE / f'src/common/{m}.js').stat().st_size for m in MODULES),
             'reference_stylesheet_utf8_bytes':(SOURCE / 'src/index.css').stat().st_size,
             'binding_sha256':sha(HERE / 'compiler.js'), 'binding_utf8_bytes':(HERE / 'compiler.js').stat().st_size,
             'controllers':list(CONTROLLERS),'controller_subsets':2**len(CONTROLLERS),
             'upstream_human_person_hours':None,'observed_agent_preparation_wall_seconds_including_runner_protocol':freeze['agent_preparation_elapsed_seconds']},
             'ai': {'package_sha256':sha(AI), 'construction':historical_build_cost()},
             'direct': {'inputs':'Public starter files and requirements through current target; no library or previous candidate.'}},
        'summaries': {s:protocol_summary(scores[s],valid[s],controls) for s in scores},
        'fixed_page_controls': {c: {'passed':sum(controls[c].values()),'observed':len(TASKS),
                      'page_manifest_sha256':digest(source_files(OUT / 'control-pages' / c))} for c in CONTROLS},
        'responses': {a: {st:{'attempted_positions':sum(r['arm']==a and r['stage']==st for r in record_list),
                        'received':sum(r['arm']==a and r['stage']==st and r['generated'] for r in record_list),
                        'valid':sum(r['arm']==a and r['stage']==st and r['valid'] for r in record_list)}
                        for st in ('first','repair')} for a in ARMS},
        'planning_ledger':ledger,'cost_by_arm':ledger_by_arm(calls(OUT / 'budget.sqlite3'),record_list),
        'targets':targets, 'evaluation_runtime':runtime_provenance(), 'audit_sha256':{n:sha(OUT / n) for n in ('freeze.json','generation-complete.json',
                                                                  'controls-complete.json','scores-complete.json')}}


def check_public(value):
    assert tuple(value['targets']) == TASKS
    assert value['model'] == MODEL
    controls = {c:{t:value['targets'][t]['fixed_pages'][c]['passed'] for t in TASKS} for c in CONTROLS}
    for c, outcomes in controls.items():
        assert value['fixed_page_controls'][c]['observed'] == len(TASKS)
        assert value['fixed_page_controls'][c]['passed'] == sum(outcomes.values())
    for stage in ('first','after_public_repair'):
        scores = {a:{t:value['targets'][t][a][stage]['passed'] for t in TASKS} for a in ARMS}
        valid = {a:{t:value['targets'][t][a][stage]['valid'] for t in TASKS} for a in ARMS}
        assert protocol_summary(scores, valid, controls) == value['summaries'][stage]
    amounts = value['cost_by_arm'].values()
    for field in ('exposure_usd', 'settled_usd', 'unsettled_calls'):
        assert abs(sum(arm[field] for arm in amounts) - value['planning_ledger'][field]) < 1e-9
    assert value['planning_ledger']['exposure_usd'] <= value['planning_ledger']['cap_usd'] == CAP


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--write', action='store_true')
    group.add_argument('--check', action='store_true')
    group.add_argument('--check-public', action='store_true')
    ns = parser.parse_args()
    value = read(DESTINATION) if ns.check_public else report()
    check_public(value)
    if ns.write:
        if DESTINATION.exists() and read(DESTINATION)!=value:
            raise SystemExit('Existing public result differs; preserve it for audit')
        dump(DESTINATION,value)
    elif value != read(DESTINATION):
        raise SystemExit('Public result differs from the verified ledger and raw reports')
    print({s:p['by_arm_common'] for s,p in value['summaries'].items()})
    print(value['planning_ledger'])
