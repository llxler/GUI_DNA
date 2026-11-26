"""Match the view's declared props and allow one same-model whole-module repair."""
from pathlib import Path
import argparse
import subprocess
from unittest.mock import patch

from scripts.check_openrouter_credits import check_credits
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, read, sha, now
from .. import run as base

HERE = Path(__file__).resolve().parent
OUT = ROOT/'artifacts/duo-prop-contract-20261126'
PARENT = base.OUT
CAP = .75


def register():
    seal=read(PARENT/'seal.json')
    assert all(sha(PARENT/p)==v for p,v in seal['sources'].items())
    paths=[Path(__file__),HERE/'PROTOCOL.md',HERE/'props.cjs',PARENT/'seal.json',base.HERE/'result.json',
           Path(base.__file__),Path(base.donor.components.__file__),base.compact.OUT/'public-contracts.json']
    hashes={str(p.relative_to(ROOT)):sha(p) for p in paths}
    f=OUT/'registration.json'
    if not f.exists():
        balance=check_credits(CAP)
        assert balance['sufficient']
        core.save(f,dict(utc=now(),sources=hashes,cap=CAP,deadline=base.action.END.isoformat(),
                         balance=balance,models={'qwen9':base.action.settings('table','qwen9','plan')['model']}))
    assert read(f)['sources']==hashes
    return read(f)


def failures(checks):
    return {(name,issue['public_case']) for name,entry in checks.items() for issue in entry['feedback']}


def repair(job):
    tag,rep,domain,names,label,public,ledger=job
    relative=Path(tag)/rep/domain/label
    folder=OUT/relative
    result=folder/'component.json'
    if result.exists():return
    previous=read(PARENT/relative/'component.json')
    src=previous.get('source')
    checks=previous.get('checks',{})
    events=[]
    def measure(candidate,stage):
        return {name:base.runtime.single((folder/'public'/stage/name,domain,name,candidate))[1] for name in names}
    if src:
        call=subprocess.run(['node',str(HERE/'props.cjs')],input=src,text=True,capture_output=True,check=True,timeout=10).stdout
        if call:
            assert src.count('return View(props,vm);')==1
            amended=src.replace('return View(props,vm);','return '+call+';')
            after=measure(amended,'binding')
            keep=failures(after)<failures(checks)
            events.append(dict(stage='declared-props',retained=keep,failures=sorted(failures(after))))
            if keep:src,checks=amended,after
    if not src or failures(checks):
        msg=core.messages('Return a complete default-export React component as one standalone JSX module. The module receives ordinary React props. Integrate real handlers, asynchronous responses and view state in one lexical scope. Read the supplied public context and errors, use the actual request/response shapes and accessible user actions. Do not import test facilities or mock anything. Preserve working success and failure cases.',dict(features=public,original_source=src,
            feedback={n:entry['feedback'] for n,entry in checks.items()}))
        try:
            raw=base.action.compact.base.request(ledger,('table',tag,rep),folder/'calls'/'module',msg,'plan' if rep=='direct' else 'build',6400)
            candidate=base.donor.components.extract(raw)
            if not candidate:raise ValueError('No complete React component')
            after=measure(candidate,'whole-module')
            keep=not src or failures(after)<failures(checks)
            events.append(dict(stage='whole-module',retained=keep,failures=sorted(failures(after))))
            if keep:src,checks=candidate,after
        except (ValueError,*base.action.typed.MISSING) as exc:
            events.append(dict(stage='whole-module',retained=False,reason=str(exc)[:240]))
    record=dict(status='valid',source=src,checks=checks) if src else previous
    core.save(result,dict(record,history=events))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('phase',choices=('generate','score'))
    phase=p.parse_args().phase
    with browser.lock(OUT/(phase+'.lock')):
        reg=register()
        with patch.multiple(base,OUT=OUT,HERE=HERE,TAGS=('qwen9',),CAP=CAP,component=repair):
            if phase=='generate':base.generate()
            else:base.score(reg)
