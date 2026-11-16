"""Reconstruct November 16 raw observations and verify both frozen boundaries."""
import argparse
from pathlib import Path
from test.history_replay.run import ROOT, read, dump, sha
from test.replay_hashes import verify_report_hash
from test.matched_feedback.analyze import reconstruct as feedback, raw_outcome
from test.schema_search.analyze import reconstruct as search, scoring_out
from test.matched_feedback_frontier.analyze import reconstruct as frontier_feedback, effective_out
from test.compiler_reuse_audit.analyze import reconstruct as reuse_audit
from test.authorized_costs import summarize
from collections import Counter,defaultdict


def verify_snapshots(original_only=False):
    count = 0
    entries=[('matched-feedback-20261116',('snapshot.json','candidate-snapshot.json')),
                         ('schema-search-20261116',('snapshot.json',)),
                         ('matched-feedback-frontier-20261116',('snapshot.json','shared-dependencies.json')),
                         ('compiler-reuse-audit-20261116',('snapshot.json',))]
    entries.append((effective_out().name,('candidate-snapshot.json',)))
    if scoring_out('bom').name!='schema-search-20261116':entries.append((scoring_out('bom').name,('snapshot.json',)))
    if effective_out().name!='matched-feedback-frontier-20261116':entries.append((effective_out().name,('snapshot.json',)))
    for stage, names in entries:
        for name in names:
            snapshot = read(ROOT/'artifacts'/stage/name)
            for path, expected in snapshot['sha256'].items():
                if original_only: assert sha(ROOT/path)==expected, path
                else: verify_report_hash(ROOT/path,expected)
            count += 1
    return count


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source-integrity',action='store_true');args=parser.parse_args()
    snapshots=verify_snapshots(args.source_integrity)
    if args.source_integrity:
        print('Original snapshots verified:',snapshots);return
    matched=feedback(); bounded=search(); frontier=frontier_feedback(); reuse=reuse_audit(True); calibration=[]
    base=ROOT/'artifacts/matched-feedback-20261116'
    specs={'public':['init','task-4','task-8','task-12','task-16'],
        'withheld':[f'task-{i}' for i in range(1,21) if i%4 or i==20],
        'history':['init',*[f'task-{i}' for i in range(1,21)]],
        'blank-init':['init'],'blank-history':['init',*[f'task-{i}' for i in range(1,21)]]}
    for row in read(base/'calibration.json'):
        passed,_=raw_outcome(base/'calibration'/row['project']/row['label'],specs[row['label']])
        assert passed==row['expected']==row['all_passed'];calibration.append(row)
    strong=effective_out()
    for row in read(strong/'calibration.json'):
        passed,_=raw_outcome(strong/'calibration'/row['project']/row['label'],specs[row['label']])
        assert passed==row['expected']==row['all_passed'];calibration.append({'stage':'frontier',**row})
    other=ROOT/'artifacts/schema-search-20261116'
    for project in ('calculator','table','bom'):
        for label,tests,expected in [('current',['task-20'],True),('history',specs['history'],True),('blank',['task-20'],False)]:
            passed,_=raw_outcome(other/'calibration'/project/label,tests)
            if project=='bom' and label=='blank':
                assert passed and not expected
            else:assert passed==expected
            calibration.append({'stage':'schema-search','project':project,'label':label,'all_passed':passed,'expected':expected,
                'calibration_exception':project=='bom' and label=='blank'})
    continued=scoring_out('bom')
    passed,_=raw_outcome(continued/'calibration/bom/blank-history',specs['history'])
    assert not passed
    calibration.append({'stage':'schema-search-continue','project':'bom','label':'blank-history','all_passed':passed,'expected':False})
    import subprocess,json
    probe=read(continued/'matcher-probe.json')
    rerun=subprocess.run(['node','-e',probe['script'],str(ROOT/probe['runtime'])],check=True,capture_output=True,text=True)
    assert json.loads(rerun.stdout)==probe['result']=={'null_passes':True,'undefined_passes':False}
    assert matched==read(ROOT/'test/results/matched-feedback.json')
    assert bounded==read(ROOT/'test/results/schema-search.json')
    assert frontier==read(ROOT/'test/results/matched-feedback-frontier.json')
    assert reuse==read(ROOT/'test/results/compiler-reuse-audit.json')
    costs=summarize('20261116')
    assert costs==read(ROOT/'test/results/review-20261116-costs.json')
    assert all(s['stop_usd']==0 for s in costs['stages'].values())
    # The added cohort is generated before new matched hidden outcomes are inspected;
    # BOM search follows both matched scoring queues.
    base_stage=ROOT/'artifacts/matched-feedback-20261116'
    original_frontier=ROOT/'artifacts/matched-feedback-frontier-20261116'
    frontier_stage=effective_out()
    assert read(base_stage/'generation-complete.json')['finished_utc'] <= read(original_frontier/'generation-started.json')['started_utc']
    if frontier_stage!=original_frontier:
        assert read(original_frontier/'generation-started.json')['started_utc'] <= read(frontier_stage/'generation-started.json')['started_utc']
    assert read(frontier_stage/'generation-complete.json')['finished_utc'] <= read(base_stage/'grading-started.json')['started_utc']
    assert read(base_stage/'evaluation-complete.json')['finished_utc'] <= read(frontier_stage/'grading-started.json')['started_utc']
    assert read(frontier_stage/'evaluation-complete.json')['finished_utc'] <= read(scoring_out('bom')/'grading-started-bom.json')['started_utc']
    figure=read(ROOT/'test/results/history-endpoint-figure.json')
    verify_report_hash(ROOT/figure['source'],figure['source_sha256'])
    expansion=[r for r in read(ROOT/figure['source'])['rows'] if r['cohort']=='expansion' and r['label']=='final']
    sensitivity={}
    for method in ('free','free_lib','plan'):
        chosen=[r for r in expansion if r['method']==method]
        excluded=[r for r in chosen if r['project']=='bom' and r['task']=='task-20']
        retained=[r for r in chosen if not(r['project']=='bom' and r['task']=='task-20')]
        sensitivity[method]={'original':{'passed':sum(r['old_current_passed'] for r in chosen),'total':len(chosen)},
            'excluded':{'passed':sum(r['old_current_passed'] for r in excluded),'total':len(excluded)},
            'retained':{'passed':sum(r['old_current_passed'] for r in retained),'total':len(retained)}}
    history=[r for r in expansion if r['method'] in ('plan','free_lib')]
    pairs=defaultdict(dict)
    for row in history:pairs[(row['project'],row['builder'],row['model'],row['task'])][row['method']]=row
    for endpoint in ('old_current_passed','history_passed'):
        observed=dict(Counter(('both' if p['plan'][endpoint] and p['free_lib'][endpoint] else
            'plan_only' if p['plan'][endpoint] else 'code_only' if p['free_lib'][endpoint] else 'neither') for p in pairs.values()))
        assert observed==figure['paired_outcomes'][endpoint]
    for row in figure['rows']:
        chosen=sorted([r for r in history if all(r[k]==row[k] for k in ('project','builder','method','model'))],key=lambda r:int(r['task'].split('-')[1]))
        assert row['states']==[int(r['old_current_passed'])+2*int(r['history_passed']) for r in chosen]
    names=('Neither endpoint','Current file only','Full history only','Both endpoints')
    assert figure['counts']=={name:sum(r['states'].count(i) for r in figure['rows']) for i,name in enumerate(names)}
    result={'snapshots':snapshots,'calibration_reports':len(calibration),'calibration':calibration,
        'matched_feedback':{k:v for k,v in matched.items() if k not in ('rows','records')},
        'matched_feedback_frontier':{k:v for k,v in frontier.items() if k not in ('rows','records')},
        'compiler_reuse_audit':{k:v for k,v in reuse.items() if k!='rows'},
        'history_endpoint_figure':{k:figure[k] for k in ('cells','counts','paired_outcomes')},
        'bom_task20_posthoc_sensitivity':{'groups':sensitivity,
            'scope':'Exclude the newly identified weak current-file test from every original main method. Stored scores unchanged; this does not correct or certify all remaining assertions.'},
        'schema_search':{k:v for k,v in bounded.items() if k!='rows'},'costs':costs,
        'scope':'Reconstruct raw new reports, recompile matched candidates, reconstruct schema-only search population and read original ledgers. Not fresh browser execution. Original and anonymous bytes use explicit hash mapping.'}
    dump(ROOT/'test/results/nov16-replay.json',result)
    print('Replayed matched feedback and bounded schema search; snapshots',snapshots)


if __name__=='__main__':main()
