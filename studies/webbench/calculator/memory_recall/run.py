"""Compile separately authored display and register expressions for an absent memory group."""

import json
from pathlib import Path
import re
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, UPSTREAM, now, read, sha
from studies.webbench.calculator.key_programs import run as keys
from studies.webbench.calculator.key_programs.individual_keys import run as individual
from studies.webbench.table.model_modules.public_trace import run as table_trace
from . import observe

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/calculator-memory-recall-20261128"
CAP = 0.50
base = keys.base


def register():
    dst = OUT / "registration.json"
    paths = [
        Path(__file__),
        Path(observe.__file__),
        HERE / "PROTOCOL.md",
        Path(keys.__file__),
        Path(individual.__file__),
        individual.OUT / "seal.json",
        keys.OUT / "seal.json",
        table_trace.OUT / "registration.json",
    ]
    for tag in base.TARGETS:
        origin, _ = observe.foundation(tag)
        paths.append(origin / "libraries" / tag / "library.json")
        paths.extend(
            (keys.OUT / "libraries" / tag / "programs/memory/0/0").glob(
                "transmission-*/settled.json"
            )
        )
    sums = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    if not dst.exists():
        reference = {
            s: observe.observe(UPSTREAM / "projects/calculator" / s)
            for s in ("src", "src-init")
        }
        assert all(v["ok"] for v in reference["src"].values()) and not any(
            v["ok"] for v in reference["src-init"].values()
        )
        checks = {
            t: observe.observe(ROOT / observe.foundation(t)[1]["page"])
            for t in base.TARGETS
        }
        failed = [t for t, v in checks.items() if not all(x["ok"] for x in v.values())]
        prior = read(table_trace.OUT / "registration.json")["upper"]
        assert prior + CAP <= 20
        balance = check_credits(CAP)
        assert balance["sufficient"]
        models = read(keys.OUT / "registration.json")["models"]
        core.save(
            dst,
            dict(
                utc=now(),
                cap=CAP,
                upper=prior + CAP,
                deadline=base.END.isoformat(),
                balance=balance,
                sources=sums,
                reference_checks=reference,
                initial_checks=checks,
                models={t: models[t] for t in failed},
                contract=browser.verify_contract("calculator"),
            ),
        )
    assert read(dst)["sources"] == sums
    return read(dst)


def expression(raw):
    text = base.calc.base.uncode(raw).strip()
    text = (
        re.sub(
            r"^(?:(?:display|memory|register|expression)\s*[:=]\s*|return\s+)",
            "",
            text,
            flags=re.I,
        )
        .removesuffix(";")
        .strip()
    )
    if text.startswith('"') and text.endswith('"'):
        decoded = json.loads(text)
        if isinstance(decoded, str):
            text = decoded
    return keys.expression(text)


def program(tag, folder, ledger, trial, pub, initial):
    source = keys.OUT / "libraries" / tag / "programs/memory/0/0"
    receipt = next(iter(sorted(source.glob("transmission-*/settled.json"))), None)
    if receipt is None:
        raise ValueError("No original ordered key declaration")
    response = receipt.with_name("response.json")
    assert sha(response) == read(receipt)["response_sha256"]
    original = json.loads(
        base.calc.base.uncode(read(response)["choices"][0]["message"]["content"])
    )
    labels = keys.KEYS["memory"]
    layout = {k: individual.order(original[k], labels) for k in ("early", "full")}
    brief = [
        pub["requirements"][i - 1]["description"] for i in base.GROUPS["memory"][0]
    ]
    actions = {}
    for i, key in enumerate(labels):
        answers = []
        for channel in ("display", "register"):
            msg = core.messages(
                "Write exactly ONE JavaScript expression. It computes just the requested next value when the named memory key is pressed. d is the current display string, x is Number(d), m is the numeric memory value. State persists if its previous value is returned. Use these variables, numbers, String, Number and arithmetic. No assignments, function, object, prose or code fence.",
                dict(
                    public_requirements=brief,
                    button=key,
                    requested_output=channel,
                    public_browser_before_rebuild=initial,
                ),
            )
            for retry in range(2):
                raw = base.request(
                    ledger,
                    tag,
                    folder / str(i) / channel / str(retry),
                    msg,
                    "build",
                    450,
                    trial + 69,
                )
                try:
                    answers.append(expression(raw))
                    break
                except (TypeError, ValueError) as err:
                    if retry:
                        raise
                    msg.extend(
                        [
                            dict(role="assistant", content=raw),
                            dict(
                                role="user",
                                content=f"Format check: {err}. Reply with a single expression.",
                            ),
                        ]
                    )
        actions[key] = answers
    return keys.parse(
        json.dumps(layout | dict(actions=actions, panel=original.get("panel"))),
        "memory",
    )


