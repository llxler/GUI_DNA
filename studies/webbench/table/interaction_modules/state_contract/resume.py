"""Acquire browser capacity before starting a registered probe's wall-clock timeout."""
from contextlib import nullcontext
from pathlib import Path
import json
import runpy
import sys
from unittest.mock import patch

from studies.public_library_transfer import core,browser
from studies.study_io import ROOT,now,read,sha
from . import run as state

if __name__=='__main__' and sys.argv[1:2]==['reserved']:
    module,*args=sys.argv[2:]
    assert module in ('studies.webbench.table.interaction_modules.probe','studies.webbench.table.interaction_modules.state_contract.trace','studies.webgen_bench.functional_pilot.native_plans.run')
    sys.argv=[module,*args]
    with patch.object(browser,'browser_slot',nullcontext):runpy.run_module(module,run_name='__main__',alter_sys=True)
elif __name__=='__main__':
    parent=state.parent
    def obs(candidate):
        import subprocess,os,signal
        def bounded(module,arguments,payload,seconds):
            with browser.browser_slot():
                proc=subprocess.Popen([sys.executable,'-m',__spec__.name,'reserved',module,*arguments],text=True,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
                try:
                    out,err=proc.communicate(payload,timeout=seconds)
                except subprocess.TimeoutExpired:
                    for pid in parent.descendants(proc.pid)|{proc.pid}:
                        try:os.kill(pid,signal.SIGKILL)
                        except ProcessLookupError:pass
                    proc.communicate();return None
                if proc.returncode:raise RuntimeError(err[-900:])
                return out
        result=bounded('studies.webbench.table.interaction_modules.probe',[],json.dumps(candidate),32)
        checks=json.loads(result) if result else dict(checks={},errors=['Public browser exceeded 32 seconds after admission'])
        trace=bounded('studies.webbench.table.interaction_modules.state_contract.trace',[candidate['page']],None,20)
        checks['trace']=trace.strip()[:700] if trace else 'Unavailable after 20 seconds of actual browser execution'
        return checks
    with browser.lock(state.OUT/'run.lock'),patch.multiple(parent,OUT=state.OUT,HERE=state.HERE,ABI=state.ABI,emit=state.emit,observe=obs,CAP=state.CAP,SEED=state.SEED):
        file=state.OUT/'capacity-recovery.json'
        if not file.exists():core.save(file,dict(utc=now(),registered=sha(state.OUT/'registration.json'),wrapper=sha(Path(__file__)),cause='Uncaught optional trace timeout while waiting for the cross-study browser pool; preserve all existing sources and complete the open registration.'))
        r=state.register();parent.generate(r);parent.score()
