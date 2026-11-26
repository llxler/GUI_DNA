"""Score sealed pairs and derive the matched-target comparison from official receipts."""
import argparse
from collections import defaultdict
import os
import time
from pathlib import Path

from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, read, sha, digest
from . import run

RESULT = run.HERE / 'result.json'


def controls(project, tag):
    stage = run.old_root(project,tag).name
    path = ROOT/'studies/results'/f'{stage}.json'
    model = run.template(project,tag,'build')['model']
    arms = defaultdict(dict)
    for row in read(path)['models'][model]['rows']:
        if row['project'] == project:
            arms[row['arm']][row['task']] = row
    return model, path, arms


def score_branch(project, tag, rep, root, seal, protocol, workers):
    assert seal['case']==[project,tag,rep] and seal['registration_sha256']==sha(run.OUT/'registration.json')
    state=seal['build']
    entry={'status':state['status'],'reason':state.get('reason'),'seal_sha256':sha(root/rep/'seal.json')}
    if state['status']!='valid':
        return entry
    assert sha(ROOT/state['package'])==state['package_sha256'] and len(seal['rows'])==20
    fixed=[dict(project=project,task=n,arm='fixed',status='valid',page=state['fixed'],files=state['fixed_files'])
           for n in range(1,21)]
    rows=browser.evaluate(seal['rows']+fixed,run.OUT,{project:protocol},workers)
    paired=defaultdict(dict)
    for row in rows:
        value=row['passed'] if row['status']!='invalid' else False
        if row.get('report'):
            assert sha(run.OUT/row['report'])==row['report_sha256']
        paired[row['arm']][str(row['task'])]={'passed':value,'status':row['status'],
            'report_sha256':row['report_sha256'],'files_digest':digest(row['files']) if row.get('files') else None}
    entry.update(package_sha256=state['package_sha256'], arms=dict(paired))
    return entry


def score(project, tag, workers):
    root=run.OUT/project/tag
    model,path,arms=controls(project,tag)
    protocol=browser.verify_contract(project)
    assert protocol == read(run.OUT/'inputs'/project/'browser.json') == read(run.old_root(project,tag)/'inputs'/project/'browser.json')
    shared = sorted(n for n in range(1,21) if all(arms[k][n]['passed'] is not None for k in ('direct','human','gpt5-library','self')))
    builds={}
    seals={k:read(root/k/'seal.json') for k in ('a','b')}
    for rep,seal in seals.items():
        builds[rep]=score_branch(project,tag,rep,root,seal,protocol,workers)
    control_rows={k:{str(n):v['passed'] for n,v in rows.items()} for k,rows in arms.items()}
    return dict(model=model,project=project,original_shared=shared,original=control_rows,
                original_source=str(path.relative_to(ROOT)),original_sha256=sha(path), builds=builds)


def collect():
    cells=[]
    for project,tag in run.ORDER:
        folder=run.OUT/project/tag
        if (folder/'comparison.json').is_file():
            cells.append(read(folder/'comparison.json'))
    bills=ledger_read.calls(run.OUT/'budget.sqlite3')
    spending=defaultdict(lambda:defaultdict(lambda:dict(calls=0,settled_microusd=0,maximum_microusd=0)))
    for call in bills:
        stage,project,tag,rep,*_ = call['purpose'].split('/')
        line=spending[f'{project}/{tag}/{rep}'][stage]
        line['calls']+=1
        line['settled_microusd']+=call['actual'] or 0
        line['maximum_microusd']+=call['reserved'] if call['actual'] is None else call['actual']
    return dict(registration_sha256=sha(run.OUT/'registration.json'),registered=read(run.OUT/'registration.json')['utc'],
                cells=cells,accounting=ledger_read.totals(run.OUT/'budget.sqlite3'),costs=spending)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('monitor','publish','check'))
    parser.add_argument('--workers',type=int,default=3)
    args=parser.parse_args()
    browser.OUT=run.OUT
    if args.action=='monitor':
        for name in list(os.environ):
            if name.endswith(('_API_KEY','_ACCESS_TOKEN','_AUTH_TOKEN')):
                os.environ.pop(name)
        while True:
            remaining=False
            for p,t in run.ORDER:
                folder=run.OUT/p/t
                if (folder/'comparison.json').exists():
                    continue
                if not all((folder/k/'seal.json').exists() for k in ('a','b')):
                    remaining=True
                    continue
                value=score(p,t,args.workers)
                core.save(folder/'comparison.json',value)
                print(p,t,'scored',flush=True)
            if not remaining:
                return
            time.sleep(4)
    elif args.action=='publish':
        value=collect()
        assert len(value['cells'])==len(run.ORDER)
        core.save(RESULT,value)
    else:
        assert read(RESULT)==collect()


if __name__=='__main__':
    main()
