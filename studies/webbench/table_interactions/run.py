"""Test the four existing edit/selection profiles on the five flagged table rows."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import os
from pathlib import Path
import time
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from studies.webbench.compact_planning import run as compact
from studies.webbench.self_build_modules import run as base
from studies.webbench.transport_completion import extend

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/table-interactions-20261125'
RESULT = HERE / 'result.json'
CAP = .75


def register():
    path = OUT / 'registration.json'
    if path.exists():
        reg = read(path)
        assert all(sha(ROOT / p) == h for p,h in reg['sources'].items())
        return reg
    parent = compact.register()
    exposure = sum(read(extend.OUT/'registration.json')['prior_exposure'].values()) + extend.CAP
    assert exposure + CAP < 10
    balance = check_credits(CAP)
    assert balance['sufficient']
    cells = [dict(c, original_targets=c['targets'], targets=list(range(1,21))) for c in parent['cells']
             if c['project']=='table' and c['arm']=='gpt5-library']
    assert len(cells)==5
    files = [Path(__file__), HERE/'PROTOCOL.md', Path(compact.__file__), Path(base.__file__),
             compact.OUT/'registration.json', extend.OUT/'registration.json', compact.HERE/'table-actions.json']
    core.save(path,dict(utc=now(),cap=CAP,deadline=compact.END.isoformat(),prior_bound=exposure,balance=balance,
                        cells=cells,sources={str(p.relative_to(ROOT)):sha(p) for p in files}))
    return read(path)


def choices(pkg, arm, project):
    assert project=='table' and arm=='gpt5-library' and pkg['examples'][0]['plan']=={}
    fields=pkg['plan_schema']['properties']['interactions']['properties']
    assert fields['edit']['type']==fields['rectangleSelection']['type']=='boolean'
    return [{}, *[{'interactions':{'edit':edit,'rectangleSelection':rectangle}}
                  for edit,rectangle in ((False,True),(True,False),(False,False))]]


def main(action):
    reg=register()
    if action=='generate':
        template, request=base.template,base.request
        def settings(project, tag, stage):
            params=template(project, tag, stage)
            if tag in ('qwen9','deepseek-flash','deepseek-pro'):params['reasoning']={'enabled':False}
            return params
        def ask(ledger, case, root, messages, stage, limit):
            return request(ledger,case,root,messages,stage,8192 if case[1] in ('qwen9','deepseek-flash','deepseek-pro') else limit)
        ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
        with patch.multiple(compact,OUT=OUT,choices=choices),patch.multiple(base,OUT=OUT,END=compact.END,template=settings,request=ask),ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(lambda c:compact.produce(c,ledger),reg['cells']))
    if action=='score':
        for key in tuple(os.environ):
            if key.endswith(('_API_KEY','_AUTH_TOKEN','_ACCESS_TOKEN')):os.environ.pop(key)
        browser.OUT=OUT
        with patch.object(compact,'OUT',OUT):
            for c in reg['cells']:
                folder=OUT/c['project']/c['tag']/c['arm']
                while not (folder/'seal.json').exists():
                    if datetime.now(timezone.utc)>=compact.END:raise SystemExit('deadline')
                    time.sleep(2)
                if not (folder/'comparison.json').exists():compact.evaluate(c)
        records=[read(OUT/c['project']/c['tag']/c['arm']/'comparison.json') for c in reg['cells']]
        core.save(RESULT,dict(registration=sha(OUT/'registration.json'),cells=records,cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('register','generate','score'))
    main(parser.parse_args().action)
