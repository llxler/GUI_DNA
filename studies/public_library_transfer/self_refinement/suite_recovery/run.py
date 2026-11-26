"""Independently build verified controllers and feature libraries for the eight suite cells."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import threading
from unittest.mock import patch

from gui_dna.budget import BudgetStop, Ledger
from scripts.check_openrouter_credits import check_credits
from studies.public_library_transfer import core, browser
from studies.public_library_transfer.backbone_suites import run as suite
from studies.public_library_transfer.self_refinement.duo_components import run as duo
from studies.public_library_transfer.self_refinement.duo_components.compact import runtime
from studies.public_library_transfer.self_refinement.todomvc.verified_controller import run as todo
from studies.study_io import ROOT, now, read, sha
from studies.webbench.self_build_modules import run as web

HERE = Path(__file__).resolve().parent
OUT = ROOT/'artifacts/suite-self-recovery-20261125'
CAP = 2.5
ORDER = [('todomvc', t) for t in ('gemma','qwen9','mistral','qwen')] + [
    ('duo', t) for t in ('oss','deepseek-flash','gemma','mistral')]
SINGLES = threading.BoundedSemaphore(2)
TRANSPORT = (BudgetStop,web.original.Unavailable)
BUILD = todo.BUILD + ('\nPut each switch case in its own braces. Follow the shape of the shell events and '
                      'use separate ids for items. In select, derive a fresh view without modifying state.')
COMPONENT = duo.SYS + (' Use the provided React props and exact callback arguments. Render the requested '
                       'controls and messages in accessible markup. Handle rejected promises inside the event handler.')


def template(project,tag,stage):
    group = 'todomvc' if project=='todomvc' else 'blogging'
    if stage=='build':
        path=suite.OUT/tag/'build'/group/'call/request.json'
    else:
        tasks,_=suite.inputs()
        task=next(t for t,row in sorted(tasks.items()) if row['group']==group)
        path=suite.OUT/tag/'targets'/task/'direct/call/request.json'
    return {k:v for k,v in read(path)['body'].items() if k!='messages'}


def register():
    files=[Path(__file__),HERE/'PROTOCOL.md',Path(web.__file__),Path(todo.__file__),Path(todo.public.__file__),
           todo.public.HERE/'probes.cjs',Path(duo.__file__),Path(runtime.__file__),Path(duo.single.__code__.co_filename),
           Path(duo.bundle.__code__.co_filename),Path(suite.__file__),suite.RESULT,suite.SOURCE/'targets.json',
           suite.SOURCE/'build-inputs.json',todo.binding.HERE/'extract.cjs',duo.original.HERE/'direct.cjs']
    for project,tag in ORDER:
        assert template(project,tag,'build')['model']==template(project,tag,'plan')['model']==suite.MODELS[tag][0]
    sources={str(f.relative_to(ROOT)):sha(f) for f in files}
    path=OUT/'registration.json'
    if path.exists():
        assert read(path)['sources']==sources
        return
    balance=check_credits(CAP)
    assert balance['sufficient'] and CAP+web.CAP==10
    core.save(path,dict(utc=now(),cells=ORDER,reps=['a','b'],deadline=web.END.isoformat(),
                        cap=CAP,balance=balance,sources=sources))


def call(ledger,case,path,messages,stage,limit):
    return web.request(ledger,case,path,messages,stage,limit)


def controller(ledger,case,root,builder):
    features=list(builder['spec'])
    messages=core.messages(BUILD,builder)
    raw=call(ledger,case,root/'first',messages,'build',6500)
    ast,info=todo.evaluate(raw,features,True)
    attempted=[info]
    if not todo.menu(info) or len(todo.public.passes(info['checks']))<len(info['checks']):
        diagnostics={'behavior':todo.public.diagnostic(info['checks']), 'options':todo.menu(info)}
        repair=messages+[dict(role='assistant',content=raw),dict(role='user',content=json.dumps(diagnostics)+
                ' Return your complete corrected controller. Demonstrate each control via a real behavior change.')]
        revised=call(ledger,case,root/'repair',repair,'build',6500)
        nxt,details=todo.evaluate(revised,features,True)
        attempted.append(details)
        if todo.acceptance(info,details)=='accepted':
            ast,info=nxt,details
    core.save(root/'observations.json',attempted)
    if not todo.menu(info) or not todo.public.passes(info['checks']):
        return {'status':'build_failed','reason':'No witnessed switch or no working public action'}
    path=root/'library.json'
    core.save(path,{'ast':ast,'options':todo.menu(info)})
    return dict(status='valid',library=str(path.relative_to(ROOT)),library_sha256=sha(path))


def component(ledger,case,root,group,name,brief):
    state=root/name/'status.json'
    if state.exists():
        return read(state)
    msg=core.messages(COMPONENT,{'feature':name,'single_feature_contract':brief})
    best=None
    for i in (1,2):
        folder=root/name/f'attempt-{i}'
        try:
            raw=call(ledger,case,folder/'call',msg,'build',4200)
        except TRANSPORT as exc:
            if not best:
                best=dict(status='missing',reason=str(exc))
            break
        code=duo.extract(raw)
        feedback='Return one complete default-export React module with valid JSX.'
        if code:
            with SINGLES:
                _,res=runtime.single((folder/'public',group,name,code))
            cases=read(folder/'public/jest.json')['testResults'][0]['assertionResults']
            passed=sum(r['status']=='passed' for r in cases)
            if best is None or passed>best['public_passes']:
                core.save(folder/'source.json',dict(source=code))
                best=dict(status='valid',public_passes=passed,source=str((folder/'source.json').relative_to(ROOT)),
                          source_sha256=sha(folder/'source.json'),public_report_sha256=res['report_sha256'])
            if passed==2:
                break
            feedback=json.dumps(res['feedback'],ensure_ascii=False)[:5500]
        msg=msg+[dict(role='assistant',content=raw[:18000]),dict(role='user',content=feedback+
                '\nReturn your full corrected React module.')]
    result=best or dict(status='build_failed',reason='Could not compile either delivered component')
    core.save(state,result)
    return result


def feature_library(ledger,case,root,group,briefs):
    def one(name):
        return name,component(ledger,case,root,group,name,briefs[name])
    with ThreadPoolExecutor(max_workers=4) as pool:
        modules=dict(pool.map(one,sorted(briefs)))
    if any(m['status']=='missing' for m in modules.values()):
        status='missing'
    elif all(m['status']=='valid' for m in modules.values()) and any(m['public_passes']==2 for m in modules.values()):
        status='valid'
    else:
        status='build_failed'
    return dict(status=status,components=modules)


def candidates(ledger,case,root,task,target,lib):
    if lib['status']!='valid':
        return {m:dict(status=lib['status']) for m in ('self','fixed')}
    public=target['public']
    setting=None
    if case[0]=='todomvc':
        assert sha(ROOT/lib['library'])==lib['library_sha256']
        data=read(ROOT/lib['library'])
        base=todo.literal(data['ast'])['first']
        options=data['options']
        msg=core.messages('Set each witnessed behavior switch for this public TodoMVC request. '
                         'Return just a JSON object with a boolean per exact option name.',
                         dict(target=public,options=options))
        def compile_plan(values):
            return {'candidate.js':todo.instance(data['ast'],{**base,**values})}
        fixed=compile_plan({})
    else:
        modules=[]
        for name,entry in sorted(lib['components'].items()):
            assert sha(ROOT/entry['source'])==entry['source_sha256']
            modules.append(dict(id=name,source=read(ROOT/entry['source'])['source']))
        names=[m['id'] for m in modules]
        msg=core.messages('Choose the two registered components which implement the public request. '
                         'Return a JSON array of two distinct exact identifiers.',dict(target=public,registered=names))
        def compile_plan(values):
            return duo.bundle(public['module'],dict(components=modules),values)
        fixed=compile_plan(dict(first=names[0],second=names[1]))
    def store(arm,files,selected):
        path=root/'targets'/task/arm/'files.json'
        core.save(path,files)
        return dict(status='valid',file=str(path.relative_to(ROOT)),files_sha256=sha(path),setting=selected)
    rows=dict(fixed=store('fixed',fixed,'registered default'))
    try:
        raw=call(ledger,case,root/'targets'/task/'plan',msg,'plan',8192)
        if case[0]=='todomvc':
            setting=web.parse_json(raw)
            if not isinstance(setting,dict) or set(setting)!=set(options) or any(type(v)!=bool for v in setting.values()):
                raise ValueError('Invalid witnessed option set')
        else:
            setting=duo.parse_plan(raw,names)
            if not setting:
                raise ValueError('Invalid component pair')
        rows['self']=store('self',compile_plan(setting),setting)
    except TRANSPORT as exc:
        rows['self']=dict(status='missing',reason=str(exc))
    except web.ERRORS as exc:
        rows['self']=dict(status='invalid',reason=str(exc)[:250])
    return rows


def branch(ledger,case):
    project,tag,rep=case
    root=OUT/project/tag/rep
    with browser.lock(root/'.lock'):
        if (root/'seal.json').exists():return
        tasks,briefs=suite.inputs()
        groups=['todomvc'] if project=='todomvc' else list(duo.original.GROUPS)
        builds={}
        for g in groups:
            base=root/'build'/g
            status=base/'status.json'
            if not status.exists():
                try:
                    state=(controller(ledger,case,base,briefs[g]) if project=='todomvc' else
                           feature_library(ledger,case,base,g,briefs[g]))
                except TRANSPORT as exc:
                    state=dict(status='missing',reason=str(exc))
                core.save(status,state)
            builds[g]=read(status)
        rows={}
        def plan(t):
            return t,candidates(ledger,case,root,t,tasks[t],builds[tasks[t]['group']])
        with ThreadPoolExecutor(max_workers=3) as pool:
            rows=dict(pool.map(plan,sorted(t for t,r in tasks.items() if r['group'] in groups)))
        core.save(root/'seal.json',dict(case=case,registration_sha256=sha(OUT/'registration.json'),builds=builds,rows=rows))
        print(case,[s['status'] for s in builds.values()],flush=True)


def main():
    register()
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    cases=[(project,tag,r) for project,tag in ORDER for r in ('a','b')]
    with patch.multiple(web,OUT=OUT,template=template), ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda c:branch(ledger,c),cases))


if __name__=='__main__':
    main()
