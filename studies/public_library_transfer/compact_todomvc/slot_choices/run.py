"""Select existing TodoMVC atom names and switches via bounded categorical decisions."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import argparse
import re
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,read,sha,now
from ..numbered_plans import run as previous

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/todo-slot-choices-20261126'
CAP=.65
TAG='llama3'
WEAK=previous.weak
EVENTS=previous.contract.events
FUNCS=previous.contract.modules
BASE=EVENTS.base
SOURCE=previous.reception.OUT/TAG
ARMS=('human','gpt5-library','a','b')


def register():
    paths=[Path(__file__),HERE/'PROTOCOL.md',previous.OUT/TAG/'seal.json',WEAK.GPT,Path(WEAK.library.__file__),
           Path(WEAK.domain.__file__),Path(WEAK.generic.__file__),Path(FUNCS.__file__),Path(EVENTS.__file__),
           WEAK.suite.SOURCE/'targets.json',*(SOURCE/r/'library.json' for r in ('a','b'))]
    sums={str(p.relative_to(ROOT)):sha(p) for p in paths}
    f=OUT/'registration.json'
    if not f.exists():
        bal=check_credits(CAP)
        assert bal['sufficient']
        core.save(f,dict(utc=now(),sources=sums,balance=bal,cap=CAP,model=WEAK.SMALL[TAG],deadline=previous.contract.route.END.isoformat()))
    assert read(f)['sources']==sums
    return read(f)


def select(ledger,task,arm,slot,options,descriptions,dest):
    if len(options)==1:return options[0]
    symbols='ABCDEFGHIJKLMNOPQRSTUVWXYZ'[:len(options)]
    alternatives=dict(zip(symbols,options,strict=True))
    msg=core.messages('Choose one option for this slot so that the described public TodoMVC behavior works. Reply solely with the corresponding capital letter.',dict(requirement=task['requirement'],slot=slot,choices={s:dict(name=v,description=descriptions.get(v,v)) for s,v in alternatives.items()}))
    for attempt in range(2):
        raw=BASE.request(ledger,('todomvc',TAG,arm if arm in ('a','b') else 'a'),dest/'choices'/slot/str(attempt),msg,'plan',200)
        text=BASE.uncode(raw).strip()
        match=re.fullmatch(r'(?:(?:the (?:answer|choice) is|(?:i choose|option|answer))\s*[:=]?\s*)?([A-Z])(?:[.!)])?',text,flags=re.I)
        if match and match[1].upper() in alternatives:return alternatives[match[1].upper()]
        msg=msg+[dict(role='assistant',content=raw),dict(role='user',content='Reply with one character only, among '+', '.join(symbols)+'.')]
    raise ValueError('Multiple or absent categorical choices for '+slot)


def generate():
    seal=OUT/TAG/'seal.json'
    if seal.exists():return
    old=read(previous.OUT/TAG/'seal.json')
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    human,gpt=WEAK.library.library(),read(WEAK.GPT)
    self_lib={r:read(SOURCE/r/'library.json') for r in ('a','b')}
    tables={'gpt5-library':WEAK.tables_of(gpt),'human':dict(inits=WEAK.library.INITS,afters=WEAK.library.AFTERS,
        routes=WEAK.library.ROUTES,views=WEAK.library.VIEWS)}
    names={k:{f['name']:f['description'] for f in lib['functions']} for k,lib in [('human',human),('gpt5-library',gpt)]}
    def job(args):
        task,arm=args
        folder=OUT/TAG/task['id']/arm
        rec=folder/'record.json'
        if rec.exists():return read(rec)
        def pick(key,options,doc):
            return select(ledger,task,arm,key,options,doc,folder)
        def save_page(sub,code):
            f=folder/sub/'files.json'
            core.save(f,{'candidate.js':code})
            return dict(status='valid',file=str(f.relative_to(ROOT)),files_sha256=sha(f))
        def configure(fixed=False):
            choose=(lambda slot,options,doc:options[0]) if fixed else pick
            if arm in self_lib:
                lib=self_lib[arm]
                options=lib['options']
                config={k:True if k not in options else choose(k,['enabled','disabled'],{})=='enabled' for k in FUNCS.OPTIONS}
                return FUNCS.assemble(lib['functions'],config)
            cfg=tables[arm]; features=task['features']; defs=names[arm]
            init=choose('initialization',cfg['inits'],defs)
            handlers={k:choose('event-'+k,cfg['routes'][k],defs) for k in WEAK.domain.enabled_events(features)}
            views={k:choose('view-'+k,cfg['views'][k],defs) for k in WEAK.domain.enabled_slots(features)}
            after=[]
            for k,feature in cfg['afters'].items():
                if feature=='core' or feature in features:
                    if choose('after-'+k,['enabled','disabled'],{'enabled':defs[k],'disabled':'Omit this handler.'})=='enabled':
                        after.append(k)
            plan=dict(init=init,handlers=handlers,view=views,after=after)
            if arm=='human':return WEAK.domain.compile_plan(plan,features,human)
            return WEAK.generic.compile_plan(plan,features,gpt,cfg)
        static=save_page('fixed',configure(True))
        try:value=save_page('planned',configure())
        except EVENTS.MISSING as exc:value=dict(status='missing',reason=str(exc))
        except (ValueError,TypeError,KeyError) as exc:value=dict(status='invalid',reason=str(exc))
        core.save(rec,{arm:value,'fixed-'+arm:static})
        return read(rec)
    tasks=WEAK.domain.tasks()
    jobs=[(task,arm) for task in tasks for arm in ARMS]
    rows={task['id']:{'direct':old['rows'][task['id']]['direct']} for task in tasks}
    with patch.multiple(BASE,OUT=OUT,END=previous.contract.route.END,template=EVENTS.template),ThreadPoolExecutor(max_workers=4) as pool:
        for ((task,_),out) in zip(jobs,pool.map(job,jobs),strict=True):rows[task['id']].update(out)
    core.save(seal,dict(registration=sha(OUT/'registration.json'),rows=rows,libraries=old['libraries']))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('phase',choices=('generate','score'))
    phase=p.parse_args().phase
    with browser.lock(OUT/(phase+'.lock')):
        reg=register()
        if phase=='generate':generate()
        else:
            with patch.multiple(WEAK,OUT=OUT,MODELS={TAG:WEAK.SMALL[TAG]}):WEAK.score()
            core.save(HERE/'result.json',dict(registration=sha(OUT/'registration.json'),cost=ledger_read.totals(OUT/'budget.sqlite3'),
                     models={reg['model']:read(OUT/TAG/'result.json')}))
