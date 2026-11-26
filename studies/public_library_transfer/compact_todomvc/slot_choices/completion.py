"""Complete only missing categorical decisions, retaining the original request and response links."""
import time
from pathlib import Path
from threading import Lock
from unittest.mock import patch

from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from . import run as slots

OUT = ROOT / "artifacts/todo-slot-completion-20261126"
CAP = .45
OLD = slots.OUT
TAG = slots.TAG
RESULT = slots.HERE / "completion-result.json"


def register():
    files = [Path(__file__), slots.HERE / "completion.md", Path(slots.__file__),
             OLD / "registration.json", OLD / TAG / "seal.json"]
    sources = {str(p.relative_to(ROOT)): sha(p) for p in files}
    dest = OUT / "registration.json"
    if not dest.exists():
        balance = check_credits(CAP)
        assert balance["sufficient"]
        core.save(dest, dict(utc=now(), deadline=slots.previous.contract.route.END.isoformat(),
                             model=slots.WEAK.SMALL[TAG], cap=CAP, balance=balance, sources=sources))
    assert read(dest)["sources"] == sources


def generate():
    for record in (OLD / TAG).glob("*/*/record.json"):
        arm = record.parent.name
        if read(record)[arm]["status"] != "missing":
            core.save(OUT / record.relative_to(OLD), read(record))
    transmit = slots.BASE.request
    lock = Lock()

    def resume(ledger, case, folder, messages, stage, limit):
        assert stage == "plan"
        body = slots.EVENTS.template(case[0], TAG, stage) | dict(messages=messages, max_tokens=limit)
        for receipt in sorted((OLD / folder.relative_to(OUT)).glob("transmission-*/settled.json")):
            response = receipt.with_name("response.json")
            assert read(receipt.with_name("request.json"))["body"] == body
            assert sha(response) == read(receipt)["response_sha256"]
            core.save(folder / "reused.json", dict(source=str(response.relative_to(ROOT)), sha256=sha(response)))
            return read(response)["choices"][0]["message"].get("content") or ""
        with lock:
            time.sleep(6)
            return transmit(ledger, case, folder, messages, stage, limit)

    with patch.multiple(slots, OUT=OUT, CAP=CAP), patch.object(slots.BASE, "request", resume):
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
