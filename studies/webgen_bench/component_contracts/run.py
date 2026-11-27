"""Repair renderer functions on public DOM contracts and seal disjoint test websites."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from gui_dna.budget import Ledger
from playwright.sync_api import sync_playwright
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from studies.webgen_bench.functional_pilot import generate as gen, pages, schema
from studies.webgen_bench.functional_pilot.function_binding import run as previous
from studies.webgen_bench.functional_pilot.native_plans import run as native

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/webgen-component-contracts-20261127'
OLD = previous.HERE / 'candidates.json'
PILOT_INPUT = gen.OUT / 'generation-input.json'
PILOT_PLANS = native.OUT / 'plans'
MODELS = ('gemma', 'qwen9')
CAP = 1.05
END = datetime(2026, 11, 27, 12, 48, tzinfo=timezone.utc)
GOALS = {
    'tabs':'Create a permanent navigation element and a separate body element. Use actual buttons. Switch by replacing only the body. Call env.mount(bodyElement, tab.body) for any child type, including mixed arrays. Select the first initially and preserve buttons for return navigation.',
    'table':'Use env.get(component.source), an array; append actual table cell text for each named column in each row.',
    'form':'Mount BOTH component.body AND component.actions directly inside the same native form using env.mount. On a form submit intercept and display the message at component.onEvent.submitSucc.actions[0].args.msg. Keep named fields and commit their values.',
    'button':'Append the labeled native button to root. On click delegate the provided dialog schema to env.mount(root, {...component.dialog,type:"dialog"}).',
    'page':'Append heading and pass component.body unchanged to env.mount regardless of whether it is an object or array.',
}

def register():
    import duckdb
    spec = read(gen.REG)
    assert sha(gen.SRC) == spec['sha256']
    public = duckdb.sql('select id, instruction, Category.primary_category from read_parquet(?)',
                        params=[str(gen.SRC)]).fetchall()
    sites = {}
    for category, original in spec['pilot_sites'].items():
        group = [(s, brief) for s, brief, cat in public if cat == category]
        group.sort(key=lambda pair: (hashlib.sha256(('gui-dna-webgen-v1:'+pair[0]).encode()).hexdigest(), pair[0]))
        assert set(original) == {s for s, _ in group[:2]}
        site, brief = group[2]
        sites[site] = brief
    inputs = [Path(__file__), HERE/'PROTOCOL.md', HERE/'probe.js', Path(previous.__file__), Path(native.__file__),
              OLD, gen.REG, gen.SRC, PILOT_INPUT, *[previous.OUT/'build'/t/'library.json' for t in MODELS]]
    sources = {str(p.relative_to(ROOT)):sha(p) for p in inputs}
    dest = OUT/'registration.json'
    if not dest.exists():
        balance = check_credits(CAP)
        assert balance['sufficient']
        core.save(OUT/'held-out-briefs.json', sites)
        core.save(dest, dict(utc=now(), deadline=END.isoformat(), cap=CAP, balance=balance, sources=sources,
                             holdout=sorted(sites), briefs=sha(OUT/'held-out-briefs.json'), generators={t:gen.model(t) for t in MODELS}))
    assert read(dest)['sources']==sources and read(OUT/'held-out-briefs.json')==sites
    return sites


def public_probe(kind, source):
    script = (HERE/'probe.js').read_text()
    with browser.browser_slot(), sync_playwright() as pw, pw.chromium.launch(env=browser.browser_env()) as engine:
        with pages.local_tab(engine,'<!doctype html><body></body>') as tab:
            return tab.evaluate(script,dict(kind=kind,source=source))


def fix(tag, kind, old, ledger):
    folder = OUT/'build'/tag/'components'/kind
    result = folder/'result.json'
    if result.exists():
        return read(result)
    observation = public_probe(kind, old)
    history = [observation]
    chosen = old
    last = old
    for attempt in range(2):
        if observation['passed']:
            break
        requirement = previous.parent.KINDS[kind]
        messages = core.messages(
            'Implement one isolated browser component. Return a complete anonymous JavaScript function(root, component, env) only. '
            'Use native DOM APIs; append visible DOM nodes using root.append. env.mount(parent, childOrArray) appends model-written child renderers and returns nothing. '
            'env.text(value) returns a string; env.get(keyOrReference) returns data. Data and labels vary. Do not hardcode samples. '
            'Repair the observed failing action. Keep other supported behavior.',
            dict(component=kind, sample_input=requirement[1], purpose=requirement[2],
                 contract=GOALS.get(kind,requirement[2]), observed=observation, previous_source=last))
        try:
            raw = gen.call(ledger,tag,folder/f'attempt-{attempt+1}',messages,'build',3600)
            last = previous.bind(raw,True)['source']
            observation = public_probe(kind,last)
        except gen.MISSING as exc:
            history.append(dict(missing=str(exc)));break
        except gen.ERRORS as exc:
            observation = dict(passed=False, error=str(exc)[:220])
        history.append(observation)
        if observation['passed']:
            chosen = last
    core.save(result, dict(source=chosen, changed=chosen!=old, observations=history))
    return read(result)


def build(tag,ledger):
    folder = OUT/'build'/tag
    dest = folder/'library.json'
    if dest.exists():
        return read(dest)
    source = previous.OUT/'build'/tag/'library.json'
    original = read(source)
    assert original['mode'] and set(original['parts'])==set(previous.parent.KINDS)
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs = {k:pool.submit(fix,tag,k,v,ledger) for k,v in original['parts'].items()}
        records = {k:j.result() for k,j in jobs.items()}
    parts = {k:r['source'] for k,r in records.items()}
    before = original['integration']['checks']
    after = pages.check(previous.site(schema.SAMPLE,parts,True))
    kept = all(not yes or after['checks'][k] for k,yes in before.items())
    if not kept:
        parts = original['parts']
    actual = after if kept else original['integration']
    status = 'valid' if all(actual['checks'].values()) and len(actual['checks'])==5 else 'build_failed'
    core.save(dest,dict(status=status,parts=parts,origin=sha(source),before=before,attempt=after,
                        final=actual,retained=kept,changed=[k for k,r in records.items() if r['changed'] and kept],
                        isolated={k:[{a:v for a,v in x.items() if a!='trace'} for x in r['observations']] for k,r in records.items()}))
    print(tag,status,actual['checks'],flush=True)
    return read(dest)


def render(tag,site,arm,plan,lib,folder):
    if lib['status']!='valid':
        return {'status':lib['status']}
    if plan['status']!='valid':
        return {k:v for k,v in plan.items() if k!='config'}
    if arm=='human':
        html=pages.page(plan['config'],'human')
    elif arm=='gpt5-library':
        html=pages.page(plan['config'],lib['parts'])
    else:
        html=previous.site(plan['config'],lib['parts'],True)
    return pages.write_html(folder/tag/site/arm,html)


def generate():
    sites=register()
    destination=HERE/'candidates.json'
    if destination.exists():
        assert read(destination)['seal']==sha(OUT/'seal.json')
        return
    old=read(OLD)
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    with patch.multiple(gen.BASE, OUT=OUT, END=END, template=gen.settings), patch.object(gen,'OUT',OUT), patch.object(native,'OUT',OUT), ThreadPoolExecutor(max_workers=6) as pool:
        libs={t:pool.submit(build,t,ledger) for t in MODELS}
        donor=pool.submit(gen.build,'gpt5',read(PILOT_INPUT),ledger)
        direct={(t,s):pool.submit(gen.target,t,s,'direct',brief,ledger) for t in MODELS for s,brief in sites.items()}
        plans={(t,s):pool.submit(native.plan,t,s,brief,ledger) for t in MODELS for s,brief in sites.items()}
        own={t:j.result() for t,j in libs.items()}; shared=donor.result()
        held={}
        for t in MODELS:
            held[t]={}
            for site in sites:
                plan=plans[t,site].result()
                held[t][site]={'direct':direct[t,site].result()}
                for arm,lib in [('human',{'status':'valid'}),('self',own[t]),('gpt5-library',shared)]:
                    held[t][site][arm]=render(t,site,arm,plan,lib,OUT/'held-out')
    dev=old['rows']
    for t in MODELS:
        for site,arms in dev[t].items():
            plan=read(PILOT_PLANS/t/site/'record.json')
            arms['self']=render(t,site,'self',plan,own[t],OUT/'development')
    records={t:sha(OUT/'build'/t/'library.json') for t in (*MODELS,'gpt5')}
    for batch in (dev,held):
        for by_site in batch.values():
            for arms in by_site.values():
                for item in arms.values():
                    if item['status']=='valid':assert sha(ROOT/item['file'])==item['sha256']
    core.save(OUT/'seal.json',dict(registration=sha(OUT/'registration.json'),libraries=records,development=dev,holdout=held))
    core.save(destination,dict(previous=sha(OLD),registration=sha(OUT/'registration.json'),seal=sha(OUT/'seal.json'),
                               development=dev,holdout=held,models={t:gen.model(t) for t in MODELS},
                               libraries={t:{k:v for k,v in l.items() if k!='parts'} for t,l in (own|{'gpt5':shared}).items()},
                               cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__=='__main__':
    with browser.lock(OUT/'generation.lock'):
        generate()
