"""Run the unchanged public traces inside a single reserved browser process."""
from argparse import ArgumentParser
from contextlib import nullcontext
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
from unittest.mock import patch

from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from .. import evaluate as scoring, run as study, trace as worker

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/table-single-slot-20261127'
ORIGINAL=study.OUT
MODULE='studies.webbench.table.action_sequences.single_slot.run'


def reserve_once(page,cases):
    with browser.browser_slot():
        process=subprocess.Popen([sys.executable,'-m',MODULE,'worker'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,text=True,start_new_session=True)
        try:
            data,err=process.communicate(json.dumps(dict(page=str(page),cases=cases)),timeout=28)
            if process.returncode==0:return json.loads(data)
            error=err[-300:]
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL)
            process.communicate()
            error='Timed out inside an acquired browser slot'
    return {k:dict(passed=False,steps=[dict(action='browser',passed=False,error=error)]) for k in cases}


def register():
    cap=round(.58-ledger_read.totals(ORIGINAL/'budget.sqlite3')['exposure_usd'],6)
    f=OUT/'registration.json'
    old=read(ORIGINAL/'registration.json')
    paths=[Path(__file__),HERE/'PROTOCOL.md',Path(scoring.__file__),ORIGINAL/'registration.json',*map(lambda p: ROOT/p,old['sources'])]
    paths+=sorted(ORIGINAL.glob('*/functions/*/*/transmission-*/settled.json'))
    hashes={str(p.relative_to(ROOT)):sha(p) for p in paths}
    if not f.exists():
        balance=check_credits(cap);assert balance['sufficient']
        core.save(f,dict(utc=now(),deadline=study.END.isoformat(),cap=cap,balance=balance,sources=hashes,
                         previous_cost=ledger_read.totals(ORIGINAL/'budget.sqlite3')))
    assert read(f)['sources']==hashes and read(f)['cap']==cap
    return f


def generate():
    reg=register()
    for receipt in sorted(ORIGINAL.glob('*/functions/*/*/transmission-*/settled.json')):
        assert read(receipt)['response_sha256']==sha(receipt.with_name('response.json'))
        for name in ('request.json','response.json','settled.json'):
            src=receipt.with_name(name);dst=OUT/src.relative_to(ORIGINAL)
            dst.parent.mkdir(parents=True,exist_ok=True)
            if not dst.exists():shutil.copyfile(src,dst)
            assert sha(src)==sha(dst)
    with patch.multiple(study,OUT=OUT,CAP=read(reg)['cap'],register=lambda:reg,trace=reserve_once):
        study.generate()


if __name__=='__main__':
    parser=ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('worker','generate','score'))
    arg=parser.parse_args().action
    if arg=='worker':
        args=json.load(sys.stdin)
        with patch.object(browser,'browser_slot',nullcontext):
            print(json.dumps(worker.measure(Path(args['page']),args['cases'])))
    elif arg=='generate':
        with browser.lock(OUT/'run.lock'):generate()
    else:
        with browser.lock(OUT/'evaluate.lock'),patch.multiple(study,OUT=OUT,HERE=HERE,trace=reserve_once):
            scoring.assess()
