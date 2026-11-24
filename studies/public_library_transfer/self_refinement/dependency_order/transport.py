"""One explicitly registered provider and decoding policy for every arm."""
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
import time

import httpx

from gui_dna.budget import BudgetStop
from studies.public_library_transfer import core
from studies.public_library_transfer.deployments.historical.run import request_format
from studies.public_library_transfer.self_refinement.native.transport import Unavailable
from studies.study_io import read, sha

MODEL='qwen/qwen3-coder-30b-a3b-instruct'
END=datetime(2026,11,24,5,18,tzinfo=timezone.utc)
PRICES={'prompt':.25,'completion':1,'request':0}
PROVIDER='SiliconFlow'

def request(folder,ledger,messages,purpose,limit,*,seed=None,schema=None):
    body={'model':MODEL,'messages':messages,'temperature':.2,'max_tokens':limit,
          'provider':{'only':[PROVIDER],'require_parameters':True,'allow_fallbacks':False,'max_price':PRICES}}
    if schema is not None: body['response_format']=request_format('answer',schema)
    req,res,stamp=(folder/p for p in ('request.json','response.json','settled.json'))
    if req.exists():
        if read(req)['body']!=body: raise ValueError('Request body mismatch')
        if stamp.exists():
            assert read(stamp)['response_sha256']==sha(res)
            return read(res)['choices'][0]['message'].get('content') or ''
        raise Unavailable('Unresolved earlier request')
    if datetime.now(timezone.utc)>=END: raise BudgetStop('Request deadline reached')
    bound=len(json.dumps(body,ensure_ascii=False).encode())+2048
    amount=(bound*Decimal('.25')+limit*Decimal('1'))/1_000_000
    ticket=ledger.reserve(amount,purpose,MODEL)
    core.save(req,{'body':body,'call_id':ticket,'input_bound':bound,'reserved_usd':float(amount)})
    start=time.monotonic()
    try:
        response=httpx.post('https://openrouter.ai/api/v1/chat/completions',json=body,
            headers={'Authorization':'Bearer '+os.environ['OPENROUTER_API_KEY']},timeout=httpx.Timeout(220,connect=25))
        response.raise_for_status()
        payload=response.json()
        core.save(res,payload)
        usage=payload['usage']
        content=payload['choices'][0]['message'].get('content') or ''
        if usage.get('cost') is None: raise ValueError('Missing billing receipt')
    except (httpx.HTTPError,ValueError,KeyError,IndexError,TypeError) as exc:
        reason=f'HTTP {exc.response.status_code}' if isinstance(exc,httpx.HTTPStatusError) else type(exc).__name__
        ledger.uncertain(ticket,reason)
        core.save(folder/'error.json',{'reason':reason})
        raise Unavailable(reason) from None
    ledger.settle(ticket,usage['cost'],time.monotonic()-start,payload.get('id'),usage)
    core.save(stamp,{'ticket':ticket,'response_sha256':sha(res)})
    return content
