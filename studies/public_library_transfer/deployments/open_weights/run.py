"""Same public preparation method, independently authored by two open-weight API models."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import time
import httpx

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies.ledger_read import totals,calls
from studies.public_library_transfer import core as c,browser
from studies.public_library_transfer.report import comparison,counts
from studies.public_library_transfer_remote import run as remote, milestones
from studies.study_io import sha

HERE=Path(__file__).resolve().parent
OUT=c.ROOT/'artifacts/public-library-transfer-open-20261123'
SPECIAL=('table','svg-chart')
ORDER=(*SPECIAL,*(p for p in c.PROJECTS if p not in SPECIAL))
CAP=1.50


def tasks(p): return tuple(range(1,21)) if p in SPECIAL else (4,8,12,16,20)


def register():
    path=OUT/'registered.json'
    src=[Path(__file__),HERE/'PROTOCOL.md',Path(c.__file__),Path(remote.__file__)]+[c.OUT/'inputs'/f'{p}.json' for p in c.PROJECTS]
    evidence={str(p.relative_to(c.ROOT)):sha(p) for p in src}
    if path.exists():
        if c.read(path)['sources']!=evidence: raise ValueError('Registered source changed')
    else:
        balance=check_credits(2*CAP)
        if not balance['sufficient']: raise RuntimeError('Unfunded')
        c.save(path,{'registered':c.now(),'sources':evidence,'budget_per_builder':CAP,'balance':balance,
                     'models':remote.MODELS,'targets':{p:tasks(p) for p in ORDER},'deadline':remote.END.isoformat()})


def build_call(tag,msg,folder,ledger,purpose):
    if (OUT/f'{tag}-route-closed.json').exists(): raise RuntimeError('Previously denied model route')
    model=remote.MODELS[tag]
    if datetime.now(timezone.utc)>=remote.END: raise RuntimeError('Deadline')
    body={'model':model,'messages':msg,'max_tokens':16000,'temperature':0,
          'provider':{'allow_fallbacks':True,'require_parameters':True,'sort':'price','max_price':remote.PRICES},
          'response_format':remote.request_format('public_website_library',c.SCHEMA)}
    if tag=='oss': body['reasoning']={'effort':'low','exclude':True}
    if (folder/'receipt.json').exists():
        return c.read(folder/'response.json')['choices'][0]['message']['content'] or ''
    if (folder/'request.json').exists(): raise RuntimeError('Prior interrupted response; preauthorization retained')
    bound=len(json.dumps(body,ensure_ascii=False).encode())+2048
    reserve=(Decimal(bound)*Decimal(str(remote.PRICES['prompt']))+16000*Decimal(str(remote.PRICES['completion'])))/1000000
    ticket=ledger.reserve(reserve,'build/'+purpose,model)
    c.save(folder/'request.json',{'body':body,'bound':bound,'reserved_usd':float(reserve),'call_id':ticket})
    since=time.monotonic()
    try:
        reply=httpx.post('https://openrouter.ai/api/v1/chat/completions',headers={
            'Authorization':'Bearer '+os.environ['OPENROUTER_API_KEY'],'X-Title':'GUI-DNA public GUI libraries'},
            json=body,timeout=400)
        reply.raise_for_status()
        val=reply.json()
        c.save(folder/'response.json',val)
        usage=val.get('usage') or {}
        if usage.get('cost') is None: raise RuntimeError('Missing usage cost')
        ledger.settle(ticket,usage['cost'],time.monotonic()-since,val.get('id'),usage)
        c.save(folder/'receipt.json',{'call_id':ticket,'cost':usage['cost']})
        return val['choices'][0]['message']['content'] or ''
    except Exception as exc:
        code=exc.response.status_code if isinstance(exc,httpx.HTTPStatusError) else None
        reason=f'HTTP {code}' if code else type(exc).__name__
        ledger.uncertain(ticket,reason)
        c.save(folder/'error.json',{'call_id':ticket,'error':reason})
        if code==403:
            c.save(OUT/f'{tag}-route-closed.json',{'model':model,'error':reason})
        raise RuntimeError(reason) from None


def build_job(p,tag,ledger):
    dest=OUT/'builds'/p/tag
    if (dest/'status.json').exists(): return
    public=c.read(c.OUT/'inputs'/f'{p}.json')
    base=c.build_messages(public)
    msg=base
    attempts=[]
    status={'status':'missing','model':remote.MODELS[tag]}
    for n in range(2):
        attempt=dest/f'attempt-{n+1}'
        c.save(attempt/'messages.json',msg)
        try: raw=build_call(tag,msg,attempt,ledger,p+f'/{n+1}')
        except RuntimeError as e:
            status.update(reason=str(e));break
        try:
            pkg=c.package(public,c.parse(raw))
            for key,plan in [('default',pkg['defaults']),('first',pkg['examples'][0]['plan'])]:
                page=attempt/key
                c.materialize(p,pkg,plan,page)
                errors=browser.public_load(p,page)
                c.save(attempt/f'{key}-load.json',errors)
                if errors: raise ValueError(str(errors)[:1600])
            c.save(dest/'package.json',pkg)
            attempts.append({'attempt':n+1,'valid':True})
            status.update(status='valid',package_sha256=sha(dest/'package.json')); break
        except (KeyError,ValueError,TypeError) as e:
            attempts.append({'attempt':n+1,'valid':False,'reason':str(e)[:1600]})
            status.update(status='build_failed')
            msg=base+[{'role':'assistant','content':raw[:65000]},
                       {'role':'user','content':'The public load/format check reported '+str(e)[:1600]+'. Return a complete replacement JSON package.'}]
    c.save(dest/'status.json',{**status,'attempts':attempts})
    print('build',p,tag,status['status'],flush=True)


def builder(tag):
    ledger=Ledger(OUT/f'{tag}-budget.sqlite3',CAP,CAP)
    for p in ORDER if tag=='oss' else SPECIAL: build_job(p,tag,ledger)


def direct_file(p,n):
    model='oss' if p=='draw' else 'mistral'
    if p in ('canvas','flex'): return milestones.OUT/'runs'/p/model/'direct'/f'task-{n}'/'result.json'
    return remote.OUT/'runs'/model/p/'direct'/f'task-{n}'/'result.json'


def deploy(p,tag,n,ledger):
    dest=OUT/'runs'/p/tag/f'task-{n}'
    if (dest/'rows.json').exists(): return
    state=OUT/'builds'/p/tag
    status=c.read(state/'status.json')['status']
    m='oss' if p=='draw' else 'mistral'
    row={'project':p,'task':n,'builder':remote.MODELS[tag],'rep':1,'planner':remote.MODELS[m],
         'arm':'plan','status':status,'page':None,'files':None}
    fixed={**row,'arm':'fixed','planner':None}
    if status=='valid':
        pkg=c.read(state/'package.json')
        public=c.read(c.OUT/'inputs'/f'{p}.json')
        msg=c.plan_messages(public,n,pkg)
        files=browser.tree(state/'fixed')
        fixed.update(page=str((state/'fixed').relative_to(c.ROOT)),files=files)
        try:
            content,hash_=remote.call(dest,m,msg,'plan',pkg['plan_schema'],ledger,f'plan/{p}/{tag}/{n}')
            c.save(dest/'raw.json',{'content':content,'receipt_sha256':hash_})
            try:
                page=dest/'page'
                files=c.materialize(p,pkg,c.parse(content),page)
                row.update(page=str(page.relative_to(c.ROOT)),files=files)
            except (ValueError,KeyError,TypeError) as e:
                row.update(status='invalid',reason=str(e)[:400])
        except Exception as e:
            row.update(status='missing',reason=str(e)[:400])
    c.save(dest/'rows.json',[row,fixed])


def generations():
    with ThreadPoolExecutor(2) as pool: list(pool.map(builder,('oss','mistral')))
    for p in ORDER:
        rows=[]
        for tag in ('oss','mistral') if p in SPECIAL else ('oss',):
            d=OUT/'builds'/p/tag
            ledger=Ledger(OUT/f'{tag}-budget.sqlite3',CAP,CAP)
            if c.read(d/'status.json')['status']=='valid':
                pkg=c.read(d/'package.json')
                c.materialize(p,pkg,pkg['examples'][0]['plan'],d/'fixed')
            with ThreadPoolExecutor(4) as pool: list(pool.map(lambda n:deploy(p,tag,n,ledger),tasks(p)))
            for n in tasks(p): rows.extend(c.read(OUT/'runs'/p/tag/f'task-{n}/rows.json'))
        while not all(direct_file(p,n).exists() for n in tasks(p)): time.sleep(4)
        sources=[direct_file(p,n) for n in tasks(p)]
        rows.extend(c.read(f) for f in sources)
        c.save(OUT/'seals'/f'{p}.json',{'rows':rows,'shared_direct':{str(f.relative_to(c.ROOT)):sha(f) for f in sources}})


def score():
    for p in ORDER:
        seal=OUT/'seals'/f'{p}.json'
        while not seal.exists(): time.sleep(5)
        dest=OUT/'scores'/f'{p}.json'
        if dest.exists(): continue
        rows=browser.evaluate(c.read(seal)['rows'],OUT,{p:browser.verify_contract(p)},2)
        direct={r['task']:r for r in rows if r['arm']=='direct'}
        groups=[]
        for tag in ('oss','mistral') if p in SPECIAL else ('oss',):
            aa,bb=[{r['task']:r for r in rows if r['arm']==a and r['builder']==remote.MODELS[tag]} for a in ('plan','fixed')]
            groups.append({'builder':remote.MODELS[tag],'planner':next(iter(aa.values()))['planner'],
                           'admission':c.read(OUT/'builds'/p/tag/'status.json')['status'],
                           'direct':comparison(aa,direct,tasks(p)),'fixed':comparison(aa,bb,tasks(p))})
        c.save(dest,{'project':p,'targets':tasks(p),'groups':groups,'seal_sha256':sha(seal),
                     'rows':[{k:r[k] for k in ('task','arm','builder','planner','status','passed','report_sha256')} for r in rows]})
    billing={}
    for tag in ('mistral','oss'):
        ledger=OUT/f'{tag}-budget.sqlite3'
        data=calls(ledger)
        billing[tag]={'totals':totals(ledger),'records':[dict(purpose=r['purpose'],model=r['model'],status=r['status'],
             actual_microusd=r['actual'],reservation_microusd=r['reserved']) for r in data]}
    c.save(c.ROOT/'studies/results/public-library-transfer-open-20261123.json',{'registered_sha256':sha(OUT/'registered.json'),
        'projects':[c.read(OUT/'scores'/f'{p}.json') for p in ORDER],'costs':billing})


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=('generate','score'));args=ap.parse_args()
    register()
    if args.action=='generate': generations()
    else: score()
