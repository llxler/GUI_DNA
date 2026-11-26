"""Repair each owning source with unique, executable edits and trace the new DOM identity."""
import json
from pathlib import Path
import subprocess
from unittest.mock import patch

from scripts.check_openrouter_credits import check_credits
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,now,read,sha
from .. import run as prior
from .probe import observe

docs=prior.docs
HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/file-explorer-entry-identity-20261126pm'
CAP=.75
SPEC=prior.SPEC|{'menu_child':'Right click a newly created directory; use Add File. Its content gains a file.',
                 'copy':'Create and copy a file via its menu, create a directory, paste via that menu; its child has the original content.'}
GROUPS=prior.GROUPS|{'menu':('delete','rename','menu_child','copy')}
OLD_OUT=prior.OUT

def apply_changes(text,reply):
    plan=json.loads(docs.ORIG.base.uncode(reply).strip())
    edits=plan['edits']
    if not isinstance(edits,list) or not 1<=len(edits)<=6:raise ValueError('Use one to six unique literal edits')
    for e in edits:
        old,new=e['before'],e['after']
        if not isinstance(old,str) or not old or not isinstance(new,str) or old==new or text.count(old)!=1:
            raise ValueError('The before text must match exactly once and change')
        text=text.replace(old,new,1)
    return text

def register():
    f=OUT/'registration.json'
    files=[Path(__file__),HERE/'PROTOCOL.md',HERE/'probe.py',Path(prior.__file__),Path(docs.__file__),
           OLD_OUT/'seal.json',OLD_OUT/'registration.json',docs.HERE/'controls.json',docs.ORIG.OUT/'public.json',docs.ORIG.OUT/'browser.json']
    files += [OLD_OUT/t/r/'library.json' for t in prior.TAGS for r in 'ab']
    sums={str(p.relative_to(ROOT)):sha(p) for p in files}
    if not f.exists():
        balance=check_credits(CAP);assert balance['sufficient']
        core.save(f,dict(utc=now(),deadline=prior.END.isoformat(),cap=CAP,balance=balance,sources=sums,
                         targets=list(range(1,21)),models=read(OLD_OUT/'registration.json')['models'],
                         seeds={'a':2026112711,'b':2026112712}))
    assert read(f)['sources']==sums
    return read(f)

def build(tag,rep,ledger,pub):
    folder=OUT/tag/rep;f=folder/'library.json'
    if f.exists():return read(f)
    base=read(OLD_OUT/tag/rep/'library.json')
    parts=dict(base['parts']);history=[]
    def check(v,where):
        d=folder/'public'/where
        if not (d/'observation.json').exists():
            core.save(d/'observation.json',observe(OUT,docs.emit(pub,v,d/'page')))
        return read(d/'observation.json')
    best=check(parts,'initial');initial=best
    for k,goals in GROUPS.items():
        for attempt in range(2):
            needed=set(goals)-prior.passed(best)
            if not needed:break
            from_core=k=='core';has=k in parts
            old=(parts[k] if from_core else parts[k]['script']) if has else ''
            form=('Return JSON {"edits":[{"before":"unique exact substring of current_source","after":"replacement source"}]}. '
                  'Edit only the code that owns the broken behavior. Prefer one small edit. Use exact spaces and quotes from the provided source.'
                  if has else 'Return one complete JS function installFeature(root) implementing the missing behavior.')
            req=core.messages('Repair your existing browser file manager. Trace the real event target, public DOM id and selection. '
                'Use the actual initially populated tree, keep responsive UI, public classes and every working interaction. '
                'The entry created by the user may follow other nested entries. '+form,
                dict(component=k,requirements=[pub['requirements'][i-1]['description'] for i in docs.MODULES[k]],
                     current_source=old or None,core_document=None if from_core else parts['core'],
                     public_goals={n:SPEC[n] for n in sorted(needed)},public_observations=best,
                     previous_attempt=history[-1].get('feedback') if attempt else None))
            try:
                raw=docs.ORIG.base.request(ledger,('table',tag,rep),folder/'calls'/k/str(attempt),req,'build',6000)
                if has:
                    s=apply_changes(old,raw)
                    if from_core:value=docs.parse_document(s)
                    else:
                        proc=subprocess.run(['node','--check'],input=s,text=True,capture_output=True,timeout=8)
                        if proc.returncode:raise ValueError('Edited installer is invalid JavaScript')
                        value=parts[k]|{'script':s}
                else:value=docs.installer(raw)
                new=parts|{k:value};label=k+'-'+str(attempt);after=check(new,label)
                keep=prior.passed(best)<=prior.passed(after) and bool((prior.passed(after)-prior.passed(best))&needed)
                admitted=None
                if keep:
                    page=docs.emit(pub,new,folder/'admission'/label)
                    admitted=docs.dom.exercise(page,[n for n in new if n!='core'])
                    keep=admitted['admitted']
                history.append(dict(group=k,attempt=attempt,retained=keep,feedback=after,original_public=admitted))
                if keep:parts=new;best=after
            except docs.dom.action.typed.MISSING as exc:
                history.append(dict(group=k,attempt=attempt,retained=False,missing=str(exc)));break
            except (ValueError,IndexError,AttributeError,TypeError,KeyError) as exc:
                history.append(dict(group=k,attempt=attempt,retained=False,feedback={'error':str(exc)[:180]}))
    core.save(f,dict(parts=parts,origin=sha(OLD_OUT/tag/rep/'library.json'),before=initial,after=best,history=history))
    print('identity',tag,rep,sorted(prior.passed(initial)),sorted(prior.passed(best)),flush=True)
    return read(f)

if __name__=='__main__':
    with browser.lock(OUT/'run.lock'),patch.multiple(prior,OUT=OUT,CAP=CAP,HERE=HERE,build=build):
        reg=register();prior.generate(reg);prior.score(reg)
