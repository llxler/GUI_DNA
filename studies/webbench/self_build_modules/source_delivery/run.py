"""Repair the source receiver and safely reuse byte-identical settled requests."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, read, sha, now
from .. import run as base

HERE = Path(__file__).resolve().parent
OLD = base.OUT
OUT = ROOT/'artifacts/webbench-self-delivery-20261125'
CAP = 4.75
ORIGINAL_SEND = base.request
ORIGINAL_MANIFEST = base.manifest
HEADER = re.compile(r'^[ \t]*(?://[ \t]*)?FILE:[ \t]*([a-zA-Z0-9_./-]+)[ \t]*$', re.M)


def extract(text,names):
    content=base.uncode(text)
    parts=HEADER.split(content)
    files={}
    for name,src in zip(parts[1::2],parts[2::2]):
        if name in names and name not in files and src.strip():
            files[name]=base.uncode(src)
    if len(parts)==1 and len(names)==1 and content.strip():
        return {next(iter(names)):content}
    return files


def manifest(text):
    data=base.parse_json(text)
    if isinstance(data.get('interfaces'),(list,dict)):
        data['interfaces']=json.dumps(data['interfaces'],ensure_ascii=False)
    return ORIGINAL_MANIFEST(json.dumps(data,ensure_ascii=False))


def body_for(case,msgs,stage,limit):
    project,tag,rep=case
    body=base.template(project,tag,stage)
    body.update(messages=msgs,max_tokens=limit)
    if stage=='build' and tag in ('deepseek-pro','deepseek-flash','qwen9'):
        body['reasoning']={'enabled':False}
    if stage=='build' and rep=='b' and 'seed' in body:
        body['seed']+=1
    return body


def request(ledger,case,root,msgs,stage,limit):
    if root.name=='design-2':
        msgs=[*msgs[:-1],{**msgs[-1],'content':msgs[-1]['content']+' Return the complete JSON. Limit interfaces to 150 words.'}]
        limit=4800
    expected=body_for(case,msgs,stage,limit)
    prev=OLD/root.relative_to(OUT)
    for settled in sorted(prev.glob('transmission-*/settled.json')):
        req=settled.with_name('request.json')
        res=settled.with_name('response.json')
        if read(req)['body']==expected and sha(res)==read(settled)['response_sha256']:
            choice=read(res)['choices'][0]
            if choice.get('finish_reason')!='error':
                core.save(root/'reused.json',dict(request=str(req.relative_to(ROOT)),request_sha256=sha(req),
                          response=str(res.relative_to(ROOT)),response_sha256=sha(res)))
                return choice['message'].get('content') or ''
    return ORIGINAL_SEND(ledger,case,root,msgs,stage,limit)


def register():
    assert extract('FILE: common/File.js\nlet x=1;\nFILE: index.js\nfoo();',['common/File.js','index.js'])=={
        'common/File.js':'let x=1;', 'index.js':'foo();'}
    sources={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),HERE/'PROTOCOL.md',Path(base.__file__),
              OLD/'registration.json',*[OLD/f'closed-{t}.json' for _,t in base.ORDER]]}
    reg=OUT/'registration.json'
    if reg.exists():
        assert read(reg)['sources']==sources
    else:
        old=ledger_read.totals(OLD/'budget.sqlite3')
        assert old['exposure_usd']+CAP+2.5<=10
        balance=check_credits(CAP)
        assert balance['sufficient']
        core.save(reg,dict(utc=now(),sources=sources,cap=CAP,old_at_registration=old,balance=balance,
                            cells=base.ORDER,deadline=base.END.isoformat(),reps=['a','b']))
    for p in base.GROUPS:
        core.save(OUT/'inputs'/p/'browser.json',read(OLD/'inputs'/p/'browser.json'))


def main():
    register()
    ledger=Ledger(OUT/'budget.sqlite3',CAP,CAP)
    cases=[(p,t,r) for p,t in base.ORDER for r in ('a','b')]
    browser.OUT=OUT
    with patch.multiple(base,OUT=OUT,request=request,extract=extract,manifest=manifest), ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda c:base.branch(c,ledger),cases))


if __name__=='__main__':
    main()
