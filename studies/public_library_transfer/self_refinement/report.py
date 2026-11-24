"""Verify a local sealed refinement stage and export anonymous per-target evidence."""
import argparse
from pathlib import Path

from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.public_library_transfer.self_refinement import run
from studies.study_io import ROOT, digest, read, sha

SOURCES=ROOT/'studies/results'
ARMS=('direct_original','self_original','self_refined','fixed_refined')

def cost_of(rows):
    return {'calls':len(rows),'settled_usd':sum(r['actual'] or 0 for r in rows)/1e6,
            'exposure_usd':sum(r['reserved'] if r['actual'] is None else r['actual'] for r in rows)/1e6,
            'unsettled_calls':sum(r['actual'] is None for r in rows)}

def evidence(base, model, project):
    folder=base/model
    rows=ledger_read.calls(folder/'budget.sqlite3')
    receipts={}
    by_id={r['id']:r for r in rows}
    for path in sorted(folder.rglob('request.json')):
        request=read(path)
        call_id=request['call_id']
        call=by_id[call_id]
        if call_id in receipts or call['model']!=request['body']['model']:
            raise ValueError('Request identity mismatch')
        stamp=path.parent/'settled.json'
        response=path.parent/'response.json'
        if stamp.exists():
            if read(stamp)['response_sha256']!=sha(response) or read(stamp)['ticket']!=call_id:
                raise ValueError('Settled response checksum mismatch')
        receipts[call_id]={'purpose':call['purpose'],'status':call['status'],'request_sha256':sha(path),
            'response_sha256':sha(response) if response.exists() else None,
            'receipt_sha256':sha(stamp) if stamp.exists() else None}
    if set(receipts)!=set(by_id): raise ValueError('Ledger and request inventory disagree')
    return {'ledger':ledger_read.totals(folder/'budget.sqlite3'),
            'cost_by_phase':{phase:cost_of([r for r in rows if r['purpose'].startswith(phase+'/'+project+'/')])
                            for phase in ('build','plan')},'calls':list(receipts.values())}

def summarize(rows):
    summary={}
    for arm in ARMS:
        seen=[r for r in rows if r[arm]['passed'] is not None]
        summary[arm]={'passed':sum(r[arm]['passed'] for r in seen),'observed':len(seen),
                      'scheduled':len(rows),'missing_ids':[r['task'] for r in rows if r[arm]['passed'] is None]}
    return summary

def paired(rows, comparator):
    received=[r for r in rows if None not in (r['self_refined']['passed'],r[comparator]['passed'])]
    return {'jointly_observed_ids':[r['task'] for r in received],
            'gained_ids':[r['task'] for r in received if r['self_refined']['passed'] and not r[comparator]['passed']],
            'lost_ids':[r['task'] for r in received if not r['self_refined']['passed'] and r[comparator]['passed']]}

