"""Repeat exactly the six registered transport losses, retaining both ledgers."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from gui_dna.budget import Ledger
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from studies.webbench.backbone_matrix import run as original
from .. import run as parent
from ..file_repair import run as previous

OUT = ROOT / "artifacts/flash-form-transport-20261125"
CAP = 0.30


def complete():
    registration = read(OUT / "registration.json")
    assert registration["protocol_sha256"] == sha(Path(__file__).with_name("PROTOCOL.md"))
    assert registration["original_registration_sha256"] == sha(previous.OUT / "registration.json")
    assert registration["cap_usd"] == CAP
    scheduled = registration["original_requests"]
    assert len(scheduled) == 6
    public_path = previous.OUT / "inputs/form/public.json"
    public = read(public_path)
    core.save(OUT / "inputs/form/public.json", public)
    ledger = Ledger(OUT / "budget.sqlite3", CAP, CAP)
    methods = {}
    for branch in previous.BRANCHES:
        files = previous.OUT / branch / "form/build"
        target = OUT / branch / "form/build"
        for name in ("status.json", "package.json"):
            core.save(target / name, read(files / name))
            assert sha(target / name) == sha(files / name)
        methods[branch] = (parent.MODEL, CAP, .3, .9)

    def request(branch, ledger, folder, messages, purpose, limit=8192):
        prior = previous.OUT / folder.relative_to(OUT) / "request.json"
        key = f"{branch}/{int(folder.parent.name)}"
        assert sha(prior) == scheduled[key] and not prior.with_name("response.json").exists()
        assert read(prior)["body"]["messages"] == messages
        # Parent constructs the same target body used by the frozen batch.
        base = read(parent.OLD / parent.TAG / "form/gpt5-library/1/call/request.json")["body"]
        assert dict(base, messages=messages, max_tokens=limit) == read(prior)["body"]
        return parent.send(branch, ledger, folder, messages, purpose, limit)

    def replay(key):
        branch, n = key.split("/")
        folder = OUT / branch / "form/self" / n
        prior = previous.OUT / folder.relative_to(OUT)
        row = original.target(branch, "form", "self", int(n), ledger)
        assert read(folder / "call/request.json")["body"] == read(prior / "call/request.json")["body"]
        return key, {"row": row, "result_sha256": sha(folder / "result.json"),
                     "request_sha256": sha(folder / "call/request.json"), "original_request_sha256": scheduled[key]}

    with patch.multiple(original, OUT=OUT, MODELS=methods, request=request), patch.object(parent, "OUT", OUT):
        with ThreadPoolExecutor(max_workers=3) as pool:
            rows = dict(pool.map(replay, scheduled))
    payload = {"rows": rows, "registration_sha256": sha(OUT / "registration.json")}
    dest = OUT / "seal.json"
    if not dest.exists():
        core.save(dest, {"utc": now(), **payload})
    assert all(read(dest)[k] == v for k, v in payload.items())


if __name__ == "__main__":
    with browser.lock(OUT / ".lock"):
        complete()
