"""Collect pure state-transition modules from two independently seeded Qwen builds."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import re
import subprocess
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,now,read,sha
from ..interaction_modules import run as prior
from ..interaction_modules.state_contract import run as state

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/table-pure-state-20261126pm'
CAP=1.10
GROUPS={
 'select':('table',['click'],[4],'Ordinary click replaces old selection with cell; update active and anchor.'),
 'menu':('menu',['context','dismiss','item'],[1,2,3,7,19,20],'Context on header or body sets target and menu to exact title case labels in the brief. Dismiss or activating an item hides the menu. Do not modify the grid here.'),
 'rows':('rows',['item'],[2],'For an applicable row menu label at event.cell, insert/delete a body row. Preserve other cells. Clear the menu.'),
 'columns':('columns',['item'],[3],'For an applicable column menu label insert/delete a column including header and all body rows. Preserve other cells.'),
 'keys':('key',['key'],[5,6,7,9],'Arrow keys including shift, Tab, Shift+Tab, ctrl+a; coordinate bounds include the header. Update active, anchor and selection. Ignore other keys.'),
 'edit':('edit',['double','click','key'],[8,11,12],'Double-click or Enter starts editing. Escape ends editing but retains selection. Delete or Backspace outside editing clears all selected cells.'),
 'copy':('clipboard',['key'],[13,14],'When mod and c/v case insensitive, copy actual cell values into clipboard rect or paste at current cell. Extend grid when needed.'),
 'range':('mouse',['drag'],[9,10],'Interior drag selects all coordinates in rectangle between start.cell and event.cell inclusive. Ignore edge drags.'),
 'size':('layout',['drag'],[15,16],'Near a bottom/right edge resize the original row/column using pixel deltas and public minimums.') }
CHECKS={'select':['selection'],'menu':[],'rows':['row'],'columns':['column'],'keys':['arrow','wrap'],'edit':['clear','edit'],'copy':['clipboard'],'range':['range'],'size':['resize']}
CONTRACT="""Write only function transition(state,event){...}. This is data transformation only. No DOM, selectors, external functions, event listeners or imports.
state.grid is an array of arrays of cell text (row 0 is the header). Coordinates are [row,col] integer pairs, zero based, including row 0.
state.active,state.anchor,state.editing,state.target are coordinate pairs or null; state.selected is an ARRAY of coordinate pairs, not a Set. state.menu is an array of exact label strings.
state.clipboard is a matrix of strings; rowHeights/colWidths are arrays of pixel sizes. event.kind,cell,key,mod,shift,label,start,dx,dy use these exact names.
Return a shallow patch object with changed state fields only. You may modify the supplied state copy but must RETURN the affected fields. Return {} if an event is unrelated.
The browser driver renders returned state. A menu is drawn only for labels you return; no operation logic is implemented for you."""
def register():
    f=OUT/'registration.json'
    sources=[Path(__file__),HERE/'host.js',HERE/'units.cjs',HERE/'PROTOCOL.md',prior.PUBLIC,prior.HERE/'probe.py',prior.HERE/'result.json',state.HERE/'PROTOCOL.md']
    sums={str(p.relative_to(ROOT)):sha(p) for p in sources}
    if not f.exists():
        bal=check_credits(CAP);assert bal['sufficient']
        core.save(f,dict(utc=now(),balance=bal,cap=CAP,deadline=prior.END.isoformat(),sources=sums,seeds=[2026112631,2026112632],model=prior.old.settings('table','qwen9','plan')['model']))
    assert read(f)['sources']==sums

def page(pub,parts,folder):
    files=dict(pub['starter']);imports=[];handlers=[]
    for i,(name,src) in enumerate(parts.items()):
        module,events,_,_=GROUPS[name]
        files[f'common/{module}.js']='export '+src
        imports.append(f'import {{transition as op{i}}} from "./common/{module}.js";')
        handlers.append('['+json.dumps(events)+f',op{i}]')
    files['index.js']+='\n'+'\n'.join(imports)+'\nconst handlers=['+','.join(handlers)+'];\n'+(HERE/'host.js').read_text()
    return dict(status='valid',page=str(folder.relative_to(ROOT)),files=core.emit('table',files,folder))

def extract(raw):
    txt=prior.BASE.uncode(raw).strip()
    fence=re.search(r'```(?:javascript|js)?\s*\n([\s\S]*?)```',txt,re.I)
    txt=re.sub(r'^\s*export\s+(?:default\s+)?','',fence[1] if fence else txt)
    m=prior.old.build.modules
    x=subprocess.run(['node',str(m.HERE/'function.cjs'),str(m.ACORN)],input=json.dumps(dict(name='transition',arity=2,text=txt)),text=True,capture_output=True,timeout=10)
    if x.returncode or not x.stdout:raise ValueError('Return one complete named function transition(state,event)')
    return x.stdout

def completed(p):return {k for k,v in p.get('checks',{}).items() if v}
def prepare(rep,ledger,pub):
    folder=OUT/rep;f=folder/'library.json'
    if f.exists():return read(f)
    parts={};last=set();history={}
    for name,(_,events,req,role) in GROUPS.items():
        history[name]=[]
        msg=core.messages(CONTRACT,dict(role=role,events=events,requirements=[pub['requirements'][i-1]['description'] for i in req],
            sample_state=dict(grid=[['Name','Value'],['Apple','2']],selected=[[1,0]],active=[1,0],anchor=[1,0],editing=None,target=None,menu=[],clipboard=[],rowHeights=[],colWidths=[]),
            output='Use the exact named function and return changed fields.'))
        for i in range(2):
            dest=folder/'modules'/name/str(i);raw=''
            try:
                raw=prior.BASE.request(ledger,('table','qwen9',rep),dest/'call',msg,'build',3500)
                fn=extract(raw)
                u=subprocess.run(['node',str(HERE/'units.cjs')],input=json.dumps(dict(group=name,fn=fn)),text=True,capture_output=True,timeout=6)
                if u.returncode:raise ValueError('State example failed to run')
                units=json.loads(u.stdout);unitpass=all(x['passed'] for x in units.values())
                if unitpass:
                    candidate=page(pub,parts|{name:fn},dest/'page');obs=prior.observe(candidate);new=completed(obs)
                    keep=last<=new and (name=='menu' or bool(set(CHECKS[name]) & (new-last)))
                else:obs={};new=set();keep=False
                feedback=dict(units=units,browser=obs,previous_checks=sorted(last),expected_group=CHECKS[name])
                history[name].append(dict(retained=keep,**feedback))
                if keep:parts[name]=fn;last=new;break
            except prior.MISSING as e:history[name].append(dict(missing=str(e)));break
            except (ValueError,TypeError,KeyError,subprocess.TimeoutExpired) as e:feedback=str(e)[:180];history[name].append(dict(error=feedback))
            msg += [dict(role='assistant',content=raw),dict(role='user',content='Please correct your complete state transition. Public interaction report: '+json.dumps(feedback)[:4700])]
    status='valid' if {'select','menu','rows'}<=parts.keys() and {'selection','row'}<=last else 'build_failed'
    core.save(f,dict(status=status,parts=parts,checks=sorted(last),history=history))
    return read(f)

def generate():
    reg=register();f=OUT/'seal.json'
    if f.exists():return
    pub=read(prior.PUBLIC);ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    def settings(_,tag,phase):return prior.old.settings('table',tag,phase)|{'seed':2026112631}
    def run(rep):
        lib=prepare(rep,ledger,pub);folder=OUT/rep
        if lib['status']!='valid':return []
        parts=lib['parts'];fixed=page(pub,parts,folder/'fixed')
        optional=[k for k in parts if k not in ('select','menu','rows')]
        def task(n):
            options=[optional,[],*[[k] for k in optional],*[optional[:i] for i in range(2,len(optional))]]
            options=list(dict.fromkeys(map(tuple,options)))
            msg=core.messages('Select the single profile whose publicly verified behaviors implement the newest requirement and its prerequisites. Reply solely with the integer profile index.',dict(brief=core.prefix(pub,n),always_present=['select','menu','rows'],
                    profiles=[{'index':i,'optional_modules':o} for i,o in enumerate(options)],modules={k:GROUPS[k][3] for k in optional}))
            dest=folder/'plans'/str(n)
            try:
                raw=prior.BASE.uncode(prior.BASE.request(ledger,('table','qwen9',rep),dest/'call',msg,'plan',1300)).strip()
                if not raw.isdigit() or int(raw)>=len(options):raise ValueError('Expected a legal profile index')
                keep=set(options[int(raw)])|{'select','menu','rows'}
                v=page(pub,{k:z for k,z in parts.items() if k in keep},dest/'page')
            except prior.MISSING as e:v=dict(status='missing',reason=str(e))
            except ValueError as e:v=dict(status='invalid',reason=str(e))
            return [dict(project='table',task=n,arm=k,**data) for k,data in [('self-'+rep,v),('fixed-'+rep,fixed)]]
        with ThreadPoolExecutor(max_workers=2) as pool:return sum(pool.map(task,range(1,21)),[])
    with patch.multiple(prior.BASE,OUT=OUT,END=prior.END,template=settings),ThreadPoolExecutor(max_workers=2) as pool:rows=sum(pool.map(run,'ab'),[])
    host=page(pub,{},OUT/'starter')
    rows.extend(dict(project='table',task=n,arm='starter',**host) for n in range(1,21))
    core.save(f,dict(registration=sha(OUT/'registration.json'),libs={r:sha(OUT/r/'library.json') for r in 'ab'},rows=rows))

def score():
    seal=read(OUT/'seal.json');assert all(sha(OUT/r/'library.json')==h for r,h in seal['libs'].items())
    proto=browser.verify_contract('table');assert proto==read(prior.PUBLIC.with_name('browser.json'))
    rows=browser.evaluate(seal['rows'],OUT,{'table':proto},3)
    result=[{k:r.get(k) for k in ('task','arm','status','report_sha256')}|{'passed':False if r['status']=='invalid' else r.get('passed')} for r in rows]
    result.extend(r for r in read(prior.HERE/'result.json')['rows'] if r['arm']=='direct')
    core.save(HERE/'result.json',dict(registration=seal['registration'],seal=sha(OUT/'seal.json'),cost=ledger_read.totals(OUT/'budget.sqlite3'),direct_source=sha(prior.HERE/'result.json'),
             libraries={r:{k:v for k,v in read(OUT/r/'library.json').items() if k!='parts'} for r in seal['libs']},rows=result))

if __name__=='__main__':
    with browser.lock(OUT/'run.lock'):generate();score()
