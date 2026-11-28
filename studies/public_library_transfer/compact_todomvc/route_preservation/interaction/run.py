"""Cross the saved view and route functions within each Ministral library, without new model calls."""
from itertools import product
from pathlib import Path

from studies.public_library_transfer import browser, core
from studies.public_library_transfer.compact_todomvc.route_preservation import run as route
from studies.study_io import ROOT, now, read, sha

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/todo-route-view-interaction-20261128'
TAG='ministral3'
MODEL=route.weak.MODELS[TAG]
STAGES=(route.view.choices.HERE/'result.json',route.view.HERE/'result.json',route.HERE/'result.json')


def main():
    reg,seal,result=OUT/'registration.json',OUT/'seal.json',HERE/'result.json'
    libs={r:(route.state.OUT/TAG/r/'library.json',route.OUT/TAG/r/'library.json') for r in 'ab'}
    paths=[Path(__file__),HERE/'PROTOCOL.md',*STAGES,route.view.choices.OUT/'seal.json',Path(route.state.todo.MOD.__file__)]
    sums={str(p.relative_to(ROOT)):sha(p) for p in [*paths,*(p for pair in libs.values() for p in pair)]}
    if not reg.exists():
        core.save(reg,dict(utc=now(),sources=sums,paid_calls=0))
    assert read(reg)['sources']==sums
    targets,_=route.weak.suite.inputs()
    if not seal.exists():
        votes=read(route.view.choices.OUT/'seal.json')['decisions'][TAG]
        jobs=[]
        for rep,(a,b) in libs.items():
            old,new=read(a)['functions'],read(b)['functions']
            assert {k for k in old if old[k]!=new[k]}<={'select','route'}
            for use_view,use_route in product((False,True),repeat=2):
                funcs=old|{'select':(new if use_view else old)['select'],'route':(new if use_route else old)['route']}
                for task in sorted(k for k in votes[rep] if k in targets):
                    for mode in ('planned','fixed'):
                        choice=votes[rep][task]
                        if mode=='planned' and choice['status']!='valid':
                            candidate=dict(status=choice['status'])
                        else:
                            disabled=choice['disabled'] if mode=='planned' else []
                            code=route.state.todo.MOD.assemble(funcs,{k:k not in disabled for k in route.state.ALL})
                            folder=OUT/'pages'/rep/f'{int(use_view)}{int(use_route)}'/task/mode
                            candidate=route.state.candidate(folder,code)
                        jobs.append(dict(rep=rep,view=use_view,route=use_route,mode=mode,task=task,**candidate))
        core.save(seal,dict(registration=sha(reg),jobs=jobs))
    if result.exists():
        return
    assert read(seal)['registration']==sha(reg)
    cache={}
    for p in STAGES:
        for r in read(p)['models'][MODEL]['rows']:
            if r['status']=='valid':
                key=(r['task'],r['files_sha256'])
                if key in cache:
                    assert cache[key]['passed']==r['passed']
                cache[key]=r
    server=route.weak.evaluate.todo.Server(OUT)
    rows=[]
    try:
        for item in read(seal)['jobs']:
            task=item['task']
            row={k:v for k,v in item.items() if k!='file'}
            row['passed']=False if item['status']=='invalid' else None
            if item['status']=='valid':
                path=ROOT/item['file']; digest=sha(path); assert digest==item['files_sha256']
                key=task,digest
                reused=key in cache
                if not reused:
                    dest=OUT/'scores'/task/digest
                    with browser.browser_slot():
                        route.weak.evaluate.score(('todomvc',targets[task],read(path),dest,server))
                    cache[key]=route.weak.recovery.todo.binding.official(dest,targets[task],{})
                row.update(passed=cache[key]['passed'],report_sha256=cache[key]['report_sha256'],reused=reused)
            rows.append(row)
    finally:
        server.close()
    core.save(result,dict(registration=sha(reg),seal=sha(seal),paid_calls=0,rows=rows))


if __name__=='__main__':
    with browser.lock(OUT/'study.lock'):
        main()
