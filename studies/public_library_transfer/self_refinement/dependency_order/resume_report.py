"""Audit reused first answers and each new transmission, including unknown reservations."""
import argparse

from studies.public_library_transfer import core
from studies.public_library_transfer.self_refinement.dependency_order import report, resume, run
from studies.study_io import ROOT, read, sha

RESULT=ROOT/'studies/results/self-dependency-resume-20261124.json'

def logical_inventory(root):
    logical={}
    for p in sorted(root.rglob('delivery.json')):
        record=read(p)
        folder=ROOT/record['path']
        assert all(record[k]==sha(folder/file) for k,file in (
            ('request_sha256','request.json'),('response_sha256','response.json'),('receipt_sha256','settled.json')))
        assert read(folder/'settled.json')['response_sha256']==record['response_sha256']
        assert record['purpose'] not in logical
        logical[record['purpose']]={k:v for k,v in record.items() if k!='path'}
    _, phase,ledger=report.requests(root)
    return logical,phase,ledger

def create():
    result=report.create(resume.OUT,logical_inventory)
    root=resume.OUT/run.PROJECT
    fresh,_,_=report.requests(root)
    original,old_phase,old_ledger=report.requests(resume.SOURCE/run.PROJECT)
    reg=read(resume.OUT/'registered.json')
    assert old_ledger['exposure_usd']==reg['source_exposure_usd']
    known={r['response_sha256'] for r in original.values() if r['response_sha256']}
    for item in result['requests']:
        if item['origin']=='original': assert item['response_sha256'] in known
    old_report=read(report.DEST)
    old_direct={r['task']:r['direct'] for r in old_report['replicas']['build-a']['rows']}
    current={r['task']:r['direct'] for r in result['replicas']['build-a']['rows']}
    same=[t for t,old in old_direct.items() if old['status']=='valid']
    for t in same:
        assert current[t]['files_digest']==old_direct[t]['files_digest']
        assert current[t]['response_sha256']==old_direct[t]['response_sha256']
    reuse_check={'same_received_pages':same,'rescored_flips':[t for t in same if current[t]['passed']!=old_direct[t]['passed']],
                 'previously_missing':[t for t,r in old_direct.items() if r['passed'] is None]}
    cost={}
    for name in sorted(set(old_phase)|set(result['cost_by_phase'])):
        cost[name]={k:round(old_phase.get(name,{}).get(k,0)+result['cost_by_phase'].get(name,{}).get(k,0),6)
                    for k in ('calls','settled_usd','exposure_usd','unsettled_calls')}
    result.update(stage='Serialized continuation of registered dependency-ordered construction',
                  continuation_protocol_sha256=sha(run.HERE/'RESUME.md'),original_registration_sha256=sha(resume.SOURCE/'registered.json'),
                  historical_experiment_sha256=sha(report.DEST),wire_attempts=list(fresh.values()),original_ledger=old_ledger,original_direct_replay=reuse_check,
                  logical_responses=result.pop('requests'),combined_cost_by_phase=cost,
                  combined_exposure_usd=round(old_ledger['exposure_usd']+result['ledger']['exposure_usd'],6),
                  combined_settled_usd=round(old_ledger['settled_usd']+result['ledger']['settled_usd'],6),
                  combined_cap_usd=float(resume.TOTAL))
    assert result['combined_exposure_usd']<=result['combined_cap_usd']
    return result

def public_check(result):
    assert result['historical_experiment_sha256']==sha(report.DEST)
    assert result['continuation_protocol_sha256']==sha(run.HERE/'RESUME.md')
    report.check_public(dict(result,requests=result['wire_attempts']))
    costs=result['combined_cost_by_phase']
    assert abs(sum(r['exposure_usd'] for r in costs.values())-result['combined_exposure_usd'])<1e-6
    assert abs(sum(r['settled_usd'] for r in costs.values())-result['combined_settled_usd'])<1e-6

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--check-public',action='store_true')
    args=parser.parse_args()
    if args.check_public: return public_check(read(RESULT))
    value=create()
    public_check(value)
    if args.check: assert value==read(RESULT)
    else: core.save(RESULT,value)
    for key,b in value['replicas'].items(): print(key,b['paired']['direct'],b['paired']['fixed'])
    print(value['ledger'],value['combined_exposure_usd'])

if __name__=='__main__': main()
