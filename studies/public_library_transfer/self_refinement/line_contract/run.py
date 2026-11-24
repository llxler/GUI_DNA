"""Line-contract staged Self. Reuse the frozen planner, transport and evaluator."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath
import re

import httpx

from gui_dna.budget import BudgetStop
from scripts.check_openrouter_credits import check_credits
from studies.public_library_transfer import browser, core
from studies.public_library_transfer.self_refinement import method, run as base
from studies.study_io import ROOT, read, sha

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/self-line-contract-20261124'
PROJECT='table'
MODELS={k:(model,1.90,pin,pout) for k,(model,_,pin,pout) in base.MODELS.items()}
END=base.END
save=core.save

ARCHITECT="""Design an implementable state and module architecture for the supplied public website. You will implement it yourself next. Read ALL requests and the actual starter. First output 1–4 lines, exactly like this (replace the placeholders):
CONTROL|unique-name|visible behavior with this switch on|visible behavior with this switch off
Each control expresses an actual incompatible UI behavior or revision. Put the richer/default choice first. Do not turn unrelated features into alternatives. Build shared functionality unconditionally. Controls have the two fixed STRING values on and off; no JSON, HTML, code, labels or task numbers in these lines. Choose one public initial-page interaction with an observable effect. Write it as:
PROBE|existing CSS selector|click or dblclick or contextmenu or input or change or mouseover|CSS selector visible after the interaction
Next design module interfaces for ALL listed file paths: a line FILE|path|exported signatures, dependencies, persistent state and event ownership. Include exact UI selectors, literals, state semantics, update paths and keyboard/mouse lifecycles from public requirements in your subsequent design notes. Assume each file will be written by a separate call. Provide enough concrete detail for them to agree; continue to implement all requirements, including prerequisites. Avoid task-number branches, external dependencies and per-target pages. No tools or implementation code."""
AUTHOR=method.AUTHOR+""" Read the actual source when supplied. JS imports must resolve to one of the exact listed paths. Preserve the required public module names. Prefer namespace imports for other generated modules and use the specified signatures. Share mutable state and coordinate event setup exactly as the contract describes. Do not assume an element exists before creating it. Implement all publicly requested stable features in every configuration; only incompatible choices change. The first example uses every option's string value "on"."""
REPLACE="""The generated public GUI package failed the following public check. Write one complete corrected version of the requested source file, raw code only. All other modules remain as shown. Fix the observed problem and preserve the publicly required behavior, configured alternatives and exact public interfaces. No tools, no external inputs."""

def configure(root,project,models,end):
    global OUT,PROJECT,MODELS,END
    OUT=Path(root).resolve()
    PROJECT,MODELS,END=project,models,end
    base.configure(OUT,PROJECT,MODELS,END)
    base.build=build

def register():
    if (OUT/'registered.json').exists():
        base.verify()
        return
    cap=sum(values[1] for values in MODELS.values())
    balance=check_credits(cap)
    if not balance['sufficient']: raise BudgetStop('Insufficient credit')
    res=httpx.get('https://openrouter.ai/api/v1/models',timeout=30)
    res.raise_for_status()
    catalog={m['id']:m['supported_parameters'] for m in res.json()['data']}
    public=core.public_input(PROJECT)
    save(OUT/'public.json',public)
    save(OUT/'browser.json',browser.verify_contract(PROJECT))
    save(OUT/'file-layout.json',layout(public))
    paths=[HERE/'PROTOCOL.md',Path(__file__),Path(base.__file__),Path(method.__file__),Path(core.__file__),
           Path(browser.__file__),Path(base.transport.__file__),ROOT/'src/gui_dna/budget.py',
           OUT/'public.json',OUT/'browser.json',OUT/'file-layout.json']
    if (OUT/'transfer-protocol.json').exists(): paths.append(OUT/'transfer-protocol.json')
    save(OUT/'registered.json',{'utc':core.now(),'project':PROJECT,'tasks':list(range(1,21)),'end':END.isoformat(),
        'models':MODELS,'balance':balance,'budget_usd':cap,'parameters':{m:catalog[m] for m,*_ in MODELS.values()},
        'files':{str(p.relative_to(ROOT)):sha(p) for p in paths}})

def layout(data):
    entry=re.findall(r'<script\b[^>]*\bsrc=["\x27]([^"\x27]+)["\x27]',data['starter']['index.html'],re.I)
    if len(entry)!=1: raise ValueError('Expected one public JS starter')
    entry=str(PurePosixPath(entry[0]))
    paths={p:[] for p in data['starter'] if p.endswith(('.js','.css','.mjs'))}
    for request in data['requirements']:
        names=re.findall(r'(?<![\w./-])(?:[\w-]+/)*[A-Za-z_][\w-]*\.(?:m?js|css)\b',request['description'])
        for name in sorted(set(names)): paths.setdefault(name,[]).append(request['id'])
    core.files_map([{'path':p,'content':''} for p in paths])
    if entry not in paths: raise ValueError('Missing public entrypoint')
    return {'entry':entry,'public_paths':dict(sorted(paths.items()))}

