"""Author pure key transitions and let each target choose from its own observed public pages."""

from concurrent.futures import ThreadPoolExecutor
from itertools import product
from pathlib import Path
from unittest.mock import patch
import json
import re
import shutil
import subprocess

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read, paper_target_extensions as earlier
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from studies.webbench.calculator.behavior_modules import run as base
from studies.webbench.calculator.behavior_modules.incremental import run as increment
from studies.webbench.calculator.behavior_modules.gpt5_delivery import run as delivery
from studies.webbench.table.author_modules import run as table
from studies.webbench.table.model_modules import run as table_self
from studies.webbench.table.model_modules.structured_design import run as structured

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/calculator-key-programs-20261128"
CAP = 1.65
KEYS = {
    "scientific": ["√", "^2", "1/x", "sin", "π", "cos", "tan", "sinh", "cosh"],
    "memory": ["MR", "M+", "M-", "MC"],
}
BASES = (base.OUT, delivery.OUT, table.OUT, table_self.OUT)
CATALOG = [
    base.FULL,
    *[
        [level if i == col else 2 for i in range(4)]
        for level in (1, 0)
        for col in range(4)
    ],
    base.NONE,
]
IDENTIFIERS = set(
    "x d m Math Number String abs acos acosh asin asinh atan atanh ceil cos cosh exp floor log max min pow round sign sin sinh sqrt tan tanh trunc PI E isFinite isNaN parseFloat toString Error Infinity NaN".split()
)


def register():
    f = OUT / "registration.json"
    record = [
        Path(__file__),
        HERE / "PROTOCOL.md",
        Path(base.__file__),
        Path(increment.__file__),
        base.HERE / "host.js",
        base.HERE / "probe.js",
        earlier.ACCOUNTING,
        base.OUT / "seal.json",
        increment.OUT / "registration.json",
        structured.OUT / "registration.json",
        table_self.OUT / "seal.json",
        base.calc.OUT / "public.json",
    ]
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in record}
    if not f.exists():
        prior = read(earlier.ACCOUNTING)["campaign"]["exposure_usd"] + sum(
            ledger_read.totals(p / "budget.sqlite3")["exposure_usd"] for p in BASES
        )
        max_total = prior + increment.CAP + structured.CAP + CAP
        assert max_total <= 20
        balance = check_credits(CAP)
        assert balance["sufficient"]
        core.save(
            f,
            dict(
                utc=now(),
                cap=CAP,
                prior_exposure=prior,
                upper=max_total,
                balance=balance,
                sources=hashes,
                deadline=base.END.isoformat(),
                models={
                    t: base.calc.action.settings("table", t, "build")["model"]
                    for t in base.TARGETS
                },
            ),
        )
    assert read(f)["sources"] == hashes
    return read(f)


def expression(value):
    if type(value) in (int, float):
        value = str(value)
    if not isinstance(value, str) or len(value) > 256 or not value.strip():
        raise ValueError("Expected a short expression")
    if not re.fullmatch(r"""[\w\s.$+*/%?:<>=!&|()'"-]+""", value, re.ASCII):
        raise ValueError("Unsupported expression characters")
    words = set(re.findall(r"[A-Za-z_$][A-Za-z0-9_$]*", value))
    if words - IDENTIFIERS or re.search(r"(?<![<>=!])=(?!=)|=>|\+\+|--|/\*|//", value):
        raise ValueError("Use only d, x, m and pure numeric or string operations")
    return value.strip()


def parse(raw, g):
    obj = json.loads(base.calc.base.uncode(raw))
    keys = KEYS[g]
    early, full = obj["early"], obj["full"]
    if (
        not isinstance(early, list)
        or not early
        or not set(early) <= set(keys)
        or len(set(early)) != len(early)
    ):
        raise ValueError("List distinct existing labels in early")
    if not isinstance(full, list) or set(full) != set(keys) or len(full) != len(keys):
        raise ValueError("Use each public caption exactly once in full")
    actions = {key: [expression(x) for x in obj["actions"][key]] for key in keys}
    if not all(len(v) == 2 for v in actions.values()):
        raise ValueError("Provide exactly two expressions per key")
    panel = None
    if g == "memory":
        panel = obj.get("panel")
        if not isinstance(panel, str) or not re.fullmatch(
            "[A-Za-z][A-Za-z0-9_-]{0,40}", panel
        ):
            raise ValueError(
                "Supply the public memory panel id, without a selector prefix"
            )
    result = dict(early=early, full=full, actions=actions, panel=panel)
    checked = subprocess.run(
        ["node", "--check"],
        input=module(result),
        text=True,
        capture_output=True,
        timeout=6,
    )
    if checked.returncode:
        raise ValueError(checked.stderr[:220])
    return result


