"""Apply model-proposed exclusions only when accompanied by a quoted prohibition."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import re
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,now,read,sha
from . import defaults as previous

state=previous.state
OUT=ROOT/'artifacts/todo-evidence-choices-20261127'
HERE=previous.HERE
RESULT=HERE/'evidence-result.json'
CAP=.12
EXTRA={
 'permit-toggle':'All controls are available. In this view let a user reverse the completion status of one item by operating its individual toggle.',
 'forbid-toggle':'All other controls are available. Do not allow the individual toggle to change the completion status of one item.',
}
NEGATIVE=re.compile(r"\b(?:not|no|never|disable[ds]?|forbid(?:den)?|prohibit(?:ed)?|prevent(?:ed)?|without|cannot|read.only)\b",re.I)


def decode(text):
    raw=state.todo.BASE.uncode(text).strip()
    try:return json.loads(raw),'standard'
    except ValueError:
        head,sep,rest=raw.partition('\n')
        if sep and head.strip() in (']','}'):
            return json.loads(rest.strip()),'leading_delimiter'
        raise


def plan(tag,rep,key,brief,lib,ledger):
    dest=OUT/tag/key/rep;f=dest/'decision.json'
    if f.exists():return read(f)
    options=lib['options']
    msg=core.messages('You may submit edits to a qualified controller. An edit disables one working feature. Each edit requires a verbatim quote from the current brief explicitly prohibiting that feature. An omitted feature is allowed; do not disable it. Persistence requirements, empty state and hiding sections are not prohibitions on editing, routing or toggling. Return ONLY a JSON array; use [] when no optional feature is forbidden. Each entry must be {"option":"exact name","quote":"exact words from this brief"}.',
        dict(enabled_option_names=options,brief=brief))
    try:
        raw=state.todo.BASE.request(ledger,('todomvc',tag,rep),dest/'call',msg,'plan',800)
        proposals,parser=decode(raw)
        if not isinstance(proposals,list):raise ValueError('Expected an array')
        disabled=[];rejected=[]
        for item in proposals:
            if not isinstance(item,dict) or set(item)!={'option','quote'} or item['option'] not in options or not isinstance(item['quote'],str):
                raise ValueError('Malformed proposal')
            name,quote=item['option'],item['quote'].strip()
            if quote and quote.casefold() in brief.casefold() and NEGATIVE.search(quote):
                if name not in disabled:disabled.append(name)
            else:rejected.append(item)
        fn=state.todo.MOD.assemble(lib['functions'],{k:k not in disabled for k in state.ALL})
        row=dict(status='valid',disabled=disabled,proposals=proposals,rejected=rejected,parser=parser,candidate=state.candidate(dest/'page',fn))
    except state.todo.slots.EVENTS.MISSING as e:row=dict(status='missing',reason=str(e))
    except (ValueError,TypeError) as e:row=dict(status='invalid',reason=str(e))
    core.save(f,row)
    return read(f)


def generate():
    reg=OUT/'registration.json';seal=OUT/'seal.json'
    files=[Path(__file__),HERE/'EVIDENCE.md',HERE/'default_toggle.cjs',previous.OUT/'seal.json',HERE/'result.json',
           *[state.OUT/t/r/'library.json' for t in state.TAGS for r in 'ab']]
    hashes={str(p.relative_to(ROOT)):sha(p) for p in files}
    if not reg.exists():
        used=sum(ledger_read.totals(d/'budget.sqlite3')['exposure_usd'] for d in (state.OUT,previous.OUT))
        assert used+CAP<=state.CAP
        balance=check_credits(CAP);assert balance['sufficient']
        core.save(reg,dict(utc=now(),deadline=state.END.isoformat(),cap=CAP,balance=balance,sources=hashes,extra=EXTRA))
    assert read(reg)['sources']==hashes
    if seal.exists():return
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    tasks={t['id']:t['requirement'] for t in state.todo.WEAK.domain.tasks()}|EXTRA
    records={}
    with patch.multiple(state.todo.BASE,OUT=OUT,END=state.END,template=state.todo.slots.EVENTS.template),ThreadPoolExecutor(max_workers=3) as pool:
        for t in state.TAGS:
            records[t]={}
            for rep in 'ab':
                lib=read(state.OUT/t/rep/'library.json');assert lib['status']=='valid'
                jobs={k:pool.submit(plan,t,rep,k,brief,lib,ledger) for k,brief in tasks.items()}
                records[t][rep]={k:j.result() for k,j in jobs.items()}
    core.save(seal,dict(registration=sha(reg),decisions=records))


if __name__=='__main__':
    import argparse
    from . import default_score
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=('generate','score'))
    phase=parser.parse_args().phase
    with browser.lock(OUT/(phase+'.lock')):
        if phase=='generate':generate()
        else:
            with patch.multiple(previous,OUT=OUT,RESULT=RESULT,EXTRA=EXTRA):
                default_score.evaluate()
            summary={t:{r:{k:{f:v[f] for f in ('disabled','proposals','rejected','parser','status') if f in v}
                                 for k,v in tasks.items()} for r,tasks in reps.items()} for t,reps in read(OUT/'seal.json')['decisions'].items()}
            core.save(HERE/'evidence-decisions.json',dict(seal=sha(OUT/'seal.json'),models=summary))
