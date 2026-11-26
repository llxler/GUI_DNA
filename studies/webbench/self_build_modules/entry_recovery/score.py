"""Select the first publicly admitted preparation without consulting either official score."""
import argparse
import os
import time
from unittest.mock import patch

from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import read, sha
from .. import run as base, score
from ..source_delivery import run as delivery
from . import run

RESULT=run.HERE/'result.json'


def compare(p,t):
    first=read(delivery.OUT/p/t/'comparison.json')
    protocols=browser.verify_contract(p)
    assert protocols==read(run.OUT/'inputs'/p/'browser.json')
    for rep in ('a','b'):
        prior=first['builds'][rep]
        root=run.OUT/p/t
        if prior['status']!='build_failed':
            status=delivery.OUT/p/t/rep/'build/status.json'
            assert read(root/rep/'skip.json')==dict(primary_status=prior['status'],status_sha256=sha(status))
            prior['preparation']='modules'
            continue
        seal=read(root/rep/'seal.json')
        next_result=score.score_branch(p,t,rep,root,seal,protocols,3)
        first['builds'][rep]=dict(**next_result,preparation='entry',module_build_status=prior['status'],
                                  module_reason=prior['reason'],module_seal_sha256=prior['seal_sha256'])
    return first


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('publish','monitor','check'))
    action=parser.parse_args().action
    browser.OUT=run.OUT
    with patch.object(base,'OUT',run.OUT):
        if action=='monitor':
            for k in list(os.environ):
                if k.endswith(('_API_KEY','_AUTH_TOKEN','_ACCESS_TOKEN')):os.environ.pop(k)
            while True:
                pending=False
                for p,t in base.ORDER:
                    path=run.OUT/p/t
                    if (path/'comparison.json').exists():continue
                    if not (delivery.OUT/p/t/'comparison.json').exists() or not all(
                            any((path/r/f).exists() for f in ('seal.json','skip.json')) for r in ('a','b')):
                        pending=True
                        continue
                    core.save(path/'comparison.json',compare(p,t))
                    print(p,t,'verified',flush=True)
                if not pending:return
                time.sleep(4)
        else:
            result=score.collect()
            assert len(result['cells'])==len(base.ORDER)
            result.update(primary_result_sha256=sha(delivery.HERE/'result.json'),
                          interrupted_engineering_cost=ledger_read.totals(delivery.OLD/'budget.sqlite3'),
                          primary_accounting=ledger_read.totals(delivery.OUT/'budget.sqlite3'))
            if action=='publish':
                core.save(RESULT,result)
            else:
                assert result==read(RESULT)


if __name__=='__main__':
    main()
