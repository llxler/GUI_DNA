"""Check candidate actions independently, then admit the assembled real browser page."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
from unittest.mock import patch

from scripts.check_openrouter_credits import check_credits
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,now,read,sha
from ..action_library import run as parent
from ..action_library.event_feedback import run as feedback

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/table-action-contracts-20261126'
CAP=1.40
TAGS=feedback.TAGS
REPS=feedback.REPS
SOURCE=parent.OUT
build,public=parent.build,parent.public


def register():
    reg=read(SOURCE/'registration.json')
    files=[HERE/'PROTOCOL.md',Path(__file__),HERE/'units.cjs',Path(parent.__file__),Path(feedback.__file__),
           Path(build.__file__),Path(public.__file__),SOURCE/'registration.json',feedback.OUT/'registration.json']
    files += [p/tag/r/'library.json' for p in (SOURCE,feedback.OUT) for tag in TAGS for r in ('a','b')]
    receipts=[]
    for tag in TAGS:
        for rep in REPS[tag]:
            for p in (SOURCE,feedback.OUT):
                receipts+=list((p/tag/rep/'calls').glob('**/settled.json'))
    files+=receipts
    hashes={str(f.relative_to(ROOT)):sha(f) for f in files}
    path=OUT/'registration.json'
    if not path.exists():
        balance=check_credits(CAP)
        assert balance['sufficient']
        core.save(path,dict(utc=now(),deadline=parent.END.isoformat(),cap=CAP,balance=balance,sources=hashes,
                            public=reg['public'],targets=reg['targets']))
    assert hashes==read(path)['sources']
    return read(path)


def units(name,fn):
    res=subprocess.run(['node',str(HERE/'units.cjs')],input=json.dumps(dict(name=name,source=fn)),
                       capture_output=True,text=True,check=True,timeout=12)
    return json.loads(res.stdout)


def variants(name,tag,rep,first):
    yield 'starting',first
    root=SOURCE/tag/rep/'calls'/name
    folders=[root/k for k in ('first','syntax','repair')]+[feedback.OUT/tag/rep/'calls'/k/name for k in ('first','second')]
    for folder in folders:
        for receipt in sorted(folder.glob('transmission-*/settled.json')):
            response=receipt.with_name('response.json')
            assert sha(response)==read(receipt)['response_sha256']
            try:
                raw=read(response)['choices'][0]['message'].get('content') or ''
                fn=build.extract(name,raw)
            except ValueError:break
            yield str(response.relative_to(ROOT)),fn
            break


def prepare(tag,rep,pub,ledger):
    folder=OUT/tag/rep
    path=folder/'library.json'
    if path.exists():return read(path)
    base=read(feedback.OUT/tag/rep/'library.json')['functions']
    def improve(name):
        tried=set()
        record=[]
        best=None
        def consider(label,fn):
            nonlocal best
            if fn in tried:return
            tried.add(fn)
            checks=units(name,fn)
            n=sum(v['passed'] for v in checks.values())
            record.append(dict(source=label,checks=checks))
            if best is None or n>best[0]:
                best=(n,fn,checks)
        for label,fn in variants(name,tag,rep,base[name]):consider(label,fn)
        for i in range(2):
            n,fn,checks=best
            if n==len(checks):break
            args=build.ACTIONS[name][2]
            failed={k:v for k,v in checks.items() if not v['passed']}
            msg=core.messages('Implement a single small browser event handler. Use just one complete JavaScript function. '
               'Prefer a straightforward implementation under 35 lines. Use only variables defined in the signature or locally. '
               'Use the DOM provided by ctx. No module imports, frameworks, global current selection, event installation or unrelated features.',
               dict(signature=f'function {name}({args})',interface=build.CONTRACT,role=build.ACTIONS[name][4],
                    failing=failed,successes=[k for k,v in checks.items() if v['passed']],
                    example_interfaces=['ctx.select([cell], cell, cell) sets the active selection. Its three arguments are cells to select, active cell, anchor cell.',
                      'On ordinary document click, cell may be null on hide. ctx.target is null until a contextmenu.'],
                    previous=fn if i else None))
            dest=folder/'calls'/name/str(i+1)
            try:
                raw=parent.compact.base.request(ledger,('table',tag,rep),dest,msg,'build',2600)
                consider('fresh-'+str(i+1),build.extract(name,raw))
            except (ValueError,*parent.typed.MISSING):continue
        return name,(best[1],record)
    with ThreadPoolExecutor(max_workers=3) as pool:actions=dict(pool.map(improve,base))
    candidates=[('parent',base),('isolated',{k:v[0] for k,v in actions.items()})]
    checks=[]
    def measure(label,fs):
        val=public.measure(OUT,build.page(pub,fs,build.OPTIONS,folder/'public'/label))
        return (public.admitted(val),sum(val['checks'].values()),-len(val['errors'])),val
    best=None
    for label,fs in candidates:
        rank,val=measure(label,fs)
        checks.append(dict(name=label,**val))
        if best is None or rank>best[0]:best=(rank,fs,label)
    # An isolated winner can interfere with a sibling. Integrate each non-identical winner in declared order.
    for name in build.ACTIONS:
        fn=actions[name][0]
        if best[1][name]==fn:continue
        fs={**best[1],name:fn}
        rank,val=measure(name,fs)
        checks.append(dict(name=name,**val))
        if rank>best[0]:best=(rank,fs,name)
    status='valid' if best[0][0] else 'build_failed'
    core.save(path,dict(tag=tag,rep=rep,status=status,reason='' if status=='valid' else 'Failed public integration',
        functions=best[1],selected=best[2],public=checks,unit_records={k:v[1] for k,v in actions.items()}))
    print(tag,rep,status,best[0],flush=True)
    return read(path)


def main():
    reg=register()
    with patch.multiple(parent,OUT=OUT,RESULT=HERE/'result.json',CAP=CAP,TAGS=TAGS,REPS=REPS,prepare=prepare):
        parent.generate(reg)
        parent.score(reg)


if __name__=='__main__':
    with browser.lock(OUT/'.lock'):main()
