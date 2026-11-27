"""Transfer the already admitted Flash renderer to the identical third site in each category."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,now,read,sha
from ..component_contracts.typed_inputs import dom_inputs as dom

comp=dom.comp
native=comp.native
gen=comp.gen
HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/webgen-flash-transfer-20261127'
CAP=.30
TAG='deepseek-flash'
CANDIDATES=HERE/'candidates.json'


def generate():
    olddir=native.OUT
    libpath=olddir/'build'/TAG/'library.json'
    source=read(libpath)
    dev=read(comp.OLD)['rows'][TAG]
    original_plans={s:olddir/'plans'/TAG/s/'record.json' for s in dev}
    assert source['status']=='valid'
    for s,arms in dev.items():
        plan=read(original_plans[s])
        if plan['status']=='valid':
            assert native.html(plan['config'],source['parts'],source['mode']).encode()==(ROOT/arms['self']['file']).read_bytes()
        else:assert arms['self']['status']==plan['status']
    prior=read(comp.OUT/'registration.json')
    briefs=comp.OUT/'held-out-briefs.json'
    assert sha(briefs)==prior['briefs'] and set(read(briefs)).isdisjoint(dev)
    shared=comp.OUT/'build/gpt5/library.json'
    inputs=[Path(__file__),HERE/'PROTOCOL.md',libpath,comp.OLD,briefs,shared,Path(native.__file__),
            Path(gen.__file__),olddir/'seal.json',*original_plans.values()]
    hashes={str(p.relative_to(ROOT)):sha(p) for p in inputs}
    reg=OUT/'registration.json'
    if not reg.exists():
        used=sum(ledger_read.totals(d/'budget.sqlite3')['exposure_usd'] for d in (comp.OUT,dom.typed.bodies.OUT,dom.typed.OUT,dom.prior.OUT,dom.OUT))
        assert used+CAP<=1.60
        balance=check_credits(CAP);assert balance['sufficient']
        core.save(reg,dict(utc=now(),deadline=comp.END.isoformat(),balance=balance,cap=CAP,sources=hashes,sites=prior['holdout']))
    assert read(reg)['sources']==hashes
    if CANDIDATES.exists():return
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    sites=read(briefs);rows={}
    with patch.multiple(gen.BASE,OUT=OUT,END=comp.END,template=gen.settings),patch.object(gen,'OUT',OUT),patch.object(native,'OUT',OUT),ThreadPoolExecutor(max_workers=4) as pool:
        direct={s:pool.submit(gen.target,TAG,s,'direct',b,ledger) for s,b in sites.items()}
        plans={s:pool.submit(native.plan,TAG,s,b,ledger) for s,b in sites.items()}
        for s in sites:
            plan=plans[s].result()
            arms={'direct':direct[s].result()}
            for arm,lib in [('self',source),('human',{'status':'valid'}),('gpt5-library',read(shared))]:
                if lib['status']!='valid':item={'status':lib['status']}
                elif plan['status']!='valid':item={k:v for k,v in plan.items() if k!='config'}
                else:
                    if arm=='human':html=comp.pages.page(plan['config'],'human')
                    elif arm=='self':html=native.html(plan['config'],lib['parts'],lib['mode'])
                    else:html=comp.pages.page(plan['config'],lib['parts'])
                    item=comp.pages.write_html(OUT/'sites'/s/arm,html)
                arms[arm]=item
            rows[s]=arms
    core.save(OUT/'seal.json',dict(registration=sha(reg),library=sha(libpath),rows=rows))
    core.save(CANDIDATES,dict(registration=sha(reg),seal=sha(OUT/'seal.json'),library=sha(libpath),verified_development_sites=sorted(dev),
                              model=gen.model(TAG),rows=rows,plans={s:sha(OUT/'plans'/TAG/s/'record.json') for s in sites},
                              cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__=='__main__':
    with browser.lock(OUT/'run.lock'):
        generate()