def run():
    reg = register()
    ledger = Ledger(OUT / "budget.sqlite3", CAP, CAP)
    pub = read(base.calc.OUT / "public.json")
    seal_path = OUT / "seal.json"
    if not seal_path.exists():
        rows = []
        libs = {}
        for tag in reg["models"]:
            origin, _ = observe.foundation(tag)
            before = read(origin / "libraries" / tag / "library.json")
            old = before["parts"]
            parts, neutral = old, old
            trials = []
            for i in range(3):
                folder = OUT / "libraries" / tag / str(i + 1)
                trial = dict(attempt=i + 1, accepted=False)
                try:
                    with patch.multiple(
                        base.calc.base, OUT=OUT, END=base.END, template=base.settings
                    ):
                        spec = program(
                            tag, folder, ledger, i, pub, reg["initial_checks"][tag]
                        )
                    proposed = old | {"memory": keys.module(spec)}
                    page = base.compile_page(
                        pub["starter"]["index.html"],
                        proposed,
                        base.FULL,
                        folder / "page",
                    )
                    flags = base.probe(page)
                    mem = observe.observe(ROOT / page["page"])
                    ok = all(
                        not v or flags[k] for k, v in before["checks"].items()
                    ) and all(v["ok"] for v in mem.values())
                    trial.update(
                        spec=spec, checks=flags, public_memory=mem, accepted=ok
                    )
                    if ok:
                        parts, neutral = (
                            proposed,
                            old | {"memory": keys.module(spec, True)},
                        )
                except (
                    ValueError,
                    TypeError,
                    KeyError,
                    *base.calc.action.typed.MISSING,
                ) as exc:
                    trial["error"] = str(exc)
                trials.append(trial)
                if trial["accepted"]:
                    break
            libs[tag] = dict(
                trials=trials,
                status=before["status"],
                parent_seal=sha(origin / "seal.json"),
                selected="memory" if trials[-1]["accepted"] else "previous",
            )
            choices = [
                r
                for r in read(origin / "seal.json")["rows"]
                if r["arm"] == "self" and r["tag"] == tag
            ]
            assert len(choices) == 20
            for choice in choices:
                for arm, impl, levels in [
                    ("self", parts, choice["levels"]),
                    ("old-code-same-choice", old, choice["levels"]),
                    ("fixed-self", parts, base.FULL),
                    ("fixed-old", old, base.FULL),
                    ("neutral-memory", neutral, base.FULL),
                    ("binding-only", {}, base.NONE),
                ]:
                    page = (
                        dict(status=choice["status"])
                        if levels is None
                        else base.compile_page(
                            pub["starter"]["index.html"],
                            impl,
                            levels,
                            OUT / "pages" / tag / arm / "".join(map(str, levels)),
                        )
                    )
                    rows.append(
                        dict(
                            project="calculator",
                            tag=tag,
                            task=choice["task"],
                            arm=arm,
                            levels=levels,
                            **page,
                        )
                    )
        core.save(
            seal_path,
            dict(
                registration=sha(OUT / "registration.json"), libraries=libs, rows=rows
            ),
        )
    destination = HERE / "result.json"
    if destination.exists():
        return
    seal = read(seal_path)
    assert seal["registration"] == sha(OUT / "registration.json") and reg[
        "contract"
    ] == browser.verify_contract("calculator")
    independent = {}
    for tag in base.TARGETS:
        origin, old = observe.foundation(tag)
        if tag in seal["libraries"]:
            current = next(
                r for r in seal["rows"] if r["tag"] == tag and r["arm"] == "fixed-self"
            )
        else:
            current = old
        independent[tag] = {
            "before": observe.observe(ROOT / old["page"], True),
            "after": observe.observe(ROOT / current["page"], True),
        }
    scores = browser.evaluate(seal["rows"], OUT, {"calculator": reg["contract"]}, 4)
    models = {
        model: [
            {
                k: r[k]
                for k in ("task", "arm", "status", "levels", "report_sha256", "passed")
            }
            for r in scores
            if r["tag"] == tag
        ]
        for tag, model in reg["models"].items()
    }
    core.save(
        destination,
        dict(
            registration=seal["registration"],
            seal=sha(seal_path),
            libraries=seal["libraries"],
            public_checks=reg["initial_checks"],
            reference=reg["reference_checks"],
            independent=independent,
            models=models,
            cost=ledger_read.totals(OUT / "budget.sqlite3"),
        ),
    )


if __name__ == "__main__":
    with browser.lock(OUT / "study.lock"):
        run()
