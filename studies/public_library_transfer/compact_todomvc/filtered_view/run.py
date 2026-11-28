"""Repair the view selector on public states, holding four controllers' deployed choices fixed."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import shutil
import subprocess
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.public_library_transfer.compact_todomvc.edit_choices import run as choices
from studies.study_io import ROOT, now, read, sha

state, weak = choices.state, choices.weak
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'artifacts/todo-filtered-view-20261128'
CAP = .20


def example(ids, flags, view, editing=None):
    todos = [dict(id=i, title='Leaf '+str(i), completed=f) for i,f in zip(ids,flags,strict=True)]
    active = sum(not f for f in flags)
    expected = dict(visible=[t for t in todos if view=='all' or t['completed']==(view=='completed')],
                    countText=f'{active} item left' if active==1 else f'{active} items left',
                    allCompleted=bool(todos) and all(flags), hasCompleted=any(flags), hasTodos=bool(todos),
                    editing=editing, filter=view)
    return dict(state=dict(todos=todos,filter=view,editing=editing,nextId=max(ids,default=0)+1),event=None,expected=expected)


TRAIN = [example([8,4,23],[False,True,False],'completed'),
         example([17,6],[True,True],'active'), example([],[],'all'),
         example([7,9],[False,True],'all',7), example([26],[False],'active')]
UNSEEN = [example([82,36,19,53],[True,False,True,True],'active',36),
          example([127,14,59],[False,False,False],'completed'), example([39],[True],'completed')]


def check(fn, cases):
    node = shutil.which('node')
    if not node:
        raise RuntimeError('Node.js unavailable')
    job = dict(name='select',source=fn,cases=cases)
    p = subprocess.run([node,'--max-old-space-size=160',str(state.HERE/'check.cjs')], input=json.dumps(job),
                       text=True,capture_output=True,timeout=8,check=True)
    return json.loads(p.stdout)


def register():
    paths = [Path(__file__), HERE/'PROTOCOL.md', state.HERE/'check.cjs', Path(state.todo.MOD.__file__),
             state.SPEC, choices.HERE/'result.json', choices.OUT/'seal.json']
    paths += [state.OUT/t/r/'library.json' for t in state.TAGS for r in 'ab']
    sums = {str(p.relative_to(ROOT)):sha(p) for p in paths}
    f = OUT/'registration.json'
    if not f.exists():
        balance = check_credits(CAP)
        if not balance['sufficient']:
            raise RuntimeError('Insufficient balance')
        core.save(f, dict(utc=now(), deadline=choices.prior.END.isoformat(), cap=CAP, balance=balance,
                          sources=sums, train=TRAIN, evaluation=UNSEEN))
    if read(f)['sources']!=sums:
        raise ValueError('Frozen controller or test inputs changed')


def build(ledger, tag, rep, lib):
    out = OUT/tag/rep/'library.json'
    if out.exists():
        return read(out)
    original = lib['functions']['select']
    old_cases = state.examples(7,23,'Basil','Moss')['select'] if rep=='a' else state.examples(11,32,'Linen','Bay')['select']
    cases = TRAIN + old_cases
    initial = check(original,cases)
    history, selected = [], original
    msg = core.messages('Write a single pure JavaScript function select(state) for the public TodoMVC shell. '
                        'Only visible uses the current filter. Compute countText from the number of incomplete todos '
                        'across ALL items, singular exactly when that number is one. Compute allCompleted, hasCompleted '
                        'and hasTodos across ALL items, with allCompleted false on an empty list. Return the original '
                        'editing id and filter. Preserve item IDs and order. No DOM, storage or extra helpers. '
                        'Return the entire function only.',
                        dict(interface=read(state.SPEC)['todomvc']['contract'], public_examples=TRAIN))
    if not all(o['passed'] for o in initial):
        for attempt in range(2):
            try:
                raw = state.todo.BASE.request(ledger,('todomvc',tag,rep),out.parent/'calls'/str(attempt),msg,'build',1900)
                fn = state.todo.MOD.extract('select',raw)
                observations = check(fn,cases) if fn else [dict(passed=False,error='Expected select(state)')]
                history.append(observations)
                if all(o['passed'] for o in observations):
                    selected = fn
                    break
                msg += [dict(role='assistant',content=raw),dict(role='user',content='Public checks. Return the corrected full function. '+json.dumps(observations[:len(TRAIN)]))]
            except state.todo.slots.EVENTS.MISSING as exc:
                history.append([dict(missing=str(exc))])
                break
    core.save(out,dict(functions=lib['functions']|{'select':selected}, changed=selected!=original,initial=initial,history=history))
    return read(out)


def generate():
    seal = OUT/'seal.json'
    if seal.exists():
        return
    ledger = Ledger(OUT/'budget.sqlite3',CAP,CAP)
    votes = read(choices.OUT/'seal.json')['decisions']
    tasks = [t['id'] for t in weak.domain.tasks()]
    records = {}
    with patch.multiple(state.todo.BASE,OUT=OUT,END=choices.prior.END,template=state.todo.slots.EVENTS.template), ThreadPoolExecutor(max_workers=3) as pool:
        jobs = {(t,r):pool.submit(build,ledger,t,r,read(state.OUT/t/r/'library.json')) for t in state.TAGS for r in 'ab'}
        for (tag,rep),job in jobs.items():
            revised = job.result()
            block = records.setdefault(tag,{})
            block[rep] = {}
            for key in tasks:
                vote = votes[tag][rep][key]
                for arm in (rep,'fixed-'+rep):
                    if arm==rep and vote['status']!='valid':
                        value = dict(status=vote['status'])
                    else:
                        excluded = vote['disabled'] if arm==rep else []
                        enabled = {k:k not in excluded for k in state.ALL}
                        code = state.todo.MOD.assemble(revised['functions'],enabled)
                        value = state.candidate(OUT/tag/rep/key/arm,code)
                    block[rep].setdefault(key,{})[arm] = value
    core.save(seal,dict(registration=sha(OUT/'registration.json'),records=records,
                        libraries={t:{r:sha(OUT/t/r/'library.json') for r in 'ab'} for t in state.TAGS}))


def score():
    dest = HERE/'result.json'
    if dest.exists():
        return
    seal = read(OUT/'seal.json')
    assert seal['registration']==sha(OUT/'registration.json')
    before = read(choices.HERE/'result.json')['models']
    cache = {}
    for v in before.values():
        for row in v['rows']:
            if row['status']=='valid':
                key = row['task'], row['files_sha256']
                assert key not in cache or cache[key]['passed']==row['passed']
                cache[key]=row
    models = {}
    targets,_=weak.suite.inputs()
    server=weak.evaluate.todo.Server(OUT)
    try:
        for tag,reps in seal['records'].items():
            m=weak.MODELS[tag]
            rows=[r for r in before[m]['rows'] if r['arm'] in ('direct','human','gpt5-library')]
            probes={}
            for rep,tasks in reps.items():
                path=OUT/tag/rep/'library.json'
                assert seal['libraries'][tag][rep]==sha(path)
                lib=read(path)
                probes[rep]=dict(changed=lib['changed'],before=check(read(state.OUT/tag/rep/'library.json')['functions']['select'],UNSEEN),
                                 after=check(lib['functions']['select'],UNSEEN), training_before=lib['initial'],attempts=lib['history'])
                for key,arms in tasks.items():
                    for arm, page in arms.items():
                        row=dict(task=key,arm=arm,status=page['status'],passed=False if page['status']=='invalid' else None)
                        if page['status']=='valid':
                            f=ROOT/page['file']
                            fingerprint=sha(f)
                            assert fingerprint==page['files_sha256']
                            if (key,fingerprint) in cache:
                                row=dict(cache[key,fingerprint],arm=arm,reused=True)
                            else:
                                folder=OUT/'scores'/key/fingerprint
                                with browser.browser_slot():
                                    weak.evaluate.score(('todomvc',targets[key],read(f),folder,server))
                                row.update(weak.recovery.todo.binding.official(folder,targets[key],{}),files_sha256=fingerprint,reused=False)
                                cache[key,fingerprint]=row
                        rows.append(row)
            models[m]=dict(rows=rows,views=probes)
    finally:
        server.close()
    core.save(dest,dict(registration=seal['registration'],seal=sha(OUT/'seal.json'),previous=sha(choices.HERE/'result.json'),
                        models=models,cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__=='__main__':
    with browser.lock(OUT/'study.lock'):
        register()
        generate()
        score()
