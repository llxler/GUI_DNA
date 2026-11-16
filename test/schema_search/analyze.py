"""Reconstruct bounded-search populations and raw outcomes without API calls."""
from collections import Counter, defaultdict
import hashlib
import subprocess
from .run import ROOT, OUT, read, dump, digest, source_files
from .population import select
from test.matched_feedback.analyze import raw_outcome
from test.replay_hashes import verify_report_hash
from test.webbench_expand.core import compile_plan


def scoring_out(project):
    resumed=ROOT/'artifacts/schema-search-continue-20261116'
    return resumed if project=='bom' and (resumed/'continuation.json').exists() else OUT


def reconstruct():
    inputs = read(OUT/'inputs.json')
    for project in ('calculator','table','bom'):
        complete = read(scoring_out(project)/f'evaluation-complete-{project}.json')
        verify_report_hash(OUT/'inputs.json',complete['inputs_sha256'])
    libraries = []
    recompiled = 0
    for library in inputs['libraries']:
        saved = read(ROOT/library['pool']); package = read(ROOT/library['package'])
        regenerated = select(package['plan_schema'],saved['anchors'])
        # JSON represents tuple paths as lists; compare canonical serializations.
        assert digest(regenerated) == digest(saved)
        for key in saved['selected']:
            selected_rows=[r for r in inputs['rows'] if r['project']==library['project'] and
                r['builder']==library['builder'] and r['plan_key']==key]
            assert {r['endpoint'] for r in selected_rows}=={'current','history'}
            try:
                files=compile_plan(package,saved['pool'][key]['plan'])
            except (ValueError,KeyError,TypeError,TimeoutError,subprocess.TimeoutExpired) as error:
                expected=f'{type(error).__name__}: {error}'[:2000]
                assert all(r['compile_error']==expected and r['score_key'] is None for r in selected_rows)
            else:
                hashes={name:hashlib.sha256(value.encode()).hexdigest() for name,value in files.items()}
                assert all(not r['compile_error'] and inputs['jobs'][r['score_key']]['files']==hashes for r in selected_rows)
                recompiled+=1
        libraries.append({**library, 'rejected_proposals':len(saved['rejected']),
            'distinct_anchors':len({digest(x) for x in saved['anchors']})})
    outcomes, failures = {}, {}
    for key, job in inputs['jobs'].items():
        assert source_files(ROOT/job['page']) == job['files']
        outcomes[key], failures[key] = raw_outcome(scoring_out(job['project'])/'scores'/key,job['specs'])
    groups = defaultdict(lambda:{'passed':0,'total':0,'compile_failed':0})
    rows = []
    for row in inputs['rows']:
        value = outcomes[row['score_key']] if row['score_key'] else False
        key = '/'.join((row['project'],row['builder'],row['endpoint']))
        groups[key]['total'] += 1; groups[key]['passed'] += value
        groups[key]['compile_failed'] += bool(row['compile_error'])
        rows.append({**row,'passed':value,'failures':failures.get(row['score_key'],[])})
    return {'posthoc':True,'libraries':libraries,'configurations':len(rows)//2,'comparisons':len(rows),
        'unique_reports':len(outcomes),'recompiled_configurations':recompiled,
        'calibration_exception':{'project':'bom','blank_current_passes':True,
            'reason':'Missing content iframe is null, satisfies toBeDefined, and returns before feature assertions.',
            'continuation':str(scoring_out('bom').relative_to(ROOT))},'groups':dict(sorted(groups.items())),'rows':rows,
        'scope':'Five libraries; deterministic bounded single-change search around three anchors, including non-Boolean values, optional omission/insertion and arrays. Task-20 current and complete-history endpoints only. BOM current-file passes include a known vacuous-test risk and are not feature-correctness witnesses alone. No uniform full-schema sampling or impossibility bound. Original 53/120 and 14/120 witness snapshots unchanged.'}


if __name__=='__main__':
    result=reconstruct();dump(ROOT/'test/results/schema-search.json',result)
    print(result['groups'])
