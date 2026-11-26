"""Bound the price and duration of each evaluation request, including unknown deliveries."""
from datetime import datetime,timezone,timedelta
from decimal import Decimal
import base64
import hashlib
import json
import os
from pathlib import Path
import time

import httpx

from gui_dna.budget import BudgetStop
from studies.public_library_transfer import core,browser
from studies.study_io import ROOT,read,sha
from .generate import END

EXACT='qwen/qwen2.5-vl-32b-instruct'
ALTERNATE='qwen/qwen3-vl-30b-a3b-instruct'
PRICES={EXACT:(2,4),ALTERNATE:(.4,1.3)}
CAP=6.80
OUT=ROOT/'artifacts/webgen-browser-judge-20261126pm'
class Undelivered(Exception):pass

def image_message(messages):
    copies=[]
    for msg in messages:
        content=msg['content']
        if isinstance(content,list):
            content=[dict(type='image_url',image_url={'url':'data:image/png;base64,'+base64.b64encode((ROOT/e['file']).read_bytes()).decode()}) if e.get('type')=='local_image' else e for e in content]
        copies.append(dict(role=msg['role'],content=content))
    return copies

def send(ledger,model,folder,messages):
    # The text-plus-screenshot operator has a harder input bound than text alone.
    # Reserve the provider's entire supported context at its capped input price.
    prompt,completion=PRICES[model]
    has_images=any(isinstance(msg['content'],list) for msg in messages)
    maxout=1000 if has_images else 128
    maxin=262144 if has_images else len(json.dumps(messages).encode())+2048
    bound=(Decimal(str(prompt))*maxin+Decimal(str(completion))*maxout)/1_000_000
    body=dict(model=model,messages=image_message(messages),seed=42,max_tokens=maxout,temperature=1,
              provider=dict(allow_fallbacks=True,sort='price',max_price=dict(prompt=prompt,completion=completion,request=0)))
    fingerprint=hashlib.sha256(json.dumps(body,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    for i in (1,2):
        dest=folder/str(i);req=dest/'request.json';done=dest/'settled.json'
        if req.exists():
            assert read(req)['body_sha256']==fingerprint
            if done.exists():
                f=dest/'response.json';assert sha(f)==read(done)['sha256']
                s=read(f)['choices'][0]['message'].get('content')
                if s:return s
            continue
        if datetime.now(timezone.utc)+timedelta(seconds=80)>=END:raise Undelivered('Deadline')
        closed=OUT/('closed-'+model.split('/')[-1]+'.json')
        if closed.exists():raise Undelivered(read(closed)['reason'])
        try:ticket=ledger.reserve(bound,('judge/' if has_images else 'route/')+str(dest.relative_to(OUT)),model)
        except BudgetStop as e:raise Undelivered('Reservation declined') from e
        core.save(req,dict(id=ticket,body_sha256=fingerprint,model=model,reserved_usd=float(bound),messages=messages))
        start=time.monotonic()
        try:
            response=httpx.post('https://openrouter.ai/api/v1/chat/completions',json=body,
                     headers={'Authorization':'Bearer '+os.environ['OPENROUTER_API_KEY']},timeout=httpx.Timeout(70,connect=15))
            response.raise_for_status();data=response.json();usage=data['usage']
            if usage.get('cost') is None:raise ValueError('Missing cost')
            core.save(dest/'response.json',data)
        except (httpx.HTTPError,ValueError,KeyError,TypeError) as e:
            status=e.response.status_code if isinstance(e,httpx.HTTPStatusError) else None
            reason=f'HTTP {status}' if status else type(e).__name__
            ledger.uncertain(ticket,reason);core.save(dest/'error.json',dict(reason=reason))
            if status in (401,402,403,404):
                with browser.lock(closed.with_suffix('.lock')):
                    if not closed.exists():core.save(closed,dict(reason=reason))
                raise Undelivered(reason) from None
            time.sleep(2);continue
        ledger.settle(ticket,usage['cost'],time.monotonic()-start,data.get('id'),usage)
        core.save(done,dict(sha256=sha(dest/'response.json')))
        s=data['choices'][0]['message'].get('content')
        if s:return s
    raise Undelivered('No usable judge response after two transmissions')
