"""Have each builder edit its own first typed submission, one anchored change at a time."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,now,read,sha
from . import fragment_replay as replay, run as typed

HERE=typed.HERE
OUT=ROOT/'artifacts/webgen-local-edits-20261127'
CANDIDATES=HERE/'edit-candidates.json'
CAP=.25
ARGUMENTS={
    'tabs':'entries IS THE ARRAY itself, e.g. [{title:"North",body:{type:"panel"}},{title:"South",body:[...]}]. Read it directly.',
    'form':'fields and actions are SEPARATE arrays. renderChildren accepts EXACTLY ONE nodes argument, and returns a real DocumentFragment. Each array must be rendered. successMessage is already a literal string.',
    'dialog':'body is a SINGLE schema object OR array. No schema.type special cases. The one-argument renderChildren(body) returns the real DOM fragment regardless of type. The raw body is plain data and cannot be appended as a DOM node.',
    'checkbox':'name and label are strings; required and value may be booleans.'
}


def repair(tag,kind,initial,ledger):
    dest=OUT/'build'/tag/kind
    passed=replay.probe(kind,initial)
    if passed['passed']:
        return initial,[{'original':True,'observation':passed}]
    receipts=sorted((typed.OUT/'build'/tag/kind).glob('*/transmission-*/settled.json'))
    source=None
    for f in receipts:
        reply=f.with_name('response.json')
        assert sha(reply)==read(f)['response_sha256']
        try:
            source=typed.extract(read(reply)['choices'][0]['message']['content'])
            break
        except ValueError:
            continue
    if not source:
        return initial,[{'unavailable':'no parsable typed function'}]
    observed=replay.probe(kind,typed.bind(kind,source))
    history=[dict(observation=observed,response=sha(reply))]
    for i in range(3):
        if observed['passed']:
            break
        message=core.messages('You are maintaining YOUR JavaScript DOM component. Repair the first faulty expression with ONE exact-text edit to your existing code. Output only a JSON object with two string fields "old" and "new". "old" must be a nonempty exact substring occurring once; "new" may be multiline. Do not rewrite the entire function. No markdown. Keep correct behavior. The function receives precisely the parameters shown. '+ARGUMENTS[kind],
                              {'function_source':source,'public_dom_observation':observed,'required_behavior':typed.FIELDS[kind][2]})
        try:
            raw=typed.GEN.call(ledger,tag,dest/str(i),message,'build',2000)
            edit=typed.GEN.parse(raw)
            old,new=edit['old'],edit['new']
            if not isinstance(old,str) or not old or not isinstance(new,str) or source.count(old)!=1:
                raise ValueError('old must match exactly once.')
            candidate=typed.extract(source.replace(old,new,1))
            observation=replay.probe(kind,typed.bind(kind,candidate))
            previous_checks={k for k,ok in observed.get('checks',{}).items() if ok}
            kept=all(observation.get('checks',{}).get(k) for k in previous_checks)
            history.append(dict(observation=observation,kept=kept))
            if kept:
                source,observed=candidate,observation
        except typed.GEN.MISSING as error:
            history.append(dict(missing=str(error)))
            break
        except typed.GEN.ERRORS as error:
            history.append(dict(error=str(error)[:220]))
            observed=observed|{'last_edit_error':str(error)[:220]}
    return (typed.bind(kind,source) if observed['passed'] else initial),history


def build(tag,ledger):
    file=OUT/'build'/tag/'library.json'
    if file.exists():return read(file)
    original=read(replay.OUT/'build'/tag/'library.json')
    parts=dict(original['parts'])
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs={k:pool.submit(repair,tag,k,parts[k],ledger) for k in typed.FIELDS}
        result={k:j.result() for k,j in jobs.items()}
    parts.update({k:r[0] for k,r in result.items()})
    changed=[k for k in typed.FIELDS if parts[k]!=original['parts'][k]]
    def check(fns):return replay.COMP.pages.check(replay.COMP.previous.site(replay.COMP.schema.SAMPLE,fns,True))
    attempted=check(parts)
    keep=all(not ok or attempted['checks'][k] for k,ok in original['final']['checks'].items())
    final=attempted if keep else original['final']
    empty=check(parts|{k:typed.bind(k,'function render(){}') for k in changed})
    status='valid' if len(final['checks'])==5 and all(final['checks'].values()) else 'build_failed'
    core.save(file,dict(status=status,parts=parts if keep else original['parts'],initial=original['final'],final=final,
                        attempted=attempted,empty_replacements=empty,changed=changed if keep else [],
                        isolated={k:r[1] for k,r in result.items()}))
    print(tag,status,final['checks'],flush=True)
    return read(file)


def generate():
    reg=OUT/'registration.json'
    files=[Path(__file__),HERE/'LOCAL_EDITS.md',replay.CANDIDATES,Path(replay.__file__),Path(typed.__file__),
           *[replay.OUT/'build'/t/'library.json' for t in replay.COMP.MODELS]]
    hashes={str(p.relative_to(ROOT)):sha(p) for p in files}
    if not reg.exists():
        used=sum(ledger_read.totals(p/'budget.sqlite3')['exposure_usd'] for p in (replay.COMP.OUT,typed.bodies.OUT,typed.OUT))
        assert used+CAP<=1.60
        balance=check_credits(CAP)
        assert balance['sufficient']
        core.save(reg,dict(utc=now(),sources=hashes,cap=CAP,balance=balance,deadline=replay.COMP.END.isoformat()))
    assert read(reg)['sources']==hashes
    if CANDIDATES.exists():return
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    with patch.multiple(typed.GEN.BASE,OUT=OUT,END=replay.COMP.END,template=typed.GEN.settings),ThreadPoolExecutor(max_workers=2) as pool:
        jobs={t:pool.submit(build,t,ledger) for t in replay.COMP.MODELS}
        libs={t:j.result() for t,j in jobs.items()}
    prior=read(replay.CANDIDATES)
    batches={}
    for batch,plan_dir in [('development',replay.COMP.PILOT_PLANS),('holdout',replay.COMP.OUT/'plans')]:
        pages=prior[batch]
        for t,lib in libs.items():
            for site,arms in pages[t].items():
                plan=read(plan_dir/t/site/'record.json')
                arms['self']=replay.COMP.render(t,site,'self',plan,lib,OUT/batch)
        batches[batch]=pages
    core.save(OUT/'seal.json',dict(registration=sha(reg),libraries={t:sha(OUT/'build'/t/'library.json') for t in libs},**batches))
    core.save(CANDIDATES,dict(previous=sha(replay.CANDIDATES),registration=sha(reg),seal=sha(OUT/'seal.json'),
                               cost=ledger_read.totals(OUT/'budget.sqlite3'),models=prior['models'],
                               libraries={t:{k:v for k,v in lib.items() if k!='parts'} for t,lib in libs.items()},**batches))


if __name__=='__main__':
    with browser.lock(OUT/'run.lock'):
        generate()
