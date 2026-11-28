"""Let the same target model design, implement, repair and configure its library."""

from concurrent.futures import ThreadPoolExecutor
from itertools import product
from pathlib import Path
from unittest.mock import patch
import json
import re
import subprocess
import sys

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read, paper_target_extensions as earlier
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from studies.webbench.calculator.behavior_modules import run as model_api
from studies.webbench.calculator.behavior_modules.incremental import run as incremental
from studies.webbench.calculator.behavior_modules.gpt5_delivery import run as recovery
from studies.webbench.table.author_modules import run as merged
from . import probes

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/table-model-modules-20261128"
TAGS = ("mistral", "qwen", "oss")
CAP = 2.25
REQUIRED = ("menu", "insert", "outside", "click")


def register():
    dst = OUT / "registration.json"
    inputs = [
        Path(__file__),
        HERE / "PROTOCOL.md",
        Path(probes.__file__),
        earlier.ACCOUNTING,
        model_api.OUT / "seal.json",
        merged.OUT / "seal.json",
        recovery.OUT / "seal.json",
        incremental.OUT / "registration.json",
        Path(model_api.calc.base.__file__),
    ]
    inputs.extend(
        sorted((model_api.calc.ORIGINAL.parent / "table/src-init").glob("*.*"))
    )
    hs = {str(p.relative_to(ROOT)): sha(p) for p in inputs}
    if not dst.exists():
        prior = read(earlier.ACCOUNTING)["campaign"]["exposure_usd"]
        prior += sum(
            ledger_read.totals(p / "budget.sqlite3")["exposure_usd"]
            for p in (model_api.OUT, merged.OUT, recovery.OUT)
        )
        assert prior + incremental.CAP + CAP <= 20
        balance = check_credits(CAP)
        assert balance["sufficient"]
        core.save(
            dst,
            dict(
                utc=now(),
                sources=hs,
                cap=CAP,
                prior_exposure=prior,
                concurrent_cap=incremental.CAP,
                balance=balance,
                deadline=model_api.END.isoformat(),
                models={
                    t: model_api.calc.action.settings("table", t, "plan")["model"]
                    for t in TAGS
                },
                contract=browser.verify_contract("table"),
            ),
        )
    assert read(dst)["sources"] == hs
    return read(dst)


def design(raw):
    obj = json.loads(model_api.calc.base.uncode(raw))
    mods = obj["modules"]
    if not isinstance(mods, list) or not 2 <= len(mods) <= 5:
        raise ValueError("Expected two to five modules")
    covered = set()
    files = set()
    for mod in mods:
        f = mod["file"]
        ids = mod["requirements"]
        if (
            not isinstance(f, str)
            or not re.fullmatch(r"(?:[a-zA-Z][\w-]*/)*[a-zA-Z][\w-]*\.js", f)
            or f == "index.js"
            or f in files
        ):
            raise ValueError("Each module needs its own relative .js filename")
        if (
            not isinstance(ids, list)
            or not ids
            or any(type(v) is not int or not 1 <= v <= 20 for v in ids)
        ):
            raise ValueError("Use numeric requirement IDs 1..20")
        for k in ("name", "responsibility", "interface"):
            if not isinstance(mod[k], str) or not mod[k].strip():
                raise ValueError("Describe every interface and responsibility")
        files.add(f)
        covered.update(ids)
    if covered != set(range(1, 21)):
        raise ValueError("Module design left some public requirements unassigned")
    return mods


def source(raw):
    code = model_api.calc.base.uncode(raw).strip()
    if not re.search(r"export\s+default\s+function(?:\s+\w+)?\s*\(\s*env\s*\)", code):
        raise ValueError(
            "Expected export default function install(env) with no imports"
        )
    if re.search(r"^\s*import\b", code, re.M):
        raise ValueError("Use the declared env.api instead of module imports")
    res = subprocess.run(
        ["node", "--input-type=module", "--check"],
        input=code,
        text=True,
        capture_output=True,
        timeout=8,
    )
    if res.returncode:
        raise ValueError(res.stderr[:280])
    return code


