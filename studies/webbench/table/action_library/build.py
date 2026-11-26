"""Compile model-written actions against the declared table event interface."""
from itertools import combinations
import json
from pathlib import Path
import re
import subprocess

from studies.public_library_transfer import browser,core
from studies.public_library_transfer.self_refinement.todomvc.event_modules import modules
from studies.study_io import ROOT
from studies.webbench.compact_planning import run as compact

HERE=Path(__file__).resolve().parent
# Public selector and module names come from the starter and numbered public requirements.
ACTIONS={
 'markSelection':('table','core','ctx,cells,active,anchor',(4,9),'Update ctx.selected (Set), ctx.active, ctx.anchor and visible selected classes. cells is an iterable of th/td; preserve supplied anchor. Add a visible selection style.'),
 'cellClick':('table','core','ctx,event,cell',(4,9,11),'Handle an ordinary, shift or already-selected click using ctx.select. Set contentEditable when appropriate.'),
 'menuVisibility':('menu','menu','ctx,event,cell,mode',(1,),'Host has created a .menu div with items. For show, prevent native menu, set hidden=false AND visible display, style size/absolute position at event coordinates. For hide, reverse visibility.'),
 'rowAction':('menu','menu','ctx,event,cell,label',(2,),'Perform exactly the named Insert Row Above, Insert Row Below or Delete Row on the clicked body row. cell is the original right-click td.'),
 'columnAction':('menu','menu','ctx,event,cell,label',(3,),'Perform the named Insert Col Left, Insert Col Right or Delete Col on every table row, preserving th/td.'),
 'selectGroup':('menu','menu','ctx,event,cell,label',(7,),'Select the group named by label using ctx.select.'),
 'filterColumn':('menu','menu','ctx,event,cell,label',(19,),'Handle the user filtering this header column; items and listeners already exist.'),
 'sortColumn':('menu','menu','ctx,event,cell,label',(20,),'Handle sorting this header column; items and listeners already exist.'),
 'navigate':('key','keys','ctx,event',(5,6,9),'Use the original full table including header. Handle arrows, Shift+Arrow and Tab, respecting editing.'),
 'editingKeys':('key','keys','ctx,event',(7,8,12),'Handle Delete, Backspace, Escape, Enter, Ctrl/Cmd+A. Start/end editing or change selected cells as the public brief requires.'),
 'editCell':('table','core','ctx,event,cell',(11,),'Handle double-click using ctx.select and contentEditable.'),
 'clipboardKeys':('key','clipboard','ctx,event',(13,14),'Handle Ctrl/Cmd+C and V. Use ctx for clipboard state.'),
 'rangePointer':('mouse','range','ctx,event,cell',(10,),'Handle only left-button cell range dragging, use ctx.select. Do not claim an ordinary click.'),
 'resizeCells':('layout','resize','ctx,event,cell',(15,16),'Handle row/column edge resize. cell may be null at document-level moves or release. Ignore non-edge starts.'),
 'reorderCells':('drag','reorder','ctx,event,cell',(17,18),'Handle selected row/column reorder. Ignore other events and guard null targets.'),
}
OPTIONS=('menu','keys','clipboard','range','resize','reorder')
PROFILES=[list(OPTIONS), [], ['menu'], ['menu','keys'], ['menu','keys','range'], ['menu','keys','range','clipboard'],
          ['menu','keys','range','clipboard','resize'], ['keys'], ['keys','range'], ['menu','resize','reorder']]
CONTRACT='''ctx.table is the starter HTMLTableElement. ctx.menu is a single pre-mounted div. ctx.active and ctx.anchor are cells or null.
ctx.selected is a Set of elements. ctx.target is the last right-clicked cell. ctx.select(cells, active, anchor) calls the shared model-written markSelection.
You may store new state on ctx. Only implement the assigned function. The host already binds all listed event listeners and invokes you.
Never register sibling handlers, initialize the application, import modules, or identify task numbers. Return one complete named synchronous JS function using the exact signature.'''


def messages(name,pub,previous=None,feedback=None):
    _,_,args,nums,role=ACTIONS[name]
    msg=core.messages(CONTRACT,dict(signature=f'function {name}({args})',role=role,
        starter=pub['starter']['index.html'],requirements=[pub['requirements'][i-1]['description'] for i in nums]))
    if feedback is not None:
        msg+=[dict(role='assistant',content=previous or ''),dict(role='user',content='Return the complete corrected function. Public observation: '+str(feedback))]
    return msg


def extract(name,raw):
    src=modules.js_block(raw)
    src=re.sub(r'^\s*export\s+(?:default\s+)?(?=function\b)','',src)
    run=subprocess.run(['node',str(modules.HERE/'function.cjs'),str(modules.ACORN)],
        input=json.dumps(dict(name=name,arity=len(ACTIONS[name][2].split(',')),text=src)),text=True,capture_output=True,timeout=10)
    if run.returncode or not run.stdout.strip():raise ValueError('Missing complete named function with the registered arity')
    return run.stdout


def page(pub,funcs,profile,folder):
    files=dict(pub['starter'])
    enabled={k:v for k,v in funcs.items() if ACTIONS[k][1]=='core' or ACTIONS[k][1] in profile}
    imports=[]
    for module in dict.fromkeys(x[0] for x in ACTIONS.values()):
        names=[k for k in enabled if ACTIONS[k][0]==module]
        files[f'common/{module}.js']='\n'.join('export '+enabled[k] for k in names)
        if names:imports.append('import {'+','.join(names)+'} from "./common/'+module+'.js";')
    files['index.js']+='\n'+'\n'.join(imports)+'\nconst handlers={'+','.join(enabled)+'};\n'+(HERE/'host.js').read_text()
    tree=core.emit('table',files,folder)
    return dict(status='valid',page=str(folder.relative_to(ROOT)),files=tree)
