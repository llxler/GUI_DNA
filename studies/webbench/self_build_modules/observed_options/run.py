"""Preserve the first entry program and expose a bounded set of its actual Boolean reads."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
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

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/webbench-self-options-20261125'
CAP=1.30


def register():
    reg=OUT/'registration.json'
    paths=[Path(__file__),HERE/'options.cjs',HERE/'PROTOCOL.md',Path(base.__file__),entry.OUT/'registration.json',
           entry.ACORN,Path(entry.__file__),duo.OUT/'registration.json']
    sums={str(f.relative_to(ROOT)):sha(f) for f in paths}
    if reg.exists():
        assert read(reg)['sources']==sums
        return
    pilot=ledger_read.totals(delivery.OLD/'budget.sqlite3')
    old_suite=ledger_read.totals(suites.OUT/'budget.sqlite3')
    assert all((suites.OUT/p/t/r/'seal.json').exists() for p,t in suites.ORDER for r in ('a','b'))
    assert pilot['exposure_usd']+old_suite['exposure_usd']+delivery.CAP+entry.CAP+duo.CAP+CAP<=10
    balance=check_credits(CAP)
    assert balance['sufficient']
    core.save(reg,dict(sources=sums,utc=now(),balance=balance,cap=CAP,deadline=base.END.isoformat(),
                       pilot=pilot,original_suite=old_suite,cells=base.ORDER))
    for p in base.GROUPS:
        core.save(OUT/'inputs'/p/'browser.json',read(entry.OUT/'inputs'/p/'browser.json'))


def build(ledger,case,root,public):
    project,tag,rep=case
    folder=entry.OUT/project/tag/rep/'build/entry-1'
    stamps=[s for s in sorted(folder.glob('transmission-*/settled.json')) if
            read(s.with_name('response.json'))['choices'][0]['finish_reason']!='error']
    if not stamps:
        raise ValueError('First entry source was not delivered')
    stamp=stamps[0]
    response=stamp.with_name('response.json')
    assert sha(response)==read(stamp)['response_sha256']
    raw=read(response)['choices'][0]['message'].get('content') or ''
    source=base.uncode(raw)
    if source.startswith('FILE: index.js\n'):source=source.partition('\n')[2]
    proc=subprocess.run(['node',str(HERE/'options.cjs'),str(entry.ACORN)],input=source,text=True,
                        capture_output=True,timeout=10)
    if proc.returncode:
        raise ValueError('No usable literal in the first entry: '+proc.stderr[:400])
    parsed=json.loads(proc.stdout)
    fields=parsed['fields']
    defaults={f['key']:f['value'] for f in fields}
    overrides=', '.join(json.dumps(f['name'])+':globalThis.APP_CONFIG['+json.dumps(f['key'])+']' for f in fields)
    code=parsed['before']+'Object.assign({}, '+parsed['literal']+', {'+overrides+'})'+parsed['after']
    options=[defaults]+[{**defaults,k:not v} for k,v in defaults.items()]
    for i,setting in enumerate(options):
        controls=[dict(id=f['key'],type='boolean',values=[],default=str(setting[f['key']]).lower(),
                       example=str(setting[f['key']]).lower(),behavior='Toggle '+f['name']+' in the generated application.')
                  for f in fields]
        pkg=core.package(public,dict(design='Publicly checked controls in the submitted entry program.',controls=controls,
                                     files=[dict(path='index.js',content=code)],css='',script='',anchor='',fragment=''))
        dst=root/f'configuration-{i}'
        core.save(dst/'package.json',pkg)
        errs=base.check(public,pkg,dst)
        if not errs:
            fixed=dst/'first'
            return dict(status='valid',package=str((dst/'package.json').relative_to(ROOT)),package_sha256=sha(dst/'package.json'),
                        fixed=str(fixed.relative_to(ROOT)),fixed_files=browser.tree(fixed),source_sha256=sha(response),
                        model_defaults=defaults,calibrated=setting,fields=fields)
    raise ValueError('Neither the model default nor any single-key flip passed the public operation')


def main():
    register()
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    browser.OUT=OUT
    waiting=[(p,t,r) for p,t in base.ORDER for r in ('a','b')]
    with patch.multiple(base,OUT=OUT,build=build),ThreadPoolExecutor(max_workers=4) as pool:
        jobs=[]
        while waiting:
            for case in waiting[:]:
                folder=Path(*case)
                status=entry.OUT/folder/'build/status.json'
                skip=entry.OUT/folder/'skip.json'
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
