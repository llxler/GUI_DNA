"""Build one admitted GPT-5 calculator library and deploy its observed profiles."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from ..behavior_modules import run as modules
from ..key_programs import run as profiles

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/calculator-gpt5-profiles-20261128"
CAP = 3.0
END = datetime(2026, 11, 28, 15, 5, tzinfo=timezone.utc)
PUBLIC = modules.calc.OUT / "public.json"
TASKS = tuple(range(1, 21))


def register():
    registration = OUT / "registration.json"
    inputs = [
        Path(__file__),
        HERE / "PROTOCOL.md",
        Path(modules.__file__),
        Path(profiles.__file__),
        Path(profiles.increment.__file__),
        Path(modules.calc.base.__file__),
        modules.HERE / "host.js",
        modules.HERE / "probe.js",
        PUBLIC,
        profiles.HERE / "result.json",
        profiles.OUT / "seal.json",
        profiles.delivery.HERE / "result.json",
        modules.OUT / "registration.json",
    ]
    hashes = {str(path.relative_to(ROOT)): sha(path) for path in inputs}
    if not registration.exists():
        assert (
            datetime.now(timezone.utc) < END
            and read(profiles.delivery.HERE / "result.json")["library"]["status"]
            == "missing"
        )
        balance = check_credits(CAP)
        if not balance["sufficient"]:
            raise RuntimeError("Insufficient balance")
        ids = read(modules.OUT / "registration.json")["models"]
        assert ids["gpt5"] == "openai/gpt-5"
        core.save(
            registration,
            dict(
                utc=now(),
                deadline=END.isoformat(),
                budget=CAP,
                balance=balance,
                sources=hashes,
                models=ids,
                targets=list(TASKS),
                catalog=profiles.CATALOG,
                contract=browser.verify_contract("calculator"),
            ),
        )
    reg = read(registration)
    assert (
        reg["sources"] == hashes
        and reg["contract"] == read(modules.OUT / "registration.json")["harness"]
    )
    return reg


def accepted_responses(parts):
    replies = {}
    for path in sorted((OUT / "libraries/gpt5").rglob("settled.json")):
        response = path.with_name("response.json")
        assert sha(response) == read(path)["response_sha256"]
        data = read(response)
        assert (
            data["model"]
            == read(path.with_name("request.json"))["body"]["model"]
            == "openai/gpt-5"
        )
        try:
            code = modules.module_source(data["choices"][0]["message"]["content"] or "")
        except ValueError:
            continue
        group = path.parents[1].name
        if group in parts and code == parts[group]:
            replies.setdefault(
                group,
                dict(
                    path=str(response.relative_to(ROOT)),
                    sha256=sha(response),
                    model=data["model"],
                    provider=data["provider"],
                ),
            )
    assert replies.keys() == parts.keys()
    return replies


def generate(reg):
    if (OUT / "seal.json").exists():
        return
    pub = read(PUBLIC)
    starter = pub["starter"]["index.html"]
    ledger = Ledger(OUT / "budget.sqlite3", CAP, CAP)
    with (
        patch.object(modules, "OUT", OUT),
        patch.multiple(modules.calc.base, OUT=OUT, END=END, template=modules.settings),
    ):
        empty = modules.probe(
            modules.compile_page(starter, {}, modules.NONE, OUT / "starter")
        )
        library = modules.build("gpt5", ledger, pub, empty)
    source = accepted_responses(library["parts"])
    cards, pages, choices = [], {}, {}
    jobs = list(product(modules.TARGETS, TASKS))
    if library["status"] == "valid":
        for i, levels in enumerate(profiles.CATALOG):
            page = modules.compile_page(
                starter, library["parts"], levels, OUT / "catalog" / str(i)
            )
            pages[i] = page
            observed = profiles.increment.detail(page)
            cards.append(
                dict(
                    number=i,
                    available_keys=observed["visible"],
                    mode=observed.get("modeCaption"),
                    operations=[
                        dict(key=k, after=v[1])
                        for k, v in observed["math"].items()
                        if k in observed["visible"]
                    ],
                )
            )
        assert cards[0]["number"] == 0 and profiles.CATALOG[0] == modules.FULL
        core.save(OUT / "catalog.json", cards)
        with (
            patch.object(profiles, "OUT", OUT),
            patch.multiple(
                modules.calc.base, OUT=OUT, END=END, template=modules.settings
            ),
        ):
            with ThreadPoolExecutor(max_workers=4) as pool:
                picks = pool.map(
                    lambda job: profiles.choose(
                        job, ledger, pub, dict.fromkeys(modules.TARGETS, cards)
                    ),
                    jobs,
                )
                choices = dict(zip(jobs, picks, strict=True))
    previous = read(profiles.HERE / "result.json")
    rows = []
    for tag, task in jobs:
        (old,) = [
            r
            for r in previous["models"][reg["models"][tag]]
            if r["arm"] == "self" and r["task"] == task
        ]
        choice = choices.get((tag, task), dict(status=library["status"]))
        old_levels = old["levels"]
        treatments = [
            ("gpt5-library", choice),
            ("fixed-gpt5-library", dict(status="valid", number=0)),
            (
                "self-choice",
                dict(
                    status=old["status"],
                    number=profiles.CATALOG.index(old_levels)
                    if old_levels is not None
                    else None,
                ),
            ),
        ]
        for arm, request in treatments:
            status = (
                request["status"] if library["status"] == "valid" else library["status"]
            )
            number = request.get("number") if status == "valid" else None
            candidate = pages[number] if status == "valid" else dict(status=status)
            rows.append(
                dict(
                    project="calculator",
                    tag=tag,
                    task=task,
                    arm=arm,
                    profile=number,
                    levels=profiles.CATALOG[number] if number is not None else None,
                    **candidate,
                )
            )
    core.save(
        OUT / "seal.json",
        dict(
            registration=sha(OUT / "registration.json"),
            rows=rows,
            catalog=cards,
            empty=empty,
            library={k: v for k, v in library.items() if k != "parts"},
            accepted_responses=source,
            source_library=sha(OUT / "libraries/gpt5/library.json"),
        ),
    )


def score(reg):
    seal = read(OUT / "seal.json")
    assert seal["registration"] == sha(OUT / "registration.json")
    assert seal["source_library"] == sha(OUT / "libraries/gpt5/library.json")
    assert reg["contract"] == browser.verify_contract("calculator")
    valid = seal["library"]["status"] == "valid"
    full = next(r for r in seal["rows"] if r["arm"] == "fixed-gpt5-library")
    alternate_inputs = modules.probe(full, True) if valid else {}
    judged = browser.evaluate(seal["rows"], OUT, {"calculator": reg["contract"]}, 4)
    models = {reg["models"][tag]: [] for tag in modules.TARGETS}
    for row in judged:
        record = {
            k: row[k]
            for k in ("task", "arm", "status", "profile", "levels", "report_sha256")
        }
        record.update(
            passed=False if row["status"] == "invalid" else row["passed"],
            files_digest=browser.digest(row["files"])
            if row["status"] == "valid"
            else None,
        )
        models[reg["models"][row["tag"]]].append(record)
    costs = {}
    ledger_path = OUT / "budget.sqlite3"
    for call in ledger_read.calls(ledger_path):
        group = costs.setdefault(
            call["model"], dict(calls=0, settled_micro_usd=0, exposure_micro_usd=0)
        )
        group["calls"] += 1
        group["settled_micro_usd"] += call["actual"] or 0
        group["exposure_micro_usd"] += (
            call["actual"] if call["actual"] is not None else call["reserved"]
        )
    core.save(
        HERE / "result.json",
        dict(
            registration=seal["registration"],
            seal=sha(OUT / "seal.json"),
            library=seal["library"],
            source_library=seal["source_library"],
            accepted_responses=seal["accepted_responses"],
            catalog=seal["catalog"],
            empty=seal["empty"],
            alternate_inputs=alternate_inputs,
            models=models,
            targets=reg["targets"],
            by_model=costs,
            cost=ledger_read.totals(ledger_path),
            registered_sources=reg["sources"],
            browser_contract=reg["contract"],
        ),
    )


if __name__ == "__main__":
    with browser.lock(OUT / "study.lock"):
        registration = register()
        generate(registration)
        if not (HERE / "result.json").exists():
            score(registration)
