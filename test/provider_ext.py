"""OpenRouter client for the external-benchmark stages: identical to the frozen gui_dna.provider.OpenRouter except
that reasoning models are asked for low-effort reasoning instead of having reasoning disabled (which the OpenAI
endpoints reject with HTTP 400/404).  `_single` is copied from the frozen file with that one change.
"""
from __future__ import annotations

import json
import os
import time
from decimal import Decimal
from pathlib import Path

import httpx

from gui_dna.provider import OpenRouter, ProviderError, RateLimited
from gui_dna.tasks import dump


class ReasoningAwareOpenRouter(OpenRouter):
    def _single(self, model, messages, out, purpose, max_tokens=None, seed=None):
        out = Path(out)
        out.mkdir(parents=True, exist_ok=True)
        config = self.config
        caps = config.get("model_price_caps", {}).get(model, config["price_caps_per_million"])
        max_tokens = max_tokens or config["max_tokens"]
        body = {"model": model, "messages": messages, "temperature": config["temperature"],
                "max_tokens": max_tokens, "stream": False,
                "response_format": {"type": "json_object"},
                "provider": {"allow_fallbacks": False, "require_parameters": True,
                             "max_price": {**caps, "request": 0}}}
        supported = self.models[model]["supported_parameters"]
        if model in config.get("provider_order", {}):
            body["provider"]["order"] = config["provider_order"][model]
        if "seed" in supported and seed is not None:
            body["seed"] = seed
        if "reasoning" in supported:
            effort = config.get("reasoning_effort", {}).get(model)
            body["reasoning"] = {"effort": effort} if effort else {"enabled": False}   # change 1: allow low-effort reasoning
        for key in config.get("omit_params", {}).get(model, []):                        # change 2: e.g. gpt-5 rejects temperature
            body.pop(key, None)
        input_bound = sum(len(m["content"].encode()) + 256 for m in messages) + 1024
        reserve = (Decimal(input_bound) * Decimal(str(caps["prompt"])) + Decimal(max_tokens) * Decimal(str(caps["completion"]))) / 1_000_000
        call_id = self.ledger.reserve(reserve, purpose, model)
        dump(out / "request.json", {"call_id": call_id, "input_token_upper_bound": input_bound,
                                     "reserved_usd": float(reserve), "body": body, "model_metadata": self.models[model]})
        started = time.monotonic()
        try:
            response = httpx.post("https://openrouter.ai/api/v1/chat/completions", json=body,
                                  headers={"Authorization": "Bearer " + os.environ["OPENROUTER_API_KEY"],
                                           "X-OpenRouter-Title": "GUI DNA research prototype"}, timeout=300)
            response.raise_for_status()
            payload = response.json()
            dump(out / "response.json", payload)
            usage = payload.get("usage", {})
            if usage.get("cost") is None:
                raise ProviderError("Response has no billed cost; reservation retained and no retry issued")
            self.ledger.settle(call_id, usage["cost"], time.monotonic() - started, payload.get("id"), usage)
            if payload.get("error"):
                raise ProviderError(str(payload["error"]))
            content = payload["choices"][0]["message"]["content"]
            if content is None:
                return ""
            if not isinstance(content, str):
                raise ProviderError("Provider returned non-text content")
            return content
        except Exception as error:
            detail = f"{type(error).__name__}: " + (f"HTTP {error.response.status_code}" if isinstance(error, httpx.HTTPStatusError) else str(error))
            self.ledger.uncertain(call_id, detail)
            receipt = {"call_id": call_id, "error": detail}
            if isinstance(error, httpx.HTTPStatusError):
                receipt["http_status"] = error.response.status_code
                try:
                    safe_body = json.dumps(error.response.json()).replace(os.environ.get("OPENROUTER_API_KEY", ""), "[REDACTED]")
                    receipt["provider_error"] = json.loads(safe_body).get("error")
                except (ValueError, AttributeError):
                    pass
                hint = error.response.headers.get("retry-after", "30")
                receipt["retry_after"] = int(hint) if hint.isdigit() else 30
            dump(out / "error.json", receipt)
            if receipt.get("http_status") == 429:
                raise RateLimited(detail, receipt["retry_after"]) from None
            raise ProviderError(detail) from None
