"""Resolve an explicit owner prefix and give one type diagnostic for an invalid binding."""
from pathlib import Path
from unittest.mock import patch

from scripts.check_openrouter_credits import check_credits
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,read,sha,now
from . import run as initial

OUT=ROOT/'artifacts/table-typed-binding-20261126'
PARENT=initial.OUT
RESULT=initial.HERE/'typed-result.json'
CAP=.65
base=initial.parent.compact.base
PARSE=base.parse_json
REQUEST=base.request


def parse(raw):
    value=PARSE(raw)
    if isinstance(value,dict) and value.get('collection')=='ctx.selected':
        return {**value,'collection':'selected'}
    return value


def receive(ledger,case,folder,messages,stage,size):
    if folder.name!='binding-call':return REQUEST(ledger,case,folder,messages,stage,size)
    _,tag,rep=case
    source=PARENT/tag/rep/'binding-call'
    receipt=next(source.glob('transmission-*/settled.json'),None)
    if receipt is None:
        return REQUEST(ledger,case,folder,messages,stage,size)
    response=receipt.with_name('response.json')
    assert sha(response)==read(receipt)['response_sha256']
    raw=read(response)['choices'][0]['message'].get('content') or ''
    core.save(folder/'reused.json',dict(response=str(response.relative_to(ROOT)),sha256=sha(response)))
    try:
        value=parse(raw)
        if isinstance(value,dict) and value.get('collection')=='selected':return raw
    except ValueError:pass
    msg=messages+[dict(role='assistant',content=raw),dict(role='user',content='Public binding type check failed. Runtime property types on ctx: table=HTMLTableElement, menu=HTMLDivElement, selected=Set, active=Element or null, anchor=Element or null, target=Element or null. Choose a Set for collection. Reply with the complete corrected JSON declaration.')]
    return REQUEST(ledger,case,folder/'type-repair',msg,stage,size)


def main(phase):
    f=OUT/'registration.json'
    old=read(PARENT/'registration.json')
    records=[*PARENT.glob('*/*/binding-call/transmission-*/settled.json')]
    paths=[Path(__file__),initial.HERE/'TYPED_FIELDS.md',PARENT/'registration.json',Path(initial.__file__),*records]
    sums={str(p.relative_to(ROOT)):sha(p) for p in paths}
    if not f.exists():
        balance=check_credits(CAP)
        assert balance['sufficient'] and len(records)==4
        core.save(f,dict(utc=now(),deadline=initial.parent.END.isoformat(),cap=CAP,balance=balance,sources=sums,
                         public=old['public'],targets=old['targets']))
    assert sums==read(f)['sources']
    with patch.multiple(initial,OUT=OUT,CAP=CAP),patch.multiple(base,parse_json=parse,request=receive):
        if phase=='generate':initial.generate(read(f))
        else:
            # The frozen scorer accepts its output through the module's stage directory.
            with patch.object(initial,'HERE',OUT/'summary'):
                initial.score(read(f))
            core.save(RESULT,read(OUT/'summary/result.json'))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('phase',choices=('generate','score'))
    phase=parser.parse_args().phase
    with browser.lock(OUT/(phase+'.lock')):main(phase)
