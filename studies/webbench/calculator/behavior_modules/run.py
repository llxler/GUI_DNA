"""Build calculator behavior modules on the public starter and score the first admitted library."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit
import json
import re
import subprocess
import threading

from playwright.sync_api import sync_playwright
from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read, paper_target_extensions as previous
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from studies.webbench.calculator.key_groups import run as calc
from studies.webbench.calculator.target_models.run import END

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/calculator-behavior-modules-20261128"
TARGETS = ("gemma", "qwen9", "oss", "deepseek-flash")
BUILDERS = ("gpt5", *TARGETS)
CAP = 5.50
GROUPS = {
    "scientific": (
        [1, 2, 3, 4, 5, 6, 14],
        ["root", "square", "reciprocal", "constant", "cosine"],
    ),
    "appearance": ([7, 8, 9, 10, 11, 12, 13], ["theme", "mode", "layout"]),
    "memory": ([15, 16, 18, 19], ["mem", "memoryPanel"]),
    "history": ([17, 20], ["history", "replay"]),
}
FULL = [2] * len(GROUPS)
NONE = [0] * len(GROUPS)
HOST = (HERE / "host.js").read_text()
PROBE = (HERE / "probe.js").read_text()
EXPECTED = [
    "digits",
    "arithmetic",
    *(key for _, keys in GROUPS.values() for key in keys),
    "loaded",
]


def register():
    path = OUT / "registration.json"
    inputs = [HERE / f for f in ("run.py", "PROTOCOL.md", "host.js", "probe.js")]
    inputs += [
        Path(calc.base.__file__),
        Path(calc.__file__),
        calc.OUT / "public.json",
        previous.CALC,
        previous.capabilities.CALCULATOR,
        previous.ACCOUNTING,
        calc.OUT / "registration.json",
    ]
    hashes = {str(f.relative_to(ROOT)): sha(f) for f in inputs}
    if not path.exists():
        prior = read(previous.ACCOUNTING)["campaign"]["exposure_usd"]
        assert prior + CAP <= 20 and datetime.now(timezone.utc) < END
        balance = check_credits(CAP)
        if not balance["sufficient"]:
            raise RuntimeError("Insufficient available credits")
        contract = browser.verify_contract("calculator")
        assert contract == read(calc.OUT / "registration.json")["harness"]
        core.save(
            path,
            dict(
                utc=now(),
                cap=CAP,
                deadline=END.isoformat(),
                sources=hashes,
                harness=contract,
                prior_exposure_usd=prior,
                balance=balance,
                targets=list(range(1, 21)),
                models={
                    t: calc.action.settings("table", t, "build")["model"]
                    for t in BUILDERS
                },
            ),
        )
    assert read(path)["sources"] == hashes
    return read(path)


def compile_page(starter, parts, levels, dest):
    modules = ",\n".join(
        parts.get(name, "") or "function install(ctx,level){}" for name in GROUPS
    )
    js = HOST.replace("/*LEVELS*/", json.dumps(levels)).replace("/*MODULES*/", modules)
    html = starter.replace("</body>", "<script>\n" + js + "\n</script>\n</body>")
    return calc.files.emit(dest, core.emit("calculator", {"index.html": html}, dest))


def probe(candidate, heldout=False):
    page = ROOT / candidate["page"]
    with (
        browser.serve("calculator", page) as url,
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
        feedback = tab.evaluate(PROBE, heldout)
    assert set(EXPECTED) == set(feedback) and all(
        type(v) is bool for v in feedback.values()
    )
    return feedback


def module_source(raw):
    code = calc.base.uncode(raw).strip()
    if not re.match(
        r"^function\s+install\s*\(\s*ctx\s*,\s*level\s*\)", code
    ) or re.search(r"</script\s*>", code, re.I):
        raise ValueError("Return just function install(ctx, level) { ... }")
    parsed = subprocess.run(
        ["node", "--check"],
        input="const proposed = (" + code + "\n);",
        text=True,
        capture_output=True,
        timeout=8,
    )
    if parsed.returncode:
        raise ValueError(parsed.stderr[:300])
    return code


REQUEST = threading.local()


def settings(project, tag, stage):
    body = calc.action.settings(project, tag, stage)
    if "seed" in body:
        body["seed"] = 202611281 + getattr(REQUEST, "attempt", 0)
    return body


def request(ledger, tag, directory, prompt, stage, limit, attempt=0):
    REQUEST.attempt = attempt
    return calc.base.request(
        ledger, ("table", tag, str(attempt)), directory, prompt, stage, limit
    )


def ask_module(ledger, tag, trial, pub, group, folder, current="", feedback=None):
    subset = [pub["requirements"][i - 1]["description"] for i in GROUPS[group][0]]
    directions = dict(
        scientific="Add scientific buttons to the existing button grid. Keep every starter key. Use the displayed operand, write its result. Give the requested actual captions and relative order.",
        appearance="Implement the public layout, themes, basic/scientific mode and stateful controls. Do not create scientific/memory/history keys. Styles must also apply to buttons subsequently mounted. Hide optional panels in basic mode. Both modes must remain usable after toggling back.",
        memory="Implement the memory buttons and display panel, keeping the memory value across calculator Clear. In basic mode listen to appearance changes or use the current visible mode control. Insert the buttons in the requested order.",
        history="Observe native delegated calculator button clicks, retain their captions, render the requested interactive list. Replaying dispatches one original key action and must avoid recursion. Respect the public mode control.",
    )
    payload = dict(
        public_changes=subset,
        starter=pub["starter"]["index.html"],
        binding=HOST,
        component=group,
        neighbors=list(GROUPS),
        responsibility=directions[group],
        convention="level 1 is the early version; level 2 implements all public changes for this group. Level 0 is skipped by host. All four modules installed in the listed order. The host calls your function once after starter initialization. ctx.read()/write(value) share the starter displayValue. ctx.addKey(caption,callback) appends a button. ctx.find(caption) locates a button. ctx.state is shared; do not override the starter keyboard or template.",
    )
    if feedback is not None:
        payload.update(your_previous_source=current, observations=feedback)
    prompt = core.messages(
        "Implement a reusable calculator component in plain browser JavaScript. Return exactly one complete named function install(ctx, level) { ... }, no explanation, no HTML wrappers, no external services. Preserve working checks and implement the entire public component. Put CSS in a DOM style element as needed.",
        payload,
    )
    return module_source(request(ledger, tag, folder, prompt, "build", 5400, trial))


def admitted(checks, empty):
    return all(
        checks[k] and empty[k] for k in ("digits", "arithmetic", "loaded")
    ) and any(checks[k] and not empty[k] for k in GROUPS["scientific"][1])


def build(tag, ledger, pub, empty):
    destination = OUT / "libraries" / tag
    completed = destination / "library.json"
    if completed.exists():
        return read(completed)
    attempts = []
    starter = pub["starter"]["index.html"]
    for trial in range(3):
        folder = destination / f"attempt-{trial + 1}"
        parts, events = {}, []
        transport = False
        for group in GROUPS:
            try:
                parts[group] = ask_module(
                    ledger, tag, trial, pub, group, folder / "initial" / group
                )
            except calc.action.typed.MISSING as err:
                transport = True
                events.append(dict(stage="initial", group=group, availability=str(err)))
            except calc.base.ERRORS as err:
                events.append(dict(stage="initial", group=group, error=str(err)))
        checks = probe(compile_page(starter, parts, FULL, folder / "initial-page"))
        initial = checks.copy()
        for turn in range(2):
            for group, (_, keys) in GROUPS.items():
                if group in parts and all(
                    checks[k] for k in [*keys, "digits", "arithmetic", "loaded"]
                ):
                    continue
                try:
                    code = ask_module(
                        ledger,
                        tag,
                        trial,
                        pub,
                        group,
                        folder / f"patch-{turn + 1}" / group,
                        parts.get(group, ""),
                        dict(
                            public_browser_checks=checks,
                            earlier_delivery=[e for e in events if e["group"] == group][
                                -1:
                            ],
                        ),
                    )
                    new = parts | {group: code}
                    observations = probe(
                        compile_page(
                            starter, new, FULL, folder / f"after-{turn + 1}-{group}"
                        )
                    )
                    accepted = all(
                        not checks[k] or observations[k] for k in EXPECTED
                    ) and (
                        sum(observations[k] for k in keys)
                        > sum(checks[k] for k in keys)
                        or (group not in parts and any(observations[k] for k in keys))
                        or (not checks["loaded"] and observations["loaded"])
                    )
                    events.append(
                        dict(
                            stage=turn + 1,
                            group=group,
                            accepted=accepted,
                            checks=observations,
                        )
                    )
                    if accepted:
                        parts, checks = new, observations
                except calc.action.typed.MISSING as err:
                    transport = True
                    events.append(
                        dict(stage=turn + 1, group=group, availability=str(err))
                    )
                except calc.base.ERRORS as err:
                    events.append(dict(stage=turn + 1, group=group, error=str(err)))
        valid = admitted(checks, empty)
        result = dict(
            trial=trial + 1,
            initial=initial,
            checks=checks,
            events=events,
            delivered=list(parts),
            status="valid"
            if valid
            else "missing"
            if transport and not parts
            else "build_failed",
        )
        core.save(folder / "attempt.json", result | dict(parts=parts))
        attempts.append(result)
        if valid:
            core.save(
                completed,
                dict(status="valid", trial=trial + 1, attempts=attempts, parts=parts),
            )
            break
        if result["status"] == "missing" and (OUT / f"closed-{tag}.json").exists():
            break
    if not completed.exists():
        core.save(
            completed,
            dict(
                status=attempts[-1]["status"], trial=None, attempts=attempts, parts={}
            ),
        )
    print(
        "builder", tag, read(completed)["status"], "attempts", len(attempts), flush=True
    )
    return read(completed)


def plan(job, ledger, pub):
    tag, n = job
    folder = OUT / "plans" / tag / str(n)
    dest = folder / "choice.json"
    if dest.exists():
        return read(dest)
    msg = core.messages(
        "Choose one level per optional calculator component for the current request, preserving prior behavior. Reply with exactly one JSON array of four integers in the indicated order. 0 disables the group, 1 enables its early version, 2 enables its complete version. Arithmetic and the original keyboard are always on.",
        dict(public=core.prefix(pub, n), ordered_components=list(GROUPS)),
    )
    choice = dict(status="invalid")
    try:
        for attempt in range(2):
            raw = request(ledger, tag, folder / str(attempt), msg, "plan", 700)
            try:
                data = json.loads(calc.base.uncode(raw))
                if not (
                    isinstance(data, list)
                    and len(data) == 4
                    and all(type(v) is int and v in (0, 1, 2) for v in data)
                ):
                    raise ValueError("Invalid levels")
                choice = dict(status="valid", levels=data)
                break
            except (ValueError, TypeError):
                msg.extend(
                    [
                        dict(role="assistant", content=raw),
                        dict(
                            role="user",
                            content="Reply only with an array of four numbers 0, 1 or 2.",
                        ),
                    ]
                )
    except calc.action.typed.MISSING as err:
        choice = dict(status="missing", reason=str(err))
    core.save(dest, choice)
    return choice


def generate(reg):
    if (OUT / "seal.json").exists():
        return
    ledger = Ledger(OUT / "budget.sqlite3", CAP, CAP)
    pub = read(calc.OUT / "public.json")
    starter = pub["starter"]["index.html"]
    empty_page = compile_page(starter, {}, NONE, OUT / "binding-only")
    empty = probe(empty_page)
    assert (
        empty["digits"]
        and empty["arithmetic"]
        and not any(empty[k] for k in GROUPS["scientific"][1])
    )
    with (
        patch.multiple(calc.base, OUT=OUT, END=END, template=settings),
        ThreadPoolExecutor(max_workers=5) as pool,
    ):
        libraries = dict(
            zip(
                BUILDERS,
                pool.map(lambda t: build(t, ledger, pub, empty), BUILDERS),
                strict=True,
            )
        )
        jobs = list(product(TARGETS, reg["targets"]))
        plans = dict(
            zip(jobs, pool.map(lambda j: plan(j, ledger, pub), jobs), strict=True)
        )
    rows = []
    for (tag, n), choice in plans.items():
        for name, builder in [("self", tag), ("gpt5-library", "gpt5")]:
            lib = libraries[builder]
            for arm, levels in [(name, choice.get("levels")), ("fixed-" + name, FULL)]:
                if lib["status"] != "valid":
                    candidate = dict(status=lib["status"])
                elif levels is None:
                    candidate = dict(status=choice["status"])
                else:
                    path = OUT / "pages" / builder / "".join(map(str, levels))
                    candidate = compile_page(starter, lib["parts"], levels, path)
                rows.append(
                    dict(
                        project="calculator",
                        tag=tag,
                        builder=builder,
                        task=n,
                        arm=arm,
                        levels=levels,
                        **candidate,
                    )
                )
        rows.append(
            dict(
                project="calculator",
                tag=tag,
                builder=None,
                task=n,
                arm="binding-only",
                levels=NONE,
                **empty_page,
            )
        )
    core.save(
        OUT / "seal.json",
        dict(
            registration=sha(OUT / "registration.json"),
            rows=rows,
            empty=empty,
            libraries={
                tag: {k: v for k, v in lib.items() if k != "parts"}
                for tag, lib in libraries.items()
            },
        ),
    )


def score(reg):
    seal = read(OUT / "seal.json")
    assert seal["registration"] == sha(OUT / "registration.json")
    heldout = {}
    for tag, lib in seal["libraries"].items():
        if lib["status"] == "valid":
            part = read(OUT / "libraries" / tag / "library.json")["parts"]
            heldout[tag] = probe(
                compile_page(
                    read(calc.OUT / "public.json")["starter"]["index.html"],
                    part,
                    FULL,
                    OUT / "heldout" / tag,
                ),
                True,
            )
    assert browser.verify_contract("calculator") == reg["harness"]
    scored = browser.evaluate(seal["rows"], OUT, {"calculator": reg["harness"]}, 4)
    models = {}
    for tag in TARGETS:
        models[reg["models"][tag]] = [
            {k: v[k] for k in ("task", "arm", "status", "levels", "report_sha256")}
            | dict(passed=False if v["status"] == "invalid" else v["passed"])
            for v in scored
            if v["tag"] == tag
        ]
    bill = ledger_read.totals(OUT / "budget.sqlite3")
    by_phase = {}
    for call in ledger_read.calls(OUT / "budget.sqlite3"):
        phase = call["purpose"].split("/")[0]
        d = by_phase.setdefault(call["model"], {}).setdefault(
            phase, dict(calls=0, settled_micro_usd=0, exposure_micro_usd=0)
        )
        d["calls"] += 1
        d["settled_micro_usd"] += call["actual"] or 0
        d["exposure_micro_usd"] += (
            call["reserved"] if call["actual"] is None else call["actual"]
        )
    core.save(
        HERE / "result.json",
        dict(
            registration=seal["registration"],
            seal=sha(OUT / "seal.json"),
            libraries=seal["libraries"],
            models=models,
            builders=reg["models"],
            heldout=heldout,
            empty=seal["empty"],
            cost=bill,
            by_model_phase=by_phase,
            prior_exposure_usd=reg["prior_exposure_usd"],
        ),
    )


if __name__ == "__main__":
    with browser.lock(OUT / "study.lock"):
        reg = register()
        generate(reg)
        if not (HERE / "result.json").exists():
            score(reg)
