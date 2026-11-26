"""Build behavior modules from a public project brief and seal two independent libraries."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import re
import threading
import time
from urllib.parse import urlsplit

import httpx
from playwright.sync_api import sync_playwright

from gui_dna.budget import BudgetStop, Ledger
from gui_dna.provider import parse_json
from scripts.check_openrouter_credits import check_credits
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from studies.webbench.backbone_matrix import run as original
from studies.webbench.form.flash_self_build.file_repair.public_checks import _node_diagnostic

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/webbench-self-modules-20261125'
END = datetime(2026, 11, 25, 13, 32, tzinfo=timezone.utc)
CAP = 7.5
ORDER = [('form', 'deepseek-pro'), ('form', 'mistral'), ('table', 'deepseek-flash'),
         ('form', 'qwen9'), ('form', 'qwen'), ('table', 'mistral'), ('table', 'qwen'),
         ('table', 'oss'), ('svg-chart', 'mistral'), ('svg-chart', 'oss'), ('form', 'gemma'),
         ('svg-chart', 'qwen9'), ('table', 'qwen9'), ('table', 'gemma'),
         ('svg-chart', 'gemma'), ('table', 'deepseek-pro'), ('svg-chart', 'deepseek-pro')]
GROUPS = {
    'table': [('index.css', 'common/table.js'), ('common/menu.js', 'common/key.js'),
              ('common/mouse.js', 'common/layout.js', 'common/drag.js'), ('index.js',)],
    'form': [('index.css', 'common/Question.js'), tuple(f'common/{n}Question.js' for n in
             ('SingleSelection', 'MultiSelection', 'Open', 'Rating')), tuple(f'common/{n}Question.js' for n in
             ('Ranking', 'Nps', 'Likert', 'Data')), ('common/Contents.js', 'common/Survey.js'), ('index.js',)],
    'svg-chart': [('common/Chart.scss', 'common/Chart.js'), ('common/LineChart.js',),
                  tuple(f'common/{n}Chart.js' for n in ('Scatter', 'Step', 'Area')),
                  ('common/BarChart.js', 'common/PieChart.js'), ('index.js',)],
}
API_SLOTS = threading.BoundedSemaphore(12)
ERRORS = (ValueError, TypeError, KeyError, AttributeError, IndexError)
DESIGN = """Design a reusable behavior library for this complete public brief, using the listed local
module groups in dependency order. Return one short JSON object with these exact fields:
{"controls":{"lowercase-kebab-name":"what changes when enabled and disabled"}, "defaults":["enabled-key"],
"first":["enabled-key"], "interfaces":"concise explicit imports, exports, shared state and constructor
signatures for every module"}. Supply 1 to 4 behavior switches with actual meaning, all identifiers
lowercase kebab case. Defaults and first example should demonstrate the integrated usable app.
Configuration is given by globalThis.APP_CONFIG before modules execute. No target number dispatch.
Only design the interface now. No implementation or tools."""
SOURCE = """Write only the requested files of your reusable browser library. Use the public brief,
starter, your design and the exact exports of modules already delivered. Implement the interactions
in full. Preserve the public DOM names, values, assets and module interfaces. Share state between
event handlers. Use globalThis.APP_CONFIG for the advertised behavior switches. The integrated
default and first example must mount and work immediately. No external code, tests, tools or
target-number dispatch. For each requested file put a line 'FILE: relative/path' followed by the
complete raw file content, with no Markdown fences. Use exactly the listed paths. No commentary."""
PROBES = {
    'table': """() => {const c=document.querySelector('tbody td'); if(!c)return false;
      c.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,button:2,clientX:40,clientY:40}));
      return [...document.querySelectorAll('.menu')].some(e=>e.getBoundingClientRect().height>0)}""",
    'form': """() => {const f=document.querySelector('form'); const e=f?.querySelector(
      'input[type=checkbox]:not(:disabled),input[type=radio]:not(:checked):not(:disabled)');
      if(!f?.querySelector('fieldset legend')||!e)return false; const b=e.checked;e.click();return e.checked!==b}""",
    'svg-chart': """() => !!document.querySelector('.root svg :is(path,line,polyline,polygon,rect,circle,text)')""",
}
OBSERVATION = {'form': 'mount a question with a legend and toggle a native choice',
               'table': 'right-click a body cell and display a visible context menu',
               'svg-chart': 'mount an SVG chart with a graphical element in the public root'}


def old_root(project, tag):
    stage = 'form' if project == 'form' else (
        'extension' if tag in {'deepseek-pro', 'deepseek-flash', 'qwen9'} else 'matrix')
    return ROOT / f'artifacts/backbone-{stage}-20261124'


def template(project, tag, stage):
    old = old_root(project, tag) / tag / project
    p = old / ('build/attempt-1/request.json' if stage == 'build' else 'gpt5-library/1/call/request.json')
    return {k: v for k, v in read(p)['body'].items() if k != 'messages'}


def register():
    files = [Path(__file__), HERE/'PROTOCOL.md', Path(original.__file__), Path(core.__file__),
             Path(browser.__file__), Path(_node_diagnostic.__code__.co_filename)]
    for p, t in ORDER:
        old = old_root(p, t)
        files += [old/'inputs'/p/'public.json', old/'inputs'/p/'browser.json',
                  old/t/p/'build/attempt-1/request.json', old/t/p/'gpt5-library/1/call/request.json']
        assert read(old/'inputs'/p/'public.json') == core.public_input(p) == read(core.OUT/'inputs'/f'{p}.json')
    fingerprints = {str(f.relative_to(ROOT)): sha(f) for f in files}
    reg = OUT/'registration.json'
    if reg.exists():
        assert read(reg)['sources'] == fingerprints
        return
    balance = check_credits(CAP)
    if not balance['sufficient']:
        raise BudgetStop('Insufficient credit')
    core.save(reg, dict(utc=now(), deadline=END.isoformat(), cap=CAP, balance=balance, cells=ORDER,
                        reps=['a','b'], tasks=list(range(1,21)), sources=fingerprints))
    for p in GROUPS:
        core.save(OUT/'inputs'/p/'browser.json', browser.verify_contract(p))


def request(ledger, case, root, messages, stage, max_tokens):
    project, tag, rep = case
    body = template(project, tag, stage)
    body.update(messages=messages, max_tokens=max_tokens)
    if stage == 'build':
        if tag in ('deepseek-pro', 'deepseek-flash', 'qwen9'):
            body['reasoning'] = {'enabled': False}
        if rep == 'b' and 'seed' in body:
            body['seed'] += 1
    for attempt in (1, 2):
        folder = root/f'transmission-{attempt}'
        req, res, settled = (folder/f'{k}.json' for k in ('request','response','settled'))
        if req.exists():
            assert read(req)['body'] == body
            if settled.exists():
                assert sha(res) == read(settled)['response_sha256']
                return read(res)['choices'][0]['message'].get('content') or ''
            continue
        with API_SLOTS:
            if datetime.now(timezone.utc) + timedelta(seconds=225) >= END or (OUT/f'closed-{tag}.json').exists():
                raise original.Unavailable('Deadline or closed route')
            price = body['provider']['max_price']
            bound = len(json.dumps(body, ensure_ascii=False).encode()) + 2048
            reserve = (bound * Decimal(str(price['prompt'])) + max_tokens * Decimal(str(price['completion']))) / 1_000_000
            label = f'{stage}/{root.relative_to(OUT)}/{attempt}'
            ticket = ledger.reserve(reserve, label, body['model'])
            core.save(req, dict(call_id=ticket, body=body, input_bound=bound, reserved_usd=float(reserve)))
            start = time.monotonic()
            try:
                r = httpx.post('https://openrouter.ai/api/v1/chat/completions', json=body, headers={
                    'Authorization':'Bearer '+os.environ['OPENROUTER_API_KEY']}, timeout=httpx.Timeout(210, connect=20))
                r.raise_for_status()
                payload = r.json()
                core.save(res, payload)
                usage = payload['usage']
                if usage.get('cost') is None:
                    raise ValueError('Missing usage')
                content = payload['choices'][0]['message'].get('content') or ''
            except (httpx.HTTPError, *ERRORS) as exc:
                status = exc.response.status_code if isinstance(exc,httpx.HTTPStatusError) else None
                why = f'HTTP {status}' if status else type(exc).__name__
                ledger.uncertain(ticket, why)
                core.save(folder/'error.json', dict(reason=why))
                if status in (401,402,403,404):
                    with browser.lock(OUT/f'closed-{tag}.lock'):
                        if not (OUT/f'closed-{tag}.json').exists():
                            core.save(OUT/f'closed-{tag}.json', dict(reason=why))
                    raise original.Unavailable(why) from None
                continue
            ledger.settle(ticket, usage['cost'], time.monotonic()-start, payload.get('id'), usage)
            core.save(settled, dict(response_sha256=sha(res)))
            if payload['choices'][0].get('finish_reason') == 'error':
                continue
            return content
    raise original.Unavailable('Two undelivered transmissions')


def manifest(value):
    info = parse_json(value)
    controls = info['controls']
    if not isinstance(controls, dict) or not 1 <= len(controls) <= 4 or not isinstance(info['interfaces'],str):
        raise ValueError('Expected 1-4 named controls and a text interfaces field')
    for key, description in controls.items():
        if not re.fullmatch('[a-z][a-z0-9-]{0,63}', key) or not isinstance(description,str) or not description.strip():
            raise ValueError('Expected a lowercase kebab-case key and a nonempty description')
    for field in ('defaults','first'):
        if not isinstance(info[field], list) or set(info[field])-controls.keys():
            raise ValueError(f'{field} must list only enabled control identifiers')
    return info


def uncode(text):
    text = text.strip()
    match = re.fullmatch(r'```[\w-]*\s*\n(.*?)\n?```', text, re.S)
    return match[1] if match else text


def extract(text, names):
    sections = re.split(r'(?m)^\s*(?://\s*)?FILE:\s*([w./-]+)\s*$', uncode(text))
    found = {}
    for name, code in zip(sections[1::2],sections[2::2]):
        if name in names and name not in found and code.strip():
            found[name] = uncode(code)
    if not found and len(names)==1 and len(sections)==1 and text.strip():
        found[names[0]] = uncode(text)
    return found


def diagnose_source(name, code):
    if not code or not code.strip():
        return 'No source received at the requested path'
    if name.endswith('.js'):
        error = _node_diagnostic(name, code, True)
        return error['message'] if error else None
    return None


def package(public, spec, files):
    controls = [dict(id=k,type='boolean',values=[],behavior=v,default=str(k in spec['defaults']).lower(),
                     example=str(k in spec['first']).lower()) for k,v in spec['controls'].items()]
    return core.package(public, dict(design=spec['interfaces'],controls=controls,anchor='',fragment='',
                       css='',script='',files=[dict(path=k,content=v) for k,v in files.items()]))


def check(public, pkg, folder):
    project = public['project']
    issues = []
    for label, plan in [('default',pkg['defaults']), ('first',pkg['examples'][0]['plan'])]:
        page = folder/label
        files = core.materialize(project,pkg,plan,page)
        served = browser.served_page(OUT,project,page,files)
        with browser.serve(project,served) as url, sync_playwright() as pw:
            engine = pw.chromium.launch(env=browser.browser_env())
            try:
                ctx = engine.new_context(service_workers='block')
                ctx.route('**/*',lambda r: r.continue_() if urlsplit(r.request.url).netloc==urlsplit(url).netloc else r.abort())
                tab = ctx.new_page()
                errors = []
                tab.on('pageerror',lambda e: errors.append(str(getattr(e,'stack','') or e)[:650]))
                tab.on('response',lambda r: errors.append(f'{r.status} {urlsplit(r.url).path}') if r.status>=400 and
                       r.request.resource_type in ('script','stylesheet','document') else None)
                tab.on('dialog',lambda d: d.dismiss())
                tab.goto(url+'/index.html', wait_until='load',timeout=20000)
                tab.wait_for_timeout(400)
                active = tab.evaluate(PROBES[project])
                tab.wait_for_timeout(100)
                errors = [e.replace(url,'<origin>') for e in errors]
                if not active:
                    errors.append('Could not '+OBSERVATION[project])
                core.save(folder/f'{label}-check.json', dict(active=active,errors=errors))
                issues.extend(errors)
            finally:
                engine.close()
    return list(dict.fromkeys(issues))


def build(ledger, case, root, public):
    project, tag, rep = case
    groups = GROUPS[project]
    ask = lambda path, msg, limit: request(ledger,case,root/path,msg,'build',limit)
    base = core.messages(DESIGN,dict(public_project=public,groups=groups))
    messages = base
    for i in (1,2):
        raw = ask(f'design-{i}',messages,2400)
        try:
            spec = manifest(raw)
            break
        except ERRORS as exc:
            if i==2:
                raise ValueError(f'Configuration delivery: {exc}') from exc
            messages = base+[dict(role='assistant',content=raw),dict(role='user',content=str(exc))]
    core.save(root/'design.json',spec)
    files = {}
    def source(paths, diagnosis=None):
        return core.messages(SOURCE,dict(public_project=public,design=spec,requested=paths,
                             previous_sources=files,public_diagnostic=diagnosis))
    for i, paths in enumerate(groups):
        files.update(extract(ask(f'group-{i+1}', source(paths), 11000),paths))
        for name in paths:
            defect = diagnose_source(name,files.get(name))
            if defect:
                result = ask('single-'+name.replace('/','_'), source([name],defect),6500)
                files.update(extract(result,[name]))
                defect = diagnose_source(name,files.get(name))
                if defect:
                    raise ValueError(f'{name}: {defect}')
    for version in range(3):
        pkg = package(public,spec,files)
        folder = root/f'v{version}'
        core.save(folder/'package.json',pkg)
        errors = check(public,pkg,folder)
        if not errors:
            fixed = folder/'first'
            return dict(status='valid',version=version,package=str((folder/'package.json').relative_to(ROOT)),
                        package_sha256=sha(folder/'package.json'),fixed=str(fixed.relative_to(ROOT)),fixed_files=browser.tree(fixed))
        if version == 2:
            raise ValueError('Public behavior check: '+' | '.join(errors)[:1400])
        messages = core.messages(SOURCE+' Choose exactly one existing implementation file responsible for the error. '
                                 'Include its FILE: path header.',dict(public_project=public,design=spec,
                                 current_sources=files,public_errors=errors))
        repaired = extract(ask(f'behavior-repair-{version+1}',messages,9000),files)
        if len(repaired)!=1 or any(diagnose_source(name,code) for name,code in repaired.items()):
            raise ValueError('Undeliverable public behavior repair: '+' | '.join(errors)[:1400])
        files.update(repaired)


def branch(case, ledger):
    project,tag,rep = case
    root = OUT/project/tag/rep
    reg = OUT/'registration.json'
    with browser.lock(root/'.lock'):
        if (root/'seal.json').exists():
            return
        public = read(old_root(project,tag)/'inputs'/project/'public.json')
        status = root/'build/status.json'
        if not status.exists():
            try:
                state = build(ledger,case,root/'build',public)
            except (BudgetStop, original.Unavailable) as exc:
                state = dict(status='missing',reason=str(exc))
            except ERRORS as exc:
                state = dict(status='build_failed',reason=str(exc))
            core.save(status,state)
        state = read(status)
        rows = []
        if state['status']=='valid':
            pkg = read(ROOT/state['package'])
            def plan(n):
                dest=root/'plans'/str(n)
                row=dict(project=project,task=n,arm='self')
                try:
                    raw = request(ledger,case,dest,core.plan_messages(public,n,pkg),'plan',8192)
                    config = parse_json(raw)
                    page = dest/'page'
                    files = core.materialize(project,pkg,config,page)
                    row.update(status='valid',page=str(page.relative_to(ROOT)),files=files)
                except (BudgetStop,original.Unavailable) as exc:
                    row.update(status='missing', reason=str(exc))
                except ERRORS as exc:
                    row.update(status='invalid', reason=str(exc)[:400])
                core.save(dest/'result.json',row)
                return row
            with ThreadPoolExecutor(max_workers=3) as pool:
                rows=list(pool.map(plan,range(1,21)))
        core.save(root/'seal.json',dict(case=case,registration_sha256=sha(reg),build=state,rows=rows))
        print(project,tag,rep,state['status'],state.get('reason','')[:100],flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('register','run'))
    parser.add_argument('--workers',type=int,default=6)
    args=parser.parse_args()
    browser.OUT=OUT
    register()
    if args.action=='run':
        ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
        cases=[(p,t,r) for p,t in ORDER for r in ('a','b')]
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            list(pool.map(lambda case: branch(case,ledger), cases))


if __name__=='__main__':
    main()
