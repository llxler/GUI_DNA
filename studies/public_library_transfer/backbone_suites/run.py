"""Same-builder/same-generator trials under the published TodoMVC and Duo harnesses."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path

from gui_dna.budget import BudgetStop, Ledger
from gui_dna.provider import parse_json
from scripts.check_openrouter_credits import check_credits
from studies.ledger_read import totals, calls
from studies.public_library_transfer.other_benchmarks import generate as menus
from studies.study_io import ROOT, digest, read, sha
from studies.todomvc_dna import domain, library
from studies.webbench.backbone_matrix import run as transport
from studies.webbench.backbone_matrix.extension.__main__ import EXTRA, INITIAL

HERE=Path(__file__).resolve().parent
SOURCE=ROOT/'artifacts/public-library-transfer-extra-20261123'
EXT=ROOT/'artifacts/backbone-extension-20261124'
OUT=ROOT/'artifacts/backbone-suites-20261124'
FIRST=transport.MODELS.copy()
MODELS={tag:(model,1,pin,pout) for tag,(model,_,pin,pout) in (FIRST|EXTRA).items()
        if tag in ('qwen','mistral','oss','gemma','qwen9','deepseek-flash')}
save=transport.save
GROUPS=('todomvc','blogging','taskmanagement')
RESULT=ROOT/'studies/results/backbone-suites-20261124.json'


def inputs():
    return read(SOURCE/'targets.json'),read(SOURCE/'build-inputs.json')


def verify():
    reg=read(OUT/'registered.json')
    for rel,checksum in reg['files'].items():
        assert sha(ROOT/rel)==checksum,rel
    return reg


def register():
    if (OUT/'registered.json').exists():
        verify()
        return
    prior={}
    for model_root, models in ((INITIAL,FIRST),(EXT,EXTRA)):
        for tag,(_,cap,*_) in models.items():
            folder=model_root/tag
            prior[tag]=totals(folder/'budget.sqlite3')['exposure_usd'] if (folder/'seal.json').exists() else cap
    assert sum(prior.values())+len(MODELS)<=20
    balance=check_credits(len(MODELS))
    if not balance['sufficient']:
        raise BudgetStop('Insufficient suite funding')
    reg=read(SOURCE/'registered.json')
    assert reg['target_sha256']==sha(SOURCE/'targets.json') and reg['input_sha256']==sha(SOURCE/'build-inputs.json')
    files=[Path(__file__),HERE/'PROTOCOL.md',Path(menus.__file__),Path(transport.__file__),
           Path(domain.__file__),Path(library.__file__),domain.HERE/'shell.html',
           domain.HERE/'harness/demo-todo-app.spec.ts',SOURCE/'targets.json',SOURCE/'build-inputs.json',
           Path(menus.__file__).with_name('evaluate.py'),Path(menus.__file__).with_name('duo_original_results.py')]
    targets,_=inputs()
    files.extend(ROOT/r['test'] for r in targets.values() if 'test' in r)
    params=read(INITIAL/'registered.json')['parameters']|read(EXT/'registered.json')['parameters']
    save(OUT/'registered.json',{'utc':transport.public.now(),'models':MODELS,'parameters':params,'prior_liability':prior,
                               'balance':balance,'files':{str(p.relative_to(ROOT)):sha(p) for p in files}})


def ask(tag,ledger,folder,system,context,schema,purpose,limit=8192):
    msg=[{'role':'system','content':system},{'role':'user','content':json.dumps({'public':context,'output_schema':schema},ensure_ascii=False)}]
    raw=transport.request(tag,ledger,folder,msg,purpose,limit)
    return parse_json(raw)


def build(tag,ledger,group,context):
    folder=OUT/tag/'build'/group
    marker=folder/'status.json'
    if marker.exists():return read(marker)
    todo=group=='todomvc'
    try:
        value=ask(tag,ledger,folder/'call',menus.TODO_BUILD if todo else menus.DUO_BUILD,context,
                  menus.TODO_SCHEMA if todo else menus.DUO_SCHEMA,'build/'+group,16000)
        interface=menus.interface(group,value)
        save(folder/'package.json',value)
        state={'status':'valid','menu':interface,'package_sha256':sha(folder/'package.json')}
    except (transport.Unavailable,BudgetStop) as exc:
        state={'status':'missing','reason':str(exc)}
    except (ValueError,TypeError,KeyError,IndexError,AttributeError) as exc:
        state={'status':'build_failed','reason':str(exc)[:500]}
    save(marker,state)
    return state


def produce(tag,ledger,task,row,arm,builds):
    folder=OUT/tag/'targets'/task/arm
    marker=folder/'result.json'
    if marker.exists():return read(marker)
    group=row['group']
    result={'arm':arm,'task':task,'group':group,'status':'invalid'}
    try:
        if arm=='direct':
            instruction=' Provide browser JS assigning window.candidate.' if group=='todomvc' else ' Provide one React default-export module. Only import react or react-router-dom.'
            src=ask(tag,ledger,folder/'call',menus.DIRECT+instruction,row['public'],menus.DIRECT_SCHEMA,'target/'+group+'/direct/'+task)['source']
            if not isinstance(src,str) or not src.strip():raise ValueError('Empty source')
            files={'candidate.js' if group=='todomvc' else row['public']['module']+'.js':src}
        elif arm=='human':
            current=next(t for t in domain.tasks() if t['id']==task)
            lib=library.library()
            msg=domain.messages_for(current,'dna',lib)
            raw=transport.request(tag,ledger,folder/'call',msg,'target/todomvc/human/'+task)
            files={'candidate.js':domain.compile_plan(parse_json(raw),current['features'],lib)}
        elif builds[group]['status']!='valid':
            result['status']=builds[group]['status']
            save(marker,result)
            return result
        else:
            menu=builds[group]['menu']
            pkg=read(OUT/tag/'build'/group/'package.json')
            plan=menu['first'] if arm=='fixed' else ask(tag,ledger,folder/'call',menus.PLAN,
                     {'current':row['public'],'library':menu},menu['schema'],'target/'+group+'/self/'+task)
            if set(plan)!=set(menu['schema']['properties']):raise ValueError('Unexpected fields')
            if group=='todomvc':
                if not all(type(v) is bool for v in plan.values()):raise ValueError('Expected Boolean switches')
                files={'candidate.js':'(function(){\nconst DNA_CONFIG = Object.freeze('+json.dumps(plan,sort_keys=True)+');\n'+pkg['source']+'\n})();\n'}
            else:
                from studies.public_library_transfer.other_benchmarks.duo_original_results import bundle
                files=bundle(row['public']['module'],pkg,plan)
        save(folder/'files.json',files)
        result.update(status='valid',files_sha256=sha(folder/'files.json'))
    except (transport.Unavailable,BudgetStop) as exc:
        result.update(status='missing',reason=str(exc))
    except (ValueError,TypeError,KeyError,IndexError,AttributeError) as exc:
        result['reason']=str(exc)[:500]
    if (folder/'call/response.json').exists():
        result['response_sha256']=sha(folder/'call/response.json')
    save(marker,result)
    return result


def generate(tag):
    verify()
    if (OUT/tag/'seal.json').exists():return
    transport.OUT,transport.MODELS=OUT,MODELS
    ledger=Ledger(OUT/tag/'budget.sqlite3',1,1)
    targets,contexts=inputs()
    builds={g:build(tag,ledger,g,contexts[g]) for g in GROUPS}
    jobs=[(t,r,a) for t,r in targets.items() for a in (('direct','human','self','fixed') if r['group']=='todomvc' else ('direct','self','fixed'))]
    with ThreadPoolExecutor(max_workers=3) as pool:
        rows=list(pool.map(lambda j:produce(tag,ledger,*j,builds),jobs))
    save(OUT/tag/'seal.json',{'registered_sha256':sha(OUT/'registered.json'),
                             'rows':rows,'builds':builds,'utc':transport.public.now()})


def score(tag):
    # Test processes only need local benchmark assets.
    for key in tuple(os.environ):
        if key.endswith(('_API_KEY','_ACCESS_TOKEN','_AUTH_TOKEN')):os.environ.pop(key)
    from studies.public_library_transfer.other_benchmarks import evaluate
    from studies.public_library_transfer.browser import browser_slot
    verify()
    seal=read(OUT/tag/'seal.json')
    assert seal['registered_sha256']==sha(OUT/'registered.json')
    targets,_=inputs()
    server=evaluate.todo.Server(OUT)
    def one(row):
        task,arm=row['task'],row['arm']
        passed=None if row['status']=='missing' else False
        result={**row,'passed':passed}
        if row['status']=='valid':
            source=OUT/tag/'targets'/task/arm/'files.json'
            assert sha(source)==row['files_sha256']
            with browser_slot():
                out=evaluate.score((row['group'],targets[task],read(source),OUT/tag/'scores'/task/arm,server))
            result.update(passed=out['passed'],report_sha256=out['report_sha256'],official_tests=out['official_tests'])
        return result
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            rows=list(pool.map(one,seal['rows']))
    finally:
        server.close()
    save(OUT/tag/'scores.json',{'seal_sha256':sha(OUT/tag/'seal.json'),'rows':rows})


def report():
    reg=verify()
    result={'registered_utc':reg['utc'],'registered_sha256':sha(OUT/'registered.json'),'models':{}}
    for tag,(model,*_) in MODELS.items():
        scored=read(OUT/tag/'scores.json')
        assert scored['seal_sha256']==sha(OUT/tag/'seal.json') and len(scored['rows'])==62
        assert len({(r['task'],r['arm']) for r in scored['rows']})==62
        accounting={}
        for call in calls(OUT/tag/'budget.sqlite3'):
            key='/'.join(call['purpose'].split('/')[:2 if call['purpose'].startswith('build/') else 3])
            values=accounting.setdefault(key,{'settled_microusd':0,'exposure_microusd':0})
            values['settled_microusd']+=call['actual'] or 0
            values['exposure_microusd']+=call['actual'] if call['actual'] is not None else call['reserved']
        result['models'][model]={**scored,'builds':read(OUT/tag/'seal.json')['builds'],
                 'ledger':totals(OUT/tag/'budget.sqlite3'),'cost_by_project_method':accounting}
    save(RESULT,result)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('register','generate','score','report'))
    parser.add_argument('tag',choices=MODELS,nargs='?')
    args=parser.parse_args()
    if args.action in ('register','report'):
        {'register':register,'report':report}[args.action]()
    else:
        {'generate':generate,'score':score}[args.action](args.tag)
