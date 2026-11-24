"""Isolated per-model reservation, response and settlement for the registered hour."""
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
import time

import httpx

from gui_dna.budget import BudgetStop
from studies.public_library_transfer import core
from studies.study_io import read, sha

END = datetime(2026, 11, 24, 11, 45, 40, tzinfo=timezone.utc)
MODELS = {
    "qwen9": ("qwen/qwen3.5-9b", .95, .35, 1.20, {"enabled": False}),
    "oss": ("openai/gpt-oss-120b", 1., .25, 1., {"effort": "low", "exclude": True}),
}


class Unavailable(RuntimeError):
    pass


def request(tag, ledger, root, path, messages, purpose, seed, limit):
    model, _, cin, cout, reasoning = MODELS[tag]
    body = {"model": model, "messages": messages, "reasoning": reasoning, "temperature": .2,
            "seed": seed, "max_tokens": limit, "provider": {"allow_fallbacks": True, "sort": "price",
                "require_parameters": True, "max_price": {"prompt": cin, "completion": cout, "request": 0}}}
    stamp, req, res = (path / f"{name}.json" for name in ("settled", "request", "response"))
    closed = root / "route-closed.json"
    if req.exists():
        assert read(req)["body"] == body
        if stamp.exists():
            assert read(stamp)["response_sha256"] == sha(res)
            return read(res)["choices"][0]["message"].get("content") or ""
        raise Unavailable("Previous unresolved reservation")
    if closed.exists() or datetime.now(timezone.utc) >= END:
        raise BudgetStop("Route closed or time window ended")
    bound = len(json.dumps(body, ensure_ascii=False).encode()) + 2048
    amount = (bound * Decimal(str(cin)) + limit * Decimal(str(cout))) / 1_000_000
    ticket = ledger.reserve(amount, purpose, model)
    core.save(req, {"body": body, "call_id": ticket, "input_bound": bound, "reserved_usd": float(amount)})
    t0 = time.monotonic()
    try:
        r = httpx.post("https://openrouter.ai/api/v1/chat/completions", json=body,
                       headers={"Authorization": "Bearer " + os.environ["OPENROUTER_API_KEY"]},
                       timeout=httpx.Timeout(95, connect=15))
        r.raise_for_status()
        payload = r.json()
        core.save(res, payload)
        usage = payload["usage"]
        if usage.get("cost") is None:
            raise ValueError("Missing receipt")
        content = payload["choices"][0]["message"].get("content") or ""
    except (httpx.HTTPError, ValueError, IndexError, KeyError, TypeError) as e:
        code = e.response.status_code if isinstance(e, httpx.HTTPStatusError) else None
        why = f"HTTP {code}" if code else type(e).__name__
        ledger.uncertain(ticket, why)
        core.save(path / "error.json", {"reason": why})
        if code in (401,402,403,404):
            core.save(closed, {"reason": why})
        raise Unavailable(why) from None
    ledger.settle(ticket, usage["cost"], time.monotonic()-t0, payload.get("id"), usage)
    core.save(stamp, {"ticket": ticket, "response_sha256": sha(res)})
    return content
