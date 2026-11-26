"""Respect provider backoff and resume two interrupted TodoMVC plans."""
import time
from pathlib import Path
from threading import Lock
from unittest.mock import patch

from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from . import completion, run as slots

OUT = ROOT / "artifacts/todo-slot-final-20261126"
CAP = .20
TAG = slots.TAG
RESULT = slots.HERE / "last-result.json"
ORIGINS = (slots.OUT, completion.OUT)


def register():
    files = [Path(__file__), slots.HERE / "last_delivery.md", Path(slots.__file__),
             *(origin / TAG / "seal.json" for origin in ORIGINS)]
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in files}
    reg = OUT / "registration.json"
    if not reg.exists():
        balance = check_credits(CAP)
        assert balance["sufficient"]
        core.save(reg, dict(utc=now(), balance=balance, cap=CAP, sources=hashes,
                             model=slots.WEAK.SMALL[TAG], deadline=slots.previous.contract.route.END.isoformat()))
    assert read(reg)["sources"] == hashes


def generate():
    previous = ORIGINS[-1]
    for record in (previous / TAG).glob("*/*/record.json"):
        if read(record)[record.parent.name]["status"] != "missing":
            core.save(OUT / record.relative_to(previous), read(record))
    lock = Lock()
    send = slots.BASE.request
    http = slots.BASE.httpx.post

    def throttled(*args, **kwargs):
        time.sleep(12)
        reply = http(*args, **kwargs)
        if reply.status_code == 429:
            time.sleep(25)
        return reply

    def replay(ledger, case, folder, messages, stage, limit):
        assert stage == "plan"
        body = slots.EVENTS.template(case[0], TAG, stage) | dict(messages=messages, max_tokens=limit)
        for origin in ORIGINS:
            for receipt in sorted((origin / folder.relative_to(OUT)).glob("transmission-*/settled.json")):
                assert read(receipt.with_name("request.json"))["body"] == body
                response = receipt.with_name("response.json")
                assert sha(response) == read(receipt)["response_sha256"]
                core.save(folder / "reused.json", dict(source=str(response.relative_to(ROOT)), sha256=sha(response)))
                return read(response)["choices"][0]["message"].get("content") or ""
        with lock:
            try:
                return send(ledger, case, folder, messages, stage, limit)
            except slots.BASE.original.Unavailable:
                errors = [read(f)["reason"] for f in folder.glob("transmission-*/error.json")]
                if errors != ["HTTP 429"] * 2:
                    raise
                return send(ledger, case, folder / "last", messages, stage, limit)

    with patch.multiple(slots, OUT=OUT, CAP=CAP), patch.object(slots.BASE, "request", replay), patch.object(slots.BASE.httpx, "post", throttled):
        slots.generate()


if __name__ == "__main__":
    with browser.lock(OUT / ".run.lock"):
        register()
        generate()
        with patch.multiple(slots.WEAK, OUT=OUT, MODELS={TAG: slots.WEAK.SMALL[TAG]}):
            slots.WEAK.score()
        core.save(RESULT, dict(registration=sha(OUT / "registration.json"),
                              cost=ledger_read.totals(OUT / "budget.sqlite3"),
                              models={slots.WEAK.SMALL[TAG]: read(OUT / TAG / "result.json")}))
