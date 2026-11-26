"""Bound a browser evaluation even if a candidate's synchronous JS monopolizes the page."""
from contextlib import nullcontext
from pathlib import Path
import json
import os
import signal
import subprocess
import sys
from unittest.mock import patch

from studies.public_library_transfer import browser,core
from studies.study_io import digest,read
from . import run

MODULE='studies.webbench.table.selection_binding.replication.bounded'


def descendants(pid):
    children=set()
    for f in Path(f'/proc/{pid}/task').glob('*/children'):
        try:children.update(map(int,f.read_text().split()))
        except FileNotFoundError:continue
    return children.union(*(descendants(n) for n in children))


def one(root,candidate,mode,seconds):
    payload=json.dumps(dict(root=str(root),candidate=candidate,mode=mode))
    with browser.browser_slot():
        proc=subprocess.Popen([sys.executable,'-m',MODULE],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE,text=True,start_new_session=True)
        try:
            output,err=proc.communicate(payload,timeout=seconds)
        except subprocess.TimeoutExpired:
            for pid in descendants(proc.pid)|{proc.pid}:
                try:os.kill(pid,signal.SIGKILL)
                except ProcessLookupError:pass
            proc.communicate()
            return None
        if proc.returncode:
            raise RuntimeError(err[-1600:])
        return json.loads(output)


def measure(root,candidate,mode='standard'):
    f=run.OUT/'public-time-bounds'/mode/(digest(candidate['files'])+'.json')
    if not f.exists():
        durations=[]
        value=None
        for seconds in (35,60):
            value=one(root,candidate,mode,seconds)
            if value is not None:break
            durations.append(seconds)
        if value is None:
            names=list(run.parent.public.OWNERS)+(['range'] if mode=='range' else [])
            value=dict(checks=dict.fromkeys(names,False),errors=['Public browser did not return within 35s or 60s; capability unverified'])
        core.save(f,dict(candidate_sha256=digest(candidate['files']),timeouts=durations,result=value))
    return read(f)['result']


if __name__=='__main__':
    args=json.load(sys.stdin)
    root=Path(args['root'])
    # The parent holds one shared browser slot until this entire worker exits.
    with patch.object(browser,'browser_slot',nullcontext),patch.object(run.projection,'OUT',root):
        value=run.parent.public.measure(root,args['candidate']) if args['mode']=='standard' else run.projection.observe(args['candidate'])
    print(json.dumps(value))
