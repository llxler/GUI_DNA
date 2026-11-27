"""Repair the observed native dialog visibility and independently readable form feedback."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from gui_dna.budget import Ledger
from playwright.sync_api import sync_playwright
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,now,read,sha
from . import dom_inputs as dom

HERE=dom.HERE
OUT=ROOT/'artifacts/webgen-visibility-20261127'
CANDIDATES=HERE/'visibility-candidates.json'
CAP=.15
TAG=dom.MODEL
PROBE=HERE/'visibility.js'


def observe(kind, fn):
    with browser.browser_slot(),sync_playwright() as pw,pw.chromium.launch(env=browser.browser_env()) as engine:
        with dom.comp.pages.local_tab(engine,'<!doctype html><body></body>') as tab:
            return [tab.evaluate(PROBE.read_text(),dict(kind=kind,source=fn,labels=labels)) for labels in
                    [('Cedar plan','Bark shards','Reserve','Reservation complete'),('Slate tools','Spare wrench','Store','Box updated')]]


def repair(kind, initial, ledger):
    f=OUT/'build'/TAG/kind/'result.json'
    if f.exists():return read(f)
    folder=dom.OUT/'build'/TAG/kind/'0/transmission-1'
    assert read(folder/'settled.json')['response_sha256']==sha(folder/'response.json')
    last=dom.typed.extract(read(folder/'response.json')['choices'][0]['message']['content'])
    history=[observe(kind,dom.bind(kind,last))]
    chosen=initial
    for i in range(2):
        if all(v['passed'] for v in history[-1]):
            chosen=dom.bind(kind,last)
            break
        ABI=('root is HTMLElement; titleText and successText are plain strings. Every Fragment argument is a '
             'ready-to-append DOM DocumentFragment. Preserve parameters and existing functionality. ')
        detail=('A native dialog is hidden when its open attribute is false. It must be visible immediately after mounting; Close must dismiss it.'
                if kind=='dialog' else 'Place submitted successText in its own visible output or status element where its exact accessible text can be read apart from form controls. Collect the form values at submit.')
        msg=core.messages('Return only the whole corrected JavaScript function. '+ABI+detail,
                          dict(your_function=last,public_browser_observations=history[-1]))
        try:
            last=dom.typed.extract(dom.typed.GEN.call(ledger,TAG,f.parent/str(i),msg,'build',2300))
            fn=dom.bind(kind,last);obs=observe(kind,fn)
            history.append(obs)
            if all(v['passed'] for v in obs):
                chosen=fn;break
        except dom.typed.GEN.MISSING as e:
            history.append([dict(passed=False,missing=str(e))]);break
        except dom.typed.GEN.ERRORS as e:
            history.append([dict(passed=False,error=str(e)[:240])])
    core.save(f,dict(source=chosen,changed=chosen!=initial,history=history))
    return read(f)


def generate():
    source=dom.OUT/'build'/TAG/'library.json';reg=OUT/'registration.json'
    files=[Path(__file__),PROBE,HERE/'NATIVE_VISIBILITY.md',Path(dom.__file__),dom.CANDIDATES,source,
           *[dom.OUT/'build'/TAG/k/'0/transmission-1/settled.json' for k in dom.FIELDS]]
    hashes={str(p.relative_to(ROOT)):sha(p) for p in files}
    if not reg.exists():
        # Flash transfer may be in flight. Reserve its entire registered generation cap.
        used=sum(ledger_read.totals(d/'budget.sqlite3')['exposure_usd'] for d in
                 (dom.comp.OUT,dom.typed.bodies.OUT,dom.typed.OUT,dom.prior.OUT,dom.OUT))
        assert used+.30+CAP<=1.60
        balance=check_credits(CAP);assert balance['sufficient']
        core.save(reg,dict(utc=now(),deadline=dom.comp.END.isoformat(),cap=CAP,balance=balance,sources=hashes))
    assert read(reg)['sources']==hashes
    if CANDIDATES.exists():return
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    old=read(source);parts=dict(old['parts'])
    with patch.multiple(dom.typed.GEN.BASE,OUT=OUT,END=dom.comp.END,template=dom.typed.GEN.settings),ThreadPoolExecutor(max_workers=2) as pool:
        jobs={k:pool.submit(repair,k,parts[k],ledger) for k in dom.FIELDS}
        changes={k:j.result() for k,j in jobs.items()}
    parts.update({k:r['source'] for k,r in changes.items()})
    def check(fs):return dom.comp.pages.check(dom.comp.previous.site(dom.comp.schema.SAMPLE,fs,True))
    attempted=check(parts);changed=[k for k,r in changes.items() if r['changed']]
    keep=all(not ok or attempted['checks'][k] for k,ok in old['final']['checks'].items())
    final=attempted if keep else old['final']
    empty=check(parts|{k:dom.bind(k,'function render(){}') for k in changed})
    status='valid' if len(final['checks'])==5 and all(final['checks'].values()) else 'build_failed'
    lib=dict(status=status,parts=parts if keep else old['parts'],initial=old['final'],final=final,attempted=attempted,
             empty_replacements=empty,changed=changed if keep else [],isolated={k:r['history'] for k,r in changes.items()})
    file=OUT/'build'/TAG/'library.json';core.save(file,lib)
    before=read(dom.CANDIDATES);batches={}
    for batch,plan_dir in [('development',dom.comp.PILOT_PLANS),('holdout',dom.comp.OUT/'plans')]:
        rows=before[batch]
        for site,arms in rows[TAG].items():
            plan=read(plan_dir/TAG/site/'record.json');arms['self']=dom.comp.render(TAG,site,'self',plan,lib,OUT/batch)
        batches[batch]=rows
    core.save(OUT/'seal.json',dict(registration=sha(reg),libraries={TAG:sha(file)},**batches))
    core.save(CANDIDATES,dict(previous=sha(dom.CANDIDATES),registration=sha(reg),seal=sha(OUT/'seal.json'),models=before['models'],
                              cost=ledger_read.totals(OUT/'budget.sqlite3'),libraries={TAG:{k:v for k,v in lib.items() if k!='parts'}},**batches))
    print(TAG,status,final['checks'],flush=True)


if __name__=='__main__':
    with browser.lock(OUT/'run.lock'):
        generate()
