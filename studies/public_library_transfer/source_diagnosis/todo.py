"""Hold component sources fixed during planning and repair Self on public event sequences."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import subprocess

from studies.public_library_transfer import core
from studies.study_io import ROOT, read, sha
from studies.public_library_transfer.compact_todomvc.slot_choices import run as slots

WEAK=slots.WEAK
CONTRACT=slots.previous.contract
MOD=slots.FUNCS
BASE=slots.BASE
SUPPLIED=('gemma4','qwen9','deepseek-flash','ministral3')
SMALL=('gemma4','llama3','ministral3')
HERE=Path(__file__).resolve().parent

def source(tag,rep):
    base=slots.previous.reception.OUT if tag==slots.previous.reception.TAG else CONTRACT.OUT
    return base/tag/rep/'library.json'

def direct(tag,task):
    if tag in SMALL:
        seal=(slots.previous.OUT if tag=='llama3' else WEAK.OUT)/tag/'seal.json'
        return read(seal)['rows'][task]['direct']
    path=WEAK.suite.OUT/tag/'targets'/task/'direct/result.json'
    row=read(path)
    if row['status']=='valid':
        file=path.with_name('files.json');assert sha(file)==row['files_sha256']
        return dict(status='valid',file=str(file.relative_to(ROOT)),files_sha256=sha(file))
    return dict(status=row['status'],reason=row.get('reason'))

def features(functions, enabled, spec):
    code=MOD.assemble(functions,enabled)
    prior=CONTRACT.feedback.evaluate_public(code,list(spec['spec']))
    proc=subprocess.run(['node',str(HERE/'sequences.cjs')],input=json.dumps(dict(source=code)),
                        capture_output=True,text=True,timeout=35,check=True)
    return {**prior,**{'flow-'+k:v for k,v in json.loads(proc.stdout).items()}}

def passed(checks):return {k for k,val in checks.items() if val['passed']}

def repair(tag,rep,folder,ledger):
    path=folder/tag/rep/'library.json'
    if path.exists():return read(path)
    old=read(source(tag,rep));assert old['status']=='valid'
    functions=dict(old['functions']);defaults=dict.fromkeys(MOD.OPTIONS,True)
    spec=read(WEAK.suite.SOURCE/'build-inputs.json')['todomvc']
    current=features(functions,defaults,spec);initial=sorted(passed(current));history=[]
    for name,(signature,group,objective) in MOD.CONTRACTS.items():
        for i in range(2):
            failures={k:v for k,v in current.items() if name in v['owners'] and not v['passed']}
            if not failures:break
            feedback={k:{a:vv for a,vv in v.items() if a in ('expected','actual','error','state','shown')} for k,v in failures.items()}
            context=core.messages('Return one complete JavaScript function with the exact requested name. Use the public shared state contract. Match all existing values and preserve unrelated todos and fields. The public page dispatches real events using their exact id. No dependencies.',
                 dict(signature=f'function {name}({signature})',goal=objective,shared_state=spec['contract'],
                      requirements=spec['spec'].get(group,spec['spec']['core']),original=functions[name],public_failures=feedback,
                      public_example={'state':{'todos':[{'id':1,'title':'Almond','completed':False},{'id':2,'title':'Birch','completed':True}],'nextId':3,'filter':'all','editing':None},
                                      'storage':'JSON array of todo records as react-todos; never persist the outer state.'}))
            try:
                raw=BASE.request(ledger,('todomvc',tag,rep),folder/tag/rep/'repairs'/name/str(i),context,'build',2000)
                fn=MOD.extract(name,raw)
                if not fn:raise ValueError('Complete function not delivered')
                changed=functions|{name:fn};observation=features(changed,defaults,spec)
                keep=passed(current)<passed(observation) and bool(failures.keys() & (passed(observation)-passed(current)))
                history.append(dict(name=name,attempt=i,retained=keep,passed=sorted(passed(observation))))
                if keep:functions=changed;current=observation
            except slots.EVENTS.MISSING as exc:history.append(dict(name=name,error=str(exc)));break
            except (TypeError,ValueError,subprocess.TimeoutExpired) as exc:history.append(dict(name=name,error=str(exc)))
    enabled=[k for k in MOD.OPTIONS if passed(current)-passed(features(functions,defaults|{k:False},spec))]
    value=dict(status='valid' if all(functions.values()) and old['status']=='valid' and set(initial)<=passed(current) else 'build_failed',
               initial=initial,public=sorted(passed(current)),options=enabled,functions=functions,history=history)
    core.save(path,value);return read(path)

def select(ledger,tag,task,folder,choices):
    multiple=[k for k,opts in choices.items() if len(opts)>1]
    selected={k:opts[0][0] for k,opts in choices.items()}
    if not multiple:return selected
    encoded={k:{chr(65+i):dict(name=o,meaning=desc) for i,(o,desc) in enumerate(choices[k])} for k in multiple}
    msg=core.messages('For each listed slot choose ONE legal capital letter in listed order. Return only the ordered letters, such as ABAC. No other text.',
                      dict(requirement=task['requirement'],ordered_slots=multiple,choices=encoded))
    raw=BASE.uncode(BASE.request(ledger,('todomvc',tag,'a'),folder/'joint',msg,'plan',700)).strip()
    code=re.sub(r'\s+','',raw).upper()
    if len(code)==len(multiple) and all(c in encoded[k] for k,c in zip(multiple,code,strict=True)):
        selected.update({k:encoded[k][c]['name'] for k,c in zip(multiple,code,strict=True)});return selected
    def one(k):
        msg=core.messages('Choose one legal option; reply only with its capital letter.',dict(requirement=task['requirement'],slot=k,choices=encoded[k]))
        raw=BASE.uncode(BASE.request(ledger,('todomvc',tag,'a'),folder/'slot'/k,msg,'plan',250)).strip()
        match=re.fullmatch(r'(?:(?:option|answer|choice)\s*[:=]?\s*)?([a-z])(?:[.!])?',raw,re.I)
        if not match or match[1].upper() not in encoded[k]:raise ValueError('Invalid slot '+k)
        return encoded[k][match[1].upper()]['name']
    for k in multiple:selected[k]=one(k)
    return selected

def render(ledger,tag,arm,task,folder,lib):
    dest=folder/tag/task['id']/arm
    if (dest/'record.json').exists():return read(dest/'record.json')
    def page(sub,src):
        f=dest/sub/'files.json';core.save(f,{'candidate.js':src})
        return dict(status='valid',file=str(f.relative_to(ROOT)),files_sha256=sha(f))
    if arm in ('a','b'):
        if lib['status']!='valid':return {arm:dict(status=lib['status']),'fixed-'+arm:dict(status=lib['status'])}
        choices={k:[('enabled','Enable the named public feature'),('disabled','Omit the named public feature')] for k in lib['options']}
        def compile(options):return MOD.assemble(lib['functions'],{k:options.get(k,'enabled')=='enabled' for k in MOD.OPTIONS})
    else:
        gpt=arm=='gpt5-library'
        cfg=WEAK.tables_of(lib) if gpt else dict(inits=WEAK.library.INITS,afters=WEAK.library.AFTERS,routes=WEAK.library.ROUTES,views=WEAK.library.VIEWS)
        desc={f['name']:f['description'] for f in lib['functions']}
        events=WEAK.domain.enabled_events(task['features']);views=WEAK.domain.enabled_slots(task['features'])
        choices={'init':[(k,desc[k]) for k in cfg['inits']]}
        for prefix,names,table in [('event',events,cfg['routes']),('view',views,cfg['views'])]:
            for k in names:choices[prefix+'-'+k]=[(x,desc[x]) for x in table[k]]
        for k,v in cfg['afters'].items():
            if v=='core' or v in task['features']:choices['after-'+k]=[('enabled',desc[k]),('disabled','Omit this handler')]
        def compile(options):
            plan=dict(init=options['init'],handlers={k:options['event-'+k] for k in events},view={k:options['view-'+k] for k in views},
                      after=[k[6:] for k,v in options.items() if k.startswith('after-') and v=='enabled'])
            return WEAK.generic.compile_plan(plan,task['features'],lib,cfg) if gpt else WEAK.domain.compile_plan(plan,task['features'],lib)
    fixed=page('fixed',compile({k:v[0][0] for k,v in choices.items()}))
    try:
        options=select(ledger,tag,task,dest/'plan',choices);candidate=page('planned',compile(options))
        core.save(dest/'selected.json',options)
    except slots.EVENTS.MISSING as exc:candidate=dict(status='missing',reason=str(exc))
    except (ValueError,TypeError,KeyError) as exc:candidate=dict(status='invalid',reason=str(exc))
    out={arm:candidate,'fixed-'+arm:fixed};core.save(dest/'record.json',out);return out

def generate(folder,ledger,reg):
    tags=list(dict.fromkeys([*SUPPLIED,*SMALL]))
    with ThreadPoolExecutor(max_workers=3) as pool:
        builds={(t,r):pool.submit(repair,t,r,folder,ledger) for t in SMALL for r in 'ab'}
        libs={k:j.result() for k,j in builds.items()}
    for tag in tags:
        dest=folder/tag/'seal.json'
        if dest.exists():continue
        sources={r:libs[tag,r] for r in 'ab'} if tag in SMALL else {}
        if tag in SUPPLIED:sources.update({'gpt5-library':read(WEAK.GPT),'human':WEAK.library.library()})
        tasks=WEAK.domain.tasks();rows={t['id']:{'direct':direct(tag,t['id'])} for t in tasks}
        with ThreadPoolExecutor(max_workers=4) as pool:
            jobs={(t['id'],a):pool.submit(render,ledger,tag,a,t,folder,l) for t in tasks for a,l in sources.items()}
            for (task,_),job in jobs.items():rows[task].update(job.result())
        core.save(dest,dict(registration=sha(reg),rows=rows,libraries={r:{'status':libs[tag,r]['status']} for r in 'ab' if tag in SMALL}))
