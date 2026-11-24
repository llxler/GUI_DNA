"""Continue only previously missing transmissions, preserving their original charge exposure."""
import argparse
from decimal import Decimal
import fcntl
from pathlib import Path
import time
from types import SimpleNamespace

from gui_dna.budget import BudgetStop
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import core
from studies.public_library_transfer.deployments.historical.run import request_format
from studies.public_library_transfer.self_refinement.dependency_order import run, transport
from studies.study_io import ROOT, read, sha

SOURCE=run.OUT
OUT=ROOT/'artifacts/self-dependency-resume-20261124'
TOTAL=Decimal('1.30')
PROJECT=run.PROJECT

def transient(failure):
    return failure in {'RemoteProtocolError','ReadTimeout','ReadError','WriteError','WriteTimeout','ConnectError',
                       'ConnectTimeout','PoolTimeout','ProxyError','HTTP 429'} or failure.startswith('HTTP 5')

def configure():
    run.configure()
    run.engine.OUT=OUT
    if (OUT/'registered.json').exists(): run.engine.CAP=read(OUT/'registered.json')['cap_usd']
    run.engine.transport=SimpleNamespace(request=request)

def register():
    dest=OUT/'registered.json'
    if dest.exists(): return run.engine.verify()
    src=SOURCE/PROJECT
    original=read(SOURCE/'registered.json')
    paths=[run.HERE/'RESUME.md',Path(__file__),SOURCE/'registered.json',*(src/g/'seal.json' for g in run.engine.GROUPS)]
    for g in run.engine.GROUPS:
        for p,h in read(src/g/'seal.json').items(): assert sha(src/p)==h
    for name,h in original['files'].items(): assert sha(ROOT/name)==h
    old=ledger_read.totals(src/'budget.sqlite3')
    cap=float(TOTAL-Decimal(str(old['exposure_usd'])))
    if cap<=0: raise BudgetStop('No remaining allowance')
    balance=check_credits(cap)
    if not balance['sufficient']: raise BudgetStop('Insufficient remaining credit')
    for n in ('public.json','browser.json','paths.json'):
        core.save(OUT/PROJECT/n,read(src/n))
        assert sha(OUT/PROJECT/n)==sha(src/n)
        paths.append(OUT/PROJECT/n)
    for p in sorted(src.rglob('request.json')):
        paths.append(p)
        for name in ('response.json','settled.json','error.json'):
            q=p.parent/name
            if q.exists(): paths.append(q)
    files=original['files']|{str(p.relative_to(ROOT)):sha(p) for p in paths}
    registered=dict(original,utc=core.now(),cap_usd=cap,balance=balance,files=files,
                    source_registration_sha256=sha(SOURCE/'registered.json'),source_exposure_usd=old['exposure_usd'],
                    combined_max_usd=float(TOTAL),max_network_concurrency=1,max_transmissions_per_request=3)
    core.save(dest,registered)

def request(folder,ledger,messages,purpose,limit,*,seed=None,schema=None):
    logical=folder/'delivery.json'
    origin=SOURCE/folder.relative_to(OUT)
    body={'model':transport.MODEL,'messages':messages,'temperature':.2,'max_tokens':limit,
          'provider':{'only':[transport.PROVIDER],'require_parameters':True,'allow_fallbacks':False,'max_price':transport.PRICES}}
    if schema is not None: body['response_format']=request_format('answer',schema)
    def use(path,kind):
        req,res,stamp=(path/n for n in ('request.json','response.json','settled.json'))
        assert read(req)['body']==body and read(stamp)['response_sha256']==sha(res)
        core.save(logical,{'purpose':purpose,'origin':kind,'path':str(path.relative_to(ROOT)),
                           'request_sha256':sha(req),'response_sha256':sha(res),'receipt_sha256':sha(stamp)})
        return read(res)['choices'][0]['message'].get('content') or ''
    prior=0
    if (origin/'request.json').exists():
        if read(origin/'request.json')['body']!=body: raise ValueError('Changed original prompt')
        if (origin/'settled.json').exists(): return use(origin,'original')
        prior=1
        failure=read(origin/'error.json')['reason'] if (origin/'error.json').exists() else 'unknown'
        if not transient(failure): raise transport.Unavailable('Previously unresolved '+failure)
    last='unknown'
    for attempt in range(prior+1,4):
        actual=folder/('transmission-'+str(attempt))
        if (actual/'settled.json').exists(): return use(actual,'continuation')
        if attempt>1: time.sleep(2 if attempt==2 else 6)
        try:
            with (OUT/'serial-transmission.lock').open('a') as stream:
                fcntl.flock(stream,fcntl.LOCK_EX)
                transport.request(actual,ledger,messages,purpose+'/transmission-'+str(attempt),limit,seed=seed,schema=schema)
            return use(actual,'continuation')
        except transport.Unavailable as exc:
            last=read(actual/'error.json')['reason'] if (actual/'error.json').exists() else str(exc)
            if not transient(last): break
    raise transport.Unavailable('Transmission missing after retained attempts: '+last)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('register','verify','generate','score'))
    parser.add_argument('group',nargs='?',choices=run.engine.GROUPS)
    args=parser.parse_args()
    configure()
    if args.action=='register': return register()
    if args.action=='verify': return run.engine.verify()
    if args.action=='score': return run.engine.score(PROJECT)
    if not args.group: parser.error('Group required')
    run.engine.generate(PROJECT,args.group)

if __name__=='__main__': main()
