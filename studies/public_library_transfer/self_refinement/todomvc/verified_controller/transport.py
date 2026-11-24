"""Pinned Gemma transport with immutable receipts and per-call dollar reservations."""
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
import time

import httpx

from gui_dna.budget import BudgetStop
from studies.public_library_transfer import browser
from studies.public_library_transfer.deployments.historical.run import request_format
from studies.study_io import read, sha

MODEL="google/gemma-3-12b-it"
END=datetime(2026,11,24,11,45,40,tzinfo=timezone.utc)
PRICES={"prompt":0.08,"completion":0.24,"request":0}
CAP=0.65


class Missing(RuntimeError):
    pass


def request(root,ledger,folder,messages,purpose,seed,limit=4096,schema=None):
    body={"model":MODEL,"messages":messages,"seed":seed,"temperature":0.25,"max_tokens":limit,
          "provider":{"only":["DeepInfra"],"allow_fallbacks":False,"require_parameters":True,"max_price":PRICES}}
    if schema is not None:
        body["response_format"]=request_format("selection",schema)
    for route_try in (1,2):
        site=folder/str(route_try)
        req,res,settled=(site/(name+".json") for name in ("request","response","settled"))
        if req.exists():
            assert read(req)["body"]==body
            if settled.exists():
                stamp=read(settled)
                assert stamp["response_sha256"]==sha(res)
                return read(res)["choices"][0]["message"].get("content") or ""
            if (site/"error.json").exists() and read(site/"error.json")["retryable"] and route_try==1:
                continue
            raise Missing("Previous reservation unresolved")
        if (root/"route-closed.json").exists() or datetime.now(timezone.utc)>=END:
            raise Missing("Route closed or time window ended")
        bound=len(json.dumps(body,ensure_ascii=False).encode())+2048
        reserve=(bound*Decimal('0.08')+limit*Decimal('0.24'))/1_000_000
        try:
            ticket=ledger.reserve(reserve,purpose,MODEL)
        except BudgetStop as e:
            raise Missing(str(e)) from None
        browser.preserve_json(req,{"call_id":ticket,"body":body,"input_token_bound":bound,"reserved_usd":float(reserve)})
        start=time.monotonic()
        try:
            response=httpx.post("https://openrouter.ai/api/v1/chat/completions",json=body,
                headers={"Authorization":"Bearer "+os.environ["OPENROUTER_API_KEY"]},timeout=httpx.Timeout(110,connect=18))
            response.raise_for_status()
            payload=response.json()
            browser.preserve_json(res,payload)
            usage=payload["usage"]
            if usage.get("cost") is None:
                raise ValueError("No cost in receipt")
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            code=exc.response.status_code if isinstance(exc,httpx.HTTPStatusError) else None
            why=f"HTTP {code}" if code else type(exc).__name__
            retryable=(code is None and isinstance(exc,httpx.TransportError)) or code in (408,429,500,502,503,504)
            ledger.uncertain(ticket,why)
            browser.preserve_json(site/"error.json",{"reason":why,"retryable":retryable})
            if code in (401,402,403,404):
                browser.write_json(root/"route-closed.json",{"reason":why})
            if retryable and route_try==1:
                continue
            raise Missing(why) from None
        ledger.settle(ticket,usage["cost"],time.monotonic()-start,payload.get("id"),usage)
        browser.preserve_json(settled,{"ticket":ticket,"response_sha256":sha(res),
            "provider":payload.get("provider"),"model":payload.get("model"),"generation_id":payload.get("id")})
        choice=(payload.get("choices") or [{}])[0]
        if not isinstance(choice.get("message"),dict):
            raise Missing("Settled receipt without a model message")
        return choice["message"].get("content") or ""
    raise Missing("No delivered response")
