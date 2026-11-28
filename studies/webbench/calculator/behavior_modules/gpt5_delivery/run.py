"""Complete undelivered GPT-5 builds using the same model and registered interface."""

from pathlib import Path
from unittest.mock import patch

import httpx
from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from .. import run as parent

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/calculator-behavior-gpt5-delivery-20261128"
CAP = 2.0
FAILED = parent.OUT / "closed-gpt5.json"


def register():
    path = OUT / "registration.json"
    inputs = [
        HERE / "PROTOCOL.md",
        Path(__file__),
        Path(parent.__file__),
        parent.HERE / "host.js",
        parent.HERE / "probe.js",
        FAILED,
        parent.OUT / "registration.json",
        parent.calc.OUT / "public.json",
    ]
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in inputs}
    if not path.exists():
        reg = read(parent.OUT / "registration.json")
        assert (
            read(FAILED)["reason"] == "HTTP 403"
            and reg["prior_exposure_usd"] + reg["cap"] + CAP <= 20
        )
        balance = check_credits(CAP)
        assert balance["sufficient"]
        res = httpx.get(
            "https://openrouter.ai/api/v1/models/openai/gpt-5/endpoints", timeout=20
        )
        res.raise_for_status()
        routes = [
            e
            for e in res.json()["data"]["endpoints"]
            if e["tag"] == "azure" and e["status"] == 0
        ]
        assert routes and reg["models"]["gpt5"] == "openai/gpt-5"
        core.save(
            path,
            dict(
                utc=now(),
                deadline=reg["deadline"],
                cap=CAP,
                sources=hashes,
                provider=routes[0]["tag"],
                model=reg["models"]["gpt5"],
                balance=balance,
                seed=2026112613,
                harness=reg["harness"],
            ),
        )
    assert read(path)["sources"] == hashes
    return read(path)


def build(reg):
    pub = read(parent.calc.OUT / "public.json")
    base = parent.calc.base
    real_post = httpx.post

    def log_failure(*args, **kwargs):
        response = real_post(*args, **kwargs)
        if response.is_error:
            try:
                err = response.json()["error"]
                msg = str(err.get("message", ""))[:300]
            except (ValueError, KeyError, TypeError):
                msg = "No structured provider message"
            index = len(list(OUT.glob("provider-failure-*.json")))
            core.save(
                OUT / f"provider-failure-{index}.json",
                dict(status=response.status_code, message=msg),
            )
        return response

    def settings(project, tag, stage):
        body = parent.calc.action.settings(project, tag, stage)
        body["provider"] |= dict(only=[reg["provider"]], allow_fallbacks=False)
        body["seed"] = reg["seed"] + getattr(parent.REQUEST, "attempt", 0)
        return body

    ledger = Ledger(OUT / "budget.sqlite3", CAP, CAP)
    with (
        patch.object(parent, "OUT", OUT),
        patch.multiple(base, OUT=OUT, END=parent.END, template=settings),
        patch.object(httpx, "post", log_failure),
    ):
        empty = parent.probe(
            parent.compile_page(
                pub["starter"]["index.html"], {}, parent.NONE, OUT / "binding"
            )
        )
        lib = parent.build("gpt5", ledger, pub, empty)
    return pub, lib


def generate(reg, pub, lib):
    primary = parent.OUT / "seal.json"
    seal = OUT / "seal.json"
    if seal.exists():
        return
    if not primary.exists():
        return
    source = read(primary)
    assert source["libraries"]["gpt5"]["status"] == "missing"
    rows = []
    for r in source["rows"]:
        if r["arm"] not in ("gpt5-library", "fixed-gpt5-library"):
            continue
        levels = r["levels"]
        if lib["status"] != "valid":
            candidate = dict(status=lib["status"])
        elif levels is None:
            candidate = dict(
                status=read(
                    parent.OUT / "plans" / r["tag"] / str(r["task"]) / "choice.json"
                )["status"]
            )
        else:
            folder = OUT / "pages" / "".join(map(str, levels))
            candidate = parent.compile_page(
                pub["starter"]["index.html"], lib["parts"], levels, folder
            )
        rows.append(
            dict(
                project="calculator",
                arm=r["arm"],
                task=r["task"],
                tag=r["tag"],
                levels=levels,
                **candidate,
            )
        )
    core.save(
        seal,
        dict(
            main_seal=sha(primary),
            registration=sha(OUT / "registration.json"),
            rows=rows,
            library={k: v for k, v in lib.items() if k != "parts"},
        ),
    )


def score(reg, pub, lib):
    seal = read(OUT / "seal.json")
    assert seal["main_seal"] == sha(parent.OUT / "seal.json") and reg[
        "harness"
    ] == browser.verify_contract("calculator")
    heldout = {}
    if lib["status"] == "valid":
        heldout = parent.probe(
            parent.compile_page(
                pub["starter"]["index.html"], lib["parts"], parent.FULL, OUT / "heldout"
            ),
            True,
        )
    scored = browser.evaluate(seal["rows"], OUT, {"calculator": reg["harness"]}, 3)
    ids = read(parent.OUT / "registration.json")["models"]
    models = {
        ids[t]: [
            {k: v[k] for k in ("task", "arm", "status", "levels", "report_sha256")}
            | dict(passed=False if v["status"] == "invalid" else v["passed"])
            for v in scored
            if v["tag"] == t
        ]
        for t in parent.TARGETS
    }
    arrivals = []
    for p in sorted(OUT.glob("libraries/**/settled.json")):
        response = read(p.with_name("response.json"))
        assert (
            sha(p.with_name("response.json")) == read(p)["response_sha256"]
            and response["model"] == reg["model"]
        )
        arrivals.append(
            dict(
                provider=response.get("provider"),
                model=response["model"],
                sha256=read(p)["response_sha256"],
            )
        )
    core.save(
        HERE / "result.json",
        dict(
            registration=seal["registration"],
            main_seal=seal["main_seal"],
            seal=sha(OUT / "seal.json"),
            library=seal["library"],
            heldout=heldout,
            models=models,
            deliveries=arrivals,
            failures=[read(p) for p in sorted(OUT.glob("provider-failure-*.json"))],
            cost=ledger_read.totals(OUT / "budget.sqlite3"),
        ),
    )


if __name__ == "__main__":
    with browser.lock(OUT / "study.lock"):
        reg = register()
        pub, lib = build(reg)
        generate(reg, pub, lib)
        if (OUT / "seal.json").exists() and not (HERE / "result.json").exists():
            score(reg, pub, lib)
