"""Two public-only Gemma controller builds with witnessed options and a paired direct arm."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import subprocess

import httpx

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.public_library_transfer.backbone_suites import run as suite
from studies.public_library_transfer.self_refinement.todomvc.event_modules.feedback import run as public
from studies.public_library_transfer.self_refinement.todomvc.source_binding import run as binding
from studies.study_io import ROOT,now,read,sha
from . import transport

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/todomvc-gemma-verified-20261124'
RESULT=HERE/'result.json'
SEEDS={'A':18271,'B':76151}
TASKS=binding.TASKS
save=browser.preserve_json

COMMON=(
    'Write one complete classic JavaScript program for the supplied TodoMVC state-controller contract. '
    'The HTML host owns all DOM events and rendering. Assign window.candidate with init, reduce and select. '
    'Use the exact state, event and view fields in the contract. Maintain one shared state. '
    'Initialize safely with or without storage. Persist the todos in the specified format after every change. '
    'Every reducer path returns state. The view derives from the state and may not mutate it. '
    'Return bare complete JavaScript code. No JSON envelope, commentary, imports, or tools.\n')
BUILD=COMMON+(
    'Build a reusable controller from these public specifications. In your own source declare exactly once '
    'const DNA_CONFIG = { ... } containing one to six actual Boolean literals, with semantic names that you choose. '
    'Set the defaults to deliver the complete behavior. Use the individual Boolean values inside the actual matching '
    'event or view implementations. Turning a feature off must observably disable its action or view; leave unrelated '
    'behavior working. All state, handlers, views and code are yours to implement. Use valid JavaScript throughout; '
    'the host will change only the values of your existing declaration.')
DIRECT=COMMON+'Implement the current public specification directly, with no behavior library or configuration layer.'


def register():
    paths=[HERE/'PROTOCOL.md',HERE/'transport.py',Path(__file__),public.HERE/'probes.cjs',Path(public.__file__),
           binding.HERE/'extract.cjs',binding.ACORN,
           suite.SOURCE/'targets.json',suite.SOURCE/'build-inputs.json']
    targets,contexts=suite.inputs()
    save(OUT/'public.json',{'builder':contexts['todomvc'],'targets':{t:targets[t]['public'] for t in TASKS}})
    paths.append(OUT/'public.json')
    params={'model':transport.MODEL,'seeds':SEEDS,'tasks':list(TASKS),'end':transport.END.isoformat(),
            'cap_usd':transport.CAP,'prices':transport.PRICES,'files':{str(p.relative_to(ROOT)):sha(p) for p in paths}}
    marker=OUT/'registered.json'
    if marker.exists():
        assert read(marker)['parameters']==params
        return
    credits=check_credits(transport.CAP)
    if not credits['sufficient']:
        raise RuntimeError('Account does not cover the registered stage')
    url='https://openrouter.ai/api/v1/models/'+transport.MODEL+'/endpoints'
    response=httpx.get(url,timeout=25)
    response.raise_for_status()
    routes=[{'provider':e['provider_name'],'tag':e.get('tag'),'pricing':e['pricing'],'parameters':e['supported_parameters']}
            for e in response.json()['data']['endpoints'] if e['provider_name'].lower()=='deepinfra']
    assert any({'seed','temperature','structured_outputs','response_format'}<=set(e['parameters'])
               and float(e['pricing']['prompt'])*1e6 <= transport.PRICES['prompt']
               and float(e['pricing']['completion'])*1e6 <= transport.PRICES['completion'] for e in routes)
    save(marker,{'utc':now(),'parameters':params,'balance':credits,'routes':routes})


def raw_program(raw):
    fences=re.findall(r'^\s*```(\w*)[^\S\n]*\n(.*?)^\s*```[^\S\n]*$',raw,re.M|re.S)
    source=None
    for candidate in [raw,*(b for lang,b in fences if lang.lower() in ('json',''))]:
        try:
            data=json.loads(candidate)
        except ValueError:
            continue
        if isinstance(data,dict) and isinstance(data.get('source'),str):
            source=data['source']
            break
    if source is None:
        blocks=[b for lang,b in fences if lang.lower() in ('js','javascript','') and 'window.candidate' in b]
        source=blocks[0] if blocks else raw
    if not source.strip():
        return None
    command=subprocess.run(['node',str(binding.HERE/'extract.cjs'),str(binding.ACORN)],input=source,
                           text=True,capture_output=True,timeout=15)
    return json.loads(command.stdout) if command.returncode==0 else None


def literal(ast):
    config=ast['binding'] if ast else None
    if config is None or len(config['first'])>6 or not all(
            re.fullmatch('[A-Za-z_$][A-Za-z0-9_$]*',name) for name in config['first']):
        return None
    return config


def instance(ast, chosen=None):
    if not ast:
        return None
    value=literal(ast)
    if chosen is None or (value and chosen==value['first']):
        return ast['code']
    assert value and set(chosen)==set(value['first']) and all(type(v) is bool for v in chosen.values())
    return value['before']+json.dumps(chosen,sort_keys=True)+value['after']


def observation(entry):
    try:
        json.loads(entry['actual'])
        return True
    except (ValueError,TypeError):
        return False


def evaluate(raw,features,library):
    ast=raw_program(raw)
    source=instance(ast)
    checks=public.evaluate_public(source,features)
    info={'status':'valid' if ast else 'invalid','checks':checks,'options':{},
          'source_sha256':public.digest(source) if source else None}
    binding_literal=literal(ast) if library else None
    if not binding_literal:
        info['defaults']=None
        return ast,info
    first=binding_literal['first']
    info['defaults']=first
    repeat=public.evaluate_public(source,features)
    for key,value in first.items():
        alternate={**first,key:not value}
        alt=instance(ast,alternate)
        a=public.evaluate_public(alt,features)
        b=public.evaluate_public(alt,features)
        witnessed={}
        for label,base in checks.items():
            other=a[label]
            if (base==repeat[label] and other==b[label] and base['actual']!=other['actual'] and
                    base['passed']!=other['passed'] and observation(base) and observation(other)):
                witnessed[label]={'default':base['actual'],'flipped':other['actual'],
                                   'default_passed':base['passed'],'flipped_passed':other['passed'],
                                   'expected':base['expected']}
        info['options'][key]={'default':value,'witnesses':witnessed,
                              'flipped_source_sha256':public.digest(alt)}
    return ast,info


def witnesses(info):
    return {(key,label,e['default_passed'],e['flipped_passed']) for key,opt in info['options'].items()
            for label,e in opt['witnesses'].items()}


def acceptance(old,new):
    if new['status']!='valid':
        return 'invalid'
    passed_old,passed_new=(public.passes(v['checks']) for v in (old,new))
    signed_old,signed_new=witnesses(old),witnesses(new)
    if passed_old-passed_new or signed_old-signed_new:
        return 'public_regression'
    return 'accepted' if (old['status']!='valid' or passed_new>passed_old or signed_new>signed_old) else 'no_public_gain'


def generate_source(ledger,group,context,seed,features,library):
    folder=OUT/'source-attempts'/group
    msgs=core.messages(BUILD if library else DIRECT,context)
    prompt_purpose='library/'+group if library else 'direct/'+group
    try:
        raw=transport.request(OUT,ledger,folder/'initial',msgs,prompt_purpose+'/initial',seed)
    except transport.Missing as exc:
        state={'status':'missing','reason':str(exc)}
        save(folder/'audit.json',{'initial':state,'final':state,'repair':'not_requested'})
        return None,state,None,state
    old,info=evaluate(raw,features,library)
    if public.passes(info['checks'])==set(info['checks']) and (not library or witnesses(info)):
        save(folder/'audit.json',{'initial':info,'final':info,'repair':'not_needed'})
        return old,info,old,info
    defects=public.diagnostic(info['checks'])
    if library and not witnesses(info):
        defects['configuration']={'expected':'Declare 1-6 Boolean literals in DNA_CONFIG, and read them to change a public event or view. Provide the working default.',
                                  'observed':'No key changed a stable public pass/fail outcome in both repetitions.'}
    repair=[*msgs,{'role':'assistant','content':raw},
            {'role':'user','content':json.dumps({'public_diagnostics':defects,
                'instruction':'Return the entire corrected plain JavaScript controller. Preserve every working behavior and option.'})}]
    try:
        revised=transport.request(OUT,ledger,folder/'repair',repair,prompt_purpose+'/repair',seed+101)
    except transport.Missing as exc:
        save(folder/'audit.json',{'initial':info,'final':info,'repair':'unavailable','reason':str(exc)})
        return old,info,old,info
    new,new_info=evaluate(revised,features,library)
    status=acceptance(info,new_info)
    winning_ast,winning_info=(new,new_info) if status=='accepted' else (old,info)
    save(folder/'audit.json',{'initial':info,'proposed':new_info,'final':winning_info,'repair':status})
    return old,info,winning_ast,winning_info


def menu(info):
    return {key:{'default':option['default'],'public_observations':[
                {'check':k,'expected':v['expected'],'when_default':v['default'][:155],'when_toggled':v['flipped'][:155]}
                for k,v in list(option['witnesses'].items())[:3]]}
            for key,option in info.get('options',{}).items() if option['witnesses']}


def save_candidate(group,stage,arm,task,status,source=None,plan=None):
    row={'group':group,'stage':stage,'arm':arm,'task':task,'status':status}
    if plan is not None:
        row['plan']=plan
    if source is not None:
        path=OUT/'candidates'/group/stage/arm/task/'files.json'
        save(path,{'candidate.js':source})
        row['files_sha256']=sha(path)
    return row


def plan_tasks(ledger,rep,snapshots,targets):
    rows=[]
    def one(job):
        stage,ast,info,task=job
        if info['status']=='missing':
            return [save_candidate(rep,stage,a,task,'missing') for a in ('fixed','planned')]
        source=instance(ast)
        fixed=save_candidate(rep,stage,'fixed',task,'valid' if source else 'invalid',source)
        options=menu(info)
        if not options:
            return [fixed,save_candidate(rep,stage,'planned',task,'no_witnessed_option')]
        request=core.messages('Set the Boolean options for this target. Inspect the measured action or view changes for the default and toggled values, then choose the values compatible with all requested behavior. Return the required JSON object only.',
                              {'current_target':targets[task],'verified_options':options})
        schema=core.obj({key:{'type':'boolean'} for key in options})
        signature=public.digest({'options':options,'source':info['source_sha256']})[:20]
        folder=OUT/'plans'/rep/signature/task
        # These stages can share the same immutable source, seed, prompt and schema.
        try:
            with browser.lock(folder/'.lock'):
                raw=transport.request(OUT,ledger,folder,request,'plan/'+rep+'/'+signature+'/'+task,
                                      SEEDS[rep]+1000+TASKS.index(task),256,schema)
            values=json.loads(raw)
            if not isinstance(values,dict) or set(values)!=set(options) or not all(type(v) is bool for v in values.values()):
                raise ValueError('Invalid chosen options')
            chosen={**info['defaults'],**values}
            return [fixed,save_candidate(rep,stage,'planned',task,'valid',instance(ast,chosen),chosen)]
        except transport.Missing:
            return [fixed,save_candidate(rep,stage,'planned',task,'missing')]
        except (ValueError,TypeError):
            return [fixed,save_candidate(rep,stage,'planned',task,'invalid_plan')]
    jobs=[(stage,ast,info,t) for stage,(ast,info) in snapshots.items() for t in TASKS]
    with ThreadPoolExecutor(max_workers=3) as pool:
        for output in pool.map(one,jobs):
            rows.extend(output)
    return rows


def generate():
    register()
    if (OUT/'seal.json').exists(): return
    ledger=Ledger(OUT/'budget.sqlite3',transport.CAP,transport.CAP)
    data=read(OUT/'public.json')
    builder=data['builder']
    targets=data['targets']
    libraries={}
    rows=[]
    for rep,seed in SEEDS.items():
        ast,info,end,final=generate_source(ledger,rep,builder,seed,list(builder['spec']),True)
        libraries[rep]={'initial':(ast,info),'final':(end,final)}
        print('Prepared',rep,info['status'],final['status'],len(menu(final)),flush=True)
    def direct(task):
        feature_set=public.task_features(builder,targets[task])
        start,i,end,f=generate_source(ledger,task,targets[task],88281+TASKS.index(task),feature_set,False)
        return [save_candidate('direct',stage,'direct',task,info['status'],instance(ast))
                for stage,(ast,info) in [('initial',(start,i)),('final',(end,f))]]
    with ThreadPoolExecutor(max_workers=3) as pool:
        for outcome in pool.map(direct,TASKS):
            rows.extend(outcome)
    for rep,snapshots in libraries.items():
        rows+=plan_tasks(ledger,rep,snapshots,targets)
    sources={str(p.relative_to(OUT)):sha(p) for p in sorted(OUT.rglob('*.json')) if p.name!='seal.json'}
    save(OUT/'seal.json',{'utc':now(),'registration_sha256':sha(OUT/'registered.json'),'sources':sources,'rows':rows})
    print('Sealed',len(rows),'rows',ledger_read.totals(OUT/'budget.sqlite3'),flush=True)


def paired(rows):
    def values(group,stage,arm):
        selected=[r for r in rows if (r['group'],r['stage'],r['arm'])==(group,stage,arm)]
        assert len(selected)==len(TASKS) and {r['task'] for r in selected}==set(TASKS)
        return {r['task']:r['passed'] for r in selected}
    direct={s:values('direct',s,'direct') for s in ('initial','final')}
    results={}
    for rep in SEEDS:
        cohorts={stage+'_'+arm:values(rep,stage,arm) for stage in ('initial','final') for arm in ('planned','fixed')}
        cohorts.update({s+'_direct':v for s,v in direct.items()})
        tasks=[t for t in TASKS if all(col[t] is not None for col in cohorts.values())]
        results[rep]={'targets':tasks,'passed':{key:[t for t in tasks if col[t]] for key,col in cohorts.items()},
                      'scheduled':len(TASKS)}
        # Direct and fixed can still be measured when a plan is lost in transit.
        per_arm={}
        for key,vals in cohorts.items():
            observed=[t for t in TASKS if vals[t] is not None]
            per_arm[key]={'targets':observed,'passed':[t for t in observed if vals[t]]}
        results[rep]['individual_observations']=per_arm
    return results


def score():
    from studies.public_library_transfer.other_benchmarks import evaluate
    seal=read(OUT/'seal.json')
    assert all(sha(OUT/k)==v for k,v in seal['sources'].items())
    targets,_=suite.inputs()
    server=evaluate.todo.Server(OUT)
    def one(row):
        if row['status']!='valid':
            return {**row,'passed':None if row['status']=='missing' else False}
        task=row['task']
        file=OUT/'candidates'/row['group']/row['stage']/row['arm']/task/'files.json'
        assert sha(file)==row['files_sha256']
        dest=OUT/'scores'/task/row['files_sha256']
        with browser.lock(dest/'.lock'):
            if not (dest/'verdict.json').exists():
                with browser.browser_slot():
                    evaluate.score(('todomvc',targets[task],read(file),dest,server))
        return binding.official(dest,targets[task],row)
    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            rows=list(pool.map(one,seal['rows']))
    finally:
        server.close()
    calls=ledger_read.calls(OUT/'budget.sqlite3')
    receipts={}
    for req in OUT.rglob('request.json'):
        body=read(req)
        call=next(x for x in calls if x['id']==body['call_id'])
        directory=req.parent
        details={'purpose':call['purpose'],'status':call['status'],'reserved_microusd':call['reserved'],
                 'actual_microusd':call['actual'],'request_sha256':sha(req),'model':body['body']['model'],
                 'seed':body['body']['seed'],'max_tokens':body['body']['max_tokens']}
        if (directory/'settled.json').exists():
            stamp=read(directory/'settled.json')
            assert stamp['response_sha256']==sha(directory/'response.json')
            response=read(directory/'response.json')
            details.update(stamp,usage=response['usage'],finish_reason=response['choices'][0].get('finish_reason'))
        else:
            details['error']=read(directory/'error.json')['reason'] if (directory/'error.json').exists() else 'Unresolved'
        receipts[str(directory.relative_to(OUT))]=details
    audits={key:read(OUT/'source-attempts'/key/'audit.json') for key in (*SEEDS,*TASKS)}
    reg=read(OUT/'registered.json')
    browser.write_json(RESULT,{'model':transport.MODEL,'providers':reg['routes'],'registered_utc':reg['utc'],
        'sealed_utc':seal['utc'],'parameters':reg['parameters'],'seal_sha256':sha(OUT/'seal.json'),
        'registration_sha256':sha(OUT/'registered.json'),'accounting':ledger_read.totals(OUT/'budget.sqlite3'),
        'receipts':receipts,'public':audits,'rows':rows,'paired':paired(rows)})
    check()


def check():
    data=read(RESULT)
    assert data['paired']==paired(data['rows'])
    assert len(data['rows'])==len({(r['group'],r['arm'],r['stage'],r['task']) for r in data['rows']})==80
    assert len(data['receipts'])==data['accounting']['calls'] and data['accounting']['exposure_usd']<=transport.CAP
    assert sum(r['actual_microusd'] or 0 for r in data['receipts'].values())==round(data['accounting']['settled_usd']*1e6)
    assert sum(r['actual_microusd'] if r['actual_microusd'] is not None else r['reserved_microusd']
               for r in data['receipts'].values())==round(data['accounting']['exposure_usd']*1e6)
    for path in (Path(__file__),HERE/'transport.py',HERE/'PROTOCOL.md',public.HERE/'probes.cjs'):
        assert sha(path)==data['parameters']['files'][str(path.relative_to(ROOT))]
    for rep in SEEDS:
        audit=data['public'][rep]
        if audit['repair']=='accepted':
            assert acceptance(audit['initial'],audit['final'])=='accepted'
    print({g:{k:len(v) for k,v in r['passed'].items()} for g,r in data['paired'].items()})
    print(data['accounting'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('register','generate','score','check'))
    args=parser.parse_args()
    {'register':register,'generate':generate,'score':score,'check':check}[args.action]()
