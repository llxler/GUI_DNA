"""Identify a mounting failure using public inputs, then resume the registered deployment."""

from datetime import datetime, timezone
from pathlib import Path
import shutil
from unittest.mock import patch

from playwright.sync_api import TimeoutError as BrowserTimeout
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from .. import run as first

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/calculator-gpt5-mount-recovery-20261128"
ORIGINAL = first.OUT
CAP = 2.5
modules = first.modules
original_probe = modules.probe
original_ask = modules.ask_module


def initial():
    replies = {}
    for name in modules.GROUPS:
        files = sorted(
            (ORIGINAL / "libraries/gpt5/attempt-1/initial" / name).glob(
                "transmission-*/settled.json"
            )
        )
        path = files[0].with_name("response.json")
        body = read(path)
        assert (
            body["model"] == "openai/gpt-5"
            and sha(path) == read(files[0])["response_sha256"]
        )
        code = modules.module_source(body["choices"][0]["message"]["content"])
        replies[name] = (path, code)
    return replies


def register():
    orig_reg = ORIGINAL / "registration.json"
    reg = read(orig_reg)
    sources = dict(reg["sources"])
    for f in (
        orig_reg,
        Path(__file__),
        HERE / "PROTOCOL.md",
        *(path for path, _ in initial().values()),
    ):
        sources[str(f.relative_to(ROOT))] = sha(f)
    cost = ledger_read.totals(ORIGINAL / "budget.sqlite3")
    registration = OUT / "registration.json"
    if not registration.exists():
        assert CAP + cost["cap_usd"] <= 10 and datetime.now(timezone.utc) < first.END
        balance = check_credits(CAP)
        if not balance["sufficient"]:
            raise RuntimeError("Insufficient available credits")
        core.save(
            registration,
            dict(
                utc=now(),
                prior_cost=cost,
                budget=CAP,
                deadline=first.END.isoformat(),
                balance=balance,
                sources=sources,
                models=reg["models"],
                contract=reg["contract"],
                targets=reg["targets"],
            ),
        )
    result = read(registration)
    assert result["sources"] == sources and result["prior_cost"] == cost
    return result


def guarded_probe(candidate, heldout=False):
    try:
        return original_probe(candidate, heldout)
    except BrowserTimeout:
        return dict.fromkeys(modules.EXPECTED, False)


def diagnose():
    path = OUT / "isolation.json"
    if path.exists():
        return read(path)
    starter = read(first.PUBLIC)["starter"]["index.html"]
    parts = {g: s for g, (_, s) in initial().items()}
    sets = {g: [g] for g in parts}
    sets.update(without_memory=[g for g in parts if g != "memory"], full=list(parts))
    results = {}
    for label, group in sets.items():
        subset = {g: parts[g] for g in group}
        candidate = modules.compile_page(
            starter, subset, modules.FULL, OUT / "isolation" / label
        )
        try:
            checks = original_probe(candidate)
            results[label] = dict(status="completed", checks=checks)
        except BrowserTimeout as exc:
            results[label] = dict(status="timeout", message=str(exc).splitlines()[0])
    core.save(path, results)
    return results


def build_and_score():
    reg = register()
    probes = diagnose()
    replies = initial()
    for group, (source, _) in replies.items():
        dest = OUT / "libraries/gpt5/retained" / group / source.parent.name
        dest.mkdir(parents=True, exist_ok=True)
        for n in ("request.json", "response.json", "settled.json"):
            old = source.with_name(n)
            if not (dest / n).exists():
                shutil.copyfile(old, dest / n)
            assert sha(old) == sha(dest / n)

    def ask(ledger, tag, trial, pub, group, folder, current="", feedback=None):
        if trial == 0 and feedback is None:
            source = replies[group][1]
            if probes[group]["status"] != "timeout":
                return source
            feedback = dict(
                public_isolated_mount=probes[group],
                other_public_mount=probes["without_memory"]["status"],
                runtime="A MutationObserver that watches class changes must not write the same class repeatedly. Make updates idempotent; preserve real mode changes and the component's public behaviors.",
            )
            return original_ask(
                ledger, tag, trial, pub, group, folder, source, feedback
            )
        return original_ask(ledger, tag, trial, pub, group, folder, current, feedback)

    with (
        patch.multiple(first, OUT=OUT, CAP=CAP, HERE=HERE),
        patch.multiple(modules, ask_module=ask, probe=guarded_probe),
    ):
        first.generate(reg)
        if not (HERE / "result.json").exists():
            first.score(reg)


if __name__ == "__main__":
    with browser.lock(OUT / "study.lock"):
        build_and_score()
