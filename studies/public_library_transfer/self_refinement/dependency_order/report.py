"""Audit current-task pairs, source links and distinct builder costs for both libraries."""
import argparse
import json
from collections import defaultdict
from pathlib import Path

from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.public_library_transfer.self_refinement.dependency_order import run, transport
from studies.study_io import ROOT, digest, read, sha

DEST=ROOT/'studies/results/self-dependency-table-20261124.json'
ARCHIVE=ROOT/'studies/results/backbone-matrix-20261124.json'
ARMS=('old_direct','old_self','old_fixed','direct','self','fixed')

def requests(root):
    receipts={}
    ledger=ledger_read.calls(root/'budget.sqlite3')
    ids={r['id']:r for r in ledger}
    accounting=defaultdict(list)
    for p in sorted(root.rglob('request.json')):
        req=read(p)
        call=ids.pop(req['call_id'])
        body=req['body']
        assert body['temperature']==.2 and 'seed' not in body and 'reasoning' not in body
        assert body['provider']['only']==[transport.PROVIDER] and body['provider']['require_parameters']
        assert body['model']==call['model']==transport.MODEL
        proj,replica,step,*_=call['purpose'].split('/')
        assert proj==root.name and replica in run.engine.GROUPS
        if step=='target':
            assert 'response_format' in body and body['response_format']['json_schema']['strict']
            assert body['max_tokens']==8192
        accounting[replica+('/deploy' if step=='target' else '/construction')].append(call)
        answer=p.parent/'response.json'
        stamp=p.parent/'settled.json'
        row={'purpose':call['purpose'],'request_sha256':sha(p),'response_sha256':sha(answer) if answer.exists() else None,
             'status':call['status'],'actual_usd':None if call['actual'] is None else call['actual']/1e6}
        if stamp.exists():
            resp=read(answer)
            assert read(stamp)['response_sha256']==sha(answer) and read(stamp)['ticket']==req['call_id']
            assert resp['model']==transport.MODEL and resp.get('provider')==transport.PROVIDER
            row.update(receipt_sha256=sha(stamp),provider=resp.get('provider'),finish_reason=resp['choices'][0]['finish_reason'],
                       visible_characters=len(resp['choices'][0]['message'].get('content') or ''))
        receipts[call['purpose']]=row
    assert not ids and len(receipts)==len(ledger)
    def costs(items):
        return {'calls':len(items),'settled_usd':sum(r['actual'] or 0 for r in items)/1e6,
                'exposure_usd':sum(r['reserved'] if r['actual'] is None else r['actual'] for r in items)/1e6,
                'unsettled_calls':sum(r['actual'] is None for r in items)}
    return receipts,{k:costs(v) for k,v in accounting.items()},ledger_read.totals(root/'budget.sqlite3')

def paired(rows,a,b):
    joint=[r for r in rows if None not in (r[a]['passed'],r[b]['passed'])]
    return {'joint_ids':[r['task'] for r in joint],'passed':{k:sum(r[k]['passed'] for r in joint) for k in (a,b)},
            'only_'+a:[r['task'] for r in joint if r[a]['passed'] and not r[b]['passed']],
            'only_'+b:[r['task'] for r in joint if r[b]['passed'] and not r[a]['passed']]}

