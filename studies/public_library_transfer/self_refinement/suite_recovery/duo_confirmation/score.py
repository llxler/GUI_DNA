"""Score the sealed repeats and evaluate both plan receivers on each identical response."""
import argparse
from pathlib import Path
import time
from unittest.mock import patch

from studies import ledger_read
from studies.public_library_transfer import core
from studies.study_io import read, sha
from .. import score as suite_score
from ..duo_delivery import run as pilot
from . import run

RESULT=run.HERE/'result.json'


def assemble():
    p,t='duo','mistral'
    with patch.object(suite_score.run,'OUT',run.OUT):
        cell=suite_score.score(p,t)
    existing=[r for r in read(pilot.RESULT)['rows'] if r['model']==cell['model'] and r['arm']=='direct']
    assert len(existing)==20
    for row in existing:
        assert row['status']==row['original_status'] and row['passed']==cell['original']['direct'][row['task']]
    targets,_=run.parent.suite.inputs()
    confirmed=[]
    for rep,data in cell['builds'].items():
        root=run.OUT/p/t/rep
        seal=read(root/'seal.json')
        plan_rows=data['arms']['self']
        for task,item in plan_rows.items():
            status=data['groups'][targets[task]['group']]
            if status!='valid' or item['status']=='missing':
                item['strict_passed']=None
                continue
            folder=root/'targets'/task/'plan'
            stamp=next(f for f in sorted(folder.glob('transmission-*/settled.json')) if
                       read(f.with_name('response.json'))['choices'][0]['finish_reason']!='error')
            res=stamp.with_name('response.json')
            assert sha(res)==read(stamp)['response_sha256']
            raw=read(res)['choices'][0]['message'].get('content') or ''
            names=list(seal['builds'][targets[task]['group']]['components'])
            strict=run.ORIGINAL(raw,names)
            relaxed=run.receive(raw,names)
            assert relaxed==seal['rows'][task]['self'].get('setting')
            assert strict is None or strict==relaxed
            item.update(strict_passed=item['passed'] if strict is not None else False,
                        strict_valid=strict is not None,response_sha256=sha(res))
        shared=[task for task in cell['original_shared'] if plan_rows[task]['passed'] is not None]
        planned=sum(plan_rows[t]['passed'] for t in shared)
        strict=sum(plan_rows[t]['strict_passed'] for t in shared)
        fixed=sum(data['arms']['fixed'][t]['passed'] for t in shared)
        confirmed.append(len(shared)==10 and planned>strict and planned>fixed)
    return dict(cells=[cell],registered=read(run.OUT/'registration.json')['utc'],
                registration_sha256=sha(run.OUT/'registration.json'),pilot_sha256=sha(pilot.RESULT),
                accounting=ledger_read.totals(run.OUT/'budget.sqlite3'),confirmed=all(confirmed),rep_passed=confirmed)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('monitor','check'))
    action=parser.parse_args().action
    if action=='monitor':
        while not all((run.OUT/'duo/mistral'/r/'seal.json').exists() for r in ('a','b')):
            time.sleep(3)
        core.save(RESULT,assemble())
    else:
        assert read(RESULT)==assemble()
