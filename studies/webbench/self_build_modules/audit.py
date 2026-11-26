"""Recheck paired outcomes, response and test receipts, and every ledger for this study."""
import argparse
from collections import defaultdict
from pathlib import Path

from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.public_library_transfer.self_refinement.suite_recovery import paper, run as suites
from studies.study_io import ROOT, digest, read, sha
from studies.public_library_transfer.self_refinement.suite_recovery.duo_confirmation import run as duo_confirmation
from . import run
from .entry_recovery import run as entry
from .source_delivery import run as delivery
from .observed_options import run as options
from .module_links import run as links

RESULT=run.HERE/'audit.json'


def account(root):
    registration=read(root/'registration.json')
    for rel,expected in registration['sources'].items():
        assert sha(ROOT/rel)==expected,rel
    calls={r['id']:r for r in ledger_read.calls(root/'budget.sqlite3')}
    seen=set()
    stages=defaultdict(lambda:dict(requests=0,settled_microusd=0,maximum_microusd=0,unresolved=0))
    for req in root.glob('*/*/*/**/transmission-*/request.json'):
        meta=read(req)
        key=meta['call_id']
        assert key not in seen
        seen.add(key)
        row=calls[key]
        assert meta['body']['model']==row['model'] and abs(meta['reserved_usd']*1e6-row['reserved'])<=1
        stage=row['purpose'].split('/')[0]
        bill=stages[stage]
        bill['requests']+=1
        if row['actual'] is None:
            bill['unresolved']+=1
            bill['maximum_microusd']+=row['reserved']
        else:
            res=req.with_name('response.json')
            assert sha(res)==read(req.with_name('settled.json'))['response_sha256']
            assert abs(read(res)['usage']['cost']*1e6-row['actual'])<=1
            bill['settled_microusd']+=row['actual']
            bill['maximum_microusd']+=row['actual']
    assert set(calls)==seen
    reused=0
    for proof in root.glob('*/*/*/**/reused.json'):
        item=read(proof)
        old=ROOT/item['request']
        assert sha(old)==item['request_sha256'] and sha(ROOT/item['response'])==item['response_sha256']
        assert old.relative_to(delivery.OLD).parts[:3]==proof.relative_to(root).parts[:3]
        assert not list(proof.parent.glob('transmission-*/request.json'))
        reused+=1
    totals=ledger_read.totals(root/'budget.sqlite3')
    assert round(totals['exposure_usd']*1e6)==sum(v['maximum_microusd'] for v in stages.values())
    return dict(total=totals,stages=dict(stages),same_request_reuse=reused)


def reports(cell,rep,file):
    p=cell['project']
    source=cell['builds'][rep]
    if 'groups' in source:
        for arm in source['arms'].values():
            for task,row in arm.items():
                if row['status']=='valid':
                    root=duo_confirmation.OUT if file==paper.CONFIRM else suites.OUT
                    where=root/'scores'/task/row['files_sha256']
                    report=where/('playwright.json' if p=='todomvc' else 'jest.json')
                    assert sha(report)==row['report_sha256']
                    value=read(where/'verdict.json')
                    assert value['passed']==row['passed'] and value['official_tests']==row['official_tests']
        return
    if source['status']!='valid':
        assert 'arms' not in source
        return
    root={'modules':delivery.OUT,'entry':entry.OUT,'observed options':options.OUT,'module links':links.OUT}[source['preparation']]
    contract=digest(read(root/'inputs'/p/'browser.json'))
    for arm in source['arms'].values():
        assert set(arm)==set(map(str,range(1,21)))
        for target,row in arm.items():
            if row['status']=='valid':
                task=int(target)
                path=root/'browser/scores'/p/f'task-{task}'/row['files_digest']/'score.json'
                expected=dict(project=p,task=task,files_digest=row['files_digest'],contract_digest=contract)
                value=browser.verify_receipt(root,path,expected)
                assert value['report_sha256']==row['report_sha256'] and value['passed']==row['passed']
            else:
                assert row['passed'] is (False if row['status']=='invalid' else None)


def audit():
    groups={k: account(root) for k,root in [('receiver_pilot',delivery.OLD),('modules',delivery.OUT),
                                             ('entry',entry.OUT),('options',options.OUT),('module_links',links.OUT),('suites',suites.OUT),('duo_confirmation',duo_confirmation.OUT)]}
    maximum=sum(round(r['total']['exposure_usd']*1e6) for r in groups.values())
    assert maximum<=10_000_000
    cells=[]
    for file,c in paper.cohorts():
        row=dict(project=c['project'],model=c['model'],original_targets=c['original_shared'],source=str(file.relative_to(ROOT)))
        for rep in ('a','b'):
            reports(c,rep,file)
            row[rep]=paper.paired(c,rep)
            assert row[rep]['n']==len(set(row[rep]['targets']))
        group=c['project']
        historic=read(ROOT/c['original_source'])['models'][c['model']]['rows']
        originally_measured={r['task'] for r in historic if r['arm']=='self' and r['task'] in c['original_shared']
                             and (r.get('project',group)==group) and r['status']!='build_failed' and r['passed'] is not None}
        row['original_admitted_targets']=sorted(originally_measured)
        for rep in ('a','b'):
            before=row[rep]
            common=[t for t in before['observed'] if t in originally_measured]
            row[rep]['matched_original']=dict(targets=common,
                original_self=sum(c['original']['self'][str(t)] for t in common),
                new_self=sum(c['builds'][rep]['arms']['self'][str(t)]['passed'] for t in common))
            if before['observed']:
                arms=c['builds'][rep]['arms']
                observed=before['observed']
                fixed_only=[t for t in observed if arms['fixed'][str(t)]['passed'] and not arms['self'][str(t)]['passed']]
                row[rep]['deployment_diagnosis']={
                    'valid_plans':sum(arms['self'][str(t)]['status']=='valid' for t in observed),
                    'planned_passed':[t for t in observed if arms['self'][str(t)]['passed']],
                    'only_planned':[t for t in observed if arms['self'][str(t)]['passed'] and not arms['fixed'][str(t)]['passed']],
                    'only_fixed':fixed_only,
                    'invalid_on_fixed_passes':[t for t in fixed_only if arms['self'][str(t)]['status']=='invalid'],
                }
        cells.append(row)
    assert len(cells)==len({(c['project'],c['model']) for c in cells})==25
    return dict(cells=cells,stages=groups,total_microusd=sum(round(g['total']['settled_usd']*1e6) for g in groups.values()),
                maximum_microusd=maximum,total_requests=sum(g['total']['calls'] for g in groups.values()),
                sources_sha256={str(p.relative_to(ROOT)):sha(p) for p in paper.SOURCES})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write',action='store_true')
    args=parser.parse_args()
    result=audit()
    if args.write:core.save(RESULT,result)
    assert read(RESULT)==result
    print('Verified',len(result['cells']),'cells and',result['total_requests'],'request receipts.')
