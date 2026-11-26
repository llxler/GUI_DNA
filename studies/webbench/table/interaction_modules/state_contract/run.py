"""Rebuild event modules with explicit state transitions and two supported install conventions."""
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from scripts.check_openrouter_credits import check_credits
from studies.public_library_transfer import core,browser
from studies.study_io import ROOT,read,sha,now
from .. import run as parent

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/table-state-contract-20261126pm'
CAP=1.00
SEED=2026112621
ABI=parent.ABI+"""
The host does not implement a selection algorithm. Your first module must assign ctx.select = function(cells,active,anchor){...};
a returned object {select: function(cells,active,anchor){...}} is also accepted. Other modules call ctx.select(cells,active,anchor).
A plain click on B2 followed by C2 must leave ONLY C2 in ctx.selected, active=C2 and anchor=C2. Remove the previous CSS class.
Use a real Set identity or replace it consistently. A plain click does not accumulate selected cells; shift and drag extend.
Write just function installFeature(ctx), with no helper outside. All installed handlers operate on the same live ctx and table.
"""
OBS=parent.observe
EMIT=parent.emit
def emit(pub,parts,folder):
    if not parts:return EMIT(pub,parts,folder)
    files=dict(pub['starter'])
    for name,src in parts.items():files['common/'+name+'.js']='export '+src
    imports=['import {installFeature as f'+str(i)+'} from "./common/'+name+'.js";' for i,name in enumerate(parts)]
    files['index.js']+='\n'+'\n'.join(imports)+'\nconst ctx={table:document.querySelector(".table"),selected:new Set(),active:null,anchor:null};\n'
    files['index.js']+='\n'.join(f'{{const exposed=f{i}(ctx); if(exposed && typeof exposed.select==="function") ctx.select=exposed.select.bind(exposed);}}' for i in range(len(parts)))
    return dict(status='valid',page=str(folder.relative_to(ROOT)),files=core.emit('table',files,folder))

def observe(candidate):
    obs=OBS(candidate)
    result=subprocess.run([sys.executable,'-m','studies.webbench.table.interaction_modules.state_contract.trace',candidate['page']],capture_output=True,text=True,timeout=20)
    if result.returncode==0:obs['trace']=result.stdout.strip()[:700]
    return obs

def register():
    files=[Path(__file__),HERE/'trace.py',HERE/'PROTOCOL.md',Path(parent.__file__),HERE.parent/'probe.py',parent.PUBLIC]
    f=OUT/'registration.json';hashes={str(p.relative_to(ROOT)):sha(p) for p in files}
    if not f.exists():
        bal=check_credits(CAP);assert bal['sufficient']
        core.save(f,dict(utc=now(),balance=bal,cap=CAP,deadline=parent.END.isoformat(),seeds=[SEED,SEED+1],sources=hashes,model=parent.old.settings('table',parent.TAG,'plan')['model']))
    assert read(f)['sources']==hashes
    return read(f)
if __name__=='__main__':
    with browser.lock(OUT/'run.lock'),patch.multiple(parent,OUT=OUT,HERE=HERE,ABI=ABI,emit=emit,observe=observe,CAP=CAP,SEED=SEED):
        reg=register();parent.generate(reg);parent.score()
