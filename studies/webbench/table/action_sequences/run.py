"""Generate two fresh model-owned table libraries using public action-state traces."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import subprocess
import sys
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,now,read,sha
from studies.webgen_bench.component_contracts.typed_inputs import dom_inputs as campaign
from ..selection_binding.interaction_repairs import run as previous

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/table-action-sequences-20261127'
CAP=.58
SEED=2026112707
TAG='qwen9'
build=previous.projection.build
base=previous.prior.BASE
END=campaign.comp.END
# The release also contains a separate evaluation file; the generator never opens it.
TRAIN={'columns':dict(row=1,col=0,side='Right'),'editing':dict(row=1,col=0,arrow='ArrowRight'),
       'restoration':dict(row=1,col=2,header=1,side='Right',arrow='ArrowDown')}
CONTRACT={'columnAction':'cell is the actual right-clicked header TH. Its cellIndex is the insertion reference for EVERY row of ctx.table.rows. Preserve existing cell content and order.',
          'navigate':'On ArrowRight with no active cell select table.rows[0].cells[0]. ArrowDown changes the row at fixed column. A single selection means one actual cell in ctx.selected and a matching ctx.active. Use ctx.select([next],next,next).',
          'editingKeys':'Enter on one selected TH/TD makes it editable; Escape exits edit on that same cell, keeps its selection and preserves its value. Delete clears selected values. Use the actual KeyboardEvent.key.',
          'editCell':'An editable cell is a native contentEditable cell which remains selected. Do not replace this cell with an input or detach it.',
          'markSelection':'cells is an ITERABLE OF ACTUAL CELL ELEMENTS. Keep a Set of these cells, plus active and anchor as actual DOM elements.',
          'cellClick':'A click can follow a pointer sequence. Preserve the identity of the actual selected cell in ctx. A click on another cell normalizes to one selected element.'}


def trace(page,cases):
    arg=json.dumps(dict(page=str(page),cases=cases))
    try:
        with browser.browser_slot():
            p=subprocess.run([sys.executable,'-m','studies.webbench.table.action_sequences.trace'],input=arg,text=True,
                             capture_output=True,timeout=30,check=True)
        return json.loads(p.stdout)
    except (subprocess.CalledProcessError,subprocess.TimeoutExpired):
        return {k:dict(passed=False,steps=[{'action':'browser','passed':False,'error':'runner failed or timed out'}]) for k in cases}


def register():
    reg=OUT/'registration.json'
    paths=[Path(__file__),HERE/'PROTOCOL.md',HERE/'trace.py',HERE/'heldout.json',Path(build.__file__),build.HERE/'host.js',
           previous.prior.PUBLIC,Path(previous.__file__),previous.HERE/'result.json',previous.OUT/'seal.json',
           previous.prior.OUT/'seal.json',previous.prior.HERE/'probe.py']
    hashes={str(p.relative_to(ROOT)):sha(p) for p in paths}
    if not reg.exists():
        prior=sum(ledger_read.totals(d/'budget.sqlite3')['exposure_usd'] for d in
                  (campaign.comp.OUT,campaign.typed.bodies.OUT,campaign.typed.OUT,campaign.prior.OUT,campaign.OUT))
        assert prior+.30+.15+CAP<=1.60
        balance=check_credits(CAP);assert balance['sufficient']
        core.save(reg,dict(utc=now(),deadline=END.isoformat(),balance=balance,cap=CAP,seeds=[SEED,SEED+1],sources=hashes))
    assert read(reg)['sources']==hashes
    return reg


def request_fn(ledger,rep,name,pub,dest,source=None,obs=None):
    msg=build.messages(name,pub)
    msg[0]=msg[0]|{'content':msg[0]['content']+' '+CONTRACT.get(name,'')}
    if obs:
        msg.extend([dict(role='assistant',content=source or ''),dict(role='user',content='Repair the responsible function from these public observations. Return one full named function. '+json.dumps(obs,ensure_ascii=False))])
    for attempt in range(2 if source is None else 1):
        try:
            raw=base.request(ledger,('table',TAG,rep),dest/str(attempt),msg,'build',3300)
            return build.extract(name,raw)
        except previous.prior.MISSING:
            break
        except previous.prior.ERRORS as error:
            msg.append(dict(role='user',content='The previous output could not be parsed. Return a complete named function with the specified signature. '+str(error)[:160]))
    return None


def prepare(rep,pub,ledger):
    folder=OUT/rep;dest=folder/'library.json'
    if dest.exists():return read(dest)
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs={k:pool.submit(request_fn,ledger,rep,k,pub,folder/'functions'/k) for k in build.ACTIONS}
        funcs={k:v for k,j in jobs.items() if (v:=j.result())}
    # This previously disclosed mapping reflects the model's own runtime selection Set.
    binding=dict(collection='selected',selector='th,td',className='selected')
    options=['menu','keys']
    def observe(label,parts,opts):
        f=folder/'public'/label/'report.json'
        if f.exists():return read(f)
        candidate=previous.projection.page(pub,parts,opts,binding,f.parent/'page')
        classic=previous.observe(candidate)
        sequences=trace(ROOT/candidate['page'],TRAIN)
        checks=dict(classic['checks'])
        for name,record in sequences.items():
            for step in record['steps']:
                if step['action']!='browser':
                    checks[name+'-'+step['action']]=step['passed']
        core.save(f,dict(checks=checks,sequences=sequences))
        return read(f)
    best=observe('first',funcs,options);history=[dict(stage='first',checks=best['checks'])]
    for k,targets in [('columnAction',['column','columns-insert','columns-remove','restoration-relocate']),
                      ('markSelection',['selection','editing-select']),('cellClick',['editing-select','restoration-select-after-insert']),
                      ('editingKeys',['editing-enter','editing-escape','clear']),('navigate',['arrow','wrap','editing-move','restoration-vertical-move']),
                      ('editCell',['edit'])]:
        if all(best['checks'].get(n) for n in targets):continue
        short={}
        for n,obs in best['sequences'].items():
            first=next((s for s in obs['steps'] if not s['passed']),None)
            if first:short[n]=first
        src=request_fn(ledger,rep,k,pub,folder/'repairs'/k,funcs.get(k),dict(failed_actions=short,requested_checks=targets))
        if not src:continue
        revised=funcs|{k:src};after=observe('repair-'+k,revised,options)
        gained=previous.passed(after)-previous.passed(best)
        keep=previous.passed(best)<=previous.passed(after) and bool(gained.intersection(targets))
        history.append(dict(stage=k,checks=after['checks'],retained=keep))
        if keep:funcs,best=revised,after
    for opt in ('clipboard','range','resize','reorder'):
        trial=options+[opt];after=observe('enable-'+opt,funcs,trial)
        keep=previous.passed(best)<previous.passed(after)
        history.append(dict(stage='enable-'+opt,checks=after['checks'],retained=keep))
        if keep:options,best=trial,after
    valid={'selection','row'}<=previous.passed(best)
    core.save(dest,dict(status='valid' if valid else 'build_failed',parts=funcs,options=options,binding=binding,
                        checks=sorted(previous.passed(best)),history=history))
    print(rep,'public',len(funcs),sorted(previous.passed(best)),flush=True)
    return read(dest)


def generate():
    reg=register();seal=OUT/'seal.json'
    if seal.exists():return
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    pub=read(previous.prior.PUBLIC)
    def settings(_,tag,stage):return previous.prior.old.settings('table',tag,stage)|{'seed':SEED}
    with patch.multiple(base,OUT=OUT,END=END,template=settings),ThreadPoolExecutor(max_workers=2) as pool:
        libs=dict(zip('ab',pool.map(lambda r:prepare(r,pub,ledger),'ab'),strict=True))
        rows=[]
        for r,lib in libs.items():
            folder=OUT/r
            def page(opts,dest):return previous.projection.page(pub,lib['parts'],opts,lib['binding'],dest)
            fixed=page(lib['options'],folder/'fixed') if lib['status']=='valid' else {'status':lib['status']}
            opts=lib['options']
            profiles=list(dict.fromkeys([tuple(opts),(),*[tuple(opts[:i]) for i in range(1,len(opts))],*[(k,) for k in opts]]))
            def one(task):
                dest=folder/'plans'/str(task)
                if lib['status']!='valid':candidate={'status':lib['status']}
                else:
                    msg=core.messages('Choose one profile for the current public requirement. Return only its integer index.',
                                      dict(requirements=core.prefix(pub,task),profiles={str(i):list(v) for i,v in enumerate(profiles)}))
                    try:
                        raw=base.uncode(base.request(ledger,('table',TAG,r),dest/'call',msg,'plan',900)).strip()
                        index=int(raw) if raw.isdecimal() else -1
                        if not 0<=index<len(profiles):raise ValueError('Unusable profile identifier')
                        candidate=page(profiles[index],dest/'page')
                    except previous.prior.MISSING as exc:candidate={'status':'missing','reason':str(exc)}
                    except ValueError as exc:candidate={'status':'invalid','reason':str(exc)}
                return [dict(project='table',task=task,arm=k,**v) for k,v in [('self-'+r,candidate),('fixed-'+r,fixed)]]
            rows.extend(item for pair in pool.map(one,range(1,21)) for item in pair)
    empty=previous.projection.page(pub,{},[],libs['a']['binding'],OUT/'starter')
    rows.extend(dict(project='table',task=i,arm='starter',**empty) for i in range(1,21))
    core.save(seal,dict(registration=sha(reg),libs={r:sha(OUT/r/'library.json') for r in 'ab'},rows=rows))


if __name__=='__main__':
    with browser.lock(OUT/'run.lock'):generate()
