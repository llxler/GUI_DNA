"""Apply the same typed interfaces to the five previously unobserved Self cells."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import subprocess
import sys
from unittest.mock import patch

from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import core,browser
from studies.study_io import ROOT,now,read,sha
from studies.webbench.typed_components import run as typed

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/typed-missing-20261125'
CAP=.35
ROSTER={'table':['gemma','qwen9'],'svg-chart':['qwen9','oss','mistral']}


def register():
    path=OUT/'registration.json'
    if path.exists():
        reg=read(path)
        assert all(sha(ROOT/f)==h for f,h in reg['sources'].items())
        return reg
    from studies.paper_performance import current_group
    m=read(typed.compact.MATRIX)
    cases=[]
    for p,tags in ROSTER.items():
        for t in tags:
            model=typed.base.template(p,t,'plan')['model']
            g=current_group(m[model],p)
            assert 'self' not in g['passed']
            record=dict(model=model,targets=g['targets'],previous=None,direct=g['passed']['direct'])
            cases.append(dict(project=p,builder=t,arm='self',public=str((typed.base.old_root(p,'qwen')/'inputs'/p/'public.json').relative_to(ROOT)),deploy={t:record}))
    files=[Path(__file__),HERE/'PROTOCOL.md',Path(typed.__file__),typed.OUT/'registration.json']
    balance=check_credits(CAP)
    assert balance['sufficient']
    core.save(path,dict(utc=now(),deadline=typed.compact.END.isoformat(),balance=balance,cap=CAP,cases=cases,sources={str(f.relative_to(ROOT)):sha(f) for f in files}))
    return read(path)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('register','generate','case','score','publish'))
    parser.add_argument('index',type=int,nargs='?')
    args=parser.parse_args()
    cases=register()['cases']
    if args.action=='generate':
        def child(i):
            subprocess.run([sys.executable,'-m','studies.webbench.typed_components.unavailable.run','case',str(i)],check=True)
        with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(child,range(len(cases))))
    with patch.multiple(typed,OUT=OUT,CAP=CAP):
        if args.action=='case':typed.generate(cases[args.index])
        if args.action=='score':
            import time
            from datetime import datetime,timezone
            for k in tuple(os.environ):
                if k.endswith(('_API_KEY','_AUTH_TOKEN','_ACCESS_TOKEN')):os.environ.pop(k)
            browser.OUT=OUT
            while datetime.now(timezone.utc)<typed.compact.END:
                pending=False
                for c in cases:
                    f=OUT/c['project']/c['builder']
                    if not (f/'result.json').exists():
                        if (f/'seal.json').exists():typed.score(c)
                        else:pending=True
                if not pending:break
                time.sleep(2)
        if args.action=='publish':
            core.save(HERE/'result.json',dict(registration_sha256=sha(OUT/'registration.json'),cost=ledger_read.totals(OUT/'budget.sqlite3'),cases=[read(OUT/c['project']/c['builder']/'result.json') for c in cases]))
