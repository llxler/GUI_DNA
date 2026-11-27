"""Plan with explicit exclusions on four frozen controllers and test opposite instructions."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,now,read,sha
from . import run as state

HERE=state.HERE
OUT=ROOT/'artifacts/todo-frozen-defaults-20261127'
CAP=.16
RESULT=HERE/'default-result.json'
EXTRA={
    'permit-toggle':'Keep the approved public controller settings. The user must be able to toggle an individual todo between active and completed. Keep all other controls available.',
    'forbid-toggle':'Keep the approved public controller settings except that the user must not be able to toggle an individual todo between active and completed. Keep all other controls available.',
}


def plan(tag,rep,key,brief,lib,ledger):
    f=OUT/tag/key/rep/'decision.json'
    if f.exists():return read(f)
    names=list(lib['options'])
    msg=core.messages('A controller has been qualified with every available option enabled. Leave working behavior enabled unless the requirement explicitly forbids it. A feature not mentioned is allowed. Output a JSON array of the exact option names to DISABLE. [] is legal. No prose.',
                      dict(available_enabled_options=names,requirement=brief))
    try:
        raw=state.todo.BASE.uncode(state.todo.BASE.request(ledger,('todomvc',tag,rep),f.parent/'call',msg,'plan',600)).strip()
        disabled=json.loads(raw)
        if not isinstance(disabled,list) or not all(isinstance(x,str) and x in names for x in disabled) or len(set(disabled))!=len(disabled):
            raise ValueError('Expected a list of unique allowed names')
        code=state.todo.MOD.assemble(lib['functions'],{k:k not in disabled for k in state.ALL})
        candidate=state.candidate(f.parent/'page',code)
        result=dict(status='valid',disabled=disabled,candidate=candidate)
    except state.todo.slots.EVENTS.MISSING as err:
        result=dict(status='missing',reason=str(err))
    except ValueError as err:
        result=dict(status='invalid',reason=str(err))
    core.save(f,result)
    return read(f)


def generate():
    reg=OUT/'registration.json'
    inputs=[Path(__file__),HERE/'DEFAULTS.md',HERE/'default_toggle.cjs',HERE/'result.json',Path(state.todo.MOD.__file__),
            *[state.OUT/t/r/'library.json' for t in state.TAGS for r in 'ab']]
    hashes={str(p.relative_to(ROOT)):sha(p) for p in inputs}
    if not reg.exists():
        assert ledger_read.totals(state.OUT/'budget.sqlite3')['exposure_usd']+CAP<=state.CAP
        balance=check_credits(CAP);assert balance['sufficient']
        core.save(reg,dict(utc=now(),deadline=state.END.isoformat(),balance=balance,cap=CAP,extra=EXTRA,sources=hashes))
    assert read(reg)['sources']==hashes
    seal=OUT/'seal.json'
    if seal.exists():return
    tasks={t['id']:t['requirement'] for t in state.todo.WEAK.domain.tasks()}
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    records={}
    with patch.multiple(state.todo.BASE,OUT=OUT,END=state.END,template=state.todo.slots.EVENTS.template),ThreadPoolExecutor(max_workers=3) as pool:
        for t in state.TAGS:
            records[t]={}
            for r in 'ab':
                lib=read(state.OUT/t/r/'library.json');assert lib['status']=='valid'
                jobs={k:pool.submit(plan,t,r,k,brief,lib,ledger) for k,brief in (tasks|EXTRA).items()}
                records[t][r]={k:j.result() for k,j in jobs.items()}
    core.save(seal,dict(registration=sha(reg),decisions=records))


if __name__=='__main__':
    with browser.lock(OUT/'run.lock'):generate()