def module(record, neutral=False):
    transitions = ",\n".join(
        json.dumps(k, ensure_ascii=True)
        + ":(d,x,m)=>["
        + (",".join(v) if not neutral else "d,m")
        + "]"
        for k, v in record["actions"].items()
    )
    return (
        """function install(ctx,level) {
      const transitions={"""
        + transitions
        + """};
      const names=level===1?"""
        + json.dumps(record["early"])
        + """:"""
        + json.dumps(record["full"])
        + """;
      ctx.state.keyRegister ??= 0;
      const id="""
        + json.dumps(record["panel"])
        + """; let output;
      if(id){output=document.createElement('div');output.id=id;output.textContent=String(ctx.state.keyRegister);ctx.calculator.appendChild(output);}
      for (const name of names) {
        ctx.addKey(name,()=>{try {const d=ctx.read();const [v,w]=transitions[name](d,Number(d),ctx.state.keyRegister);
          ctx.write(v);ctx.state.keyRegister=w;if(output)output.textContent=String(w);
        }catch(error){ctx.write('Error');}});
      }
    }"""
    )


def request_program(tag, g, trial, ledger, pub, feedback):
    ids = base.GROUPS[g][0]
    prompt = core.messages(
        "Declare your calculator keys as pure state transitions. Return one JSON object with early (ordered labels), full (all ordered labels), actions (map each listed label to two JavaScript expression STRINGS), and panel (memory group: public panel id). Each pair is [new display, new register]. d is the current display string, x=Number(d), m is the numeric register. Use Math.* and String/Number as needed. Preserve an unchanged register or display by returning its name. Do not return functions, assignments, statement bodies, Markdown or code fences. Decide each formula and key ordering yourself from the public request.",
        dict(
            public_changes=[pub["requirements"][i - 1]["description"] for i in ids],
            component=g,
            public_labels=KEYS[g],
            earlier_public_observations=feedback,
        ),
    )
    folder = OUT / "libraries" / tag / "programs" / g / str(trial)
    for turn in range(2):
        raw = base.request(
            ledger, tag, folder / str(turn), prompt, "build", 2600, trial + 22
        )
        try:
            return parse(raw, g)
        except (ValueError, TypeError, KeyError) as err:
            if turn:
                raise ValueError(str(err)) from err
            prompt.extend(
                [
                    dict(role="assistant", content=raw),
                    dict(
                        role="user",
                        content="Public format check: "
                        + str(err)
                        + ". Return a complete corrected JSON record.",
                    ),
                ]
            )
    raise AssertionError("unreachable")


def foundations(tag):
    if tag in read(increment.OUT / "registration.json")["tags"]:
        path = increment.OUT / "libraries" / tag / "library.json"
    else:
        path = base.OUT / "libraries" / tag / "library.json"
    return read(path)["parts"], sha(path)


def build(tag, ledger, pub):
    root = OUT / "libraries" / tag
    finish = root / "library.json"
    if finish.exists():
        return read(finish)
    parts, original_sha = foundations(tag)
    starter = pub["starter"]["index.html"]
    curr = base.compile_page(starter, parts, base.FULL, root / "original")
    initial = base.probe(curr)
    checks = initial.copy()
    history = {}
    programs = {}
    for g in KEYS:
        history[g] = []
        for trial in range(3):
            try:
                feedback = (
                    {
                        "checks": checks,
                        "observed": increment.detail(
                            curr,
                        ),
                    }
                    if trial
                    else {"checks": checks}
                )
                spec = request_program(tag, g, trial, ledger, pub, feedback)
                proposed = parts | {g: module(spec)}
                page = base.compile_page(
                    starter, proposed, base.FULL, root / g / str(trial)
                )
                actual = base.probe(page)
                acceptable = all(not checks[k] or actual[k] for k in checks) and sum(
                    actual.values()
                ) > sum(checks.values())
                history[g].append(
                    dict(
                        attempt=trial + 1, accepted=acceptable, checks=actual, spec=spec
                    )
                )
                if acceptable:
                    curr, checks, parts = page, actual, proposed
                    programs[g] = spec
                    break
                if all(checks[k] for k in base.GROUPS[g][1]):
                    break
            except (ValueError, *base.calc.action.typed.MISSING) as err:
                history[g].append(
                    dict(attempt=trial + 1, accepted=False, error=str(err))
                )
    neutral = parts | {g: module(spec, True) for g, spec in programs.items()}
    core.save(
        finish,
        dict(
            status="valid",
            foundation=original_sha,
            initial=initial,
            checks=checks,
            programs=list(programs),
            history=history,
            parts=parts,
            neutral=neutral,
        ),
    )
    return read(finish)


