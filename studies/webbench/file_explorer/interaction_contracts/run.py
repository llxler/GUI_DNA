"""Repair an existing file-explorer library using observable state across actions."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import re
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from ..document_library import run as docs
from .probe import observe

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/file-explorer-interactions-20261126pm'
CAP=1.40
END=datetime(2026,11,26,13,55,tzinfo=timezone.utc)
GROUPS={
    'core': ('insert','nest','focus'),
    'menu': ('delete','rename'),
    'exchange': ('roundtrip',),
    'autosave': ('reopen',),
}
SPEC={
    'insert':'Create a file twice; each new file is selected and the second follows the first.',
    'nest':'Create a directory, then create a file inside the selected directory; the child is selected.',
    'focus':'Create two files, delete the selected second; select the remaining first file.',
    'delete':'Right click a file and use the menu delete item. The entry disappears and the menu closes.',
    'rename':'Right click a file and use the menu rename command. Prompt for a new name; the visible label changes.',
    'roundtrip':'Import a directory containing a file with text, then export via alert. Preserve the complete tree, name and text.',
    'reopen':'Select a file, replace editor text, create another file, then select the first. Read the saved text in the editor.',
}
TAGS=docs.ORIG.TAGS

def register():
    files=[Path(__file__),HERE/'probe.py',HERE/'PROTOCOL.md',Path(docs.__file__),Path(docs.dom.__file__),
           docs.HERE/'result.json',docs.HERE/'controls.json',docs.OUT/'seal.json',docs.ORIG.OUT/'public.json',
           docs.ORIG.OUT/'browser.json',Path(docs.ORIG.base.__file__)]
    files += [docs.OUT/t/r/'library.json' for t in TAGS for r in 'ab']
    hashes={str(p.relative_to(ROOT)):sha(p) for p in files}
    f=OUT/'registration.json'
    if not f.exists():
        balance=check_credits(CAP)
        if not balance['sufficient']:raise RuntimeError('Insufficient balance for this stage')
        core.save(f,dict(utc=now(),cap=CAP,deadline=END.isoformat(),targets=list(range(1,21)),
                         models={t:docs.dom.action.settings('table',t,'plan')['model'] for t in TAGS},
                         seeds={'a':2026112691,'b':2026112692},balance=balance,sources=hashes))
    if read(f)['sources']!=hashes:raise RuntimeError('Frozen file-explorer input changed')
    return read(f)

def passed(observation):return {k for k,v in observation['checks'].items() if v}

def build(tag,rep,ledger,pub):
    folder=OUT/tag/rep
    f=folder/'library.json'
    if f.exists():return read(f)
    origin=read(docs.OUT/tag/rep/'library.json')
    assert origin['status']=='valid'
    parts=dict(origin['source']);history=[]
    def inspect(label, candidate_parts):
        dest=folder/'public'/label
        record=dest/'observation.json'
        if not record.exists():
            page=docs.emit(pub,candidate_parts,dest/'page')
            core.save(record,observe(OUT,page))
        return read(record)
    best=inspect('before',parts)
    initial=best
    for name,actions in GROUPS.items():
        system=('Repair this existing file manager, preserving its UI and existing working behaviors. '
                'All sources and interaction observations are from the public construction environment. '
                'Keep the exact selectors requested by the brief. Other scripts access DOM classes and attributes. ')
        system+=('Return only the complete core HTML with its original CSS and JavaScript. Do not duplicate the extensions.'
                 if name=='core' else 'Return only one complete vanilla JS function installFeature(root). '
                 'It runs once after the core at the end of body. Other modules own their own event handlers. '
                 'Use DOM operations and event delegation. Do not output HTML. Do not install duplicate commands.')
        for attempt in range(2):
            missing=set(actions)-passed(best)
            if not missing:break
            dest=folder/'calls'/name/str(attempt)
            observation=history[-1].get('feedback',best) if attempt else best
            message=dict(requirements=[pub['requirements'][i-1]['description'] for i in docs.MODULES[name]],
                         public_sequences={k:SPEC[k] for k in sorted(missing)},keep=sorted(passed(best)),
                         public_feedback=observation,existing_core=parts['core'],
                         existing_extension=parts.get(name) if name!='core' else None,
                         other_extension_names=[k for k in parts if k not in (name,'core')])
            try:
                raw=docs.ORIG.base.request(ledger,('table',tag,rep),dest,core.messages(system,message),'build',9800 if name=='core' else 6500)
                updated=docs.parse_document(raw) if name=='core' else docs.installer(raw)
                variant=parts|{name:updated}
                label=name+'-'+str(attempt)
                measured=inspect(label,variant)
                gain=bool(missing & (passed(measured)-passed(best)))
                keep=gain and passed(best)<=passed(measured)
                admission=None
                if keep:
                    candidate=docs.emit(pub,variant,folder/'admission'/label)
                    admission=docs.dom.exercise(candidate,[k for k in variant if k!='core'])
                    keep=admission['admitted']
                history.append(dict(group=name,attempt=attempt,retained=keep,feedback=measured,original_public=admission))
                if keep:parts=variant;best=measured
            except docs.dom.action.typed.MISSING as exc:
                history.append(dict(group=name,attempt=attempt,retained=False,missing=str(exc)));break
            except docs.ORIG.base.ERRORS as exc:
                history.append(dict(group=name,attempt=attempt,retained=False,feedback={'error':str(exc)[:250]}))
    core.save(f,dict(parts=parts,before=initial,after=best,history=history,origin=sha(docs.OUT/tag/rep/'library.json')))
    print('public file interactions',tag,rep,sorted(passed(initial)),sorted(passed(best)),flush=True)
    return read(f)

def generate(reg):
    seal=OUT/'seal.json'
    if seal.exists():return
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    pub=read(docs.ORIG.OUT/'public.json')
    def deploy(job):
        tag,rep=job;folder=OUT/tag/rep;lib=build(tag,rep,ledger,pub);parts=lib['parts']
        opts=[k for k in parts if k!='core']
        profiles=list(dict.fromkeys([tuple(opts),(),*[tuple(opts[:i]) for i in range(1,len(opts))],*[(k,) for k in opts]]))
        def page(selected,dest):return docs.emit(pub,{k:v for k,v in parts.items() if k=='core' or k in selected},dest)
        fixed=page(opts,folder/'fixed');core_page=page([],folder/'core')
        old=docs.emit(pub,read(docs.OUT/tag/rep/'library.json')['source'],folder/'old-fixed')
        def target(n):
            dest=folder/'plans'/str(n)
            msg=core.messages('Choose a feature profile that serves the latest requirement and its prerequisites. Output its number only.',
                              dict(brief=core.prefix(pub,n),profiles=[dict(index=i,features=list(p)) for i,p in enumerate(profiles)],
                                   features={k:docs.dom.DESCRIPTION[k] for k in opts}))
            try:
                text=docs.ORIG.base.uncode(docs.ORIG.base.request(ledger,('table',tag,rep),dest/'call',msg,'plan',1800)).strip()
                if not re.fullmatch('[0-9]+',text) or int(text)>=len(profiles):raise ValueError('Unknown profile')
                selected=page(profiles[int(text)],dest/'page')|dict(choice=int(text))
            except docs.dom.action.typed.MISSING as exc:selected=dict(status='missing',reason=str(exc))
            except ValueError as exc:selected=dict(status='invalid',reason=str(exc))
            return [dict(project='dom1',task=n,tag=tag,rep=rep,arm=k,**p) for k,p in
                    [('planned',selected),('fixed',fixed),('old-fixed',old),('core',core_page)]]
        with ThreadPoolExecutor(max_workers=2) as pool:
            rows=[r for group in pool.map(target,reg['targets']) for r in group]
        core.save(folder/'deployment.json',dict(library=sha(folder/'library.json'),profiles=profiles,rows=rows))
    def settings(p,t,phase):return docs.dom.action.settings('table',t,phase)|{'seed':reg['seeds']['a']}
    with patch.multiple(docs.ORIG.base,OUT=OUT,END=END,template=settings),ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(deploy,[(t,r) for t in TAGS for r in 'ab']))
    entries=[p for t in TAGS for r in 'ab' for p in (OUT/t/r/'library.json',OUT/t/r/'deployment.json')]
    core.save(seal,dict(registration=sha(OUT/'registration.json'),sources={str(p.relative_to(OUT)):sha(p) for p in entries},
                        starter=docs.emit(pub,{},OUT/'starter')))

def score(reg):
    seal=read(OUT/'seal.json')
    assert seal['registration']==sha(OUT/'registration.json') and all(sha(OUT/k)==v for k,v in seal['sources'].items())
    proto=browser.verify_contract('dom1')
    assert proto==read(docs.ORIG.OUT/'browser.json')
    groups={}
    rows=[dict(tag='starter',rep='-',arm='starter',project='dom1',task=n,**seal['starter']) for n in reg['targets']]
    for t in TAGS:
        groups[t]={}
        for r in 'ab':
            origin=OUT/t/r/'library.json'
            lib=read(origin);deploy=read(origin.with_name('deployment.json'))
            assert deploy['library']==sha(origin)
            groups[t][r]={k:v for k,v in lib.items() if k!='parts'}
            rows.extend(deploy['rows'])
    scored=browser.evaluate(rows,OUT,{'dom1':proto},3)
    compact=[{k:r.get(k) for k in ('tag','rep','task','arm','status','passed','choice','report_sha256')}|
             {'passed':False if r['status']=='invalid' else r['passed']} for r in scored]
    controls=read(docs.HERE/'controls.json')['rows']
    totals=ledger_read.totals(OUT/'budget.sqlite3');costs={}
    for row in ledger_read.calls(OUT/'budget.sqlite3'):
        key=row['model']+' / '+row['purpose'].split('/')[0]
        c=costs.setdefault(key,[0,0,0]);c[0]+=1;c[1]+=row['actual'] or 0
        c[2]+=row['reserved'] if row['actual'] is None else row['actual']
    core.save(HERE/'result.json',dict(registration=sha(OUT/'registration.json'),seal=sha(OUT/'seal.json'),libraries=groups,
                                     rows=compact,controls=controls,control_source=sha(docs.HERE/'controls.json'),cost=totals,
                                     calls_settled_exposure_micro_usd=costs))

if __name__=='__main__':
    with browser.lock(OUT/'run.lock'):
        reg=register()
        generate(reg);score(reg)
