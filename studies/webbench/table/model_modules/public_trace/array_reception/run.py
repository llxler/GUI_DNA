"""Replay literal top-level edit arrays against each original request's source."""

import json
from pathlib import Path
from unittest.mock import patch

from scripts.check_openrouter_credits import check_credits
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from studies.webbench.calculator.memory_recall import run as memory
from .. import run as original

table = original.table
HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/table-self-edit-arrays-20261128"
CAP = 0.50


def register():
    dest = OUT / "registration.json"
    paths = [
        Path(__file__),
        HERE / "PROTOCOL.md",
        Path(original.__file__),
        Path(table.__file__),
        Path(table.probes.__file__),
        original.OUT / "registration.json",
        memory.OUT / "registration.json",
    ]
    sums = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    if not dest.exists():
        prior = read(memory.OUT / "registration.json")
        upper = prior["upper"] + CAP
        assert upper <= 20
        balance = check_credits(CAP)
        assert balance["sufficient"]
        parent = read(original.OUT / "registration.json")
        core.save(
            dest,
            dict(
                utc=now(),
                deadline=prior["deadline"],
                cap=CAP,
                upper=upper,
                balance=balance,
                models=parent["models"],
                sources=sums,
                contract=parent["contract"],
            ),
        )
    assert read(dest)["sources"] == sums
    return read(dest)


def answers(tag):
    folder = original.OUT / "libraries" / tag
    for receipt in sorted(folder.glob("*/*/repair/*/transmission-*/settled.json")):
        source = receipt.with_name("response.json")
        assert sha(source) == read(receipt)["response_sha256"]
        request = read(receipt.with_name("request.json"))["body"]
        assert (
            request["model"] == read(original.OUT / "registration.json")["models"][tag]
        )
        raw = read(source)["choices"][0]
        try:
            edits = json.loads(
                table.model_api.calc.base.uncode(raw["message"]["content"])
            )
        except (TypeError, ValueError):
            continue
        if isinstance(edits, list) and raw.get("finish_reason") != "error":
            yield receipt, request, edits


def build(tag, ledger, pub):
    dest = OUT / "libraries" / tag / "library.json"
    if dest.exists():
        return read(dest)
    trials = []
    cache = {}
    adopted = None
    for receipt, request, edits in answers(tag):
        position = receipt.relative_to(original.OUT / "libraries" / tag).parts
        payload = json.loads(request["messages"][1]["content"])
        trial = dict(
            attempt=len(trials) + 1,
            original_library=int(position[0]),
            round=int(position[1]),
            response_sha256=sha(receipt.with_name("response.json")),
            request_sha256=sha(receipt.with_name("request.json")),
            status="build_failed",
        )
        base_record = read(
            original.structured.OUT / "libraries" / tag / position[0] / "attempt.json"
        )
        assert base_record["design"] == payload["design"]
        try:
            files, _ = original.edits(json.dumps({"edits": edits}), payload["files"])
            fingerprint = browser.digest(files)
            trial["files_digest"] = fingerprint
            if fingerprint not in cache:
                folder = OUT / "libraries" / tag / "candidates" / fingerprint
                page = table.emit(
                    pub,
                    payload["design"],
                    files,
                    len(payload["design"]),
                    folder / "page",
                )
                cache[fingerprint] = table.inspect(page, folder / "probe")
            observed = cache[fingerprint]
            prior = payload["checks"]["checks"]
            current = observed["checks"]
            trial["public"] = observed
            ok = (
                all(not v or current[k] for k, v in prior.items())
                and all(current[k] for k in table.REQUIRED)
                and not observed["errors"]
            )
            if ok:
                trial["status"] = "valid"
                adopted = (files, payload["design"])
        except (KeyError, TypeError, ValueError) as exc:
            trial["reason"] = str(exc)
        trials.append(trial)
        if adopted is not None:
            break
    assert trials
    files, design = adopted or ({}, [])
    core.save(
        dest,
        dict(
            status=trials[-1]["status"],
            attempt=trials[-1]["attempt"] if adopted else None,
            parts=files,
            design=design,
            trials=trials,
            parent_seal=sha(original.OUT / "seal.json"),
        ),
    )
    return read(dest)


def run():
    reg = register()
    sealed = original.OUT / "seal.json"
    if not sealed.exists():
        return
    tags = [
        t
        for t, v in read(sealed)["libraries"].items()
        if v["status"] == "build_failed" and next(answers(t), None) is not None
    ]
    selected = reg | {"models": {t: reg["models"][t] for t in tags}}
    with patch.multiple(
        table, OUT=OUT, HERE=HERE, CAP=CAP, TAGS=tuple(tags), build=build
    ):
        table.generate(selected)
        if not (HERE / "result.json").exists():
            table.score(selected)


if __name__ == "__main__":
    with browser.lock(OUT / "study.lock"):
        run()