def choose(job, ledger, pub, cards):
    tag, n = job
    dst = OUT / "plans" / tag / str(n) / "choice.json"
    if dst.exists():
        return read(dst)
    text = "\n".join(r["description"] for r in pub["requirements"][:n])
    msg = [
        dict(
            role="system",
            content="Choose a real calculator page for the current public request, including its prerequisites. Profile 0 is the complete functioning page and the default. Change it only if another observed profile fits the requested controls, initial state or ordering better. Extra compatible controls can remain. Respond only with the profile number.",
        ),
        dict(
            role="user",
            content="Public initial request:\n"
            + pub["init"]
            + "\nPublic requests through current target:\n"
            + text
            + "\nBrowser observations for each available page:\n"
            + json.dumps(cards[tag], ensure_ascii=False),
        ),
    ]
    answer = dict(status="invalid")
    try:
        for turn in range(2):
            raw = base.request(
                ledger, tag, dst.parent / "call" / str(turn), msg, "plan", 650, 24
            )
            val = base.calc.base.uncode(raw).strip()
            if re.fullmatch("[0-9]", val):
                answer = dict(status="valid", number=int(val))
                break
            msg.extend(
                [
                    dict(role="assistant", content=raw),
                    dict(
                        role="user", content="Return just the one-digit profile number."
                    ),
                ]
            )
    except base.calc.action.typed.MISSING as err:
        answer = dict(status="missing", reason=str(err))
    core.save(dst, answer)
    return answer


def generate(reg):
    seal = OUT / "seal.json"
    if seal.exists():
        return
    if not (increment.OUT / "seal.json").is_file():
        return
    pub = read(base.calc.OUT / "public.json")
    starter = pub["starter"]["index.html"]
    ledger = Ledger(OUT / "budget.sqlite3", CAP, CAP)

    def card(job):
        tag, i = job
        current = base.compile_page(
            starter, libs[tag]["parts"], CATALOG[i], OUT / "catalog" / tag / str(i)
        )
        seen = increment.detail(current)
        return dict(
            number=i,
            available_keys=seen["visible"],
            mode=seen["modeCaption"] if "modeCaption" in seen else None,
            operations=[
                dict(key=k, after=r[1])
                for k, r in seen["math"].items()
                if k in seen["visible"]
            ],
        )

    with (
        patch.multiple(base.calc.base, OUT=OUT, END=base.END, template=base.settings),
        ThreadPoolExecutor(max_workers=4) as pool,
    ):
        libs = dict(
            zip(
                base.TARGETS,
                pool.map(lambda t: build(t, ledger, pub), base.TARGETS),
                strict=True,
            )
        )
        jobs = list(product(base.TARGETS, range(len(CATALOG))))
        cards = {t: [] for t in base.TARGETS}
        for (t, _), item in zip(jobs, pool.map(card, jobs), strict=True):
            cards[t].append(item)
        jobs = list(product(base.TARGETS, range(1, 21)))
        choices = dict(
            zip(
                jobs,
                pool.map(lambda j: choose(j, ledger, pub, cards), jobs),
                strict=True,
            )
        )
    rows = []
    for (tag, n), choice in choices.items():
        old, _ = foundations(tag)
        parent_plan = read(base.OUT / "plans" / tag / str(n) / "choice.json")
        selected = CATALOG[choice["number"]] if choice["status"] == "valid" else None
        for arm, parts, levels in [
            ("self", libs[tag]["parts"], selected),
            ("old-code-new-choice", old, selected),
            ("new-code-old-choice", libs[tag]["parts"], parent_plan.get("levels")),
            ("fixed-self", libs[tag]["parts"], base.FULL),
            ("fixed-old", old, base.FULL),
            ("neutral-key-effects", libs[tag]["neutral"], base.FULL),
            ("binding-only", {}, base.NONE),
        ]:
            if levels is None:
                page = dict(
                    status=parent_plan["status"]
                    if arm == "new-code-old-choice"
                    else choice["status"]
                )
            else:
                page = base.compile_page(
                    starter,
                    parts,
                    levels,
                    OUT / "pages" / tag / arm / "".join(map(str, levels)),
                )
            rows.append(
                dict(
                    project="calculator",
                    tag=tag,
                    task=n,
                    arm=arm,
                    levels=levels,
                    **page,
                )
            )
    core.save(
        seal,
        dict(
            registration=sha(OUT / "registration.json"),
            additive_seal=sha(increment.OUT / "seal.json"),
            rows=rows,
            catalogs=cards,
            libraries={
                tag: {k: v for k, v in lib.items() if k not in ("parts", "neutral")}
                for tag, lib in libs.items()
            },
        ),
    )


