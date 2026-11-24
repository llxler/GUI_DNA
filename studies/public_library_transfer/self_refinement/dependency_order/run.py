"""Compile two independently authored JavaScript libraries in dependency order."""
import argparse
import json
from pathlib import Path
import subprocess

import httpx

from gui_dna.budget import BudgetStop
from scripts.check_openrouter_credits import check_credits
from studies.public_library_transfer import browser, core
from studies.public_library_transfer.self_refinement import method
from studies.public_library_transfer.self_refinement.dependency_order import transport
from studies.public_library_transfer.self_refinement.line_contract import run as lines
from studies.public_library_transfer.self_refinement.native import run as engine
from studies.study_io import ROOT, read, sha

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/self-dependency-table-20261124'
PROJECT='table'
CAP=1.30
COMMON='app-core.js'
DESIGN=engine.DESIGN+"""
Output an ordered_files list in true dependency-first order. The final starter entrypoint imports other modules and mounts the entire UI. When many modules depend on the same state or interact, put their shared working implementation in one optional app-core.js module with NO imports, then implement facades at the publicly specified paths. Avoid cycles. Do not scatter a single state machine among modules that each assume functions the others might implement. Explicitly specify how to run and observe each primary UI operation, labels, CSS, geometry, selectors, flags and state; all stable requirements should work together. Make the smoke a real initial user gesture with an observable effect. Do not use one mutually exclusive control to represent unrelated behaviors that need to coexist."""
AUTHOR=method.AUTHOR+""" You are writing the next file in dependency-first order. You have complete prior sources and mechanically listed real exports. Import ONLY actually available names from those sources. No speculative imports of future files. Write the complete implementation for your responsibility, including the exact user interactions specified in the public requirements. Stable behaviors must always work. If this is the shared core, implement the real state machine and all core operations now. If this is the entrypoint, initialize the app on the supplied starter and attach the actual generated implementation. If this is styling, include the exact public geometric and visible behavior contract. Use the compiled control identifiers choice1, choice2, etc., with their actual documented on/off string values."""
LINK_REPAIR=AUTHOR+""" Your previous version introduced the supplied ES module link error. Rewrite this same file and import only verified exports, preserving the whole implementation."""
FIX=engine.FIX+""" The actual dependency graph and complete per-file sources are provided. Fix all missing exports/imports, then ensure the entrypoint can initialize interactions as specified. Return clearly named replacements and keep the publicly named modules in place. If you need to fix both ends of an API, replace BOTH files."""

def configure():
    engine.OUT=OUT
    engine.PROJECTS=(PROJECT,)
    engine.CAP=CAP
    engine.transport=transport
    engine.build=build

def register():
    if (OUT/'registered.json').exists():
        engine.verify()
        return
    balance=check_credits(CAP)
    if not balance['sufficient']: raise BudgetStop('Insufficient credits')
    response=httpx.get('https://openrouter.ai/api/v1/models/'+transport.MODEL+'/endpoints',timeout=30)
    response.raise_for_status()
    endpoints=[e for e in response.json()['data']['endpoints'] if e['provider_name']==transport.PROVIDER]
    if not any({'response_format','structured_outputs','temperature'}<=set(e['supported_parameters']) for e in endpoints):
        raise ValueError('Required route parameters unavailable')
    data=core.public_input(PROJECT)
    root=OUT/PROJECT
    for name,val in [('public',data),('paths',lines.layout(data)),('browser',browser.verify_contract(PROJECT))]:
        core.save(root/(name+'.json'),val)
    files=[HERE/'PROTOCOL.md',Path(__file__),Path(transport.__file__),HERE/'graph.cjs',Path(engine.__file__),
           Path(core.__file__),Path(method.__file__),Path(lines.__file__),Path(browser.__file__),
           ROOT/'src/gui_dna/budget.py',root/'paths.json',root/'browser.json',root/'public.json']
    core.save(OUT/'registered.json',{'utc':core.now(),'model':transport.MODEL,'projects':[PROJECT],
        'deadline':transport.END.isoformat(),'cap_usd':CAP,'balance':balance,'targets':list(engine.TASKS),
        'groups':list(engine.GROUPS),'provider':transport.PROVIDER,'route_parameters':endpoints[0]['supported_parameters'],
        'temperature':.2,'seed':None,'reasoning':None,'files':{str(p.relative_to(ROOT)):sha(p) for p in files}})

def graph(files):
    result=subprocess.run(['node','--experimental-vm-modules',str(HERE/'graph.cjs')],input=json.dumps(files),
                          capture_output=True,text=True,timeout=15,check=True)
    return json.loads(result.stdout)

