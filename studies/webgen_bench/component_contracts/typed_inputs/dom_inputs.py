"""Pass named DOM fragments from the same model's child renderers to two failing parents."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,now,read,sha
from . import local_edits as prior

typed=prior.typed
comp=prior.replay.COMP
HERE=typed.HERE
OUT=ROOT/'artifacts/webgen-dom-inputs-20261127'
CANDIDATES=HERE/'dom-candidates.json'
CAP=.20
MODEL='qwen9'
FIELDS={
    'dialog': ('root, titleText, bodyFragment','root, c.title, fragment(c.body)',
               'Append a new dialog to root. Show the titleText, append the actual bodyFragment inside and create a Close button whose click removes this dialog.'),
    'form': ('root, titleText, fieldsFragment, actionsFragment, successText',
             'root, c.title, fragment(c.body), fragment(c.actions), c.onEvent?.submitSucc?.actions?.[0]?.args?.msg',
             'Append a native form. Show titleText, insert both fragments as children of that form. On submit prevent default, collect the named fields and append visible successText to root.')
}


def bind(kind,source):
    return ('function(root,c,env){const fragment=nodes=>{const f=document.createDocumentFragment();'
            'env.mount(f,nodes);return f;};return ('+source+')('+FIELDS[kind][1]+');}')


def build_one(kind,original,ledger):
    folder=OUT/'build'/MODEL/kind
    f=folder/'record.json'
    if f.exists():return read(f)
    observations=[prior.replay.probe(kind,original)]
    source=original
    example=None
    for i in range(2):
        if observations[-1]['passed']:break
        prompt=('Write just a small named JavaScript function render('+FIELDS[kind][0]+'). '
                'root is a real HTMLElement. Every argument ending in Fragment is an EXISTING DOM DocumentFragment; '
                'append it directly. Text arguments are plain strings. '+FIELDS[kind][2]+
                ' Do not inspect fragments; they already contain the model-written child elements. No styling or example. Aim for 12 lines.')
        msg=core.messages(prompt,{'previous_source':example,'previous_public_result':observations[-1]})
        try:
            example=typed.extract(typed.GEN.call(ledger,MODEL,folder/str(i),msg,'build',1800))
            candidate=bind(kind,example)
            observation=prior.replay.probe(kind,candidate)
            if observation['passed']:source=candidate
        except typed.GEN.MISSING as err:
            observations.append(dict(passed=False,missing=str(err)));break
        except typed.GEN.ERRORS as err:
            observation=dict(passed=False,error=str(err)[:220])
        observations.append(observation)
    core.save(f,dict(source=source,changed=source!=original,observations=observations))
    return read(f)


def generate():
    reg=OUT/'registration.json'
    source=prior.OUT/'build'/MODEL/'library.json'
    paths=[Path(__file__),HERE/'DOM_INPUTS.md',Path(prior.replay.__file__),comp.HERE/'probe.js',prior.CANDIDATES,source]
    hashes={str(p.relative_to(ROOT)):sha(p) for p in paths}
    if not reg.exists():
        used=sum(ledger_read.totals(d/'budget.sqlite3')['exposure_usd'] for d in (comp.OUT,typed.bodies.OUT,typed.OUT,prior.OUT))
        assert used+CAP<=1.60
        balance=check_credits(CAP);assert balance['sufficient']
        core.save(reg,dict(utc=now(),deadline=comp.END.isoformat(),cap=CAP,balance=balance,sources=hashes))
    assert read(reg)['sources']==hashes
    if CANDIDATES.exists():return
    old=read(source);parts=dict(old['parts'])
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    with patch.multiple(typed.GEN.BASE,OUT=OUT,END=comp.END,template=typed.GEN.settings),ThreadPoolExecutor(max_workers=2) as pool:
        jobs={k:pool.submit(build_one,k,parts[k],ledger) for k in FIELDS}
        revised={k:j.result() for k,j in jobs.items()}
    parts.update({k:r['source'] for k,r in revised.items()})
    def check(fns):return comp.pages.check(comp.previous.site(comp.schema.SAMPLE,fns,True))
    attempted=check(parts)
    changed=[k for k in FIELDS if revised[k]['changed']]
    keep=all(not ok or attempted['checks'][k] for k,ok in old['final']['checks'].items())
    final=attempted if keep else old['final']
    empty=check(parts|{k:bind(k,'function render(){}') for k in changed})
    status='valid' if len(final['checks'])==5 and all(final['checks'].values()) else 'build_failed'
    lib=dict(status=status,parts=parts if keep else old['parts'],initial=old['final'],final=final,attempted=attempted,
             empty_replacements=empty,changed=changed if keep else [],isolated={k:r['observations'] for k,r in revised.items()})
    file=OUT/'build'/MODEL/'library.json';core.save(file,lib)
    before=read(prior.CANDIDATES)
    batches={}
    for batch,plan_dir in [('development',comp.PILOT_PLANS),('holdout',comp.OUT/'plans')]:
        pages=before[batch]
        for site,arms in pages[MODEL].items():
            plan=read(plan_dir/MODEL/site/'record.json')
            arms['self']=comp.render(MODEL,site,'self',plan,lib,OUT/batch)
        batches[batch]=pages
    core.save(OUT/'seal.json',dict(registration=sha(reg),libraries={MODEL:sha(file)},**batches))
    core.save(CANDIDATES,dict(previous=sha(prior.CANDIDATES),registration=sha(reg),seal=sha(OUT/'seal.json'),models=before['models'],
                              cost=ledger_read.totals(OUT/'budget.sqlite3'),libraries={MODEL:{k:v for k,v in lib.items() if k!='parts'}},**batches))
    print(MODEL,status,final['checks'],flush=True)


if __name__=='__main__':
    with browser.lock(OUT/'run.lock'):
        generate()