def decode(body, paths):
    controls=[]
    names=set()
    probe=None
    for line in body.splitlines():
        value=line.strip().strip('`').strip().lstrip('-* ').strip()
        parts=[s.strip() for s in value.split('|')]
        if len(parts)==4 and parts[0].upper()=='CONTROL':
            _,name,on,off=parts
            if re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_-]{0,63}',name) and name not in names and on and off:
                controls.append({'id':name,'values':['on','off'],'example':'on',
                                 'description':'on: '+on+' / off: '+off})
                names.add(name)
        if len(parts)==4 and parts[0].upper()=='PROBE' and not probe:
            _,sel,event,visible=parts
            if sel and visible and event.lower() in ('click','dblclick','contextmenu','input','change','mouseover'):
                probe={'selector':sel[:512],'event':event.lower(),'visible':visible[:512]}
    if not 1 <= len(controls) <= 4: raise ValueError('Output 1–4 separate CONTROL|short-field-name|on meaning|off meaning lines.')
    files=[{'path':name,'public_mentions':ids} for name,ids in paths['public_paths'].items()]
    return {'controls':controls,'files':files,'entry':paths['entry'],'smoke':probe,'architecture':body}

def public_check(data,spec,files,dest):
    if spec['smoke']:
        return method.examine(data,spec,files,dest)
    hashes=method.emit(data,files,method.first(spec),dest)
    return {'files':hashes,'load_errors':browser.public_load(data['project'],dest),'probe':None}

def repair_path(errors,entry,files):
    for error in errors:
        for name in sorted(files,key=len,reverse=True):
            if name in error: return name
    return entry

def build(tag,ledger,data):
    folder=OUT/tag/'build'
    if (folder/'status.json').exists(): return read(folder/'status.json')
    paths=read(OUT/'file-layout.json')
    def ask(label,prompt,body,limit=8192):
        return base.transport.request(tag,ledger,folder/label,core.messages(prompt,body),f'build/{PROJECT}/{label}',limit)
    repair_used=False
    statuses=[]
    try:
        public_design={'public_project':data,'required_files':paths}
        raw=ask('design',ARCHITECT,public_design,6500)
        try: spec=decode(raw,paths)
        except base.INVALID as exc:
            repair_used=True
            raw=ask('design-repair',ARCHITECT,dict(public_design,previous=raw,error=str(exc)),6500)
            spec=decode(raw,paths)
        save(folder/'manifest.json',spec)
        def source_file(name):
            try:
                body=ask('source/'+name,AUTHOR,{'public_project':data,'manifest':spec,'requested_file':name})
                return name,method.source(body),None
            except base.MISSING as exc: return name,None,('missing',str(exc))
            except base.INVALID as exc: return name,None,('invalid',str(exc))
        with ThreadPoolExecutor(max_workers=6) as pool:
            pieces=list(pool.map(source_file,[p for p in paths['public_paths'] if p!=spec['entry']]))
        files={}
        for name,body,error in pieces:
            statuses.append({'path':name,'status':error[0] if error else 'received'})
            if not error: files[name]=body
        missing=next((error for _,_,error in pieces if error and error[0]=='missing'),None)
        invalid=next((error for _,_,error in pieces if error and error[0]=='invalid'),None)
        if missing: raise base.transport.Unavailable('Source module missing: '+missing[1])
        if invalid: raise ValueError('Source invalid: '+invalid[1])
        entry=spec['entry']
        body={'public_project':data,'manifest':spec,'requested_file':entry,'complete_other_files':files}
        files[entry]=method.source(ask('entry',AUTHOR,body,12000))
        save(folder/'initial-source.json',files)
        check=public_check(data,spec,files,folder/'initial-page')
        save(folder/'initial-public-check.json',check)
        selected='initial'
        repair_status=None
        if not repair_used and (check['load_errors'] or (check['probe'] and not check['probe']['passed'])):
            repair_used=True
            name=repair_path(check['load_errors'],entry,files)
            try:
                body={'public_project':data,'manifest':spec,'sources':files,'requested_file':name,
                      'public_load_errors':check['load_errors'],'public_probe':check['probe']}
                replacement=method.source(ask('source-repair',REPLACE,body,12000))
                changed=files|{name:replacement}
                attempted=public_check(data,spec,changed,folder/'repair-page')
                save(folder/'repair-public-check.json',attempted)
                if not attempted['load_errors']: selected,files,check='repair',changed,attempted
                repair_status='received'
            except base.MISSING:
                repair_status='missing'
                if check['load_errors']: raise
            except base.INVALID:
                repair_status='invalid'
                if check['load_errors']: raise
        if check['load_errors']: raise ValueError('Final public page failed to load: '+str(check['load_errors'])[:500])
        save(folder/'package.json',{'spec':spec,'sources':files})
        state={'status':'valid','selected':selected,'probe':check['probe'],'repair_used':repair_used,
               'repair_status':repair_status,'package_sha256':sha(folder/'package.json'),
               'first_files':check['files'],'source_status':statuses}
    except base.MISSING as exc:
        state={'status':'missing','reason':str(exc),'repair_used':repair_used,'source_status':statuses}
    except base.INVALID as exc:
        state={'status':'invalid','reason':str(exc),'repair_used':repair_used,'source_status':statuses}
    save(folder/'status.json',state)
    return state

generate=base.generate
score=base.score

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('register','verify','generate','score'))
    parser.add_argument('tag',choices=MODELS,nargs='?')
    parser.add_argument('--root',type=Path,default=OUT)
    parser.add_argument('--project',default=PROJECT)
    args=parser.parse_args()
    configure(args.root,args.project,MODELS,END)
    if args.action=='register': return register()
    if args.action=='verify': return base.verify()
    if not args.tag: parser.error('Model tag required')
    globals()[args.action](args.tag)

if __name__=='__main__': main()
