"""Budgeted streaming transport; retain raw SSE events and require a terminal billed response.

Sampling, JSON format, prices and repair limits match the non-streaming client.
See https://github.com/OpenRouterTeam/docs/blob/main/api_reference/streaming.mdx
and cookbook/administration/usage-accounting.mdx.
"""
from __future__ import annotations
import json
import os
import time
from decimal import Decimal
from pathlib import Path
import httpx
from gui_dna.provider import ProviderError, RateLimited
from gui_dna.tasks import dump
from test.provider_ext import ReasoningAwareOpenRouter


def assemble_chunks(chunks, done):
    payload, text, finish = {}, [], None
    for chunk in chunks:
        for key in ('id', 'model', 'provider', 'created', 'usage', 'error'):
            if chunk.get(key) is not None:
                payload[key] = chunk[key]
        for choice in chunk.get('choices', []):
            if choice.get('index', 0) != 0:
                continue
            content = choice.get('delta', {}).get('content')
            if isinstance(content, str):
                text.append(content)
            if choice.get('finish_reason'):
                finish = choice['finish_reason']
    if not done or not finish:
        raise ProviderError('Incomplete stream: no terminal DONE/finish reason; reservation retained')
    if payload.get('usage', {}).get('cost') is None:
        raise ProviderError('Stream has no billed cost; reservation retained')
    payload['choices'] = [{'index': 0, 'message': {'role': 'assistant', 'content': ''.join(text)}, 'finish_reason': finish}]
    return payload


def stream_payload(body, out):
    chunks, done = [], False
    with httpx.stream('POST', 'https://openrouter.ai/api/v1/chat/completions', json=body,
            headers={'Authorization': 'Bearer ' + os.environ['OPENROUTER_API_KEY'],
                     'X-OpenRouter-Title': 'GUI DNA research prototype'}, timeout=900) as response:
        if response.is_error:
            response.read()
        response.raise_for_status()
        with (out / 'stream-events.jsonl').open('w') as handle:
            for line in response.iter_lines():
                if not line.startswith('data:'):
                    continue
                data = line[5:].strip()
                if data == '[DONE]':
                    done = True
                    break
                if not data:
                    continue
                chunk = json.loads(data)
                handle.write(json.dumps(chunk) + '\n')
                handle.flush()
                chunks.append(chunk)
    return assemble_chunks(chunks, done)


class StreamingOpenRouter(ReasoningAwareOpenRouter):
    def _single(self, model, messages, out, purpose, max_tokens=None, seed=None):
        out = Path(out)
        out.mkdir(parents=True, exist_ok=True)
        config = self.config
        caps = config.get("model_price_caps", {}).get(model, config["price_caps_per_million"])
        max_tokens = max_tokens or config["max_tokens"]
        body = {"model": model, "messages": messages, "temperature": config["temperature"],
                "max_tokens": max_tokens, "stream": True,
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
            payload = stream_payload(body, out)
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
