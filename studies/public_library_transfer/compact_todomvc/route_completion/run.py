"""Complete the registered Llama event-function run with settled-response replay."""
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
import time
from unittest.mock import patch

from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from ..event_functions import run as events, delivery

HERE = Path(__file__).resolve().parent
OUT = ROOT/'artifacts/todomvc-route-20261126'
RESULT = HERE/'result.json'
END = datetime(2026,11,26,4,42,tzinfo=timezone.utc)
CAP = .90
TAG = delivery.TAG


def register():
    f = OUT/'registration.json'
    if f.exists():
        reg = read(f)
        assert all(sha(ROOT/name)==value for name,value in reg['sources'].items())
        return reg
    files=[Path(__file__), HERE/'PROTOCOL.md', Path(events.__file__), Path(delivery.__file__), delivery.RESULT,
           events.HERE/'result.json', events.weak.HERE/'result.json']
    balance=check_credits(CAP)
    assert balance['sufficient']
    core.save(f,dict(utc=now(),deadline=END.isoformat(),cap=CAP,model=delivery.MODEL,balance=balance,
                     sources={str(p.relative_to(ROOT)):sha(p) for p in files}))
    return read(f)


def generate():
    register()
    previous=events.OUT/TAG
    base=events.base
    send=base.request
    post=base.httpx.post
    lock=Lock()
    def transmit(*args,**kwargs):
        response=post(*args,**kwargs)
        if response.status_code==429:
            core.save(OUT/('closed-'+TAG+'.json'),dict(reason='HTTP 429',utc=now()))
        return response
    def request(ledger,case,folder,messages,stage,limit):
        relative=folder.relative_to(OUT/TAG)
        origins=[previous/relative]
        if relative.parts[0]=='restore':
            task,arm=relative.parts[1:3]
            origins=[events.weak.OUT/TAG/task/arm/'call',*origins,delivery.OUT/TAG/'fill'/task/arm]
        body=base.template(case[0],TAG,stage)|dict(messages=messages,max_tokens=limit)
        if stage=='build' and case[2]=='b' and 'seed' in body:body['seed']+=1
        for origin in origins:
            for settled in sorted(origin.glob('transmission-*/settled.json')):
                response=settled.with_name('response.json')
                if read(settled.with_name('request.json'))['body']!=body:continue
                assert read(settled)['response_sha256']==sha(response)
                choice=read(response)['choices'][0]
                if choice['finish_reason']=='error':continue
                core.save(folder/'reused.json',dict(source=str(response.relative_to(ROOT)),sha256=sha(response)))
                return choice['message'].get('content') or ''
        with lock:
            if (OUT/('closed-'+TAG+'.json')).exists():raise base.original.Unavailable('Closed route')
            time.sleep(2)
            return send(ledger,case,folder,messages,stage,limit)
    with patch.multiple(events,OUT=OUT,CAP=CAP),patch.object(events.weak.compact,'END',END),patch.object(base,'request',request),patch.object(base.httpx,'post',transmit):
        events.generate(TAG)


def main():
    generate()
    with patch.multiple(events.weak,OUT=OUT,MODELS={TAG:delivery.MODEL}):events.weak.score()
    closed=OUT/('closed-'+TAG+'.json')
    core.save(RESULT,dict(registration=sha(OUT/'registration.json'),results=read(OUT/TAG/'result.json'),
        model=delivery.MODEL,route=read(closed) if closed.exists() else None,cost=ledger_read.totals(OUT/'budget.sqlite3')))


if __name__=='__main__':
    with browser.lock(OUT/'.run.lock'):main()
