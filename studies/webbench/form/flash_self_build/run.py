"""Run two independent Flash questionnaire preparations per registered method."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import threading
import time
from unittest.mock import patch

import httpx

from gui_dna.budget import BudgetStop, Ledger
from scripts.check_openrouter_credits import check_credits
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from studies.webbench.backbone_matrix import run as original

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/flash-form-self-20261125"
OLD = ROOT / "artifacts/backbone-form-20261124"
TAG = "deepseek-flash"
MODEL = "deepseek/deepseek-v4-flash"
BRANCHES = ("delivery-a", "delivery-b", "staged-a", "staged-b")
END = datetime(2026, 11, 25, 3, 40, tzinfo=timezone.utc)
CAP = 5
TASKS = range(1, 21)
SLOTS = threading.BoundedSemaphore(5)


def register(staged=False):
    names = [HERE / "PROTOCOL.md", Path(__file__), Path(original.__file__),
             Path(core.__file__), Path(browser.__file__), OLD / "inputs/form/public.json",
             OLD / "inputs/form/browser.json", OLD / TAG / "seal.json",
             ROOT / "studies/results/backbone-form-20261124.json",
             OLD / TAG / "form/build/attempt-1/request.json",
             OLD / TAG / "form/gpt5-library/1/call/request.json", OLD / "registered.json"]
    if staged:
        names += [HERE / "staged.py", HERE / "staged.md"]
    path = OUT / ("staged-registration.json" if staged else "registration.json")
    files = {str(p.relative_to(ROOT)): sha(p) for p in names}
    if path.exists():
        assert read(path)["files"] == files
        return
    if not staged:
        balance = check_credits(CAP)
        if not balance["sufficient"]:
            raise BudgetStop("Insufficient account balance")
        pkg = read(OLD / "inputs/form/public.json")
        assert pkg == core.public_input("form")
        assert browser.verify_contract("form") == read(OLD / "inputs/form/browser.json")
        core.save(OUT / "inputs/form/public.json", pkg)
        core.save(OUT / "balance.json", balance)
    core.save(path, {"utc": now(), "files": files, "branches": BRANCHES, "deadline": END.isoformat(),
                     "budget_usd": CAP, "model": MODEL, "scheduled": list(TASKS)})


def send(branch, ledger, folder, messages, purpose, limit):
    preparation = not purpose.startswith("target/")
    purpose = branch + ("/build/" if preparation else "/plan/") + purpose
    # Use the same routing, model, seed, temperature and deployment settings as Panel A.
    base_path = (OLD / TAG / "form/build/attempt-1/request.json" if preparation else
                 OLD / TAG / "form/gpt5-library/1/call/request.json")
    base = read(base_path)["body"]
    body = {k: v for k, v in base.items() if k != "messages"}
    assert body["model"] == MODEL
    body.update(messages=messages, max_tokens=limit)
    if preparation:
        body["reasoning"] = {"enabled": False}
        if branch.endswith("-b"):
            body["seed"] += 1
    req, res, stamp = (folder / f"{key}.json" for key in ("request", "response", "settled"))
    if req.exists():
        assert read(req)["body"] == body
        if stamp.exists():
            assert sha(res) == read(stamp)["response_sha256"]
            return read(res)["choices"][0]["message"].get("content") or ""
        raise original.Unavailable("Previous unresolved or undelivered response")
    with SLOTS:
        if datetime.now(timezone.utc) >= END or (OUT / "closed.json").exists():
            raise original.Unavailable("Time window or route closed")
        price = body["provider"]["max_price"]
        bound = len(json.dumps(body, ensure_ascii=False).encode()) + 2048
        cap = (bound * Decimal(str(price["prompt"])) + limit * Decimal(str(price["completion"]))) / 1_000_000
        ticket = ledger.reserve(cap, purpose, MODEL)
        core.save(req, {"body": body, "call_id": ticket, "input_bound": bound, "reserved_usd": float(cap)})
        t0 = time.monotonic()
        try:
            r = httpx.post("https://openrouter.ai/api/v1/chat/completions", json=body,
                           headers={"Authorization": "Bearer " + os.environ["OPENROUTER_API_KEY"]},
                           timeout=httpx.Timeout(180, connect=20))
            r.raise_for_status()
            payload = r.json()
            core.save(res, payload)
            usage = payload["usage"]
            if usage.get("cost") is None:
                raise ValueError("Missing usage")
            choice = payload["choices"][0]
        except (httpx.HTTPError, ValueError, IndexError, KeyError, TypeError) as exc:
            status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            reason = f"HTTP {status}" if status else type(exc).__name__
            ledger.uncertain(ticket, reason)
            core.save(folder / "error.json", {"reason": reason})
            if status in (401, 402, 403, 404):
                core.save(OUT / "closed.json", {"reason": reason})
            raise original.Unavailable(reason) from None
        ledger.settle(ticket, usage["cost"], time.monotonic() - t0, payload.get("id"), usage)
        core.save(stamp, {"ticket": ticket, "response_sha256": sha(res)})
        if choice.get("finish_reason") == "error":
            raise original.Unavailable("Provider error finish")
    return choice["message"].get("content") or ""


def generate(branch):
    staged = branch.startswith("staged")
    register(staged)
    root = OUT / branch / "form"
    with browser.lock(OUT / branch / ".run.lock"):
        if (OUT / branch / "seal.json").exists():
            return
        ledger = Ledger(OUT / "budget.sqlite3", CAP, CAP)
        with patch.multiple(original, OUT=OUT, MODELS={branch: (MODEL, CAP, .3, .9)}, request=send), patch.object(browser, "OUT", OUT):
            if staged:
                from .staged import build_staged
                status = root / "build/status.json"
                if not status.exists():
                    def ask(folder, messages, purpose, max_tokens):
                        return send(branch, ledger, folder, messages, purpose, max_tokens)
                    try:
                        state = build_staged(read(OUT / "inputs/form/public.json"), root / "build", ask)
                    except (BudgetStop, original.Unavailable) as exc:
                        state = {"status": "missing", "reason": str(exc)}
                    core.save(status, state)
            else:
                original.build(branch, "form", ledger)
            state = read(root / "build/status.json")
            with ThreadPoolExecutor(max_workers=3) as pool:
                rows = list(pool.map(lambda n: original.target(branch, "form", "self", n, ledger), TASKS))
        fixed = state.get("fixed")
        pack = root / "build/package.json"
        core.save(OUT / branch / "seal.json", {"build": state, "build_sha256": sha(root / "build/status.json"),
                  "package_sha256": sha(pack) if pack.is_file() else None,
                  "fixed_files": browser.tree(ROOT / fixed) if fixed else {}, "rows": rows,
                  "row_sha256": {str(n): sha(root / "self" / str(n) / "result.json") for n in TASKS}})


def seal():
    register()
    register(True)
    payload = {"registration_sha256": sha(OUT / "registration.json"),
               "staged_registration_sha256": sha(OUT / "staged-registration.json"),
               "branches": {k: read(OUT / k / "seal.json") for k in BRANCHES}}
    dest = OUT / "seal.json"
    if not dest.exists():
        core.save(dest, {"utc": now(), **payload})
    assert all(read(dest)[k] == v for k, v in payload.items())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["register", "seal", *BRANCHES])
    action = parser.parse_args().action
    if action == "register":
        register()
    elif action == "seal":
        seal()
    else:
        generate(action)