def ask(ledger, tag, attempt, folder, prompt, stage, parser, tokens):
    msg = list(prompt)
    for retry in range(2):
        raw = model_api.request(
            ledger, tag, folder / str(retry), msg, stage, tokens, attempt + 12
        )
        try:
            return parser(raw)
        except (ValueError, KeyError, TypeError) as err:
            if retry:
                raise ValueError(str(err)) from err
            msg.extend(
                [
                    dict(role="assistant", content=raw),
                    dict(
                        role="user",
                        content="Public format check: "
                        + str(err)
                        + ". Return a corrected complete answer.",
                    ),
                ]
            )
    raise AssertionError("unreachable")


def emit(pub, mods, parts, n, dest):
    files = pub["starter"].copy()
    imports = []
    calls = []
    for i, mod in enumerate(mods):
        files[mod["file"]] = parts.get(
            mod["file"], "export default function install(env){}"
        )
        imports.append(f"import m{i} from './{mod['file']}';")
        if i < n:
            calls.append(f"m{i}(env);")
    files["index.js"] = "\n".join(
        imports
        + [
            "const env={table:document.querySelector('.table'),state:{},api:{}};",
            *calls,
        ]
    )
    return model_api.calc.files.emit(dest, core.emit("table", files, dest))


def inspect(page, folder, heldout=False):
    step = folder / "probe-input.json"
    dst = folder / "probe.json"
    core.save(step, page)
    if dst.exists():
        return read(dst)
    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "studies.browser_worker",
                probes.__name__,
                str(step),
                str(dst),
                "heldout" if heldout else "public",
            ],
            cwd=ROOT,
            timeout=45,
            check=True,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        if isinstance(exc, subprocess.CalledProcessError):
            msg = (exc.stderr or b"").decode(errors="replace")
            if not ("Timeout" in msg or "Page crashed" in msg):
                raise
        core.save(
            dst,
            dict(
                checks=dict.fromkeys(probes.KEYS, False),
                errors=["Browser interaction timed out or crashed"],
                final_selection=[],
            ),
        )
    return read(dst)


