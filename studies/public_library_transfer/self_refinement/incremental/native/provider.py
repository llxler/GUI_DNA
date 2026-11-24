"""Account for each native tool-call response before interpreting its arguments."""

import json
import os
import time
from datetime import datetime, timezone
from decimal import Decimal

import httpx

from studies.public_library_transfer import core
from studies.study_io import read, sha
from studies.webbench.backbone_matrix.run import Unavailable


def tool_call(root, ledger, folder, model, end, messages, function, purpose, limit):
    name = function["name"]
    body = {"model": model, "messages": messages, "max_tokens": limit, "temperature": 0, "seed": 20261124,
            "reasoning": {"effort": "low", "exclude": True}, "tools": [{"type": "function", "function": function}],
            "tool_choice": {"type": "function", "function": {"name": name}},
            "provider": {"sort": "throughput", "allow_fallbacks": True, "require_parameters": True,
                         "max_price": {"prompt": 0.25, "completion": 1, "request": 0}}}
    receipt = folder / "settled.json"
    auth = folder / "request.json"
    response = folder / "response.json"
    if receipt.exists():
        if read(auth)["body"] != body or sha(response) != read(receipt)["response_sha256"]:
            raise ValueError("Request or response identity changed")
        payload = read(response)
    else:
        if auth.exists() or (root / "route-closed.json").exists() or datetime.now(timezone.utc) >= end:
            raise Unavailable("Existing unknown reservation, closed route, or generation cutoff")
        bound = len(json.dumps(body, ensure_ascii=False).encode()) + 2048
        amount = (Decimal(bound) * Decimal("0.25") + limit) / 1_000_000
        ticket = ledger.reserve(amount, purpose, model)
        core.save(auth, {"body": body, "call_id": ticket, "input_bound": bound, "reserved_usd": float(amount)})
        started = time.monotonic()
        try:
            res = httpx.post("https://openrouter.ai/api/v1/chat/completions", json=body,
                headers={"Authorization": "Bearer " + os.environ["OPENROUTER_API_KEY"]}, timeout=httpx.Timeout(205, connect=25))
            res.raise_for_status()
            payload = res.json()
            core.save(response, payload)
            usage = payload.get("usage") or {}
            if usage.get("cost") is None:
                raise ValueError("Missing usage receipt")
            ledger.settle(ticket, usage["cost"], time.monotonic()-started, payload.get("id"), usage)
            core.save(receipt, {"ticket": ticket, "response_sha256": sha(response)})
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
            code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            reason = f"HTTP {code}" if code else type(exc).__name__
            ledger.uncertain(ticket, reason)
            core.save(folder / "error.json", {"reason": reason})
            if code in (401, 402, 403, 404):
                core.save(root / "route-closed.json", {"reason": reason})
            raise Unavailable(reason) from None
    calls = payload["choices"][0]["message"].get("tool_calls") or []
    if len(calls) != 1 or calls[0]["function"]["name"] != name:
        raise ValueError(f"Expected one native {name} call, received {len(calls)}")
    return json.loads(calls[0]["function"]["arguments"])
