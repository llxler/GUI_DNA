"""Evaluate sealed table pages, then replay the independent action sequences and controls."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
import time
from unittest.mock import patch

from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,UPSTREAM,read,sha
from . import run


def assess():
    seal=run.OUT/'seal.json'
    while not seal.exists():
        if datetime.now(timezone.utc)>=run.END:raise TimeoutError('Generation incomplete')
        time.sleep(3)
    complete=run.HERE/'result.json'
    if not complete.exists():
        with patch.multiple(run.previous.reducers,OUT=run.OUT,HERE=run.HERE):
            run.previous.reducers.score()
    doc=read(complete)
    assert doc['seal']==sha(seal)
    for rep in 'ab':
        req=read(run.OUT/rep/'functions/markSelection/0/transmission-1/request.json')
        assert req['body']['seed']==run.SEED+int(rep=='b')
    cases=read(run.HERE/'heldout.json')
    new=read(seal)['rows']
    older=read(run.previous.OUT/'seal.json')['rows']
    baseline=read(run.previous.prior.OUT/'seal.json')['rows']
    for r in baseline:
        if r['arm']=='direct' and r['status']=='valid':
            browser.verify_page(ROOT/r['page'],r['files'],'table')
    controls={group:run.trace(UPSTREAM/'projects/table'/sub,cases) for group,sub in [('reference','src'),('starter','src-init')]}
    calibrated={k:bool(controls['reference'][k]['passed'] and not controls['starter'][k]['passed']) for k in cases}
    def evaluate_case(item):
        label,case,page=item
        if page['status']!='valid':
            return label,case,dict(status=page['status'])
        path=ROOT/page['page']
        browser.verify_page(path,page['files'],'table')
        receipt=run.trace(path,{case:cases[case]})[case]
        return label,case,dict(status='observed',candidate=page['files'],passed=receipt['passed'],steps=receipt['steps'])
    jobs=[]
    for name,params in cases.items():
        target=params['task']
        for lab,rows,arm in [('direct',baseline,'direct'),('new-a',new,'self-a'),('new-b',new,'self-b'),
                             ('fixed-a',new,'fixed-a'),('fixed-b',new,'fixed-b'),('old-fixed-a',older,'fixed-a'),
                             ('old-fixed-b',older,'fixed-b'),('empty',new,'starter')]:
            page,=[r for r in rows if r['task']==target and r['arm']==arm]
            jobs.append((lab,name,page))
    out={};dest=run.HERE/'heldout-result.json'
    if dest.exists():return
    with ThreadPoolExecutor(max_workers=2) as pool:
        for lab,case,row in pool.map(evaluate_case,jobs):out.setdefault(lab,{})[case]=row
    core.save(dest,dict(official=sha(complete),cases=sha(run.HERE/'heldout.json'),controls=controls,calibrated=calibrated,rows=out))
    print('Independent action sequence calibration',calibrated,flush=True)


if __name__=='__main__':
    with browser.lock(run.OUT/'evaluate.lock'):
        assess()
