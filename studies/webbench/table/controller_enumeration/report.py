"""Recompute exact uniform subset expectations and controller effects."""
import argparse
from fractions import Fraction

from studies.study_io import ROOT, digest, dump, read, sha, source_files
from studies.table_library_sources.core import CONTROLLERS, TASKS
from studies.table_library_sources.run import verify
from .run import MASKS, OUT, RESULTS, key

DEST = ROOT/'studies/results/table-controller-enumeration-20261123.json'


def summarize(outcomes):
    rows={}
    passed=0
    observed=0
    for t in TASKS:
        vals=outcomes[t]
        assert len(vals)==len(MASKS) and all(v is None or type(v) is bool for v in vals)
        k=sum(v is True for v in vals)
        count=sum(v is not None for v in vals)
        rows[t]={'passing':k,'observed':count,'possible':len(MASKS),
                 'exact_uniform_probability':k/len(MASKS) if count==len(MASKS) else None,
                 'uniform_probability_bounds':[k/len(MASKS),(k+len(MASKS)-count)/len(MASKS)]}
        passed+=k
        observed+=count
    size=len(MASKS)*len(TASKS)
    effects={}
    for i,controller in enumerate(CONTROLLERS):
        affected={}
        bit=1<<i
        for t in TASKS:
            counts={'off_fail_on_pass':0,'off_pass_on_fail':0,'same_pass':0,'same_fail':0,'missing':0}
            for mask in MASKS:
                if mask&bit:
                    continue
                off,on=outcomes[t][mask],outcomes[t][mask|bit]
                if off is None or on is None:
                    cat='missing'
                elif off==on:
                    cat='same_pass' if off else 'same_fail'
                else:
                    cat='off_fail_on_pass' if on else 'off_pass_on_fail'
                counts[cat]+=1
            assert sum(counts.values())==len(MASKS)//2
            affected[t]=counts
        effects[controller]=affected
    return {'targets':rows,'settled_positions':observed,'planned_positions':size,'passing_positions':passed,
            'expected_tasks_passed_out_of_20':passed/len(MASKS) if observed==size else None,
            'expected_tasks_passed_bounds':[passed/len(MASKS),(passed+size-observed)/len(MASKS)],
            'uniform_pass_probability':passed/size if observed==size else None,
            'uniform_pass_fraction':str(Fraction(passed,size)) if observed==size else None,
            'one_controller_effects':effects}


def report(partial):
    manifest=read(OUT/'freeze.json')
    verify(manifest['inputs_sha256'])
    complete=OUT/'complete.json'
    if not partial and not complete.exists():
        raise SystemExit('Enumeration still running; use --progress to see bounded estimates')
    records=read(complete)['rows'] if complete.exists() else {}
    if complete.exists():
        assert set(records)=={key(m,t) for t in TASKS for m in MASKS}
        assert read(complete)['frozen_sha256']==sha(OUT/'freeze.json')
    outcomes={}
    checksums={}
    reused=0
    observed=0
    for mask in MASKS:
        path=OUT/'pages'/f'config-{mask:02d}'
        assert source_files(path)==manifest['pages_sha256'][str(mask)]
    for t in TASKS:
        outcomes[t]=[]
        checksums[t]=[]
        for mask in MASKS:
            name=key(mask,t)
            old=manifest['reused'].get(name)
            if old:
                assert source_files(ROOT/old['page'])==manifest['pages_sha256'][str(mask)]
            path=ROOT/old['raw_dir'] if old else OUT/'scores'/name
            if not (path/'score.json').exists():
                assert not records
                outcomes[t].append(None)
                checksums[t].append(None)
                continue
            score=read(path/'score.json')
            assert score['report_sha256']==sha(path/'report.json') and set(score['tests'])=={t}
            val=score['all_passed']
            if records:
                assert records[name]=={'passed':val,'report_sha256':score['report_sha256'],'reused':bool(old)}
            reused+=bool(old)
            observed+=1
            outcomes[t].append(val)
            checksums[t].append(score['report_sha256'])
    result=summarize(outcomes)
    published=read(RESULTS)
    ref={t:published['targets'][t]['reference']['first']['passed'] for t in TASKS}
    full={t:outcomes[t][-1] for t in TASKS}
    assert full=={t:published['targets'][t]['fixed_pages']['reference_full']['passed'] for t in TASKS}
    assert result['settled_positions']==observed
    return {'study':'table-controller-enumeration-20261123','project':'table','post_hoc':True,
            'scope':'Every legal subset of six frozen reference controllers, graded once per individual official file.',
            'model_calls':0,'additional_api_cost_usd':0,'controller_bit_order':list(CONTROLLERS),
            'planned_masks':len(MASKS),'planned_tasks':len(TASKS),'frozen_utc':manifest['frozen_utc'],
            'exactly_reused_prior_reports':reused,'new_browser_reports':observed-reused,
            'targets':result['targets'],'uniform':{k:v for k,v in result.items() if k not in ('targets','one_controller_effects')},
            'one_controller_effects':result['one_controller_effects'],
            'comparators':{'first_task_conditioned_reference_plan':{'passed':sum(ref.values()),'observed':len(ref)},
                           'fixed_all_enabled':{'passed':sum(full.values()),'observed':len(full)}},
            'outcomes_by_task_in_mask_order':outcomes,
            'evidence':{'paper_trial_sha256':sha(RESULTS),'freeze_sha256':sha(OUT/'freeze.json'),
                        'complete_marker_sha256':sha(complete) if complete.exists() else None,
                        'page_hashes_in_mask_order':[digest(manifest['pages_sha256'][str(m)]) for m in MASKS],
                        'report_hashes_by_task_in_mask_order':checksums,
                        'report_vector_sha256':{t:digest(v) for t,v in checksums.items()}}}


def check_public(value):
    x=summarize(value['outcomes_by_task_in_mask_order'])
    assert x['targets']==value['targets'] and x['one_controller_effects']==value['one_controller_effects']
    assert value['uniform']=={k:v for k,v in x.items() if k not in ('targets','one_controller_effects')}
    assert value['new_browser_reports']+value['exactly_reused_prior_reports']==x['settled_positions']
    evidence=value['evidence']
    assert len(evidence['page_hashes_in_mask_order'])==len(MASKS)
    for t,hashes in evidence['report_hashes_by_task_in_mask_order'].items():
        assert len(hashes)==len(MASKS) and all(isinstance(h,str) and len(h)==64 for h in hashes)
        assert digest(hashes)==evidence['report_vector_sha256'][t]
    assert x['settled_positions']==len(TASKS)*len(MASKS)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    for mode in ['write','check','check-public','progress']:
        group.add_argument('--'+mode,action='store_true')
    args=parser.parse_args()
    value=read(DEST) if args.check_public else report(args.progress)
    if not args.progress:
        check_public(value)
    if args.write:
        if DEST.exists() and read(DEST)!=value:
            raise SystemExit('Existing result differs; preserve prior data')
        dump(DEST,value)
    elif args.check:
        assert read(DEST)==value
    print(value['uniform'])
