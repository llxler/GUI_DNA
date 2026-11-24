"""Send a bounded, immutable Qwen request with the registered decoding parameters."""

import json
import os
import time
from datetime import datetime, timezone
from decimal import Decimal

import httpx

from gui_dna.budget import BudgetStop
from studies.public_library_transfer import core
from studies.public_library_transfer.deployments.historical.run import request_format
from studies.study_io import read, sha

MODEL = "qwen/qwen3.5-9b"
END = datetime(2026, 11, 24, 5, 18, tzinfo=timezone.utc)
PRICES = {"prompt": 0.35, "completion": 1.20, "request": 0}


class Unavailable(RuntimeError):
    pass


def request(folder, ledger, messages, purpose, limit, *, seed, schema=None):
    body = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0,
        "seed": seed,
        "reasoning": {"enabled": False},
        "max_tokens": limit,
        "provider": {
            "require_parameters": True,
            "allow_fallbacks": True,
            "sort": "price",
            "max_price": PRICES,
        },
    }
    if schema is not None:
        body["response_format"] = request_format("answer", schema)
    req = folder / "request.json"
    res = folder / "response.json"
    stamp = folder / "settled.json"
    if req.exists():
        assert read(req)["body"] == body
        if stamp.exists():
            assert sha(res) == read(stamp)["response_sha256"]
            return read(res)["choices"][0]["message"].get("content") or ""
        raise Unavailable("Request already attempted with unresolved delivery")
    if datetime.now(timezone.utc) >= END:
        raise BudgetStop("Request deadline reached")
    bound = len(json.dumps(body, ensure_ascii=False).encode()) + 2048
    amount = (bound * Decimal("0.35") + limit * Decimal("1.20")) / 1_000_000
    ticket = ledger.reserve(amount, purpose, MODEL)
    core.save(
        req,
        {
            "body": body,
            "call_id": ticket,
            "input_bound": bound,
            "reserved_usd": float(amount),
        },
    )
    begin = time.monotonic()
    try:
        response = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            json=body,
            headers={"Authorization": "Bearer " + os.environ["OPENROUTER_API_KEY"]},
            timeout=httpx.Timeout(230, connect=25),
        )
        response.raise_for_status()
        payload = response.json()
        core.save(res, payload)
        usage = payload["usage"]
        content = payload["choices"][0]["message"].get("content") or ""
        if usage.get("cost") is None:
            raise ValueError("Missing billing receipt")
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
        reason = (
            f"HTTP {exc.response.status_code}"
            if isinstance(exc, httpx.HTTPStatusError)
            else type(exc).__name__
        )
        ledger.uncertain(ticket, reason)
        core.save(folder / "error.json", {"reason": reason})
        raise Unavailable(reason) from None
    ledger.settle(
        ticket, usage["cost"], time.monotonic() - begin, payload.get("id"), usage
    )
    core.save(stamp, {"ticket": ticket, "response_sha256": sha(res)})
    return content
