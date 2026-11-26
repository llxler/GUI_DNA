"""Fresh Mistral libraries to confirm the response-receiver effect prospectively."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import core
from studies.study_io import ROOT, read, sha, now
from studies.webbench.self_build_modules.source_delivery import run as modules
from studies.webbench.self_build_modules.entry_recovery import run as entry
from .. import run as parent
from ..duo_delivery import run as diagnostic

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/duo-delivery-confirmation-20261125'
CAP=.75
ORIGINAL=parent.duo.parse_plan


def receive(raw,names):
    parsed=ORIGINAL(raw,names)
    if parsed is not None:
        return parsed
    try:
        val=diagnostic.block(raw)
    except (ValueError,TypeError):
        return None
    return ORIGINAL(json.dumps(val),names)


def template(project,tag,stage):
    body=parent.template(project,tag,stage)
    if 'seed' in body:
        body['seed']+=1103
    return body


def register():
    files=[Path(__file__),HERE/'PROTOCOL.md',Path(parent.__file__),Path(parent.web.__file__),
           Path(diagnostic.__file__),diagnostic.RESULT,parent.HERE/'result.json',parent.OUT/'registration.json']
    assert all((parent.OUT/p/t/r/'seal.json').exists() for p,t in parent.ORDER for r in ('a','b'))
    old=ledger_read.totals(parent.OUT/'budget.sqlite3')
    early=ledger_read.totals(modules.OLD/'budget.sqlite3')
    assert old['unsettled_calls']==0 and old['exposure_usd']+early['exposure_usd']+modules.CAP+entry.CAP+CAP<=10
    paths={str(f.relative_to(ROOT)):sha(f) for f in files}
    reg=OUT/'registration.json'
    if reg.exists():
        assert read(reg)['sources']==paths
    else:
        balance=check_credits(CAP)
        assert balance['sufficient']
        core.save(reg,dict(utc=now(),sources=paths,balance=balance,cap=CAP,prior_suite=old,deadline=parent.web.END.isoformat()))


def main():
    register()
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    with patch.object(parent,'OUT',OUT),patch.multiple(parent.web,OUT=OUT,template=template),patch.object(
            parent.duo,'parse_plan',receive),ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda r:parent.branch(ledger,('duo','mistral',r)),('a','b')))


if __name__=='__main__':
    main()
