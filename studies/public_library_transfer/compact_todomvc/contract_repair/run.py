"""Repair independently obtained TodoMVC functions using public state/event contracts."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import re
import subprocess
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from ..event_functions import run as events
from ..route_completion import run as route

HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/todomvc-contract-repair-20261126'
CAP = 1.20
TAGS = ('llama3', 'gemma4', 'ministral3')
modules, feedback = events.modules, events.feedback
EVENTS = {
    'add': {'title': '  New todo  '}, 'destroy': {'id': 7}, 'toggle': {'id': 7},
    'toggleAll': {}, 'edit': {'id': 7}, 'save': {'id': 7, 'title': '  Edited  '},
    'cancel': {'id': 7}, 'clearCompleted': {}, 'route': {'filter': 'completed'}
}


def parent(tag, rep):
    return (route.OUT if tag == 'llama3' else events.OUT) / tag / rep / 'library.json'


def register():
    paths = [HERE/'PROTOCOL.md', Path(__file__), Path(events.__file__), Path(feedback.__file__),
             feedback.HERE/'probes.cjs', Path(modules.__file__), modules.HERE/'function.cjs',
             events.weak.suite.SOURCE/'build-inputs.json', events.weak.suite.SOURCE/'targets.json']
    paths += [parent(tag, rep) for tag in TAGS for rep in ('a','b')]
    sources = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    f = OUT/'registration.json'
    if not f.exists():
        balance = check_credits(CAP)
        assert balance['sufficient']
        core.save(f, dict(utc=now(), cap=CAP, deadline=route.END.isoformat(), sources=sources, balance=balance))
    assert read(f)['sources'] == sources


def syntax_error(name, response):
    body = modules.js_block(response)
    parser = subprocess.run(['node','--check'],input=body,text=True,capture_output=True,timeout=10)
    return '\n'.join(parser.stderr.splitlines()[:6]) if parser.returncode else 'No matching complete named function.'


def repair(ledger, tag, rep, public):
    path = OUT/tag/rep/'library.json'
    if path.exists():
        return read(path)
    prior = read(parent(tag, rep))
    funcs = dict(prior['functions'])
    config = dict.fromkeys(modules.OPTIONS, True)
    def probe(fs, enabled):
        return feedback.evaluate_public(modules.assemble(fs, enabled), list(public['spec']))
    checks = probe(funcs, config)
    initial = sorted(feedback.passes(checks))
    history = []
    for name, (params, group, objective) in modules.CONTRACTS.items():
        relevant = {k:v for k,v in checks.items() if name in v['owners'] and not v['passed']}
        if funcs.get(name) and not relevant:
            continue
        previous = funcs.get(name)
        parser = None
        if previous is None:
            old = parent(tag, rep).parent/'calls'/name
            for phase in ('repair','first'):
                cache = old/phase
                responses = sorted(cache.glob('transmission-*/settled.json'))
                reused = cache/'reused.json'
                if responses:
                    previous = read(responses[-1].with_name('response.json'))['choices'][0]['message'].get('content')
                elif reused.exists():
                    previous = read(ROOT/read(reused)['source'])['choices'][0]['message'].get('content')
                if previous:
                    parser = syntax_error(name, previous)
                    break
        for attempt in range(2):
            msg = core.messages('Write a short complete JavaScript function. Use simple loops and local variables. '
                'Use exactly the function signature. Return just its code. State is plain data. '
                'No JSX, DOM, frameworks, helper functions or test cases.',
                dict(signature=f'function {name}({params})', operation=objective,
                     contract=public['contract'], requirements=public['spec'].get(group,public['spec']['core']),
                     event=dict(type=name, **EVENTS[name]) if name in EVENTS else None,
                     exampleState=dict(todos=[dict(id=7,title='First note',completed=False),
                         dict(id=11,title='Second note',completed=True)],editing=None,filter='all',nextId=12),
                     public_observations=feedback.diagnostic(relevant), prior_source=previous,
                     parser_diagnostic=parser))
            dest = path.parent/'calls'/name/str(attempt+1)
            try:
                raw = events.base.request(ledger, ('todomvc',tag,rep), dest, msg, 'build', 1600)
            except events.MISSING as exc:
                history.append(dict(name=name, attempt=attempt+1, status='missing',reason=str(exc)))
                break
            fn = modules.extract(name, raw)
            if fn is None:
                previous,parser = raw,syntax_error(name,raw)
                history.append(dict(name=name,attempt=attempt+1,status='invalid_source'))
                continue
            trial = dict(funcs, **{name:fn})
            after = probe(trial,config)
            before, gained = feedback.passes(checks), feedback.passes(after)
            keep = before <= gained and (not funcs.get(name) or before < gained)
            history.append(dict(name=name,attempt=attempt+1,status='kept' if keep else 'no_public_gain',
                                added=sorted(gained-before),lost=sorted(before-gained)))
            if keep:
                funcs,checks = trial,after
            relevant = {k:v for k,v in after.items() if name in v['owners'] and not v['passed']}
            if keep and not relevant:
                break
            previous,parser = fn,None
    passes = feedback.passes(checks)
    menu = {k:sorted(passes-feedback.passes(probe(funcs,dict(config,**{k:False})))) for k in config}
    menu = {k:v for k,v in menu.items() if v}
    status = 'valid' if all(funcs.values()) and menu and passes else 'build_failed'
    core.save(path, dict(status=status,functions=funcs,options=menu,initial=initial,public=sorted(passes),history=history))
    return read(path)


def prepare(job):
    tag, rep, ledger, targets, public = job
    lib = repair(ledger, tag, rep, public)
    folder = OUT/tag/rep
    names = list(lib['options'])
    profiles = list(dict.fromkeys([tuple(names), (), *((k,) for k in names),
                                  *(tuple(n for n in names if n!=k) for k in names)]))
    def emit(dest, selected):
        config = {k:k not in names or k in selected for k in modules.OPTIONS}
        core.save(dest, {'candidate.js':modules.assemble(lib['functions'],config)})
        return dict(status='valid', file=str(dest.relative_to(ROOT)), files_sha256=sha(dest))
    rows = {}
    for task in events.weak.recovery.todo.TASKS:
        dest = folder/task
        if lib['status'] != 'valid':
            plan = fixed = dict(status=lib['status'])
        else:
            fixed = emit(dest/'fixed.json', profiles[0])
            msg = core.messages('Choose one configuration. Return only its integer index.',
                    dict(task=targets[task]['public'], choices=dict(enumerate(profiles)), public_effects=lib['options']))
            try:
                raw = events.base.request(ledger,('todomvc',tag,rep),dest/'call',msg,'plan',1200)
                val = events.base.uncode(raw).strip()
                if not re.fullmatch(r'[0-9]+',val) or int(val)>=len(profiles):
                    raise ValueError('Expected an available profile index')
                plan = emit(dest/'plan.json',profiles[int(val)])
            except events.MISSING as exc:
                plan = dict(status='missing',reason=str(exc))
            except ValueError as exc:
                plan = dict(status='invalid',reason=str(exc))
        rows[task] = {rep:plan,'fixed-'+rep:fixed}
    return tag,rep,lib['status'],rows


def main():
    register()
    ledger = Ledger(OUT/'budget.sqlite3',CAP,CAP)
    targets,briefs = events.weak.suite.inputs()
    groups = {}
    with patch.multiple(events.base, OUT=OUT, END=route.END, template=events.template), ThreadPoolExecutor(max_workers=3) as pool:
        for tag,rep,status,rows in pool.map(prepare, ((t,r,ledger,targets,briefs['todomvc']) for t in TAGS for r in ('a','b'))):
            group=groups.setdefault(tag,dict(rows={},libraries={},registration=sha(OUT/'registration.json')))
            group['libraries'][rep]=dict(status=status)
            for task,arms in rows.items():
                group['rows'].setdefault(task,{}).update(arms)
    for tag,data in groups.items():
        core.save(OUT/tag/'seal.json',data)
    with patch.multiple(events.weak,OUT=OUT,MODELS={t:events.weak.MODELS[t] for t in TAGS}):
        events.weak.score()
    core.save(HERE/'result.json',dict(registration=sha(OUT/'registration.json'),cost=ledger_read.totals(OUT/'budget.sqlite3'),
        models={events.weak.MODELS[t]:read(OUT/t/'result.json') for t in TAGS},
        public={t:{r:{k:read(OUT/t/r/'library.json')[k] for k in ('status','initial','public')} for r in ('a','b')} for t in TAGS}))


if __name__ == '__main__':
    with browser.lock(OUT/'.run.lock'):
        main()