def score(reg):
    seal = read(OUT / "seal.json")
    contract = browser.verify_contract("calculator")
    assert (
        seal["registration"] == sha(OUT / "registration.json")
        and contract == read(base.OUT / "registration.json")["harness"]
    )
    heldout = {}
    for tag in base.TARGETS:
        page = next(
            r for r in seal["rows"] if r["tag"] == tag and r["arm"] == "fixed-self"
        )
        heldout[tag] = base.probe(page, True)
    seen = set()
    for r in seal["rows"]:
        if r["status"] != "valid":
            continue
        digest = browser.digest(r["files"])
        rel = (
            Path("browser/scores/calculator")
            / f"task-{r['task']}"
            / digest
            / "score.json"
        )
        dst = OUT / rel
        if rel in seen or dst.is_file():
            continue
        seen.add(rel)
        for peer in (base.OUT, increment.OUT):
            src = peer / rel
            if not src.is_file():
                continue
            v = browser.verify_receipt(
                peer,
                src,
                dict(
                    project="calculator",
                    task=r["task"],
                    files_digest=digest,
                    contract_digest=browser.digest(contract),
                ),
            )
            copy = dst.with_name("reused-report.json")
            copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(peer / v["report"], copy)
            core.save(
                dst,
                dict(
                    v,
                    report=str(copy.relative_to(OUT)),
                    source_receipt=str(src.relative_to(ROOT)),
                    source_receipt_sha256=sha(src),
                    source_report=str((peer / v["report"]).relative_to(ROOT)),
                ),
            )
            break
    scored = browser.evaluate(seal["rows"], OUT, {"calculator": contract}, 4)
    models = {
        m: [
            {k: v[k] for k in ("task", "arm", "status", "levels", "report_sha256")}
            | dict(passed=False if v["status"] == "invalid" else v["passed"])
            for v in scored
            if v["tag"] == t
        ]
        for t, m in reg["models"].items()
    }
    costs = {}
    for c in ledger_read.calls(OUT / "budget.sqlite3"):
        stage = c["purpose"].split("/")[0]
        v = costs.setdefault(c["model"], {}).setdefault(
            stage, dict(calls=0, settled_micro_usd=0, exposure_micro_usd=0)
        )
        v["calls"] += 1
        v["settled_micro_usd"] += c["actual"] or 0
        v["exposure_micro_usd"] += c["reserved"] if c["actual"] is None else c["actual"]
    core.save(
        HERE / "result.json",
        dict(
            registration=seal["registration"],
            seal=sha(OUT / "seal.json"),
            additive_seal=seal["additive_seal"],
            models=models,
            libraries=seal["libraries"],
            heldout=heldout,
            catalogs=seal["catalogs"],
            cost=ledger_read.totals(OUT / "budget.sqlite3"),
            by_model_phase=costs,
        ),
    )


if __name__ == "__main__":
    with browser.lock(OUT / "study.lock"):
        reg = register()
        generate(reg)
        if (OUT / "seal.json").exists() and not (HERE / "result.json").exists():
            score(reg)
