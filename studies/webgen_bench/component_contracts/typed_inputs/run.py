"""Bind public component fields as named arguments to model-written DOM functions."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from .. import run as components
from ..function_bodies import run as bodies

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/webgen-typed-inputs-20261127'
CAP = .48
GEN = components.gen
FIELDS = {
    'tabs': ('entries, renderChildren', 'c.tabs, renderChildren',
             'Each entry has title and body. Build navigation controls and a content region. Keep navigation present while changing the contents. Select the first on load; every click, including returning to the first, must render the selected body.'),
    'form': ('title, fields, actions, successMessage, renderChildren',
             'c.title, c.body, c.actions, c.onEvent?.submitSucc?.actions?.[0]?.args?.msg, renderChildren',
             'Create a native form with title, child fields and actions. On submit prevent navigation, collect named fields and show the supplied successMessage as visible text. Mount the child controls inside the form.'),
    'dialog': ('title, body, renderChildren', 'c.title, c.body, renderChildren',
               'Display the supplied title and nested body of any component type immediately, inside a closable dialog. A Close button removes this dialog.'),
    'checkbox': ('name, label, required, value', 'c.name, c.label, c.required, c.value',
                 'Create a native checkbox with the supplied name, required flag, value and visible label.'),
}


def bind(kind, source):
    args = FIELDS[kind][1]
    return ('function(root,c,env){const renderChildren = nodes => {const fragment = '
            'document.createDocumentFragment();env.mount(fragment,nodes);return fragment;};'
            'return (' + source + ')(root,' + args + ');}')


def extract(raw):
    block = re.search(r'```(?:javascript|js)?\s*\n([\s\S]*?)```', raw, re.I)
    source = (block[1] if block else raw).strip().rstrip(';')
    if not re.match(r'^function\s+(?:render\w*)\s*\(', source):
        raise ValueError('Return one complete named function render with the requested arguments.')
    result = subprocess.run(['node', '--check', '-'], input='('+source+')', text=True,
                            capture_output=True, timeout=6)
    if result.returncode:
        raise ValueError(result.stderr[:240])
    return source


def repair(tag, kind, initial, ledger):
    dest = OUT / 'build' / tag / kind
    file = dest / 'record.json'
    if file.exists():
        return read(file)
    observed = components.public_probe(kind, initial)
    observations = [observed]
    source = initial
    args, _, assignment = FIELDS[kind]
    last = None
    for i in range(2):
        if observations[-1].get('passed'):
            break
        if datetime.now(timezone.utc) >= components.END:
            raise TimeoutError('Registration window closed')
        prompt = ('You write a standalone JavaScript function render(root, ' + args + '). '
                  'Only these named arguments exist. root is a real DOM element. '
                  'renderChildren(nodes) RETURNS a DOM fragment. To show children, append that returned '
                  'fragment to an element. Labels and data come from arguments. No component, env or external '
                  'variables. Return just the complete named function and no invocation. ' + assignment)
        example = components.previous.parent.KINDS[kind][1]
        msg = core.messages(prompt, {'sample_field_values_only': example, 'previous_public_observation': observations[-1],
                                     'your_last_submission': last})
        try:
            last = extract(GEN.call(ledger,tag,dest/str(i),msg,'build',2500))
            candidate = bind(kind,last)
            observed = components.public_probe(kind,candidate)
            if observed['passed']:
                source = candidate
        except GEN.MISSING as error:
            observations.append({'missing':str(error)})
            break
        except GEN.ERRORS as error:
            observed = {'passed':False,'error':str(error)[:240]}
        observations.append(observed)
    core.save(file, {'source':source, 'changed':source != initial, 'observations':observations})
    return read(file)


def build(tag, ledger):
    file = OUT/'build'/tag/'library.json'
    if file.exists():
        return read(file)
    original = read(bodies.OUT/'build'/tag/'library.json')
    parts = dict(original['parts'])
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = {k:pool.submit(repair,tag,k,parts[k],ledger) for k in FIELDS}
        repairs = {k:j.result() for k,j in jobs.items()}
    parts.update({k:r['source'] for k,r in repairs.items()})
    def check(units):
        return components.pages.check(components.previous.site(components.schema.SAMPLE,units,True))
    observed = check(parts)
    empty = dict(original['parts'])
    for k, r in repairs.items():
        if r['changed']:
            empty[k] = bind(k, 'function render(){}')
    control = check(empty)
    keep = all(not ok or observed['checks'][k] for k,ok in original['final']['checks'].items())
    actual = observed if keep else original['final']
    status = 'valid' if len(actual['checks']) == 5 and all(actual['checks'].values()) else 'build_failed'
    core.save(file, dict(status=status, parts=parts if keep else original['parts'], initial=original['final'],
                         final=actual, attempted=observed, empty_replacements=control,
                         changed=[k for k,r in repairs.items() if keep and r['changed']],
                         isolated={k:r['observations'] for k,r in repairs.items()}))
    print(tag,status,actual['checks'],flush=True)
    return read(file)


def generate():
    before_file = bodies.HERE/'candidates.json'
    reg = OUT/'registration.json'
    inputs = [Path(__file__),HERE/'PROTOCOL.md',before_file,Path(bodies.__file__),components.HERE/'probe.js',
              *[bodies.OUT/'build'/tag/'library.json' for tag in components.MODELS]]
    hashes = {str(p.relative_to(ROOT)):sha(p) for p in inputs}
    if not reg.exists():
        earlier = sum(ledger_read.totals(d/'budget.sqlite3')['exposure_usd'] for d in (components.OUT,bodies.OUT))
        assert earlier + CAP <= components.CAP + bodies.CAP
        balance = check_credits(CAP)
        assert balance['sufficient']
        core.save(reg,dict(utc=now(),deadline=components.END.isoformat(),balance=balance,cap=CAP,sources=hashes))
    assert read(reg)['sources'] == hashes
    dest = HERE/'candidates.json'
    if dest.exists():
        return
    ledger = Ledger(OUT/'budget.sqlite3',CAP,CAP)
    with patch.multiple(GEN.BASE,OUT=OUT,END=components.END,template=GEN.settings), ThreadPoolExecutor(max_workers=2) as pool:
        jobs = {t:pool.submit(build,t,ledger) for t in components.MODELS}
        libs = {t:j.result() for t,j in jobs.items()}
    before = read(before_file)
    batches = {}
    for batch, plan_dir in [('development',components.PILOT_PLANS),('holdout',components.OUT/'plans')]:
        rows = before[batch]
        for tag, lib in libs.items():
            for site, arms in rows[tag].items():
                plan = read(plan_dir/tag/site/'record.json')
                arms['self'] = components.render(tag,site,'self',plan,lib,OUT/batch)
        batches[batch] = rows
    core.save(OUT/'seal.json',dict(registration=sha(reg),libraries={t:sha(OUT/'build'/t/'library.json') for t in libs},**batches))
    core.save(dest,dict(previous=sha(before_file),registration=sha(reg),seal=sha(OUT/'seal.json'),models=before['models'],
                        libraries={t:{k:v for k,v in lib.items() if k!='parts'} for t,lib in libs.items()},
                        cost=ledger_read.totals(OUT/'budget.sqlite3'),**batches))


if __name__ == '__main__':
    with browser.lock(OUT/'run.lock'):
        generate()
