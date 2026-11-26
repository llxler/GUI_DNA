"""Record an isolated public handler timeout without dropping its registered examples."""
from pathlib import Path
import json
import subprocess
from unittest.mock import patch

from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,read,sha,now
from . import run

ORIGINAL_UNITS=run.units


def timed_units(name,fn):
    try:return ORIGINAL_UNITS(name,fn)
    except subprocess.TimeoutExpired:
        payload=json.dumps(dict(name=name,source=fn))
        # Confirm the original timeout in a new process with a longer wall-clock allowance.
        try:
            repeat=subprocess.run(['node',str(run.HERE/'units.cjs')],input=payload,text=True,capture_output=True,check=True,timeout=35)
            return json.loads(repeat.stdout)
        except subprocess.TimeoutExpired:
            dummy=ORIGINAL_UNITS(name,"function(){throw new Error('placeholder');}")
            return {k:{**v,'passed':False,'observed':'Handler did not return in isolated processes (12s then 35s)'} for k,v in dummy.items()}


if __name__=='__main__':
    f=run.OUT/'runtime-amendment.json'
    desc=dict(original=sha(run.OUT/'registration.json'),source=sha(Path(__file__)),handler_policy='Bounded independent retry, then preserve every stalled public example as failed.')
    if not f.exists():core.save(f,dict(utc=now(),amendment=desc))
    assert read(f)['amendment']==desc
    with browser.lock(run.OUT/'.lock'),patch.object(run,'units',timed_units):run.main()
