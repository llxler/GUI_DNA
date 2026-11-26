"""Incrementally repair the behavior of two original, publicly admitted Qwen libraries."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from .. import run as projection
from ...state_reducers import run as reducers
from ...state_reducers.typed_events.run import observe
from ...interaction_modules import run as prior


HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/table-interaction-repair-20261126pm'
START=ROOT/'artifacts/table-typed-binding-20261126/qwen9'
CAP=.60
STEPS=[
 ('core','markSelection',['selection','arrow','wrap','range']),
 ('core','cellClick',['selection','edit']),
 ('menu','rowAction',['row']),('menu','columnAction',['column']),
 ('keys','navigate',['arrow','wrap']),('keys','editCell',['edit']),('keys','editingKeys',['clear','edit']),
 ('clipboard','clipboardKeys',['clipboard']),('range','rangePointer',['range']),
 ('resize','resizeCells',['resize']),('reorder','selectGroup',['reorder']),('reorder','reorderCells',['reorder']),
]
CHECKS = {
 'selection':'Click two different body cells in sequence; only the second remains styled selected.',
 'row':'Open a body context menu and click Insert Row Below; the body row count increases, the menu is hidden.',
 'column':'Insert Col Left from a header context menu; header and all body rows gain one actual cell.',
 'arrow':'On a fresh table, first ArrowRight selects top-left header, then ArrowDown selects first body cell.',
 'wrap':'Click last header cell; Tab moves to the first cell on the next row; Shift+Tab returns to that header.',
 'edit':'Double click a body cell to edit; Escape leaves that cell selected and ends editing.',
 'clear':'Click a nonempty cell and press Delete; the selected cell becomes empty.',
 'clipboard':'Select a cell, Ctrl+C; select a different cell, Ctrl+V. Its displayed value equals the source.',
 'range':'Drag from interior of a body cell to another one on the following row; select the whole rectangle only.',
 'resize':'Drag the bottom cell edge downward; the row becomes visibly taller.',
 'reorder':'Select a row with its context action, then move it below the other body row; verify actual data order.',
}

def register():
    f=OUT/'registration.json'
    files=[Path(__file__),HERE/'PROTOCOL.md',Path(projection.__file__),Path(projection.build.__file__),
           projection.build.HERE/'host.js',prior.HERE/'probe.py',prior.PUBLIC,prior.HERE/'result.json',
           *(START/rep/'library.json' for rep in 'ab'),projection.HERE/'typed-result.json']
    sums={str(p.relative_to(ROOT)):sha(p) for p in files}
    if not f.exists():
        b=check_credits(CAP);assert b['sufficient']
        core.save(f,dict(utc=now(),cap=CAP,balance=b,deadline=prior.END.isoformat(),seeds=[2026112651,2026112652],sources=sums))
    assert read(f)['sources']==sums

def passed(observation):return {k for k,v in observation['checks'].items() if v}

def build(rep, ledger, pub):
    folder=OUT/rep;dest=folder/'library.json'
    if dest.exists():return read(dest)
    old=read(START/rep/'library.json');assert old['status']=='valid'
    funcs=dict(old['functions']);binding=old['binding'];options=list(old['options']);history=[]
    def check(label,fs,opts,bnd):
        output=folder/'public'/label
        if not (output/'observation.json').exists():
            page=projection.page(pub,fs,opts,bnd,output/'page')
            core.save(output/'observation.json',observe(page))
        return read(output/'observation.json')
    best=check('original',funcs,options,binding)
    full=binding|{'selector':'th,td'}
    trial=check('all-cells',funcs,options,full)
    retain=passed(best)<=passed(trial)
    history.append(dict(stage='all-cells',before=best,after=trial,retained=retain))
    if retain:best=trial;binding=full
    for group,name,checks in STEPS:
        enabled=list(dict.fromkeys(options+([] if group=='core' else [group])))
        if enabled!=options:
            trial=check('enable-'+name,funcs,enabled,binding)
            keep=passed(best)<passed(trial)
            history.append(dict(stage='enable-'+name,checks=trial,retained=keep))
            if keep:options=enabled;best=trial
        if set(checks)<=passed(best):continue
        spec=projection.build.ACTIONS[name]
        user=dict(requested_function=name,arguments=spec[2],responsibility=spec[4],
                  relevant_public_requirements=[pub['requirements'][n-1]['description'] for n in spec[3]],
                  previous_function=funcs[name],public_observation=best,
                  public_sequences={k:CHECKS[k] for k in checks},
                  outputs='Return only the full named function with exactly the supplied parameters.')
        abi='''Repair one browser DOM operation in your own existing library. Use actual HTMLElement objects. ctx.table is HTMLTableElement; ctx.menu is a div.
ctx.selected is a Set of real TH and TD, ctx.active and ctx.anchor are real cells or null. ctx.select(iterableOfCells,activeCell,anchorCell) updates the selection.
event is the actual browser event (shiftKey,ctrlKey,metaKey,key,type,buttons). cell is a DOM cell, a row coordinate is cell.parentElement.rowIndex and column coordinate is cell.cellIndex.
ctx.table.rows includes header row 0. Do not install listeners; the caller already dispatches events. Preserve the features already working. No external helpers.
Editing uses native contentEditable, selection class comes from ctx.selected. Use actual event.key, unmodified for arrows and case-insensitive for Ctrl+C/V.'''
        try:
            txt=prior.BASE.request(ledger,('table','qwen9',rep),folder/'calls'/name,core.messages(abi,user),'build',3600)
            changed=funcs|{name:projection.build.extract(name,txt)}
            trial=check('repair-'+name,changed,enabled,binding)
            keep=passed(best)<=passed(trial) and bool((passed(trial)-passed(best))&set(checks))
            history.append(dict(stage='repair-'+name,checks=trial,retained=keep))
            if keep:funcs=changed;options=enabled;best=trial
        except (prior.MISSING+prior.ERRORS) as e:history.append(dict(stage='repair-'+name,error=str(e),retained=False))
    status='valid' if {'selection','row'}<=passed(best) else 'build_failed'
    core.save(dest,dict(status=status,parts=funcs,options=options,binding=binding,checks=sorted(passed(best)),history=history))
    return read(dest)

def generate():
    register();seal=OUT/'seal.json'
    if seal.exists():return
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP);pub=read(prior.PUBLIC)
    def settings(_,tag,stage):return prior.old.settings('table',tag,stage)|{'seed':2026112651}
    def run(rep):
        lib=build(rep,ledger,pub);folder=OUT/rep
        if lib['status']!='valid':return []
        opt=lib['options'];parts=lib['parts'];bind=lib['binding']
        fixed=projection.page(pub,parts,opt,bind,folder/'fixed')
        menus=list(dict.fromkeys([tuple(opt),(),*[tuple(opt[:i]) for i in range(1,len(opt))],*[(k,) for k in opt]]))
        def target(n):
            dest=folder/'plans'/str(n)
            msg=core.messages('Choose the feature profile needed by the newest public requirement and its prerequisites. Return a single decimal integer.',
                              dict(brief=core.prefix(pub,n),profiles=[{'index':i,'enabled':list(x)} for i,x in enumerate(menus)]))
            try:
                raw=prior.BASE.uncode(prior.BASE.request(ledger,('table','qwen9',rep),dest/'call',msg,'plan',1500)).strip()
                if not raw.isdigit() or int(raw)>=len(menus):raise ValueError('Missing valid profile index')
                v=projection.page(pub,parts,list(menus[int(raw)]),bind,dest/'page')
            except prior.MISSING as e:v=dict(status='missing',reason=str(e))
            except ValueError as e:v=dict(status='invalid',reason=str(e))
            return [dict(project='table',task=n,arm=k,**val) for k,val in [('self-'+rep,v),('fixed-'+rep,fixed)]]
        with ThreadPoolExecutor(max_workers=2) as pool:return sum(pool.map(target,range(1,21)),[])
    with patch.multiple(prior.BASE,OUT=OUT,END=prior.END,template=settings),ThreadPoolExecutor(max_workers=2) as pool:
        rows=sum(pool.map(run,'ab'),[])
    lib=read(OUT/'a/library.json')
    host=projection.page(pub,{},[],lib['binding'],OUT/'starter')
    rows.extend(dict(project='table',task=n,arm='starter',**host) for n in range(1,21))
    core.save(seal,dict(registration=sha(OUT/'registration.json'),libs={r:sha(OUT/r/'library.json') for r in 'ab'},rows=rows))

if __name__=='__main__':
    with browser.lock(OUT/'run.lock'):
        generate()
        with patch.multiple(reducers,OUT=OUT,HERE=HERE):reducers.score()
