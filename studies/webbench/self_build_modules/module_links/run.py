"""Link declarations from the model's own package before asking for a file repair."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import re
import subprocess
import time
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.public_library_transfer.self_refinement.suite_recovery import run as suites
from studies.public_library_transfer.self_refinement.suite_recovery.duo_confirmation import run as duo
from studies.study_io import ROOT,read,sha,now
from .. import run as base
from ..source_delivery import run as delivery
from ..entry_recovery import run as entry
from ..observed_options import run as options

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/webbench-self-links-20261125'
CAP=1.75
NODE=ROOT/'artifacts/benchmark-probe/WebApp1k/staging/package.json'


def register():
    reg=OUT/'registration.json'
    paths=[Path(__file__),HERE/'link.cjs',HERE/'PROTOCOL.md',Path(base.__file__),options.OUT/'registration.json',
           NODE,NODE.parent/'node_modules/@babel/parser/package.json',NODE.parent/'node_modules/@babel/traverse/package.json']
    sums={str(p.relative_to(ROOT)):sha(p) for p in paths}
    if reg.exists():
        assert read(reg)['sources']==sums
        return
    # All stages with released allocations have either sealed every scheduled branch or closed every route.
    while not all((delivery.OUT/p/t/r/'seal.json').exists() for p,t in base.ORDER for r in ('a','b')):
        time.sleep(3)
    prior={r.name:ledger_read.totals(r/'budget.sqlite3') for r in (suites.OUT,delivery.OLD,delivery.OUT)}
    assert sum(x['exposure_usd'] for x in prior.values())+duo.CAP+options.CAP+entry.CAP+CAP<=10
    balance=check_credits(CAP)
    assert balance['sufficient']
    core.save(reg,dict(sources=sums,utc=now(),balance=balance,cap=CAP,prior=prior,cells=base.ORDER,deadline=base.END.isoformat()))
    for p in base.GROUPS:
        core.save(OUT/'inputs'/p/'browser.json',read(delivery.OUT/'inputs'/p/'browser.json'))


def link(files,public):
    available=sorted(set(public['starter']) | set(public['assets']) | set(files))
    result=subprocess.run(['node',str(HERE/'link.cjs'),str(NODE)],input=json.dumps(dict(files=files,available=available)),
                          text=True,capture_output=True,timeout=20)
    if result.returncode:
        raise ValueError('Module graph could not be parsed: '+result.stderr[:600])
    return json.loads(result.stdout)


def location(errors,graph,files):
    def allowed(p):
        if not p.endswith(('.js','.mjs','.css','.scss')):
            return False
        try:
            core.files_map([dict(path=p,content='')])
            return True
        except ValueError:
            return False
    for item in graph['missing']:
        if allowed(item['target']):
            return item['target']
    for error in errors:
        paths=re.findall(r'<origin>/([A-Za-z0-9_./-]+\.(?:m?js|css|scss))',error)
        for path in paths:
            if path in files:
                return path
    return 'index.js'


def build(ledger,case,root,public):
    project,tag,rep=case
    first=delivery.OUT/project/tag/rep/'build/v0/package.json'
    if not first.exists():
        raise ValueError('No complete initial module bundle')
    pkg=read(first)
    for i in range(3):
        dest=root/f'v{i}'
        graph=link(pkg['files'],public)
        pkg={**pkg,'files':graph['files']}
        core.save(dest/'package.json',pkg)
        core.save(dest/'linkage.json',{'prior_package_sha256':sha(first),'changes':graph['changes'],'missing':graph['missing']})
        errors=base.check(public,pkg,dest)
        if not errors:
            fixed=dest/'first'
            return dict(status='valid',package=str((dest/'package.json').relative_to(ROOT)),package_sha256=sha(dest/'package.json'),
                        fixed=str(fixed.relative_to(ROOT)),fixed_files=browser.tree(fixed),version=i,prior_package_sha256=sha(first))
        if i==2:break
        target=location(errors,graph,pkg['files'])
        prompt='Repair exactly one local file in your browser library. Return only the complete raw source for the requested path. '
        prompt+='Use its actual local imports, exports and DOM. Preserve the public API, configuration and all other files. No tools or external packages.'
        context=dict(public=public,only_file=target,public_errors=errors,missing_dependencies=graph['missing'],
                     configuration=pkg['controls'],your_sources=pkg['files'])
        raw=base.request(ledger,case,root/f'repair-{i+1}',core.messages(prompt,context),'build',8500)
        fixed=delivery.extract(raw,[target]).get(target)
        if not fixed or base.diagnose_source(target,fixed):
            raise ValueError('Targeted source was not delivered or did not parse: '+target)
        core.save(root/f'repair-{i+1}'/'replacement.json',{'path':target,'source':fixed})
        pkg=deepcopy(pkg)
        pkg['files'][target]=fixed
    raise ValueError('After dependency repair: '+' | '.join(errors)[:1300])


def main():
    register()
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    browser.OUT=OUT
    waiting=[(p,t,r) for p,t in base.ORDER for r in ('a','b')]
    with patch.multiple(base,OUT=OUT,build=build),ThreadPoolExecutor(max_workers=5) as pool:
        jobs=[]
        while waiting:
            for case in waiting[:]:
                folder=Path(*case)
                status=options.OUT/folder/'build/status.json'
                skip=options.OUT/folder/'skip.json'
                ref=status if status.exists() else skip
                if not ref.exists():continue
                if status.exists() and read(status)['status']=='build_failed':
                    jobs.append(pool.submit(base.branch,case,ledger))
                else:
                    core.save(OUT/folder/'skip.json',{'source':str(ref.relative_to(ROOT)),'sha256':sha(ref)})
                waiting.remove(case)
            if waiting:time.sleep(3)
        for job in jobs:job.result()


if __name__=='__main__':
    main()