def create(directory=None, inventory=requests):
    run.configure()
    directory=directory or run.OUT
    run.engine.OUT=directory
    run.engine.verify()
    root=directory/run.PROJECT
    reg=read(directory/'registered.json')
    history=read(ARCHIVE)
    for name in ('public.json','browser.json'):
        hashes=[h for p,h in history['registration_inputs'].items() if p.endswith('/table/'+name)]
        assert hashes==[sha(root/name)]
    history_rows={(r['arm'],r['task']):r for r in history['models'][transport.MODEL]['rows'] if r['project']=='table'}
    scores=read(root/'scores.json')
    contract=read(root/'browser.json')
    assert contract==browser.verify_contract(run.PROJECT)
    index={}
    receipt,spend,ledger=inventory(root)
    for group in run.engine.GROUPS:
        for p,h in read(root/group/'seal.json').items(): assert sha(root/p)==h
    for r in scores:
        group,arm,task=r['group'],r['arm'],r['task']
        base=root/group
        if arm=='fixed':
            state=read(base/'build/status.json')
            page=base/state.get('fixed_page','')
        else:
            target=base/'targets'/str(task)
            state=read(target/'status.json')
            page=target/'page'
        key=group,arm,task
        assert key not in index and r['status']==state['status']
        if state['status']=='valid':
            files=state['files']
            browser.verify_page(page,files,run.PROJECT)
            seal=digest(files)
            expected={'project':run.PROJECT,'task':task,'files_digest':seal,'contract_digest':digest(contract)}
            proof=browser.verify_receipt(root,root/'browser/scores'/run.PROJECT/f'task-{task}'/seal/'score.json',expected)
            assert seal==r['files_digest'] and proof['passed']==r['passed'] and proof['report_sha256']==r['report_sha256']
        else:
            assert r['passed'] is (False if r['status']=='invalid' else None)
        item={k:v for k,v in r.items() if k not in ('group','arm','task')}
        if arm!='fixed': item['response_sha256']=receipt.get(f'table/{group}/target/{task}',{}).get('response_sha256')
        if 'plan' in state: item['plan']=state['plan']
        index[key]=item
    assert len(index)==100
    builds={}
    for group in ('build-a','build-b'):
        base=root/group/'build'
        state=read(base/'status.json')
        spec=read(base/'manifest.json') if (base/'manifest.json').exists() else None
        graph_summary={}
        for p in sorted(base.glob('*-check.json')):
            checked=read(p)
            graph_summary[p.stem]={k:checked[k] for k in ('graph','load_errors','probe')}
        if state['status']=='valid':
            package=read(base/'package.json')
            assert sha(base/'package.json')==state['package_sha256']
            assert not run.graph(package['sources'])['errors']
            assert package['spec']==spec
        checkpoints=[]
        for location in sorted((base/'sources').glob('*/link.json')):
            linked=read(location)
            checkpoints.append({'path':linked['path'],'link_sha256':sha(location),
                                'actual_exports':linked['exports'].get(linked['path'],[]),
                                'actual_imports':linked['imports'].get(linked['path'],[]),'errors':linked['errors']})
        rows=[]
        for t in range(1,21):
            row={'task':t,'direct':index['direct','direct',t],'self':index[group,'self',t],'fixed':index[group,'fixed',t]}
            for arm in ('direct','self','fixed'):
                old=history_rows[arm,t]
                row['old_'+arm]={k:old[k] for k in ('passed','status','response_sha256','report_sha256') if k in old}
            rows.append(row)
        summary={a:{'passed_ids':[r['task'] for r in rows if r[a]['passed']],
                    'missing_ids':[r['task'] for r in rows if r[a]['passed'] is None],
                    'observed':sum(r[a]['passed'] is not None for r in rows)} for a in ARMS}
        plan_rows=[r['self']['plan'] for r in rows if 'plan' in r['self']]
        config_evidence=None
        if spec and state['status']=='valid':
            source=package['sources']
            first={c['id']:c['example'] for c in spec['controls']}
            config_evidence={'unique_received_plans':len({json.dumps(p,sort_keys=True) for p in plan_rows}),
                'received_plans':len(plan_rows),'plans_equal_to_fixed':sum(p==first for p in plan_rows),
                'literal_APP_CONFIG_files':[name for name,body in source.items() if 'APP_CONFIG' in body],
                'literal_data_dna_files':[name for name,body in source.items() if 'data-dna-' in body],
                'files_with_control_id':{c['id']:[n for n,body in source.items() if c['id'] in body] for c in spec['controls']}}
        builds[group]={'configuration_evidence':config_evidence,'seal_sha256':sha(root/group/'seal.json'),'build_status':state['status'],
            'reason':state.get('reason'),'package_sha256':state.get('package_sha256'),
            'source_file_order':spec['files'] if spec else None,'controls':spec['controls'] if spec else None,
            'module_checkpoints':checkpoints,'public_checks':graph_summary,'rows':rows,'summary':summary,
            'paired':{b:paired(rows,'self',b) for b in ('direct','fixed','old_self')}}
        optional_repair=base/'repair/response.json'
        source_receipt=base/'repair/delivery.json'
        if source_receipt.exists():
            optional_repair=ROOT/read(source_receipt)['path']/'response.json'
        if optional_repair.exists():
            delivered=read(optional_repair)['choices'][0]
            repair_evidence={'response_sha256':sha(optional_repair),'finish_reason':delivered['finish_reason'],
                             'materialized':(base/'repaired-check.json').exists()}
            try:
                changes=core.files_map(core.parse(delivered['message'].get('content') or '')['files'])
                repair_evidence['requested_paths']=sorted(changes)
                repair_evidence['outside_frozen_manifest']=sorted(set(changes)-set(spec['files']))
            except (KeyError,TypeError,ValueError) as exc:
                repair_evidence['delivery_error']=str(exc)[:240]
            builds[group]['public_repair_delivery']=repair_evidence
    assert [r['direct'] for r in builds['build-a']['rows']]==[r['direct'] for r in builds['build-b']['rows']]
    assert ledger['exposure_usd']<=run.CAP
    return {'stage':'Dependency-ordered same-model library and assembly','registered_utc':reg['utc'],
            'model':transport.MODEL,'provider':transport.PROVIDER,'project':run.PROJECT,
            'upstream_commit':browser.UPSTREAM_COMMIT,'registration_sha256':sha(directory/'registered.json'),
            'protocol_sha256':sha(run.HERE/'PROTOCOL.md'),'public_input_sha256':sha(root/'public.json'),
            'browser_contract_sha256':sha(root/'browser.json'),'historical_source_sha256':sha(ARCHIVE),
            'direct_seal_sha256':sha(root/'direct/seal.json'),'replicas':builds,'cost_by_phase':spend,
            'ledger':ledger,'requests':list(receipt.values())}

