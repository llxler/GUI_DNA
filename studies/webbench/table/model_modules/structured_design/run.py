"""Resume failed designs using the author's structured interface declaration verbatim."""

from pathlib import Path
from unittest.mock import patch
import json

from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from .. import run as parent

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/table-structured-design-20261128"
CAP = 2.5
ORIGINAL = parent.OUT
ORIGINAL_ASK = parent.ask
ORIGINAL_DESIGN = parent.design


def design(raw):
    obj = json.loads(parent.model_api.calc.base.uncode(raw))
    for mod in obj["modules"]:
        interface = mod["interface"]
        if isinstance(interface, (dict, list)) and interface:
            mod["interface"] = json.dumps(interface, ensure_ascii=False)
    return ORIGINAL_DESIGN(json.dumps(obj, ensure_ascii=False))


def register():
    dst = OUT / "registration.json"
    initial = read(ORIGINAL / "registration.json")
    complete = read(ORIGINAL / "seal.json")
    tags = [
        tag for tag, lib in complete["libraries"].items() if lib["status"] != "valid"
    ]
    paths = [
        Path(__file__),
        HERE / "PROTOCOL.md",
        Path(parent.__file__),
        Path(parent.probes.__file__),
        ORIGINAL / "registration.json",
        ORIGINAL / "seal.json",
    ]
    for tag in tags:
        paths.extend(
            (ORIGINAL / "libraries" / tag).glob(
                "*/design/*/transmission-*/settled.json"
            )
        )
    sums = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    if not dst.exists():
        prior = (
            initial["prior_exposure"]
            + ledger_read.totals(ORIGINAL / "budget.sqlite3")["exposure_usd"]
        )
        assert prior + parent.incremental.CAP + CAP <= 20
        balance = check_credits(CAP)
        assert balance["sufficient"]
        core.save(
            dst,
            dict(
                utc=now(),
                cap=CAP,
                deadline=initial["deadline"],
                prior_exposure=prior,
                balance=balance,
                models={t: initial["models"][t] for t in tags},
                sources=sums,
                contract=initial["contract"],
            ),
        )
    assert read(dst)["sources"] == sums
    return read(dst)


def ask(ledger, tag, attempt, folder, prompt, stage, parser, tokens):
    if parser is design:
        old = ORIGINAL / "libraries" / tag / str(attempt + 1) / "design"
        for feedback_round in (0, 1):
            for receipt in sorted(
                (old / str(feedback_round)).glob("transmission-*/settled.json")
            ):
                raw = receipt.with_name("response.json")
                request = read(receipt.with_name("request.json"))["body"]
                assert (
                    request["model"]
                    == parent.model_api.calc.action.settings("table", tag, "build")[
                        "model"
                    ]
                )
                assert (
                    request["messages"][: len(prompt)] == prompt
                    and sha(raw) == read(receipt)["response_sha256"]
                )
                choice = read(raw)["choices"][0]
                if choice.get("finish_reason") == "error":
                    continue
                try:
                    parsed = design(choice["message"]["content"])
                except (ValueError, TypeError, KeyError):
                    continue
                core.save(
                    folder / "reused.json",
                    dict(
                        response=str(raw.relative_to(ROOT)),
                        sha256=sha(raw),
                        source_round=feedback_round,
                        modules=parsed,
                    ),
                )
                return parsed
    return ORIGINAL_ASK(ledger, tag, attempt, folder, prompt, stage, parser, tokens)


if __name__ == "__main__":
    with browser.lock(OUT / "study.lock"):
        reg = register()
        with patch.multiple(
            parent,
            OUT=OUT,
            HERE=HERE,
            CAP=CAP,
            TAGS=tuple(reg["models"]),
            ask=ask,
            design=design,
        ):
            parent.generate(reg)
            if not (HERE / "result.json").exists():
                parent.score(reg)
