"""Register, construct, seal and score staged self-built libraries."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import httpx

from gui_dna.budget import BudgetStop, Ledger
from scripts.check_openrouter_credits import check_credits
from studies.public_library_transfer import browser, core
from studies.public_library_transfer.self_refinement import method
from studies.study_io import ROOT, digest, read, sha
from studies.webbench.backbone_matrix import run as transport

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/self-refinement-20261124'
PROJECT='table'
MODELS={'qwen9':('qwen/qwen3.5-9b',2,.35,1.2),'oss':('openai/gpt-oss-120b',2,.25,1)}
END=datetime(2026,11,24,5,18,tzinfo=timezone.utc)
INVALID=(ValueError,KeyError,IndexError,TypeError,AttributeError)
MISSING=(BudgetStop,transport.Unavailable)
save=core.save

def configure(root,project,models,end):
    global OUT,PROJECT,MODELS,END
    OUT=Path(root).resolve()
    PROJECT,MODELS,END=project,models,end
    transport.OUT=browser.OUT=OUT
    transport.END,transport.MODELS=END,MODELS

def verify():
    frozen=read(OUT/'registered.json')
    if (PROJECT!=frozen['project'] or END.isoformat()!=frozen['end'] or
        {k:list(v) for k,v in MODELS.items()}!=frozen['models']):
        raise ValueError('Stage parameters differ from registration')
    for name,expected in frozen['files'].items():
        if sha(ROOT/name)!=expected: raise ValueError(f'Frozen input changed: {name}')

def register():
    if (OUT/'registered.json').exists():
        verify()
        return
    cap=sum(s[1] for s in MODELS.values())
    balance=check_credits(cap)
    if not balance['sufficient']: raise BudgetStop('Insufficient credit')
    response=httpx.get('https://openrouter.ai/api/v1/models',timeout=30)
    response.raise_for_status()
    routes={r['id']:r['supported_parameters'] for r in response.json()['data']}
    save(OUT/'public.json',core.public_input(PROJECT))
    save(OUT/'browser.json',browser.verify_contract(PROJECT))
    paths=[HERE/'PROTOCOL.md',HERE/'method.py',HERE/'run.py',Path(core.__file__),Path(browser.__file__),
           Path(transport.__file__),ROOT/'src/gui_dna/budget.py',OUT/'public.json',OUT/'browser.json']
    if (OUT/'transfer-protocol.json').exists(): paths.append(OUT/'transfer-protocol.json')
    save(OUT/'registered.json',{'utc':core.now(),'project':PROJECT,'tasks':list(range(1,21)),
                                'end':END.isoformat(),'models':MODELS,'balance':balance,'budget_usd':cap,
                                'parameters':{model:routes[model] for model,*_ in MODELS.values()},
                                'files':{str(p.relative_to(ROOT)):sha(p) for p in paths}})

def build(tag,ledger,data):
    base=OUT/tag/'build'
    if (base/'status.json').exists(): return read(base/'status.json')
    def ask(label,system,obj,limit=8192):
        return transport.request(tag,ledger,base/label,core.messages(system,obj),
                                 f'build/{PROJECT}/{label}',limit)
    repaired=False
    source_status=[]
    try:
        manifest_body=ask('design',method.DESIGN,data,6500)
        try:
            spec=method.manifest(manifest_body,data)
        except INVALID as exc:
            repaired=True
            response=ask('design-repair',method.DESIGN,{'public':data,'previous':manifest_body,
                                                         'validation_error':str(exc)},6500)
            spec=method.manifest(response,data)
        save(base/'manifest.json',spec)
        def file_request(f):
            name=f['path']
            obj={'public_project':data,'manifest':spec,'requested_file':f}
            try:
                raw=ask('source/'+name,method.AUTHOR,obj)
                return name,method.source(raw),None
            except MISSING as exc: return name,None,('missing',str(exc))
            except INVALID as exc: return name,None,('invalid',str(exc))
        modules=[f for f in spec['files'] if f['path']!=spec['entry']]
        with ThreadPoolExecutor(max_workers=6) as pool: pieces=list(pool.map(file_request,modules))
        files={}
        for name,body,error in pieces:
            source_status.append({'path':name,'status':error[0] if error else 'received'})
            if not error: files[name]=body
        missing=next((error for _,_,error in pieces if error and error[0]=='missing'),None)
        invalid=next((error for _,_,error in pieces if error and error[0]=='invalid'),None)
        if missing: raise transport.Unavailable('Source module missing: '+missing[1])
        if invalid: raise ValueError('Invalid source module: '+invalid[1])
        entry=next(f for f in spec['files'] if f['path']==spec['entry'])
        body={'public_project':data,'manifest':spec,'requested_file':entry,'complete_other_files':files}
        files[spec['entry']]=method.source(ask('entry',method.AUTHOR,body,12000))
        save(base/'initial-source.json',files)
        result=method.examine(data,spec,files,base/'initial-page')
        save(base/'initial-public-check.json',result)
        selected='initial'
        repair_status=None
        if not repaired and (result['load_errors'] or not result['probe']['passed']):
            repaired=True
            try:
                raw=ask('source-repair',method.FIX,{'public_project':data,'manifest':spec,'sources':files,
                        'load_errors':result['load_errors'],'public_probe':result['probe']},12000)
                patch=core.files_map(core.parse(raw)['files'])
                if not patch or set(patch)-set(files): raise ValueError('Unexpected replacement source')
                changed=files|patch
                attempt=method.examine(data,spec,changed,base/'repair-page')
                save(base/'repair-public-check.json',attempt)
                if not attempt['load_errors']:
                    selected,files,result='repair',changed,attempt
                repair_status='received'
            except MISSING as exc:
                repair_status='missing'
                if result['load_errors']: raise
            except INVALID as exc:
                repair_status='invalid'
                if result['load_errors']: raise
        if result['load_errors']: raise ValueError('Final public page did not load: '+str(result['load_errors'])[:500])
        save(base/'package.json',{'spec':spec,'sources':files})
        state={'status':'valid','selected':selected,'probe':result['probe'],'repair_used':repaired,
               'repair_status':repair_status,'package_sha256':sha(base/'package.json'),
               'first_files':result['files'],'source_status':source_status}
    except MISSING as exc:
        state={'status':'missing','reason':str(exc),'repair_used':repaired,'source_status':source_status}
    except INVALID as exc:
        state={'status':'invalid','reason':str(exc),'repair_used':repaired,'source_status':source_status}
    save(base/'status.json',state)
    return state

def generate(tag):
    verify()
    data=read(OUT/'public.json')
    ledger=Ledger(OUT/tag/'budget.sqlite3',MODELS[tag][1],MODELS[tag][1])
    built=build(tag,ledger,data)
    pkg=read(OUT/tag/'build/package.json') if built['status']=='valid' else None
    def target(task):
        folder=OUT/tag/'plans'/str(task)
        if (folder/'status.json').exists(): return read(folder/'status.json')
        row={'task':task,'status':built['status']}
        if pkg:
            spec=pkg['spec']
            try:
                raw=transport.request(tag,ledger,folder,core.messages(method.PLAN,{
                    'public_project':core.prefix(data,task),'controls':spec['controls'],
                    'first_example':method.first(spec)}),f'plan/{PROJECT}/{task}',1200)
                choice=method.plan(raw,spec)
                hashes=method.emit(data,pkg['sources'],choice,folder/'page')
                row.update(status='valid',plan=choice,files=hashes)
            except MISSING as exc: row.update(status='missing',reason=str(exc))
            except INVALID as exc: row.update(status='invalid',reason=str(exc))
        else: row['reason']='library '+built['status']
        save(folder/'status.json',row)
        return row
    with ThreadPoolExecutor(max_workers=6) as pool: rows=list(pool.map(target,range(1,21)))
    save(OUT/tag/'seal.json',{'model':MODELS[tag][0],'registered_sha256':sha(OUT/'registered.json'),
         'build_sha256':sha(OUT/tag/'build/status.json'),'plans':{
            str(r['task']):sha(OUT/tag/'plans'/str(r['task'])/'status.json') for r in rows}})

def score(tag):
    verify()
    base=OUT/tag
    seal=read(base/'seal.json')
    assert seal['registered_sha256']==sha(OUT/'registered.json') and seal['build_sha256']==sha(base/'build/status.json')
    built=read(base/'build/status.json')
    contract=read(OUT/'browser.json')
    assert contract==browser.verify_contract(PROJECT)
    def one(pair):
        arm,task=pair
        folder=base/'plans'/str(task)
        assert seal['plans'][str(task)]==sha(folder/'status.json')
        row=read(folder/'status.json') if arm=='self' else built
        outcome={'arm':arm,'task':task,'status':row['status'],'passed':None}
        if row['status']=='invalid': outcome['passed']=False
        elif row['status']=='valid':
            page=folder/'page' if arm=='self' else base/'build'/(built['selected']+'-page')
            files=row['files'] if arm=='self' else built['first_files']
            scored=browser.run_one(OUT,PROJECT,task,page,files,contract)
            outcome.update(passed=scored['passed'],files_sha256=digest(files),
                           report_sha256=scored['report_sha256'],report=scored['report'])
        return outcome
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows=list(pool.map(one,[(arm,i) for arm in ('self','fixed') for i in range(1,21)]))
    save(base/'scores.json',rows)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('register','generate','score','verify'))
    parser.add_argument('tag',choices=MODELS,nargs='?')
    parser.add_argument('--root',type=Path,default=OUT)
    parser.add_argument('--project',default=PROJECT)
    args=parser.parse_args()
    configure(args.root,args.project,MODELS,END)
    if args.action in ('register','verify'):
        return globals()[args.action]()
    if not args.tag: parser.error('A model tag is required')
    globals()[args.action](args.tag)

if __name__=='__main__': main()
