"""Localize public table exceptions to their emitting handler before model repair."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import re
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,now,read,sha
from .. import run as parent

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/table-event-feedback-20261126'
CAP=1.50
TAGS=('gemma','qwen9')
REPS={t:('a','b') for t in TAGS}
PARENT=parent.OUT
build,public=parent.build,parent.public
EXPECTED={
    'selected':'Left-click the first body td on a fresh page; that exact element must have class selected.',
    'visible':'Right-click body cell; .menu must have a visible bounding box.',
    'row':'Choose Insert Row Above on body cell; tbody must gain exactly one tr.',
    'col':'Right-click first thead th; choose Insert Col Left; thead must gain one th.',
    'arrow':'ArrowRight on fresh page, no active or anchor; first header cell gets class selected.',
    'delete':'Click the first body cell, then Delete; its text must be empty.',
    'edit':'Double-click a body cell; that cell becomes editable.',
    'clipboard':'Select first body cell, Control+c, select second, Control+v; second has original text.',
    'resize':'Drag bottom edge of body cell down 36 pixels; its height must increase.',
    'reorder':'Context menu Select Row then drag first body row onto the second; order must reverse.'
}


def register():
    reg=read(PARENT/'registration.json')
    files=[Path(__file__),HERE/'PROTOCOL.md',PARENT/'registration.json',Path(parent.__file__),
           Path(public.__file__),Path(build.__file__),build.HERE/'host.js']
    files.extend(PARENT/t/r/'library.json' for t in TAGS for r in REPS[t])
    sources={str(f.relative_to(ROOT)):sha(f) for f in files}
    f=OUT/'registration.json'
    if not f.exists():
        balance=check_credits(CAP)
        assert balance['sufficient']
        core.save(f,dict(utc=now(),cap=CAP,balance=balance,deadline=parent.END.isoformat(),
            sources=sources,public=reg['public'],targets=reg['targets']))
    assert read(f)['sources']==sources
    return read(f)


def instrument(funcs):
    result={}
    for name,fn in funcs.items():
        args=build.ACTIONS[name][2]
        result[name]=(f'function {name}({args}) {{try {{return ({fn})({args});}} catch(err) {{'
            f'throw new Error("[owner={name}] "+({("event?.type" if "event" in args.split(",") else "null")} || "state update")+" "+err.message);}}}}')
    return result


def prepare(tag,rep,pub,ledger):
    root=OUT/tag/rep
    f=root/'library.json'
    if f.exists():return read(f)
    original=read(PARENT/tag/rep/'library.json')
    funcs=dict(original['functions'])
    assert set(funcs)==set(build.ACTIONS)
    def observe(fs,stage):
        page=build.page(pub,instrument(fs),build.OPTIONS,root/'public'/stage)
        return public.measure(OUT,page)
    checks=observe(funcs,'initial')
    history=[checks]
    def passes(o):return {k for k,v in o['checks'].items() if v}
    def errors(o):
        return set(o['errors'])
    def owners(o):
        return [n for n in build.ACTIONS if any('[owner='+n+']' in e for e in o['errors'])]
    def gain(o,n):
        # Name-tagged exceptions can expose previously unreachable follow-on paths.
        prior,after=errors(o),errors(n)
        return passes(o)<=passes(n) and (prior>=after or len(after)<len(prior)) and (passes(o)<passes(n) or len(after)<len(prior))
    for turn in ('first','second'):
        start=checks
        failed=[k for k,v in checks['checks'].items() if not v]
        names=list(dict.fromkeys(owners(checks)+[n for k in failed for n in public.OWNERS[k]]))
        proposals={}
        def propose(name):
            relevant=[k for k in failed if name in public.OWNERS[k]]
            guidance={'event_dispatch':('The host supplies null cell on hide, outside-table moves and releases. ctx.active, '
                'ctx.target (last contextmenu cell), ctx.anchor may be null even when ctx.selected is nonempty. '
                'Document calls rangePointer, resizeCells and reorderCells on all mouse and drag phases. '
                'Each callback must ignore unrelated phases and idle mouse moves. A plain click must select the clicked cell '
                'with ctx.select([cell], cell, cell). markSelection receives an iterable of cells; ignore null elements. '
                'The app owns the menu and sets native hidden on mismatched items. Operate on the existing DOM nodes.'),
                'exceptions':checks['errors'], 'failing_public_examples':{k:EXPECTED[k] for k in relevant},
                'public_successes':sorted(passes(checks)), 'sibling_interfaces':{
                    k:build.ACTIONS[k][2] for k in ('cellClick','markSelection','menuVisibility','editingKeys','navigate')}}
            msgs=build.messages(name,pub,funcs[name],guidance)
            try:
                raw=parent.compact.base.request(ledger,('table',tag,rep),root/'calls'/turn/name,msgs,'build',3200)
                return name,build.extract(name,raw)
            except (ValueError,*parent.typed.MISSING):return name,None
        with ThreadPoolExecutor(max_workers=2) as pool:
            proposals={k:v for k,v in pool.map(propose,names) if v}
        # Dependencies may require simultaneous changes. Predeclared order: all first, then individuals.
        for label,mods in [(turn+'-joint',proposals),*((turn+'-'+n,{n:fn}) for n,fn in proposals.items())]:
            if not mods or all(funcs[n]==fn for n,fn in mods.items()):continue
            updated={**funcs,**mods}
            trial=observe(updated,label)
            keep=gain(checks,trial)
            history.append(dict(name=label,retained=keep,**trial))
            if keep:funcs,checks=updated,trial
        if not proposals or (not errors(checks) and len(passes(checks))==len(public.OWNERS)):break
    plain=public.measure(OUT,build.page(pub,funcs,build.OPTIONS,root/'admission'))
    history.append(dict(name='unwrapped-admission',**plain))
    status='valid' if public.admitted(plain) else 'build_failed'
    core.save(f,dict(tag=tag,rep=rep,status=status,reason='' if status=='valid' else 'Public interaction failed',
                     public=history,functions=funcs))
    print('prepared',tag,rep,status,sorted(passes(plain)),flush=True)
    return read(f)


def main():
    reg=register()
    with patch.multiple(parent,OUT=OUT,RESULT=HERE/'result.json',CAP=CAP,TAGS=TAGS,REPS=REPS,prepare=prepare):
        parent.generate(reg)
        parent.score(reg)


if __name__=='__main__':
    with browser.lock(OUT/'.run.lock'):main()