def design_spec(raw,paths):
    manifest=core.parse(raw)
    controls=[]
    if not 1<=len(manifest['choices'])<=4: raise ValueError('Expected one to four selected dimensions')
    for i,c in enumerate(manifest['choices'],1):
        if c['first'] not in ('on','off') or not c['on'].strip() or not c['off'].strip():
            raise ValueError('Invalid binary choice')
        controls.append({'id':'choice'+str(i),'values':['on','off'],'example':c['first'],
                         'description':'on: '+c['on']+' / off: '+c['off']})
    entry=paths['entry']
    allowed=set(paths['public_paths'])|{COMMON}
    order=[]
    for name in manifest['ordered_files']+list(paths['public_paths']):
        if name in allowed and name not in order and name!=entry: order.append(name)
    order.append(entry)
    return {'controls':controls,'architecture':manifest['architecture'],'smoke':manifest['smoke'],'entry':entry,'files':order}

def build(root,group,ask,data):
    folder=root/group/'build'
    if (folder/'status.json').exists(): return read(folder/'status.json')
    paths=read(root/'paths.json')
    allowed=list(paths['public_paths'])+[COMMON]
    schema=core.obj({'architecture':core.S,'ordered_files':core.array({'type':'string','enum':allowed}),
                     'choices':core.array(engine.SWITCH),'smoke':engine.SMOKE})
    try:
        design=ask(folder/'design',DESIGN,{'public_project':data,'public_paths':paths,
            'optional_shared_core':COMMON},'design',5500,schema)
        spec=design_spec(design,paths)
        core.save(folder/'manifest.json',spec)
        files={}
        graph_repairs=0
        previous=graph(files)
        for i,name in enumerate(spec['files']):
            label=f'{i+1:02d}'
            body={'public_project':data,'manifest':spec,'requested_file':name,'previous_sources':files,
                  'verified_graph':previous}
            raw=ask(folder/'sources'/label,AUTHOR,body,'source/'+name,11000)
            received=method.source(raw)
            state=graph(files|{name:received})
            if graph_repairs<2 and state['errors'] and state['errors']!=previous['errors']:
                graph_repairs+=1
                repair=ask(folder/'sources'/label/'repair',LINK_REPAIR,dict(body,previous_answer=received,
                    public_link_errors=state['errors']),'link-repair/'+name,11000)
                revised=method.source(repair)
                new_graph=graph(files|{name:revised})
                if not new_graph['errors'] or len(new_graph['errors'])<len(state['errors']):
                    received,state=revised,new_graph
            files[name]=received
            previous=state
            core.save(folder/'sources'/label/'link.json',{'path':name,**state})
        initial=method.examine(data,spec,files,folder/'initial')
        initial['graph']=graph(files)
        core.save(folder/'initial-check.json',initial)
        selected,check='initial',initial
        if initial['graph']['errors'] or initial['load_errors'] or not initial['probe']['passed']:
            body={'public_project':data,'manifest':spec,'sources':files,'dependency_graph':initial['graph'],
                  'public_browser_load_errors':initial['load_errors'],'public_interaction':initial['probe']}
            try:
                answer=ask(folder/'repair',FIX,body,'repair',14000,engine.FILE_SCHEMA)
                patch=core.files_map(core.parse(answer)['files'])
                if not patch or set(patch)-set(files): raise ValueError('Unrecognized repair path')
                revised=files|patch
                checked=method.examine(data,spec,revised,folder/'repaired')
                checked['graph']=graph(revised)
                core.save(folder/'repaired-check.json',checked)
                if not checked['graph']['errors'] and not checked['load_errors']:
                    selected,files,check='repaired',revised,checked
            except engine.MISSING+engine.INVALID:
                if initial['graph']['errors'] or initial['load_errors']: raise
        if check['graph']['errors'] or check['load_errors']:
            raise ValueError('Final graph or public load failed: '+str(check['graph']['errors']+check['load_errors'])[:420])
        core.save(folder/'package.json',{'spec':spec,'sources':files})
        row={'status':'valid','package_sha256':sha(folder/'package.json'),'fixed_page':'build/'+selected,
             'files':check['files'],'probe':check['probe'],'public_graph_sha256':sha(folder/(selected+'-check.json'))}
    except engine.MISSING as exc: row={'status':'missing','reason':str(exc)}
    except engine.INVALID as exc: row={'status':'invalid','reason':str(exc)}
    core.save(folder/'status.json',row)
    return row

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('register','verify','generate','score'))
    parser.add_argument('group',nargs='?',choices=engine.GROUPS)
    args=parser.parse_args()
    configure()
    if args.action=='register': return register()
    if args.action=='verify': return engine.verify()
    if args.action=='score': return engine.score(PROJECT)
    if not args.group: parser.error('Specify a group')
    engine.generate(PROJECT,args.group)

if __name__=='__main__': main()