def model_report(root, key, model, project, original):
    folder=root/key
    seal=read(folder/'seal.json')
    build=read(folder/'build/status.json')
    assert seal['registered_sha256']==sha(root/'registered.json')
    assert seal['build_sha256']==sha(folder/'build/status.json')
    assert seal['model']==model
    if build['status']=='valid':
        assert build['package_sha256']==sha(folder/'build/package.json')
        browser.verify_page(folder/'build'/(build['selected']+'-page'),build['first_files'],project)
    for name in ('public.json','browser.json'):
        expected=sha(root/name)
        matching=[h for n,h in original['registration_inputs'].items() if n.endswith('/'+project+'/'+name)]
        if matching!=[expected]: raise ValueError('Original and staged benchmark contracts differ')
    source={}
    for r in original['models'][model]['rows']:
        if r['project']==project and r['arm'] in ('direct','self'):
            name=r['arm']+'_original'
            if (r['task'],name) in source: raise ValueError('Repeated original target')
            source[r['task'],name]={k:r[k] for k in ('status','passed','response_sha256','report_sha256') if k in r}
    scores=read(folder/'scores.json')
    contract=read(root/'browser.json')
    assert contract==browser.verify_contract(project)
    for r in scores:
        task=r['task']
        arm=r['arm']
        assert sha(folder/'plans'/str(task)/'status.json')==seal['plans'][str(task)]
        plan=read(folder/'plans'/str(task)/'status.json')
        expect=plan if arm=='self' else build
        assert r['status']==expect['status']
        if r['status']=='valid':
            page,files=((folder/'plans'/str(task)/'page',plan['files']) if arm=='self' else
                        (folder/'build'/(build['selected']+'-page'),build['first_files']))
            browser.verify_page(page,files,project)
            assert digest(files)==r['files_sha256']
            expected={'project':project,'task':task,'files_digest':digest(files),'contract_digest':digest(contract)}
            p=root/'browser/scores'/project/f'task-{task}'/digest(files)/'score.json'
            verified=browser.verify_receipt(root,p,expected)
            assert verified['report_sha256']==r['report_sha256'] and verified['passed']==r['passed']
        elif r['status']=='invalid': assert r['passed'] is False
        elif r['status']=='missing': assert r['passed'] is None
        else: raise ValueError('Unknown outcome')
        name=('self_refined' if arm=='self' else 'fixed_refined')
        if (task,name) in source: raise ValueError('Repeated candidate target')
        source[task,name]={k:v for k,v in r.items() if k not in ('arm','task','report')}
        if arm=='self':
            answer=folder/'plans'/str(task)/'response.json'
            source[task,name]['response_sha256']=sha(answer) if answer.exists() else None
            if 'plan' in plan: source[task,name]['plan']=plan['plan']
    ordered=[{'task':i,**{arm:source[i,arm] for arm in ARMS}} for i in range(1,21)]
    assert len(source)==80
    stages={p.stem:read(p) for p in sorted((folder/'build').glob('*-public-check.json'))}
    return {'seal_sha256':sha(folder/'seal.json'),'build':build,
            'public_checks':{k:{'load_errors':v['load_errors'],'probe':v['probe']} for k,v in stages.items()},
            'summary':summarize(ordered),'paired_refined_to':{a:paired(ordered,a) for a in ARMS if a!='self_refined'},
            'rows':ordered,**evidence(root,key,project)}

def report(root, destination, check):
    reg=read(root/'registered.json')
    for n,h in reg['files'].items(): assert sha(ROOT/n)==h
    project=reg['project']
    files={'table':{'qwen9':'extension','oss':'matrix'},'form':{'qwen9':'form','oss':'form'}}
    sources={key:SOURCES/f'backbone-{files[project][key]}-20261124.json' for key in reg['models']}
    result={'study':'Prospective staged Self construction','registered_utc':reg['utc'],'generation_deadline':reg['end'],
        'registration_sha256':sha(root/'registered.json'),'project':project,'upstream_commit':browser.UPSTREAM_COMMIT,
        'public_input_sha256':sha(root/'public.json'),'browser_contract_sha256':sha(root/'browser.json'),
        'protocol_sha256':sha(run.HERE/'PROTOCOL.md'),'tasks':reg['tasks'],'allocation_usd':reg['budget_usd'],
        'historical_sources':{key:{'path':str(p.relative_to(ROOT)),'sha256':sha(p)} for key,p in sources.items()},
        'models':{model:model_report(root,key,model,project,read(sources[key])) for key,(model,*_) in reg['models'].items()}}
    protocols=[Path(n) for n in reg['files'] if n.endswith('/PROTOCOL.md')]
    if len(protocols)!=1: raise ValueError('Unexpected number of preregistered method protocols')
    result['protocol_sha256']=sha(ROOT/protocols[0])
    if 'line_contract' in protocols[0].parts:
        result['study']='Prospective line-contract Self construction'
    extra=root/'transfer-protocol.json'
    if extra.exists() and read(extra).get('stage')=='normalized-first-design':
        details=read(extra)
        result['study']='First-design punctuation normalization with same-model implementation'
        result['normalization']={'registered_supplement_sha256':sha(extra),'unicode_version':details['unicode_version'],
                                 'source_root':details['source_root'],'files':details['files']}
        for n,h in details['files'].items(): assert sha(ROOT/n)==h
    if check:
        if result!=read(destination): raise ValueError('Published report differs from verified records')
    else: core.save(destination,result)
    return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=run.OUT)
    parser.add_argument('--output',type=Path,default=SOURCES/'self-refinement-20261124.json')
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    value=report(args.root.resolve(),args.output,args.check)
    for k,v in value['models'].items(): print(k,v['summary'],v['ledger'])

if __name__=='__main__': main()
