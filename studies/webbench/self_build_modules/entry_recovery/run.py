"""Conditionally recover failed preparations with one model-authored ES module."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import subprocess
import time
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.public_library_transfer.self_refinement.todomvc.source_binding.run import ACORN
from studies.study_io import ROOT, read, sha, now
from .. import run as base
from ..source_delivery import run as delivery

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/webbench-self-entry-20261125'
CAP=2.40
PROMPT="""Implement this complete public browser app in one self-contained, executable ES module index.js.
Use the exact public starter HTML and public assets. Write all required behavior classes together in this
module; do not import your own modules. Public asset imports are allowed. If necessary inject your own
CSS and create DOM in your code. Implement real events, persistence and the integrated app. Keep the
public element names, types, constructor behavior and geometry. Use one shared model of state.
In your code declare exactly once const DNA_OPTIONS = { ... }; give it one to four meaningful named
boolean literals whose defaults run the integrated app. Read each key as DNA_OPTIONS.key or
DNA_OPTIONS['key'] in actual behavior. The assembler supplies the values. No task dispatch, external
tools or explanations. Return only the complete index.js source as raw JavaScript."""


def register():
    files=[Path(__file__),HERE/'PROTOCOL.md',HERE/'interface.cjs',ACORN,Path(delivery.__file__),
           Path(base.__file__),delivery.OUT/'registration.json']
    sums={str(p.relative_to(ROOT)):sha(p) for p in files}
    reg=OUT/'registration.json'
    if reg.exists():
        assert read(reg)['sources']==sums
        return
    previous=ledger_read.totals(delivery.OLD/'budget.sqlite3')
    assert previous['exposure_usd']+delivery.CAP+CAP+2.50<=10
    assert all((delivery.OLD/f'closed-{tag}.json').exists() for _,tag in base.ORDER)
    balance=check_credits(CAP)
    assert balance['sufficient']
    core.save(reg,dict(utc=now(),previous=previous,balance=balance,sources=sums,deadline=base.END.isoformat(),
                       cap=CAP,cells=base.ORDER,decision='First publicly admitted source per repetition.'))
    for p in base.GROUPS:
        core.save(OUT/'inputs'/p/'browser.json',read(delivery.OUT/'inputs'/p/'browser.json'))


def freeze(public,source):
    proc=subprocess.run(['node',str(HERE/'interface.cjs'),str(ACORN)],input=source,text=True,
                        capture_output=True,timeout=10)
    if proc.returncode:
        raise ValueError(proc.stderr[-2500:])
    parsed=json.loads(proc.stdout)
    fields=parsed['fields']
    names={k:re.sub('([a-z0-9])([A-Z])',r'\1-\2',k).replace('_','-').lower() for k in fields}
    if len(set(names.values()))!=len(names):
        raise ValueError('Two option names are indistinguishable after case normalization')
    # Preserve the model's literal and use its defaults for configurations not provided.
    mappings=','.join(json.dumps(k)+': globalThis.APP_CONFIG['+json.dumps(n)+']' for k,n in names.items())
    configured='Object.assign({}, '+parsed['literal']+', {'+mappings+'})'
    # Conditional replacement retains original literal values whenever no setting differs.
    differs=' || '.join('globalThis.APP_CONFIG['+json.dumps(names[k])+'] !== '+json.dumps(v) for k,v in fields.items())
    code=parsed['before']+'('+differs+' ? '+configured+' : '+parsed['literal']+')'+parsed['after']
    controls=[dict(id=names[k],type='boolean',values=[],default=str(v).lower(),example=str(v).lower(),
                   behavior='Toggle '+k+' in the integrated application. Default '+str(v)+'.') for k,v in fields.items()]
    return core.package(public,dict(design='Use the model-defined behavior switches of the shared entry module.',
                        controls=controls,files=[dict(path='index.js',content=code)],css='',script='',anchor='',fragment=''))


def build(ledger,case,root,public):
    project=case[0]
    msgs=core.messages(PROMPT,public)
    defects=[]
    for i in range(3):
        reply=base.request(ledger,case,root/f'entry-{i+1}',msgs,'build',15000)
        source=base.uncode(reply)
        if source.startswith('FILE: index.js\n'):
            source=source.partition('\n')[2]
        try:
            pkg=freeze(public,source)
            dest=root/f'v{i}'
            core.save(dest/'package.json',pkg)
            errors=base.check(public,pkg,dest)
            if not errors:
                fixed=dest/'first'
                return dict(status='valid',version=i,package=str((dest/'package.json').relative_to(ROOT)),
                            package_sha256=sha(dest/'package.json'),fixed=str(fixed.relative_to(ROOT)),fixed_files=browser.tree(fixed))
            why=' | '.join(errors)[:2000]
        except base.ERRORS as exc:
            why=str(exc)[:2200]
        defects.append(why)
        msgs=core.messages(PROMPT+' Correct the public error and return the complete module.',
                           dict(public=public,your_source=source,public_error=why))
    raise ValueError('Public entry admission: '+defects[-1])


def main():
    register()
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    browser.OUT=OUT
    jobs=[(p,t,r) for p,t in base.ORDER for r in ('a','b')]
    with patch.multiple(base,OUT=OUT,build=build),ThreadPoolExecutor(max_workers=6) as pool:
        running=[]
        waiting=jobs[:]
        while waiting:
            for case in waiting[:]:
                p,t,r=case
                status=delivery.OUT/p/t/r/'build/status.json'
                if status.is_file():
                    if read(status)['status']=='build_failed':
                        running.append(pool.submit(base.branch,case,ledger))
                    else:
                        core.save(OUT/p/t/r/'skip.json',dict(primary_status=read(status)['status'],status_sha256=sha(status)))
                    waiting.remove(case)
            if waiting:time.sleep(3)
        for job in running:job.result()


if __name__=='__main__':
    main()