def build(tag, ledger, pub):
    d = OUT / "libraries" / tag
    dst = d / "library.json"
    if dst.exists():
        return read(dst)
    trials = []
    for trial in range(3):
        root = d / str(trial + 1)
        mods = []
        parts = {}
        events = []
        status = "build_failed"
        try:
            init = core.messages(
                'Design 2 to 5 modules that can add ordered capabilities to this public table starter. The earlier modules should work independently. Group related behaviors into coherent workflows. Cover all 20 public changes. You choose module boundaries and the shared API. Return JSON {"modules":[{"name":"...","file":"common/....js","requirements":[1,2],"responsibility":"...","interface":"names and signatures in env.api, and shared env.state fields"}]}. List modules in dependency order. A shared loader supplies only env.table, env.api and env.state; your code must implement all functionality.',
                pub,
            )
            mods = ask(ledger, tag, trial, root / "design", init, "build", design, 3200)

            def implementation(mod, folder, observation=None):
                requirements = [pub["requirements"][i - 1] for i in mod["requirements"]]
                body = dict(
                    starter=pub["starter"],
                    your_library_design=mods,
                    your_module=mod,
                    public_requirements=requirements,
                    shared_contract="export default function install(env) { ... }. env.table is the live HTMLTableElement. env.state and env.api are live shared empty objects. Modules install in design order before any user event. Provide your promised helpers to env.api. Use DOM delegation, prevent default only on handled events, do not overwrite other handlers. Inject any necessary CSS via a style element. Do not replace the starter table.",
                )
                if observation is not None:
                    body.update(
                        previous_file=parts.get(mod["file"], ""),
                        public_browser=observation,
                        sibling_interfaces=[
                            dict(
                                file=k,
                                visible_api=re.findall(
                                    r"env\.api\.([A-Za-z_$][\w$]*)", v
                                )[:40],
                            )
                            for k, v in parts.items()
                            if k != mod["file"]
                        ],
                    )
                prompt = core.messages(
                    "Implement this one spreadsheet module as complete JavaScript source, with one default install(env) function and no imports. No Markdown, JSON or outside prose.",
                    body,
                )
                return ask(ledger, tag, trial, folder, prompt, "build", source, 6900)

            for idx, mod in enumerate(mods):
                try:
                    parts[mod["file"]] = implementation(
                        mod, root / "initial" / str(idx)
                    )
                except ValueError as err:
                    events.append(dict(module=idx, error=str(err)))
            curr = emit(pub, mods, parts, len(mods), root / "initial-page")
            state = inspect(curr, root / "initial-check")
            first = state
            for turn in range(2):
                if all(state["checks"].values()) and not state["errors"]:
                    break
                for idx, mod in enumerate(mods):
                    try:
                        new = implementation(
                            mod, root / f"repair-{turn + 1}" / str(idx), state
                        )
                        candidate = parts | {mod["file"]: new}
                        page = emit(
                            pub,
                            mods,
                            candidate,
                            len(mods),
                            root / f"proposed-{turn}-{idx}",
                        )
                        observed = inspect(page, root / f"checks-{turn}-{idx}")
                        passed = observed["checks"]
                        prior = state["checks"]
                        accept = all(not prior[k] or passed[k] for k in prior) and (
                            sum(passed.values()) > sum(prior.values())
                            or (not observed["errors"] and bool(state["errors"]))
                        )
                        events.append(
                            dict(
                                turn=turn + 1,
                                module=idx,
                                adopted=accept,
                                checks=observed,
                            )
                        )
                        if accept:
                            parts, state = candidate, observed
                    except ValueError as err:
                        events.append(dict(module=idx, turn=turn + 1, error=str(err)))
            if all(state["checks"][k] for k in REQUIRED) and not state["errors"]:
                status = "valid"
        except model_api.calc.action.typed.MISSING as err:
            state = {"errors": [str(err)]}
            first = None
            status = "missing"
        except ValueError as err:
            state = {"errors": [str(err)]}
            first = None
        record = dict(
            attempt=trial + 1,
            status=status,
            design=mods,
            initial=first,
            public=state,
            events=events,
        )
        trials.append(record)
        core.save(root / "attempt.json", record | dict(files=parts))
        if status == "valid":
            core.save(
                dst,
                dict(
                    status=status,
                    attempt=trial + 1,
                    parts=parts,
                    design=mods,
                    trials=trials,
                ),
            )
            break
        if status == "missing" and (OUT / f"closed-{tag}.json").is_file():
            break
    if not dst.exists():
        core.save(
            dst,
            dict(
                status=trials[-1]["status"],
                attempt=None,
                parts={},
                design=[],
                trials=trials,
            ),
        )
    print("table Self", tag, read(dst)["status"], len(trials), flush=True)
    return read(dst)


