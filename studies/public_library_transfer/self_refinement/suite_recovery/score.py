"""Score sealed suite libraries and verify the genuine matched comparator targets."""
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import os
import time

from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.public_library_transfer.other_benchmarks import evaluate
from studies.study_io import ROOT, read, sha
from . import run

RESULT=run.HERE/'result.json'


def score(project,tag):
    root=run.OUT/project/tag
    targets,_=run.suite.inputs()
    model=run.suite.MODELS[tag][0]
    history=read(run.suite.RESULT)['models'][model]['rows']
    original=defaultdict(dict)
    old_failed=set()
    for row in history:
        if (row['group']=='todomvc')!=(project=='todomvc'):
            continue
        original[row['arm']][row['task']]=row['passed']
        if row['arm']=='self' and row['status']=='build_failed':
            old_failed.add(row['task'])
    controls=[a for a in ('direct','human') if a in original]
    common=sorted(t for t in original['direct'] if all(original[a][t] is not None for a in controls))
    seals={rep:read(root/rep/'seal.json') for rep in ('a','b')}
    builds={}
    server=evaluate.todo.Server(run.OUT)
    try:
        for rep,seal in seals.items():
            assert seal['case']==[project,tag,rep] and seal['registration_sha256']==sha(run.OUT/'registration.json')
            arms=defaultdict(dict)
            def one(item):
                task,arm,row=item
                group=targets[task]['group']
                valid=seal['builds'][group]['status']=='valid'
                if row['status']!='valid':
                    return task,arm,dict(status=row['status'],passed=False if row['status']=='invalid' and valid else None)
                assert valid and sha(ROOT/row['file'])==row['files_sha256']
                dest=run.OUT/'scores'/task/row['files_sha256']
                with browser.lock(dest/'.lock'):
                    with browser.browser_slot():
                        verdict=run.runtime.score((group,targets[task],read(ROOT/row['file']),dest,server))
                if project=='todomvc':
                    run.todo.binding.official(dest,targets[task],row)
                else:
                    assert sha(dest/'jest.json')==verdict['report_sha256']
                return task,arm,dict(status='valid',passed=verdict['passed'],report_sha256=verdict['report_sha256'],
                                     files_sha256=row['files_sha256'],official_tests=verdict['official_tests'])
            jobs=[(t,a,v) for t,d in seal['rows'].items() for a,v in d.items()]
            with ThreadPoolExecutor(max_workers=2) as pool:
                for task,arm,out in pool.map(one,jobs):
                    arms[arm][task]=out
            builds[rep]=dict(groups={g:s['status'] for g,s in seal['builds'].items()},arms=arms,
                              seal_sha256=sha(root/rep/'seal.json'))
    finally:
        server.close()
    return dict(project=project,model=model,original_shared=common,original=original,
                original_failed_build=sorted(old_failed),original_source=str(run.suite.RESULT.relative_to(ROOT)),
                original_sha256=sha(run.suite.RESULT),builds=builds)


def collect():
    rows=[read(run.OUT/p/t/'comparison.json') for p,t in run.ORDER]
    bill=ledger_read.calls(run.OUT/'budget.sqlite3')
    costs=defaultdict(lambda:defaultdict(lambda:dict(calls=0,settled_microusd=0,maximum_microusd=0)))
    for call in bill:
        stage,p,t,rep,*_=call['purpose'].split('/')
        row=costs[f'{p}/{t}/{rep}'][stage]
        row['calls']+=1
        row['settled_microusd']+=call['actual'] or 0
        row['maximum_microusd']+=call['reserved'] if call['actual'] is None else call['actual']
    return dict(cells=rows,costs=costs,accounting=ledger_read.totals(run.OUT/'budget.sqlite3'),
                registration_sha256=sha(run.OUT/'registration.json'),registered=read(run.OUT/'registration.json')['utc'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('monitor','publish','check'))
    action=parser.parse_args().action
    if action=='monitor':
        for k in list(os.environ):
            if k.endswith(('_API_KEY','_AUTH_TOKEN','_ACCESS_TOKEN')):os.environ.pop(k)
        while True:
            pending=False
            for p,t in run.ORDER:
                d=run.OUT/p/t
                if (d/'comparison.json').exists():continue
                if not all((d/r/'seal.json').exists() for r in ('a','b')):
                    pending=True
                    continue
                core.save(d/'comparison.json',score(p,t))
                print(p,t,'scored',flush=True)
            if not pending:return
            time.sleep(4)
    elif action=='publish':
        core.save(RESULT,collect())
    else:
        assert read(RESULT)==collect()


if __name__=='__main__':
    main()
