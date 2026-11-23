"""Paired paid deployments of historical models on two sealed public-library sources."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
import fcntl
import json
import os
from pathlib import Path
import time

import httpx

from gui_dna.budget import BudgetStop, Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer_extra.generate import (
    HERE,
    OUT,
    ROOT,
    dump,
    now,
    read,
    sha,
)

DIR = ROOT / "artifacts/public-library-transfer-extra-remote-20261123"
CAP = 2
END = datetime(2026, 11, 23, 9, 24, tzinfo=UTC)
MODELS = {
    "mistral": ("mistralai/mistral-small-3.2-24b-instruct", 0.12, 0.45),
    "oss": ("openai/gpt-oss-120b", 0.12, 0.45),
    "qwen30b": ("qwen/qwen3-coder-30b-a3b-instruct", 0.12, 0.45),
    "deepseek": ("deepseek/deepseek-v4-pro-0813", 1.6, 4.5),
    "qwen": ("qwen/qwen3-coder", 0.65, 2),
}
TODO_MODELS = ("mistral", "oss", "qwen30b", "deepseek")
DUO_MODELS = ("deepseek", "qwen", "mistral", "oss")


def register():
    if (DIR / "registered.json").exists():
        return
    credits = check_credits(CAP)
    if not credits["sufficient"]:
        raise BudgetStop("Balance below allotted cap")
    targets = read(OUT / "targets.json")
    requests = {}
    for alias, (model, prompt, completion) in MODELS.items():
        for task, row in targets.items():
            todo = row["group"] == "todomvc"
            if alias not in (TODO_MODELS if todo else DUO_MODELS):
                continue
            for sample in range(2 if todo else 1):
                for arm, prior in [
                    ("direct", f"direct/{task}"),
                    ("dna-a", f"plan/a/{task}"),
                    ("dna-b", f"plan/b/{task}"),
                ]:
                    directory = DIR / "requests" / alias / task / f"s{sample}" / arm
                    schema = read(OUT / prior / "schema.json")
                    body = {
                        "model": model,
                        "temperature": 0.6,
                        "max_tokens": 4000 if arm == "direct" else 550,
                        "messages": [
                            {
                                "role": "user",
                                "content": (OUT / prior / "prompt.txt").read_text(),
                            }
                        ],
                        "provider": {
                            "allow_fallbacks": True,
                            "require_parameters": True,
                            "sort": "price",
                            "max_price": {
                                "prompt": prompt,
                                "completion": completion,
                                "request": 0,
                            },
                        },
                        "response_format": {
                            "type": "json_schema",
                            "json_schema": {
                                "name": "implementation"
                                if arm == "direct"
                                else "configuration",
                                "strict": True,
                                "schema": schema,
                            },
                        },
                    }
                    if alias != "qwen30b":
                        body["seed"] = (20261102 if todo else 20261101) + sample
                    if alias == "oss":
                        body["reasoning"] = {"effort": "low", "exclude": True}
                    dump(directory / "body.json", body)
                    key = directory.relative_to(DIR / "requests").as_posix()
                    requests[key] = {
                        "group": row["group"],
                        "task": task,
                        "sample": sample,
                        "arm": arm,
                        "alias": alias,
                        "body_sha256": sha(directory / "body.json"),
                    }
    dump(
        DIR / "registered.json",
        dict(
            registered=now(),
            cap_usd=CAP,
            deadline=END.isoformat(),
            credit_check=credits,
            prices_and_models=MODELS,
            source_sha256={
                p.name: sha(p)
                for p in [
                    Path(__file__),
                    HERE / "evaluate.py",
                    HERE / "HISTORICAL_MODELS.md",
                ]
            },
            main_seal_sha256=sha(OUT / "sealed.json"),
            requests=requests,
        ),
    )


def action(key, meta, ledger):
    path = DIR / "requests" / key
    if (path / "status.json").exists():
        return read(path / "status.json")
    if (path / "admit.json").exists():
        raise RuntimeError("Unresolved admission; retain exposure")
    if sha(path / "body.json") != meta["body_sha256"]:
        raise RuntimeError("Sealed request changed")
    if datetime.now(UTC) >= END:
        raise BudgetStop("Deadline reached")
    body = read(path / "body.json")
    _, p, c = MODELS[meta["alias"]]
    bound = len(json.dumps(body, ensure_ascii=False).encode()) + 2048
    reserve = (
        Decimal(bound) * Decimal(str(p)) + Decimal(body["max_tokens"]) * Decimal(str(c))
    ) / 1000000
    cid = ledger.reserve(reserve, key, body["model"])
    dump(
        path / "admit.json",
        dict(
            call_id=cid,
            reserved_usd=float(reserve),
            started=now(),
            body_sha256=meta["body_sha256"],
        ),
    )
    start = time.monotonic()
    try:
        r = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": "Bearer " + os.environ["OPENROUTER_API_KEY"],
                "X-Title": "GUI-DNA public library historical transfer",
            },
            json=body,
            timeout=120,
        )
        r.raise_for_status()
        payload = r.json()
        dump(path / "raw.json", payload)
        usage = payload.get("usage") or {}
        if usage.get("cost") is None:
            raise ValueError("Unknown charge")
        ledger.settle(
            cid, usage["cost"], time.monotonic() - start, payload.get("id"), usage
        )
        status = dict(
            status="returned", raw_sha256=sha(path / "raw.json"), cost_usd=usage["cost"]
        )
    except Exception as exc:
        http = (
            exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
        )
        detail = "HTTP " + str(http) if http else type(exc).__name__
        ledger.uncertain(cid, detail)
        status = dict(status="unresolved", reason=detail, http_status=http)
    dump(path / "status.json", status)
    return status


def run_model(alias, reg, ledger):
    stop_file = DIR / "endpoint-stops" / f"{alias}.json"
    if stop_file.exists():
        return
    consecutive = 0
    for key, meta in reg["requests"].items():
        if meta["alias"] != alias:
            continue
        try:
            state = action(key, meta, ledger)
        except (BudgetStop, RuntimeError) as exc:
            dump(stop_file, dict(stopped=now(), request=key, reason=str(exc)))
            break
        if state["status"] == "returned":
            consecutive = 0
        else:
            consecutive += 1
            if (
                state.get("http_status") in (400, 401, 402, 403, 404, 422)
                or consecutive >= 2
            ):
                dump(
                    stop_file, dict(stopped=now(), request=key, reason=state["reason"])
                )
                break
    print(alias, "complete or stopped", flush=True)


def run():
    if (DIR / "sealed.json").exists():
        raise RuntimeError("Already sealed")
    reg = read(DIR / "registered.json")
    if sha(OUT / "sealed.json") != reg["main_seal_sha256"] or any(
        sha(HERE / f) != v for f, v in reg["source_sha256"].items()
    ):
        raise RuntimeError("Registered dependency changed")
    ledger = Ledger(DIR / "budget.sqlite3", CAP, CAP)
    with ThreadPoolExecutor(max_workers=len(MODELS)) as pool:
        list(pool.map(lambda model: run_model(model, reg, ledger), MODELS))
    status = {
        k: sha(DIR / "requests" / k / "status.json")
        for k in reg["requests"]
        if (DIR / "requests" / k / "status.json").exists()
    }
    dump(
        DIR / "sealed.json",
        dict(
            sealed=now(),
            statuses=status,
            registered_sha256=sha(DIR / "registered.json"),
            account=ledger_read.totals(DIR / "budget.sqlite3"),
        ),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["register", "run"])
    args = parser.parse_args()
    if args.phase == "register":
        register()
    else:
        with (DIR / "lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            run()