def generate(reg):
    seal = OUT / "seal.json"
    if seal.exists():
        return
    pub = core.public_input("table")
    ledger = Ledger(OUT / "budget.sqlite3", CAP, CAP)
    empty = emit(pub, [], {}, 0, OUT / "empty")
    baseline = inspect(empty, OUT / "starter-check")
    assert not any(baseline["checks"][k] for k in REQUIRED)
    with (
        patch.multiple(
            model_api.calc.base, OUT=OUT, END=model_api.END, template=model_api.settings
        ),
        ThreadPoolExecutor(max_workers=3) as pool,
    ):
        libs = dict(
            zip(TAGS, pool.map(lambda t: build(t, ledger, pub), TAGS), strict=True)
        )

        def choice(job):
            tag, n = job
            folder = OUT / "plans" / tag / str(n)
            dest = folder / "record.json"
            if dest.exists():
                return read(dest)
            lib = libs[tag]
            if lib["status"] != "valid":
                return dict(status=lib["status"])
            mods = lib["design"]
            prompt = core.messages(
                "How many of these ordered cumulative modules should be installed for the current public requirement? Return a single integer from 0 (only starter) to the number of available modules.",
                dict(
                    public=core.prefix(pub, n),
                    available=[
                        dict(name=m["name"], description=m["responsibility"])
                        for m in mods
                    ],
                ),
            )

            def count(raw):
                text = model_api.calc.base.uncode(raw).strip()
                if not re.fullmatch("[0-5]", text) or int(text) > len(mods):
                    raise ValueError("Return one valid module count")
                return int(text)

            try:
                r = dict(
                    status="valid",
                    count=ask(
                        ledger, tag, 0, folder / "calls", prompt, "plan", count, 700
                    ),
                )
            except ValueError:
                r = dict(status="invalid")
            except model_api.calc.action.typed.MISSING as err:
                r = dict(status="missing", reason=str(err))
            core.save(dest, r)
            return r

        jobs = list(product(TAGS, range(1, 21)))
        choices = dict(zip(jobs, pool.map(choice, jobs), strict=True))
    rows = []
    for (tag, n), sel in choices.items():
        lib = libs[tag]
        for arm, count in [
            ("self", sel.get("count")),
            ("fixed-self", len(lib["design"])),
            ("binding-only", 0),
        ]:
            if arm == "binding-only":
                record = empty
            elif lib["status"] != "valid":
                record = dict(status=lib["status"])
            elif count is None:
                record = dict(status=sel["status"])
            else:
                record = emit(
                    pub,
                    lib["design"],
                    lib["parts"],
                    count,
                    OUT / "pages" / tag / str(count),
                )
            rows.append(
                dict(project="table", tag=tag, task=n, arm=arm, count=count, **record)
            )
    core.save(
        seal,
        dict(
            registration=sha(OUT / "registration.json"),
            empty=baseline,
            rows=rows,
            libraries={
                t: {k: v for k, v in l.items() if k != "parts"} for t, l in libs.items()
            },
        ),
    )


def score(reg):
    seal = read(OUT / "seal.json")
    assert seal["registration"] == sha(OUT / "registration.json") and reg[
        "contract"
    ] == browser.verify_contract("table")
    extra = {}
    for tag, lib in seal["libraries"].items():
        if lib["status"] == "valid":
            page = next(
                r for r in seal["rows"] if r["tag"] == tag and r["arm"] == "fixed-self"
            )
            extra[tag] = inspect(page, OUT / "heldout" / tag, True)
    scores = browser.evaluate(seal["rows"], OUT, {"table": reg["contract"]}, 3)
    models = {
        m: [
            {k: r[k] for k in ("task", "arm", "count", "status", "report_sha256")}
            | dict(passed=False if r["status"] == "invalid" else r["passed"])
            for r in scores
            if r["tag"] == t
        ]
        for t, m in reg["models"].items()
    }
    costs = {}
    for c in ledger_read.calls(OUT / "budget.sqlite3"):
        phase = c["purpose"].split("/")[0]
        v = costs.setdefault(c["model"], {}).setdefault(
            phase, dict(calls=0, settled_micro_usd=0, exposure_micro_usd=0)
        )
        v["calls"] += 1
        v["settled_micro_usd"] += c["actual"] or 0
        v["exposure_micro_usd"] += (
            c["actual"] if c["actual"] is not None else c["reserved"]
        )
    core.save(
        HERE / "result.json",
        dict(
            registration=seal["registration"],
            seal=sha(OUT / "seal.json"),
            models=models,
            libraries=seal["libraries"],
            heldout=extra,
            empty=seal["empty"],
            cost=ledger_read.totals(OUT / "budget.sqlite3"),
            by_model_phase=costs,
        ),
    )


if __name__ == "__main__":
    with browser.lock(OUT / "study.lock"):
        reg = register()
        generate(reg)
        if not (HERE / "result.json").exists():
            score(reg)
