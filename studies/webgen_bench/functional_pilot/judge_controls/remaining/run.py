"""Finish the eleven unjudged, preselected secondary-rater cases on the same endpoint."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import time

from scripts.check_openrouter_credits import check_credits
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT,now,read,sha
from ..recovery import run as previous

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/webgen-secondary-remaining-20261126pm'
CAP=1.40
OLD=previous.HERE

def register():
    f=OUT/'registration.json'
    inputs=[Path(__file__),HERE/'PROTOCOL.md',Path(previous.__file__),OLD/'result.json',previous.final.HERE/'judgments.json',
            previous.controls.native.HERE/'candidates.json',Path(previous.ev.__file__),Path(previous.api.__file__)]
    sums={str(p.relative_to(ROOT)):sha(p) for p in inputs}
    old=read(OLD/'result.json');candidates=read(previous.controls.native.HERE/'candidates.json')['rows']
    cases=[[r['model'],r['site'],r['check'],r['arm']] for r in old['second']
           if r['status']=='missing' and candidates[r['model']][r['site']][r['arm']]['status']=='valid']
    assert len(cases)==11
    if not f.exists():
        b=check_credits(CAP);assert b['sufficient']
        core.save(f,dict(utc=now(),sources=sums,cases=cases,cap=CAP,deadline=previous.gen.END.isoformat(),balance=b,
                         endpoint_registration=sha(ROOT/'artifacts/webgen-second-rater-recovery-20261126pm/registration.json')))
    assert read(f)['sources']==sums and read(f)['cases']==cases

def main():
    register();send=previous.send
    def paced(*args):
        time.sleep(max(0,previous.LAST+12-time.monotonic()))
        return send(*args)
    source=SimpleNamespace(HERE=OLD,native=previous.controls.native)
    with patch.multiple(previous,OUT=OUT,HERE=HERE,CAP=CAP,register=register,controls=source,send=paced):
        previous.run()

if __name__=='__main__':
    with browser.lock(OUT/'run.lock'):main()