def check_public(result):
    assert result['historical_source_sha256']==sha(ARCHIVE)
    assert result['protocol_sha256']==sha(run.HERE/'PROTOCOL.md')
    assert len(result['requests'])==result['ledger']['calls']
    assert sum(b['calls'] for b in result['cost_by_phase'].values())==result['ledger']['calls']
    for cost in ('settled_usd','exposure_usd'):
        assert abs(sum(b[cost] for b in result['cost_by_phase'].values())-result['ledger'][cost])<1e-6
    replicas=result['replicas']
    assert set(replicas)=={'build-a','build-b'}
    for record in replicas.values():
        rows=record['rows']
        assert [r['task'] for r in rows]==list(range(1,21))
        for arm in ARMS:
            assert record['summary'][arm]['passed_ids']==[r['task'] for r in rows if r[arm]['passed']]
            assert record['summary'][arm]['missing_ids']==[r['task'] for r in rows if r[arm]['passed'] is None]
            assert record['summary'][arm]['observed']==sum(r[arm]['passed'] is not None for r in rows)
        for comparator, pair in record['paired'].items():
            assert pair==paired(rows,'self',comparator)
    assert [r['direct'] for r in replicas['build-a']['rows']]==[r['direct'] for r in replicas['build-b']['rows']]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--check-public',action='store_true')
    args=parser.parse_args()
    if args.check_public:
        check_public(read(DEST))
        return
    result=create()
    check_public(result)
    if args.check: assert read(DEST)==result
    else: core.save(DEST,result)
    for k,b in result['replicas'].items():
        print(k,{a:(len(r['passed_ids']),r['observed']) for a,r in b['summary'].items()})
    print(result['ledger'])

if __name__=='__main__': main()
