"""Build two new libraries whose installers retain working end-to-end interactions."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,now,read,sha
from studies.webbench.table.action_library import run as old
from studies.webbench.file_explorer.document_library.run import parse_document
from studies.webbench.table.selection_binding.replication.bounded import descendants

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/table-interaction-modules-20261126pm'
CAP=1.60
END=datetime(2026,11,26,11,55,tzinfo=timezone.utc)
TAG='qwen9'
BASE=old.compact.base
SEED=2026112611
# Directory names and target behaviors appear in the public feature requests.
MODULES={
 'table':([4],['selection'],'Handle clicks and implement ctx.select(cells,active,anchor). Maintain a Set, active, anchor, visible .selected styling.'),
 'menu':([1,2,3,7,19,20],['row','column'],'Create and bind the context menu and its items following the exact names in the brief. Click actions use the originally right-clicked cell.'),
 'key':([5,6,7,8,9],['arrow','wrap','clear'],'Keyboard navigation, selection and deletion. Use ctx.select so all modules share state. Include header cells.'),
 'edit':([11,12],['edit'],'Bind editing on click, double-click and keyboard; preserve selection on Escape.'),
 'clipboard':([13,14],['clipboard'],'Copy/paste selected cells. Use shared state even when OS clipboard access is unavailable.'),
 'mouse':([9,10],['range'],'Extend selections over a rectangle using the real pointer and shared state; preserve ordinary selection.'),
 'layout':([15,16],['resize'],'Resize rows and columns using their edges. Preserve existing selection.'),
 'drag':([17,18],['reorder'],'Move selected rows and columns using a drag; avoid breaking selection or resizing.')}
ABI='The installer receives ctx={table:HTMLTableElement,selected:Set,active:null,anchor:null}. The first module implements ctx.select(cells,active,anchor), with cells an iterable of DOM elements. Other modules call that method. All event registration and UI behavior are yours. Do not import or call other free functions. Define helpers within installFeature. Use only local browser APIs and preserve earlier installed behaviors.'
PUBLIC=ROOT/read(old.OUT/'registration.json')['public']
ERRORS=(ValueError,KeyError,TypeError,IndexError)
MISSING=old.typed.MISSING

def register():
    path=OUT/'registration.json'
    sources=[Path(__file__),HERE/'probe.py',HERE/'PROTOCOL.md',PUBLIC,PUBLIC.with_name('browser.json'),Path(BASE.__file__),Path(core.__file__)]
    hashes={str(f.relative_to(ROOT)):sha(f) for f in sources}
    if not path.exists():
        b=check_credits(CAP)
        assert b['sufficient']
        core.save(path,dict(utc=now(),balance=b,deadline=END.isoformat(),cap=CAP,sources=hashes,seeds=[SEED,SEED+1],model=old.settings('table',TAG,'plan')['model']))
    assert read(path)['sources']==hashes
    return read(path)

def settings(project,tag,phase):
    return old.settings(project,tag,phase)|{'seed':SEED}

def emit(pub,parts,folder):
    files=dict(pub['starter'])
    imports=[]
    for i,(name,src) in enumerate(parts.items()):
        files['common/'+name+'.js']='export '+src
        imports.append(f'import {{installFeature as f{i}}} from "./common/{name}.js";')
    files['index.js']+='\n'+'\n'.join(imports)+'\nconst ctx={table:document.querySelector(".table"),selected:new Set(),active:null,anchor:null};\n'+'\n'.join(f'f{i}(ctx);' for i in range(len(parts)))
    return dict(status='valid',page=str(folder.relative_to(ROOT)),files=core.emit('table',files,folder))

def observe(candidate):
    mod='studies.webbench.table.interaction_modules.probe'
    proc=subprocess.Popen([sys.executable,'-m',mod],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
    try:out,err=proc.communicate(json.dumps(candidate),timeout=32)
    except subprocess.TimeoutExpired:
        for pid in descendants(proc.pid)|{proc.pid}:
            try:os.kill(pid,signal.SIGKILL)
            except ProcessLookupError:pass
        proc.communicate()
        return dict(checks={},errors=['No public browser result within 32 seconds'])
    if proc.returncode:raise RuntimeError(err[-1600:])
    return json.loads(out)

def source(raw):
    original=BASE.uncode(raw).strip()
    fence=re.search(r'```(?:javascript|js)?\s*\n([\s\S]*?)```',original,re.I)
    text=re.sub(r'^\s*export\s+(?:default\s+)?','',fence[1] if fence else original)
    mods=old.build.modules
    run=subprocess.run(['node',str(mods.HERE/'function.cjs'),str(mods.ACORN)],input=json.dumps(dict(name='installFeature',arity=1,text=text)),capture_output=True,text=True,timeout=10)
    if run.returncode or not run.stdout:raise ValueError('Expected one complete function installFeature(ctx).')
    return run.stdout

def generate(reg):
    if (OUT/'seal.json').exists():return
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    pub=read(PUBLIC)
    def call(rep,dest,msg,phase,limit):return BASE.request(ledger,('table',TAG,rep),dest,msg,phase,limit)
    def library(rep):
        folder=OUT/rep
        f=folder/'library.json'
        if f.exists():return read(f)
        parts={};passed=set();history={}
        for name,(indices,tests,role) in MODULES.items():
            if name!='table' and 'table' not in parts:break
            msg=core.messages(ABI,dict(starter=pub['starter']['index.html'],role=role,requirements=[pub['requirements'][n-1]['description'] for n in indices],
                   existing_installers=list(parts),output='Write exactly function installFeature(ctx) { ... }. No Markdown or other files.'))
            history[name]=[]
            for i in range(2):
                dest=folder/'modules'/name/str(i);raw=''
                try:
                    raw=call(rep,dest/'call',msg,'build',4800)
                    fn=source(raw)
                    trial=observe(emit(pub,parts|{name:fn},dest/'page'))
                    good={k for k,v in trial['checks'].items() if v}
                    new=set(tests)&(good-passed)
                    kept=bool(new) and passed<=good and (name!='menu' or 'row' in good)
                    history[name].append(dict(public=trial,retained=kept,source_sha256=__import__('hashlib').sha256(fn.encode()).hexdigest()))
                    if kept:parts[name]=fn;passed=good;break
                    feedback=dict(current=trial,required=tests,previously_working=sorted(passed))
                except MISSING as exc:history[name].append(dict(missing=str(exc)));break
                except ERRORS as exc:feedback=str(exc);history[name].append(dict(rejected=feedback))
                msg+=[dict(role='assistant',content=raw),dict(role='user',content='Correct the complete installer. The public operations and observations were '+json.dumps(feedback)+' . Keep working checks. Return the entire named function only.')]
        lib=dict(status='valid' if {'table','menu'}<=parts.keys() else 'build_failed',functions=parts,checks=sorted(passed),history=history)
        core.save(f,lib);return read(f)
    def direct(n):
        dest=OUT/'direct'/str(n)
        msg=core.direct_messages(pub,n)
        try:
            raw=call('a',dest/'call',msg,'plan',6500)
            try:files=core.materialize_direct('table',pub,old.compact.base.parse_json(raw),dest/'page')
            except ERRORS:files=core.emit('table',pub['starter']|{'index.html':parse_document(raw)},dest/'page')
            value=dict(status='valid',page=str((dest/'page').relative_to(ROOT)),files=files)
        except MISSING as e:value=dict(status='missing',reason=str(e))
        except ERRORS as e:value=dict(status='invalid',reason=str(e)[:180])
        return dict(task=n,project='table',arm='direct',**value)
    def deploy(rep,lib):
        parts=lib['functions'];folder=OUT/rep
        if lib['status']!='valid':return []
        fixed=emit(pub,parts,folder/'fixed')
        def job(n):
            dest=folder/'plans'/str(n)
            names=list(parts)[1:]
            msg=core.messages('Select behavior modules needed for the current user request including its prerequisites. Return a JSON array of exact module names. The table selection module always loads.',dict(brief=core.prefix(pub,n),choices={k:MODULES[k][2] for k in names}))
            try:
                pick=json.loads(BASE.uncode(call(rep,dest/'call',msg,'plan',1400)).strip())
                if not isinstance(pick,list) or not all(isinstance(i,str) and i in names for i in pick):raise ValueError('Expected an array of registered module names')
                v=emit(pub,{k:t for k,t in parts.items() if k=='table' or k in pick},dest/'page')
            except MISSING as e:v=dict(status='missing',reason=str(e))
            except ERRORS as e:v=dict(status='invalid',reason=str(e)[:180])
            return [dict(project='table',task=n,arm=k,**x) for k,x in [('self-'+rep,v),('fixed-'+rep,fixed)]]
        with ThreadPoolExecutor(max_workers=3) as pool:return sum(pool.map(job,range(1,21)),[])
    with patch.multiple(BASE,OUT=OUT,END=END,template=settings),ThreadPoolExecutor(max_workers=4) as pool:
        futures={r:pool.submit(library,r) for r in ('a','b')}
        rows=list(pool.map(direct,range(1,21)))
        for r,fut in futures.items():rows+=deploy(r,fut.result())
    host=emit(pub,{},OUT/'starter')
    rows.extend(dict(project='table',task=n,arm='starter',**host) for n in range(1,21))
    core.save(OUT/'seal.json',dict(registration=sha(OUT/'registration.json'),libs={r:sha(OUT/r/'library.json') for r in ('a','b')},rows=rows))

def score():
    seal=read(OUT/'seal.json')
    assert seal['registration']==sha(OUT/'registration.json') and all(sha(OUT/r/'library.json')==h for r,h in seal['libs'].items())
    harness=browser.verify_contract('table');assert harness==read(PUBLIC.with_name('browser.json'))
    rows=browser.evaluate(seal['rows'],OUT,{'table':harness},3)
    core.save(HERE/'result.json',dict(registration=seal['registration'],seal=sha(OUT/'seal.json'),cost=ledger_read.totals(OUT/'budget.sqlite3'),
        libraries={r:{k:v for k,v in read(OUT/r/'library.json').items() if k!='functions'} for r in seal['libs']},
        rows=[{k:r.get(k) for k in ('arm','task','status','report_sha256')}|{'passed':False if r['status']=='invalid' else r.get('passed')} for r in rows]))

if __name__=='__main__':
    with browser.lock(OUT/'run.lock'):
        reg=register();generate(reg);score()
