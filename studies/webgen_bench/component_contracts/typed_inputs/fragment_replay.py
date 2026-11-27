"""Replay submitted functions on a DOM probe that accepts the host's DocumentFragment."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import time
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from . import run as typed

HERE = typed.HERE
OUT = ROOT / 'artifacts/webgen-fragment-replay-20261127'
CANDIDATES = HERE / 'replay-candidates.json'
COMP = typed.components
CHECK = (COMP.HERE/'probe.js').read_text().replace('parent instanceof Element)',
             'parent instanceof Element || parent instanceof DocumentFragment)')
assert 'parent instanceof DocumentFragment)' in CHECK


def probe(kind, fn):
    with browser.browser_slot(), sync_playwright() as pw, pw.chromium.launch(env=browser.browser_env()) as engine:
        with COMP.pages.local_tab(engine,'<!doctype html><body></body>') as tab:
            return tab.evaluate(CHECK,dict(kind=kind,source=fn))


def library(tag):
    source = read(typed.bodies.OUT/'build'/tag/'library.json')
    parts = dict(source['parts'])
    rows = {}
    for k in typed.FIELDS:
        folder = typed.OUT/'build'/tag/k
        obs = probe(k,parts[k])
        rows[k] = [{'stage':'original','observation':obs}]
        if obs['passed']:
            continue
        for attempt in range(2):
            receipts = sorted((folder/str(attempt)).glob('transmission-*/settled.json'))
            if not receipts:
                continue
            assert len(receipts) == 1
            f = receipts[0].with_name('response.json')
            assert read(receipts[0])['response_sha256'] == sha(f)
            try:
                fn = typed.bind(k,typed.extract(read(f)['choices'][0]['message']['content']))
                obs = probe(k,fn)
            except typed.GEN.ERRORS as err:
                obs = dict(passed=False,error=str(err)[:220])
            rows[k].append(dict(stage=attempt,response=sha(f),observation=obs))
            if obs['passed']:
                parts[k] = fn
                break
    changed = [k for k in typed.FIELDS if parts[k] != source['parts'][k]]
    def check(candidate):
        return COMP.pages.check(COMP.previous.site(COMP.schema.SAMPLE,candidate,True))
    actual = check(parts)
    empty = check(parts | {k:typed.bind(k,'function render(){}') for k in changed})
    keep = all(not ok or actual['checks'][k] for k,ok in source['final']['checks'].items())
    final = actual if keep else source['final']
    status = 'valid' if len(final['checks']) == 5 and all(final['checks'].values()) else 'build_failed'
    rec = dict(status=status,parts=parts if keep else source['parts'],changed=changed if keep else [],final=final,
               initial=source['final'],attempted=actual,empty_replacements=empty,isolated=rows)
    core.save(OUT/'build'/tag/'library.json',rec)
    print(tag,status,final['checks'],flush=True)
    return rec


def generate():
    reg = OUT/'registration.json'
    paths = [Path(__file__),HERE/'FRAGMENT_REPLAY.md',Path(typed.__file__),COMP.HERE/'probe.js',
             *[typed.bodies.OUT/'build'/tag/'library.json' for tag in COMP.MODELS]]
    hashes = {str(p.relative_to(ROOT)):sha(p) for p in paths}
    if not reg.exists():
        core.save(reg,dict(utc=now(),sources=hashes,api_generation_cost=0))
    assert hashes == read(reg)['sources']
    before_file = HERE/'candidates.json'
    while not before_file.exists():
        if datetime.now(timezone.utc) >= COMP.END:
            raise TimeoutError('Earlier candidates unavailable')
        time.sleep(3)
    if CANDIDATES.exists():
        assert read(CANDIDATES)['seal'] == sha(OUT/'seal.json')
        return
    with ThreadPoolExecutor(max_workers=2) as pool:
        libs = dict(zip(COMP.MODELS, pool.map(library,COMP.MODELS),strict=True))
    before = read(before_file)
    batches = {}
    for batch, plan_dir in [('development',COMP.PILOT_PLANS),('holdout',COMP.OUT/'plans')]:
        rows = before[batch]
        for tag, lib in libs.items():
            for site, arms in rows[tag].items():
                plan = read(plan_dir/tag/site/'record.json')
                arms['self'] = COMP.render(tag,site,'self',plan,lib,OUT/batch)
        batches[batch] = rows
    core.save(OUT/'seal.json',dict(registration=sha(reg),libraries={t:sha(OUT/'build'/t/'library.json') for t in libs},**batches))
    core.save(CANDIDATES,dict(previous=sha(before_file),registration=sha(reg),seal=sha(OUT/'seal.json'),
                              models=before['models'],libraries={t:{k:v for k,v in lib.items() if k!='parts'} for t,lib in libs.items()},
                              **batches))


if __name__ == '__main__':
    with browser.lock(OUT/'run.lock'):
        generate()
