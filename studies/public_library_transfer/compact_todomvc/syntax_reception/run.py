"""Recover unambiguous serialization errors on all four Llama workflows."""
from pathlib import Path
import json
import re
import subprocess
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,read,sha,now
from ..contract_repair import run as contract
from ..event_functions import delivery

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/todo-syntax-reception-20261126'
CAP=.30
TAG='llama3'
events,modules=contract.events,contract.modules
weak=events.weak
SOURCE=contract.OUT


def register():
    f=OUT/'registration.json'
    sources=[Path(__file__),HERE/'PROTOCOL.md',HERE/'close.cjs',Path(contract.__file__),modules.ACORN,
             SOURCE/'registration.json',weak.OUT/TAG/'seal.json',events.OUT/TAG/'seal.json',
             delivery.OUT/TAG/'seal.json',contract.route.OUT/TAG/'seal.json']
    sources.extend(SOURCE/TAG/r/'library.json' for r in ('a','b'))
    hashes={str(p.relative_to(ROOT)):sha(p) for p in sources}
    if not f.exists():
        b=check_credits(CAP)
        assert b['sufficient']
        core.save(f,dict(utc=now(),cap=CAP,balance=b,deadline=contract.route.END.isoformat(),sources=hashes))
    assert read(f)['sources']==hashes


def close(src):
    return subprocess.run(['node',str(HERE/'close.cjs'),str(modules.ACORN)],input=src,
                          capture_output=True,text=True,check=True,timeout=15).stdout


def delivered(folders):
    for folder in folders:
        for receipt in sorted(folder.glob('transmission-*/settled.json')):
            path=receipt.with_name('response.json')
            assert sha(path)==read(receipt)['response_sha256']
            choice=read(path)['choices'][0]
            if choice['finish_reason']!='error':
                return (choice['message'].get('content') or ''),path
        if (folder/'reused.json').exists():
            entry=read(folder/'reused.json')
            path=ROOT/entry['source']
            assert sha(path)==entry['sha256']
            return read(path)['choices'][0]['message'].get('content') or '',path
    raise RuntimeError('No retained settled delivery for '+str(folders))


def repair(ledger,tag,rep,pub):
    old=read(SOURCE/tag/rep/'library.json')
    funcs=dict(old['functions'])
    recovered={}
    for name,src in funcs.items():
        if src:continue
        raw,path=delivered([SOURCE/tag/rep/'calls'/name/'1'])
        before=modules.js_block(raw)
        after=close(before)
        funcs[name]=modules.extract(name,after) if after else None
        recovered[name]=dict(source=str(path.relative_to(ROOT)),sha256=sha(path),parsed=bool(funcs[name]))
    features=list(pub['spec'])
    conf=dict.fromkeys(modules.OPTIONS,True)
    def probe(c):return contract.feedback.passes(contract.feedback.evaluate_public(modules.assemble(funcs,c),features))
    checks=probe(conf)
    menu={k:sorted(checks-probe({**conf,k:False})) for k in conf}
    menu={k:v for k,v in menu.items() if v}
    status='valid' if all(funcs.values()) and checks and menu else 'build_failed'
    lib=dict(status=status,options=menu,functions=funcs,public=sorted(checks),recovered=recovered)
    core.save(OUT/tag/rep/'library.json',lib)
    return lib


def first_object(raw):
    try:return events.base.parse_json(raw)
    except (ValueError,TypeError):
        # The first object only; do not search for a semantically better later plan.
        start=raw.find('{')
        if start<0:raise ValueError('No object')
        return json.JSONDecoder().raw_decode(raw[start:])[0]


def controls(task):
    t=next(x for x in weak.domain.tasks() if x['id']==task)
    orig=read(weak.OUT/TAG/'seal.json')['rows'][task]
    out={}
    for arm in ('direct','human','gpt5-library'):
        if orig[arm]['status']=='valid':
            out[arm]=orig[arm]
            continue
        raw,path=delivered([weak.OUT/TAG/task/arm/'call',events.OUT/TAG/'restore'/task/arm,
            delivery.OUT/TAG/'fill'/task/arm,contract.route.OUT/TAG/'restore'/task/arm])
        try:
            if arm=='direct':
                try:src=first_object(raw)['source']
                except (ValueError,KeyError,TypeError):
                    src=modules.js_block(raw)
                code=close(src)
                if not code.strip():raise ValueError('No parseable JavaScript source')
            else:
                plan=first_object(raw)
                if isinstance(plan.get('handlers'),dict):
                    plan['handlers']={k:v[0] if isinstance(v,list) and len(v)==1 and isinstance(v[0],str) else v
                                      for k,v in plan['handlers'].items()}
                if arm=='human':code=weak.domain.compile_plan(plan,t['features'],weak.library.library())
                else:
                    lib=read(weak.GPT)
                    code=weak.generic.compile_plan(plan,t['features'],lib,weak.tables_of(lib))
            f=OUT/TAG/task/arm/'files.json'
            core.save(f,{'candidate.js':code})
            out[arm]=dict(status='valid',file=str(f.relative_to(ROOT)),files_sha256=sha(f))
        except events.base.ERRORS as exc:
            out[arm]=dict(status='invalid',reason=str(exc)[:160])
        out[arm]['response_sha256']=sha(path)
    return out


def main():
    register()
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    targets,briefs=weak.suite.inputs()
    rows={t:controls(t) for t in weak.recovery.todo.TASKS}
    libs={}
    with patch.multiple(contract,OUT=OUT,repair=repair),patch.multiple(events.base,OUT=OUT,END=contract.route.END,template=events.template):
        for rep in ('a','b'):
            _,_,status,arms=contract.prepare((TAG,rep,ledger,targets,briefs['todomvc']))
            libs[rep]=dict(status=status)
            for task,v in arms.items():rows[task].update(v)
    core.save(OUT/TAG/'seal.json',dict(registration=sha(OUT/'registration.json'),libraries=libs,rows=rows))
    with patch.multiple(weak,OUT=OUT,MODELS={TAG:weak.SMALL[TAG]}):weak.score()
    core.save(HERE/'result.json',dict(model=weak.SMALL[TAG],results=read(OUT/TAG/'result.json'),
        registration=sha(OUT/'registration.json'),cost=ledger_read.totals(OUT/'budget.sqlite3'),
        libraries={r:{k:v for k,v in read(OUT/TAG/r/'library.json').items() if k!='functions'} for r in ('a','b')}))


if __name__=='__main__':
    with browser.lock(OUT/'.lock'):main()
