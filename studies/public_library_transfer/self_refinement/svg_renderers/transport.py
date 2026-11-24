"""Record priced requests to a single provider for the prospective SVG study."""

from datetime import datetime, timezone
from decimal import Decimal
import json
import os
import time

import httpx

from gui_dna.budget import BudgetStop
from studies.public_library_transfer import browser, core
from studies.public_library_transfer.deployments.historical.run import request_format
from studies.public_library_transfer.self_refinement.native.transport import Unavailable
from studies.study_io import read, sha

MODEL = "qwen/qwen3-coder-30b-a3b-instruct"
END = datetime(2026, 11, 24, 11, 27, tzinfo=timezone.utc)
MAX_PRICE = {"prompt": .12, "completion": .46, "request": 0}


def ask(out, ledger, name, messages, limit, schema=None):
    folder = out / "calls" / name
    body = {"model": MODEL, "temperature": .35, "messages": messages, "max_tokens": limit,
            "provider": {"only": ["SiliconFlow"], "allow_fallbacks": False, "require_parameters": True, "max_price": MAX_PRICE}}
    if schema is not None:
        body["response_format"] = request_format("renderers", schema)
    req, res, receipt = (folder / (stem + ".json") for stem in ("request", "response", "settled"))
    if req.exists():
        assert read(req)["body"] == body
        if receipt.exists():
            assert sha(res) == read(receipt)["response_sha256"]
            return read(res)["choices"][0]["message"].get("content") or ""
        raise Unavailable("Prior request has no settled delivery")
    if datetime.now(timezone.utc) >= END or (out / "route-closed.json").exists():
        raise Unavailable("Deadline or closed route")
    bound = len(json.dumps(body, ensure_ascii=False).encode()) + 2048
    reserve = (bound * Decimal(".12") + limit * Decimal(".46")) / 1000000
    ticket = ledger.reserve(reserve, name, MODEL)
    core.save(req, {"body": body, "call_id": ticket, "reserved_usd": float(reserve)})
    started = time.monotonic()
    try:
        r = httpx.post("https://openrouter.ai/api/v1/chat/completions", json=body, timeout=httpx.Timeout(125, connect=12),
                       headers={"Authorization": "Bearer " + os.environ["OPENROUTER_API_KEY"]})
        r.raise_for_status()
        payload = r.json()
        core.save(res, payload)
        usage = payload["usage"]
        content = payload["choices"][0]["message"].get("content") or ""
        if usage.get("cost") is None:
            raise ValueError("Missing charge")
    except (httpx.HTTPError, ValueError, TypeError, KeyError, IndexError) as e:
        status = e.response.status_code if isinstance(e, httpx.HTTPStatusError) else None
        reason = f"HTTP {status}" if status else type(e).__name__
        ledger.uncertain(ticket, reason)
        core.save(folder / "error.json", {"reason": reason})
        if status in (401, 402, 403, 404):
            with browser.lock(out / "route.lock"):
                if not (out / "route-closed.json").exists():
                    core.save(out / "route-closed.json", {"reason": reason})
        raise Unavailable(reason) from None
    ledger.settle(ticket, usage["cost"], time.monotonic() - started, payload.get("id"), usage)
    core.save(receipt, {"call_id": ticket, "response_sha256": sha(res)})
    return content
