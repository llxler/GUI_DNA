"""Publish first-admission web comparisons with the verified option subset and its provenance."""
import argparse
import os
import time
from unittest.mock import patch
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, read, sha
from .. import run as base, score
from ..entry_recovery import run as entry
from . import run

RESULT=run.HERE/'result.json'
PRIOR_LABEL='entry'
LABEL='observed options'
HASH_FIELD='entry_result_sha256'
METADATA=('model_defaults','calibrated','source_sha256')


def compare(p,t):
    cell=read(entry.OUT/p/t/'comparison.json')
    for rep,prior in cell['builds'].items():
        root=run.OUT/p/t
        skip=root/rep/'skip.json'
        if skip.exists():
            proof=read(skip)
            assert sha(ROOT/proof['source'])==proof['sha256'] and prior['status']!='build_failed'
            continue
        assert prior['status']=='build_failed' and prior['preparation']==PRIOR_LABEL
        seal=read(root/rep/'seal.json')
        protocol=browser.verify_contract(p)
        assert protocol==read(run.OUT/'inputs'/p/'browser.json')
        nxt=score.score_branch(p,t,rep,root,seal,protocol,2)
        current=dict(**nxt,preparation=LABEL,module_reason=prior['module_reason'])
        if LABEL=='observed options':
            current.update(entry_reason=prior['reason'],entry_seal_sha256=prior['seal_sha256'])
        else:
            current.update(prior_stage=PRIOR_LABEL,prior_reason=prior['reason'],prior_seal_sha256=prior['seal_sha256'])
        if nxt['status']=='valid':
            current.update({k:seal['build'][k] for k in METADATA})
        cell['builds'][rep]=current
    return cell


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('monitor','publish','check'))
    action=parser.parse_args().action
    browser.OUT=run.OUT
    with patch.object(base,'OUT',run.OUT):
        if action=='monitor':
            for k in list(os.environ):
                if k.endswith(('_API_KEY','_ACCESS_TOKEN','_AUTH_TOKEN')):os.environ.pop(k)
            while True:
                pending=False
                for p,t in base.ORDER:
                    where=run.OUT/p/t
                    if (where/'comparison.json').exists():continue
                    ready=all(any((where/r/f).is_file() for f in ('seal.json','skip.json')) for r in ('a','b'))
                    if not ready or not (entry.OUT/p/t/'comparison.json').exists():
                        pending=True
                        continue
                    core.save(where/'comparison.json',compare(p,t))
                    print(p,t,'verified',flush=True)
                if not pending:return
                time.sleep(4)
        else:
            value=score.collect()
            assert len(value['cells'])==len(base.ORDER)
            value[HASH_FIELD]=sha(entry.HERE/'result.json')
            if action=='publish':core.save(RESULT,value)
            else:assert value==read(RESULT)


if __name__=='__main__':
    main()
