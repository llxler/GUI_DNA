"""Run the locked Qwen pipeline on two fresh construction seeds."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,read,sha,now
from ...action_contracts import runtime
from .. import run as projection,typed_fields

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/table-binding-replication-20261126'
CAP=1.50
TAG='qwen9'
SEED=2026112601
parent=projection.parent
feedback=projection.contracts.feedback
contracts=projection.contracts
base=parent.compact.base
REQUEST=base.request
SETTINGS=parent.settings


def register():
    f=OUT/'registration.json'
    reg=read(typed_fields.OUT/'registration.json')
    files=[Path(__file__),HERE/'PROTOCOL.md',Path(parent.__file__),Path(parent.build.__file__),parent.build.HERE/'host.js',
           Path(parent.public.__file__),Path(feedback.__file__),Path(contracts.__file__),contracts.HERE/'units.cjs',
           Path(runtime.__file__),Path(projection.__file__),projection.HERE/'state.cjs',projection.HERE/'state.py',
           Path(typed_fields.__file__),typed_fields.RESULT,ROOT/reg['public']]
    hashes={str(p.relative_to(ROOT)):sha(p) for p in files}
    if not f.exists():
        b=check_credits(CAP)
        assert b['sufficient']
        core.save(f,dict(utc=now(),cap=CAP,deadline=parent.END.isoformat(),balance=b,sources=hashes,seeds=[SEED,SEED+1],
                         public=reg['public'],targets=reg['targets']))
    assert read(f)['sources']==hashes
    return read(f)


def settings(project,tag,stage):
    return {**SETTINGS(project,tag,stage),'seed':SEED}


def binding_request(ledger,case,folder,messages,stage,size):
    raw=REQUEST(ledger,case,folder,messages,stage,size)
    if folder.name!='binding-call':return raw
    try:
        v=typed_fields.parse(raw)
        if isinstance(v,dict) and v.get('collection')=='selected':return raw
    except ValueError:pass
    msg=messages+[dict(role='assistant',content=raw),dict(role='user',content='Public binding type check failed. Runtime property types on ctx: table=HTMLTableElement, menu=HTMLDivElement, selected=Set, active=Element or null, anchor=Element or null, target=Element or null. Choose a Set for collection. Reply with the complete corrected JSON declaration.')]
    return REQUEST(ledger,case,folder/'type-repair',msg,stage,size)


def main(phase):
    reg=register()
    final=OUT/'binding'
    if phase=='generate':
        pub=read(ROOT/reg['public'])
        ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
        steps=[(parent,'foundation'),(feedback,'feedback'),(contracts,'contracts')]
        for mod,name in steps:
            with ExitStack() as stack:
                stack.enter_context(patch.multiple(base,OUT=OUT,END=parent.END,template=settings))
                if mod==feedback:stack.enter_context(patch.object(feedback,'PARENT',OUT/'foundation'))
                if mod==contracts:
                    stack.enter_context(patch.multiple(contracts,SOURCE=OUT/'foundation',units=runtime.timed_units))
                    stack.enter_context(patch.object(feedback,'OUT',OUT/'feedback'))
                stack.enter_context(patch.object(mod,'OUT',OUT/name))
                with ThreadPoolExecutor(max_workers=2) as pool:
                    list(pool.map(lambda r:mod.prepare(TAG,r,pub,ledger),('a','b')))
        # projection.generate creates a ledger at its stage root. Use an alias to the single registered ledger.
        final.mkdir(parents=True,exist_ok=True)
        link=final/'budget.sqlite3'
        if not link.exists():link.symlink_to(OUT/'budget.sqlite3')
        core.save(final/'registration.json',read(OUT/'registration.json'))
        with patch.multiple(contracts,OUT=OUT/'contracts'),patch.object(feedback,'OUT',OUT/'feedback'),patch.object(parent,'settings',settings),patch.multiple(
                projection,OUT=final,CAP=CAP,TAGS=(TAG,),REPS={TAG:('a','b')}),patch.multiple(base,request=binding_request,parse_json=typed_fields.parse):
            projection.generate(reg)
        # Confirm the actual seeds in the provider request, independently of the registration.
        for r,seed in zip(('a','b'),(SEED,SEED+1),strict=True):
            req=read(OUT/'foundation'/TAG/r/'calls/markSelection/first/transmission-1/request.json')
            assert req['body']['seed']==seed
        return
    with patch.multiple(projection,OUT=final,HERE=HERE,CAP=CAP,TAGS=(TAG,),REPS={TAG:('a','b')}):
        projection.score(reg)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('phase',choices=('generate','score'))
    phase=p.parse_args().phase
    with browser.lock(OUT/(phase+'.lock')):main(phase)
