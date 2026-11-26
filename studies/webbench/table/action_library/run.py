"""Run paired preparations and first-choice deployments under the registered daily allowance."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
import os
import re
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import ROOT,read,sha,now
from studies.webbench.compact_planning import run as compact
from studies.webbench.typed_components import run as typed
from . import build,public

HERE=Path(__file__).resolve().parent
OUT=ROOT/'artifacts/table-action-library-20261126'
RESULT=HERE/'result.json'
CAP=4.50
END=datetime(2026,11,26,4,42,tzinfo=timezone.utc)
TAGS=('gemma','qwen9','gpt5')
REPS={'gemma':('a','b'),'qwen9':('a','b'),'gpt5':('a',)}
BASE_TEMPLATE=compact.base.template


def settings(project,tag,stage):
    if tag=='gpt5':
        return dict(model='openai/gpt-5',provider=dict(sort='price',allow_fallbacks=True,
                    max_price=dict(prompt=1.50,completion=12,request=0)),reasoning=dict(effort='low'))
    body=BASE_TEMPLATE(project,tag,stage)
    if tag in ('qwen9','deepseek-flash','deepseek-pro'):body['reasoning']=dict(enabled=False)
    return body


def register():
    path=OUT/'registration.json'
    if path.exists():
        reg=read(path)
        assert all(sha(ROOT/p)==v for p,v in reg['sources'].items())
        return reg
    files=[Path(__file__),Path(build.__file__),Path(public.__file__),HERE/'host.js',HERE/'PROTOCOL.md',
           Path(compact.base.__file__),build.modules.HERE/'function.cjs',build.modules.ACORN, Path(browser.__file__)]
    data=compact.base.old_root('table','qwen9')/'inputs/table'
    files.extend([data/'public.json',data/'browser.json'])
    balance=check_credits(CAP)
    assert balance['sufficient']
    core.save(path,dict(utc=now(),deadline=END.isoformat(),cap=CAP,repetitions=REPS,targets=list(range(1,21)),balance=balance,
           generators={t:settings('table',t,'plan')['model'] for t in typed.ALL_TAGS},public=str((data/'public.json').relative_to(ROOT)),
           sources={str(p.relative_to(ROOT)):sha(p) for p in files}))
    return read(path)


def prepare(tag,rep,pub,ledger):
    root=OUT/tag/rep
    path=root/'library.json'
    if path.exists():return read(path)
    def action(name,phase,previous=None,feedback=None):
        dest=root/'calls'/name/phase
        messages=build.messages(name,pub,previous,feedback)
        raw=compact.base.request(ledger,('table',tag,rep),dest,messages,'build',3200)
        return build.extract(name,raw)
    def first(name):
        try:return action(name,'first')
        except ValueError as err:return action(name,'syntax',feedback=str(err))
    funcs={}
    history=[]
    try:
        # The first billable call is a usable foundation; rejection stops this model.
        funcs['markSelection']=first('markSelection')
        names=list(build.ACTIONS)[1:]
        with ThreadPoolExecutor(max_workers=3) as pool:funcs.update(zip(names,pool.map(first,names),strict=True))
        probe=public.measure(OUT,build.page(pub,funcs,build.OPTIONS,root/'public/initial'))
        history.append(probe)
        failing=[key for key,v in probe['checks'].items() if not v]
        owners=list(dict.fromkeys(owner for key in failing for owner in public.OWNERS[key]))
        for name in owners:
            relevant=[k for k in failing if name in public.OWNERS[k] and not probe['checks'][k]]
            if not relevant:continue
            msg=dict(failed=relevant,public_actions={k:probe['checks'][k] for k in public.OWNERS},errors=probe['errors'])
            try:changed=action(name,'repair',funcs[name],msg)
            except ValueError:continue
            candidate=funcs|{name:changed}
            trial=public.measure(OUT,build.page(pub,candidate,build.OPTIONS,root/'public'/name))
            keep=all(not old or trial['checks'][k] for k,old in probe['checks'].items()) and (not trial['errors'] or bool(probe['errors']))
            if keep:funcs,probe=candidate,trial
            history.append(dict(name=name,retained=keep,**trial))
        status='valid' if public.admitted(probe) else 'build_failed'
        why='' if status=='valid' else 'Public table actions or browser errors'
    except typed.MISSING as e:status,why='missing',str(e)
    except (ValueError,KeyError,TypeError) as e:status,why='build_failed',str(e)
    out=dict(tag=tag,rep=rep,status=status,reason=why,public=history,functions=funcs)
    core.save(path,out)
    print('prepared',tag,rep,status,flush=True)
    return out


def generate(reg):
    pub=read(ROOT/reg['public'])
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    jobs=[(t,r) for t in TAGS for r in REPS[t]]
    def one(pair):
        tag,rep=pair
        lib=prepare(tag,rep,pub,ledger)
        if lib['status']!='valid':return
        folder=OUT/tag/rep
        for target in (typed.ALL_TAGS if tag=='gpt5' else (tag,)):
            seal=folder/target/'deployment.json'
            if seal.exists():continue
            fixed=build.page(pub,lib['functions'],build.OPTIONS,folder/target/'fixed')
            def pick(n):
                dest=folder/target/str(n)
                menu=[dict(enabled=s) for s in build.PROFILES]
                msgs=compact.make_messages(pub,n,dict(plan_documentation={k:v[4] for k,v in build.ACTIONS.items()}),menu,False)
                try:
                    raw=compact.base.request(ledger,('table',target,rep),dest/'call',msgs,'plan',4096)
                    index=compact.base.uncode(raw).strip()
                    if not re.fullmatch('[0-9]',index):raise ValueError('Expected a single index')
                    value=build.page(pub,lib['functions'],build.PROFILES[int(index)],dest/'page')
                    return value|dict(index=int(index))
                except typed.MISSING as e:return dict(status='missing',reason=str(e))
                except ValueError as e:return dict(status='invalid',reason=str(e))
            with ThreadPoolExecutor(max_workers=3) as pool:plans=list(pool.map(pick,reg['targets']))
            rows=[]
            for n,plan in zip(reg['targets'],plans,strict=True):
                rows.extend([dict(project='table',arm='planned',task=n,**plan),dict(project='table',arm='fixed',task=n,**fixed)])
            core.save(seal,dict(target=target,library=sha(folder/'library.json'),rows=rows))
    with patch.multiple(compact.base,OUT=OUT,END=END,template=settings), ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(one,[jobs[-1],*jobs[:-1]]))
    empty=build.page(pub,{},[],OUT/'host')
    files=[*OUT.glob('*/*/library.json'),*OUT.glob('*/*/*/deployment.json')]
    core.save(OUT/'seal.json',dict(registration=sha(OUT/'registration.json'),files={str(f.relative_to(OUT)):sha(f) for f in sorted(files)},empty=empty))


def score(reg):
    seal=read(OUT/'seal.json')
    assert seal['registration']==sha(OUT/'registration.json') and all(sha(OUT/p)==v for p,v in seal['files'].items())
    for k in tuple(os.environ):
        if k.endswith(('_API_KEY','_AUTH_TOKEN','_ACCESS_TOKEN')):os.environ.pop(k)
    browser.OUT=OUT
    protocol=browser.verify_contract('table')
    assert protocol==read((ROOT/reg['public']).with_name('browser.json'))
    def evaluate(rows):
        graded=browser.evaluate(rows,OUT,{'table':protocol},3)
        return [dict(task=r['task'],arm=r['arm'],status=r['status'],passed=False if r['status']=='invalid' else r['passed'],
                     report_sha256=r.get('report_sha256'),index=r.get('index')) for r in graded]
    controls=evaluate([dict(project='table',task=n,arm='host',**seal['empty']) for n in reg['targets']])
    cases=[]
    for tag in TAGS:
        for rep in REPS[tag]:
            root=OUT/tag/rep
            lib=read(root/'library.json')
            deployments={}
            for f in sorted(root.glob('*/deployment.json')):
                candidate=read(f)
                assert candidate['library']==sha(root/'library.json')
                deployments[candidate['target']]=evaluate(candidate['rows'])
            cases.append(dict(tag=tag,rep=rep,status=lib['status'],reason=lib['reason'],public=lib['public'],
                              library_sha256=sha(root/'library.json'),deployments=deployments))
    core.save(RESULT,dict(registration=sha(OUT/'registration.json'),seal=sha(OUT/'seal.json'),cases=cases,host=controls,
                          cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('register','generate','score'))
    action=parser.parse_args().action
    with browser.lock(OUT/(action+'.lock')):
        reg=register()
        if action=='generate':generate(reg)
        if action=='score':score(reg)
