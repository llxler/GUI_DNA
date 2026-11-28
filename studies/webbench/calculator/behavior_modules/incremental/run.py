"""Generate complete behavior through additive stages and diagnose the public browser state."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit
import json
import re
import subprocess

from playwright.sync_api import sync_playwright
from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from .. import run as base
from ..gpt5_delivery import run as delivery

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/calculator-additive-modules-20261128"
CAP = 2.50
SPLIT = {
    "scientific": ((1, 2, 3, 4, 5), (6, 14)),
    "appearance": ((7, 8, 9), (10, 11, 12, 13)),
    "memory": ((15, 16), (18, 19)),
    "history": ((17,), (20,)),
}
GUIDE = {
    "scientific": "Install independent buttons by their exact public captions. Their callbacks read the current value, compute and write the actual arithmetic result.",
    "appearance": "Use separate reachable mode and theme controls outside the .buttons grid. The mode button describes the other mode; when basic, mark only extra controls/panels hidden via CSS; restore them on toggling back. Account for elements installed later.",
    "memory": "Use ctx.state.memory for numeric memory shared across both fragments. Clear resets the display only. Update the visible memory panel from the same variable.",
    "history": "Delegate real clicks from actual buttons, render exactly the most recent five captions. Replaying an item activates the original caption once. Use ctx.state for shared data and do not duplicate listeners.",
}
DIAGNOSTIC = """() => {
 const labels=()=>Array.from(document.querySelectorAll('button')).filter(b=>b.getClientRects().length).map(b=>b.textContent.trim());
 const view=()=>document.querySelector('#display')?.value;
 const press=s=>Array.from(document.querySelectorAll('button')).find(b=>b.getClientRects().length&&b.textContent.trim()===s)?.click();
 const math={};for (const n of ['√','^2','1/x','cos','π']) {press('Clear');press(n==='cos'?'0':'9');const from=view();press(n);math[n]=[from,view()];}
 const visible=labels();const m=document.querySelector('#mode');m?.click();const inOtherMode=labels();m?.click();
 return {visible,inOtherMode,math,errors:window.calculatorModuleErrors,modeCaption:m?.textContent,
 memoryDisplay:document.querySelector('#memory')?.textContent?.slice(0,120),historyDisplay:document.querySelector('#clicks')?.textContent?.slice(0,120)};
}"""


def register():
    dst = OUT / "registration.json"
    sources = [
        Path(__file__),
        HERE / "PROTOCOL.md",
        Path(base.__file__),
        base.HERE / "host.js",
        base.HERE / "probe.js",
        base.OUT / "registration.json",
        base.OUT / "seal.json",
        delivery.OUT / "registration.json",
        *(base.OUT / "libraries" / t / "library.json" for t in base.TARGETS),
    ]
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in sources}
    if not dst.exists():
        prior = read(base.OUT / "registration.json")["prior_exposure_usd"]
        spent = sum(
            ledger_read.totals(p / "budget.sqlite3")["exposure_usd"]
            for p in (base.OUT, delivery.OUT)
        )
        table = read(
            ROOT / "artifacts/table-author-modules-20261128/registration.json"
        )["cap"]
        assert prior + spent + table + CAP <= 20
        balance = check_credits(CAP)
        assert balance["sufficient"]
        chosen = [
            t
            for t in base.TARGETS
            if sum(
                read(base.OUT / "libraries" / t / "library.json")["attempts"][-1][
                    "checks"
                ].values()
            )
            * 2
            < len(base.EXPECTED)
        ]
        assert chosen == ["gemma", "qwen9"]
        core.save(
            dst,
            dict(
                utc=now(),
                sources=hashes,
                cap=CAP,
                prior_exposure=prior + spent,
                concurrent_cap=table,
                balance=balance,
                tags=chosen,
                deadline=base.END.isoformat(),
            ),
        )
    assert read(dst)["sources"] == hashes
    return read(dst)


def receive(raw):
    code = base.calc.base.uncode(raw).strip()
    match = re.fullmatch(
        r"(?:function(?:\s+\w+)?\s*\(\s*ctx\s*\)|(?:\(\s*ctx\s*\)|ctx)\s*=>)\s*\{(.*)\}\s*;?",
        code,
        re.S,
    )
    if match:
        code = match.group(1)
    if (
        not code
        or re.search(r"</script\s*>", code, re.I)
        or re.match(r"(?:async\s+)?function\s+install\b", code)
    ):
        raise ValueError("Expected just the function body operating on ctx")
    check = subprocess.run(
        ["node", "--check"],
        input="function checked(ctx){\n" + code + "\n}",
        text=True,
        capture_output=True,
        timeout=8,
    )
    if check.returncode:
        raise ValueError(check.stderr[:320])
    return code


def ask(ledger, tag, trial, group, index, folder, pub, old, early, feedback):
    changes = [pub["requirements"][i - 1]["description"] for i in SPLIT[group][index]]
    request = "\n".join(
        [
            "Write only JavaScript statements inside a function whose parameter is ctx. No outer function declaration, JSON, HTML document or prose.",
            "The page already has .calculator, .buttons and input#display. All original basic buttons work; do not replace them.",
            "API: ctx.buttons (grid element), ctx.calculator (container), ctx.display (input), ctx.find(caption) returns an existing grid button, ctx.addKey(caption,callback) appends and returns a new grid button, ctx.read() and ctx.write(value) synchronize the original calculator, ctx.state is persistent across modules.",
            "Stage 1 installs the initial module. Stage 2 runs AFTER stage 1 to add or update behavior. Do not recreate the stage 1 buttons. Each stage has its own local variables. Use ctx.state to communicate.",
            "Other modules implement the remaining functionality. Your group is "
            + group
            + ". "
            + GUIDE[group],
            "Write stage "
            + str(index + 1)
            + ". Public requirements for this stage:\n"
            + "\n".join(changes),
        ]
    )
    if index:
        request += "\nAlready-installed stage 1 from your own library:\n" + (
            early or "(empty)"
        )
    if feedback:
        request += (
            "\nPrevious statements:\n"
            + (old or "(empty)")
            + "\nPublic browser observations:\n"
            + json.dumps(feedback, ensure_ascii=False)
        )
    messages = [
        dict(
            role="system",
            content="You implement a small portion of a browser calculator.",
        ),
        dict(role="user", content=request),
    ]
    if trial >= 1:
        messages[-1]["content"] += (
            "\nStart afresh; check each label and operand before replying."
        )
    for retry in range(2):
        raw = base.request(
            ledger, tag, folder / str(retry), messages, "build", 3800, trial + 6
        )
        try:
            return receive(raw)
        except ValueError as err:
            if retry:
                raise
            messages.extend(
                [
                    dict(role="assistant", content=raw),
                    dict(
                        role="user",
                        content=str(err) + "\nReturn the corrected statements only.",
                    ),
                ]
            )
    raise AssertionError("unreachable")


def modules(pairs):
    return {
        g: "function install(ctx,level){\n(function(ctx){\n"
        + a
        + "\n})(ctx);\nif(level===2){(function(ctx){\n"
        + b
        + "\n})(ctx);}\n}"
        for g, (a, b) in pairs.items()
    }


def detail(page):
    with (
        browser.serve("calculator", ROOT / page["page"]) as url,
        sync_playwright() as pw,
        pw.chromium.launch(env=browser.browser_env()) as engine,
    ):
        tab = engine.new_page(service_workers="block")
        tab.route(
            "**/*",
            lambda r: (
                r.continue_()
                if urlsplit(r.request.url).netloc == urlsplit(url).netloc
                else r.abort()
            ),
        )
        tab.goto(url, timeout=10000)
        return tab.evaluate(DIAGNOSTIC)


def build(tag, pub, ledger):
    folder = OUT / "libraries" / tag
    final = folder / "library.json"
    if final.exists():
        return read(final)
    previous = read(base.OUT / "libraries" / tag / "library.json")
    baseline = previous["attempts"][-1]["checks"]
    empty = read(base.OUT / "seal.json")["empty"]
    trials = []
    for trial in range(3):
        work = folder / str(trial + 1)
        pairs, log = {}, []

        def generate_pair(g, location, old, feedback):
            pair = []
            for i in range(2):
                try:
                    code = ask(
                        ledger,
                        tag,
                        trial,
                        g,
                        i,
                        location / str(i),
                        pub,
                        old[i],
                        pair[0] if pair else "",
                        feedback,
                    )
                except (ValueError, *base.calc.action.typed.MISSING) as err:
                    code = old[i]
                    log.append(dict(group=g, part=i + 1, error=str(err)[:220]))
                pair.append(code)
            return pair

        for g in SPLIT:
            pairs[g] = generate_pair(g, work / "initial" / g, ["", ""], None)

        def page(at, parts):
            return base.compile_page(
                pub["starter"]["index.html"], modules(parts), base.FULL, at
            )

        current = page(work / "first-page", pairs)
        checks = base.probe(current)
        initial = checks.copy()
        for turn in range(2):
            for g, (_, keys) in base.GROUPS.items():
                if all(checks[k] for k in [*keys, "arithmetic", "digits", "loaded"]):
                    continue
                feedback = dict(observed=detail(current), checks=checks)
                pair = generate_pair(
                    g, work / f"pass-{turn + 1}" / g, pairs[g], feedback
                )
                updated = pairs | {g: pair}
                proposed = page(work / f"candidate-{turn + 1}-{g}", updated)
                observed = base.probe(proposed)
                accepted = all(not checks[k] or observed[k] for k in checks) and sum(
                    observed.values()
                ) > sum(checks.values())
                log.append(
                    dict(group=g, round=turn + 1, checks=observed, accepted=accepted)
                )
                if accepted:
                    pairs, current, checks = updated, proposed, observed
        ok = (
            base.admitted(checks, empty)
            and all(not baseline[k] or checks[k] for k in baseline)
            and sum(checks.values()) > sum(baseline.values())
        )
        item = dict(
            attempt=trial + 1,
            status="valid" if ok else "build_failed",
            initial=initial,
            checks=checks,
            history=log,
        )
        core.save(work / "attempt.json", item | dict(bodies=pairs))
        trials.append(item)
        if ok:
            core.save(
                final,
                dict(
                    status="valid",
                    selected="incremental",
                    attempt=trial + 1,
                    trials=trials,
                    parts=modules(pairs),
                ),
            )
            break
    if not final.exists():
        core.save(
            final,
            dict(
                status="valid",
                selected="parent",
                attempt=None,
                trials=trials,
                parts=previous["parts"],
            ),
        )
    print("additive", tag, read(final)["selected"], len(trials), flush=True)
    return read(final)


def generate(reg):
    seal = OUT / "seal.json"
    if seal.exists():
        return
    ledger = Ledger(OUT / "budget.sqlite3", CAP, CAP)
    pub = read(base.calc.OUT / "public.json")
    primary = read(base.OUT / "seal.json")
    with (
        patch.multiple(base.calc.base, OUT=OUT, END=base.END, template=base.settings),
        ThreadPoolExecutor(max_workers=2) as pool,
    ):
        libs = dict(
            zip(
                reg["tags"],
                pool.map(lambda t: build(t, pub, ledger), reg["tags"]),
                strict=True,
            )
        )
    rows = []
    for r in primary["rows"]:
        if r["tag"] not in libs or r["arm"] not in (
            "self",
            "fixed-self",
            "binding-only",
        ):
            continue
        levels = r["levels"]
        if levels is None:
            rec = dict(status=r["status"])
        else:
            dst = OUT / "pages" / r["tag"] / "".join(map(str, levels))
            rec = base.compile_page(
                pub["starter"]["index.html"], libs[r["tag"]]["parts"], levels, dst
            )
        rows.append(
            dict(
                rec,
                project="calculator",
                tag=r["tag"],
                task=r["task"],
                arm=r["arm"],
                levels=levels,
            )
        )
    core.save(
        seal,
        dict(
            registration=sha(OUT / "registration.json"),
            parent_seal=sha(base.OUT / "seal.json"),
            rows=rows,
            libraries={
                t: {k: v for k, v in d.items() if k != "parts"} for t, d in libs.items()
            },
        ),
    )


def score(reg):
    d = read(OUT / "seal.json")
    original = read(base.OUT / "registration.json")
    assert d["registration"] == sha(OUT / "registration.json") and original[
        "harness"
    ] == browser.verify_contract("calculator")
    pub = read(base.calc.OUT / "public.json")
    extra = {
        t: base.probe(
            base.compile_page(
                pub["starter"]["index.html"],
                read(OUT / "libraries" / t / "library.json")["parts"],
                base.FULL,
                OUT / "heldout" / t,
            ),
            True,
        )
        for t in reg["tags"]
    }
    values = browser.evaluate(d["rows"], OUT, {"calculator": original["harness"]}, 3)
    measured = {
        original["models"][t]: [
            {k: v[k] for k in ("task", "arm", "levels", "status", "report_sha256")}
            | dict(passed=False if v["status"] == "invalid" else v["passed"])
            for v in values
            if v["tag"] == t
        ]
        for t in reg["tags"]
    }
    costs = {}
    for c in ledger_read.calls(OUT / "budget.sqlite3"):
        v = costs.setdefault(
            c["model"], dict(calls=0, settled_micro_usd=0, exposure_micro_usd=0)
        )
        v["calls"] += 1
        v["settled_micro_usd"] += c["actual"] or 0
        v["exposure_micro_usd"] += c["reserved"] if c["actual"] is None else c["actual"]
    core.save(
        HERE / "result.json",
        dict(
            registration=d["registration"],
            seal=sha(OUT / "seal.json"),
            parent_seal=d["parent_seal"],
            models=measured,
            libraries=d["libraries"],
            heldout=extra,
            cost=ledger_read.totals(OUT / "budget.sqlite3"),
            by_model=costs,
        ),
    )


if __name__ == "__main__":
    with browser.lock(OUT / "study.lock"):
        reg = register()
        generate(reg)
        if not (HERE / "result.json").exists():
            score(reg)
