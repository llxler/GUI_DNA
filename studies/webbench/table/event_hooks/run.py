"""Keep the author's modules and separately regenerate their small DOM event handlers."""

from concurrent.futures import ThreadPoolExecutor
from itertools import product
from pathlib import Path
import re
import subprocess
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from studies.webbench.table.model_modules.public_trace.array_reception import (
    run as arrays,
)

table = arrays.table
origin = arrays.original
HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/table-event-hooks-20261128"
CAP = 1.00
SIGNATURE = "env,cell,item,event,menu"
ROLES = {
    "open": (
        "Construct and RETURN the actual detached menu HTMLElement for this cell, or generic table space if cell is null. Build and style its item nodes with the public labels and class names. Position it using the event. The dispatcher mounts the node.",
        (1, 2, 3, 7, 20),
    ),
    "command": (
        "When the user clicks an item or its child, perform its operation on the live table using the original cell. The dispatcher calls dismiss afterwards. Work for arbitrary rows and columns.",
        (2, 3, 7, 20),
    ),
    "dismiss": (
        "The user clicked or right-clicked outside an existing menu, or just activated an item. Close that actual menu so it stops intercepting pointer events. A subsequent right-click creates a fresh menu.",
        (1,),
    ),
    "select": (
        "A user clicked a cell in the table. Ensure the visible selected-cell classes and shared selection are correct, while preserving editing and modifiers.",
        (4, 5, 6, 7, 9, 11),
    ),
}
CHECKS = {"open": "menu", "command": "insert", "dismiss": "outside", "select": "click"}


def register():
    f = OUT / "registration.json"
    paths = [
        Path(__file__),
        HERE / "dispatch.js",
        HERE / "PROTOCOL.md",
        Path(table.__file__),
        Path(table.probes.__file__),
        Path(arrays.__file__),
        arrays.OUT / "registration.json",
        origin.structured.OUT / "seal.json",
    ]
    sums = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    if not f.exists():
        parent = read(arrays.OUT / "registration.json")
        upper = parent["upper"] + CAP
        assert upper <= 20
        balance = check_credits(CAP)
        assert balance["sufficient"]
        core.save(
            f,
            dict(
                utc=now(),
                deadline=parent["deadline"],
                upper=upper,
                cap=CAP,
                balance=balance,
                sources=sums,
                models=parent["models"],
                contract=parent["contract"],
            ),
        )
    assert read(f)["sources"] == sums
    return read(f)


def handler(raw):
    code = table.model_api.calc.base.uncode(raw).strip()
    wrapper = re.fullmatch(
        r"(?:export\s+default\s+)?function(?:\s+\w+)?\s*\([^)]*\)\s*\{(.*)\}\s*;?",
        code,
        re.S,
    )
    if wrapper:
        code = wrapper[1].strip()
    if (
        not code
        or len(code) > 18000
        or re.search(r"^\s*(?:import|export)\b", code, re.M)
    ):
        raise ValueError("Return a short handler body only")
    check = subprocess.run(
        ["node", "--check"],
        input="function handler(" + SIGNATURE + "){\n" + code + "\n}",
        text=True,
        capture_output=True,
        timeout=8,
    )
    if check.returncode:
        raise ValueError(check.stderr[:220])
    return code


def composed(parts, filename, hooks):
    body = parts[filename]
    source, replaced = re.subn(
        r"export\s+default\s+function(?:\s+\w+)?\s*\(\s*env\s*\)",
        "function originalInstaller(env)",
        body,
        count=1,
    )
    if replaced != 1:
        raise ValueError("Could not bind the author's original installer")
    bindings = ",".join(
        k + ":function(" + SIGNATURE + "){\n" + v + "\n}" for k, v in hooks.items()
    )
    src = (
        source
        + "\n"
        + (HERE / "dispatch.js").read_text()
        + "\nexport default function install(env){bindAuthorEvents(env,{"
        + bindings
        + "});originalInstaller(env);}"
    )
    table.source(src)
    return parts | {filename: src}


def generate_handler(
    tag, role, pub, design, library, folder, ledger, trial, feedback=None
):
    instruction, ids = ROLES[role]
    package = dict(
        public_requirements=[pub["requirements"][i - 1] for i in ids],
        your_module_interfaces=design,
        role=role,
        task=instruction,
        other_handlers=library,
    )
    if feedback:
        package["public_feedback"] = feedback
    prompt = core.messages(
        "Write only JavaScript statements inside one browser event handler. Arguments are env, cell, item, event, menu. env.table is the live HTML table. env.state is shared by your four handlers; env.api is the previous library API. cell is the anchor td/th, item the clicked element inside the menu, menu the current container or null. Do not register event listeners, use imports or wrap in JSON. You provide the UI and its mutations yourself. For open return a real DOM element; for the other handlers use the provided arguments directly.",
        package,
    )
    return table.ask(ledger, tag, trial, folder, prompt, "build", handler, 2600)


def build(tag, ledger, pub):
    dest = OUT / "libraries" / tag / "library.json"
    if dest.exists():
        return read(dest)
    prev = origin.structured.OUT / "libraries" / tag
    choices = []
    adopted = None
    for record in sorted(prev.glob("*/attempt.json")):
        pkg = read(record)
        mods, parts = pkg["design"], pkg["files"]
        if not mods or len(parts) != len(mods):
            continue
        if len(choices) == 2:
            break
        trial = dict(
            attempt=len(choices) + 1,
            original_library=pkg["attempt"],
            source_sha256=sha(record),
            events=[],
            status="build_failed",
        )
        root = dest.parent / str(trial["attempt"])
        contact = next(m["file"] for m in mods if 1 in m["requirements"])
        try:
            hooks = {}
            for role in ROLES:
                hooks[role] = generate_handler(
                    tag,
                    role,
                    pub,
                    mods,
                    hooks,
                    root / "initial" / role,
                    ledger,
                    trial["attempt"] + 85,
                )
            for turn in range(2):
                new = composed(parts, contact, hooks)
                candidate = table.emit(pub, mods, new, len(mods), root / f"page-{turn}")
                check = table.inspect(candidate, root / f"probe-{turn}")
                trial["events"].append(dict(checks=check, hooks=dict(hooks)))
                previous = pkg["public"]["checks"]
                ok = (
                    all(not v or check["checks"][k] for k, v in previous.items())
                    and all(check["checks"][k] for k in table.REQUIRED)
                    and not check["errors"]
                )
                if ok:
                    trial["status"] = "valid"
                    adopted = (mods, parts, new)
                    break
                if turn:
                    break
                for role, key in CHECKS.items():
                    if not check["checks"][key]:
                        hooks[role] = generate_handler(
                            tag,
                            role,
                            pub,
                            mods,
                            hooks,
                            root / "repair" / role,
                            ledger,
                            trial["attempt"] + 90,
                            check,
                        )
        except table.model_api.calc.action.typed.MISSING as exc:
            trial.update(status="missing", error=str(exc))
        except (ValueError, TypeError, KeyError) as exc:
            trial["error"] = str(exc)
        choices.append(trial)
        if adopted or trial["status"] == "missing":
            break
    mods, before, parts = adopted or ([], {}, {})
    status = choices[-1]["status"] if choices else "build_failed"
    lib = dict(
        trials=choices,
        status=status,
        attempt=choices[-1]["attempt"] if adopted else None,
        design=mods,
        parts=parts,
        before=before,
    )
    core.save(dest, lib)
    return lib


def generate(reg):
    sealed = OUT / "seal.json"
    if sealed.exists():
        return
    ledger = Ledger(OUT / "budget.sqlite3", CAP, CAP)
    pub = core.public_input("table")
    empty = table.emit(pub, [], {}, 0, OUT / "empty")
    empty_check = table.inspect(empty, OUT / "empty-probe")
    assert not any(empty_check["checks"][k] for k in table.REQUIRED)
    tags = list(reg["models"])
    with (
        patch.multiple(
            table.model_api.calc.base,
            OUT=OUT,
            END=table.model_api.END,
            template=table.model_api.settings,
        ),
        ThreadPoolExecutor(max_workers=4) as pool,
    ):
        libs = dict(
            zip(tags, pool.map(lambda t: build(t, ledger, pub), tags), strict=True)
        )

        def choose(job):
            t, n = job
            lib = libs[t]
            if lib["status"] != "valid":
                return dict(status=lib["status"])
            mods = lib["design"]
            folder = OUT / "plans" / t / str(n)
            if (folder / "record.json").exists():
                return read(folder / "record.json")
            prompt = core.messages(
                "Select how many of your ordered table modules should be installed for this requirement. Give only a single integer from zero to the number of modules.",
                dict(
                    public=core.prefix(pub, n),
                    modules=[m["responsibility"] for m in mods],
                ),
            )

            def count(raw):
                txt = table.model_api.calc.base.uncode(raw).strip()
                if not re.fullmatch(r"[0-5]", txt) or int(txt) > len(mods):
                    raise ValueError("Expected one available module count")
                return int(txt)

            try:
                answer = dict(
                    status="valid",
                    count=table.ask(
                        ledger, t, 102, folder / "call", prompt, "plan", count, 600
                    ),
                )
            except table.model_api.calc.action.typed.MISSING as exc:
                answer = dict(status="missing", reason=str(exc))
            except ValueError:
                answer = dict(status="invalid")
            core.save(folder / "record.json", answer)
            return answer

        jobs = list(product(tags, range(1, 21)))
        decisions = dict(zip(jobs, pool.map(choose, jobs), strict=True))
    rows = []
    for (t, n), sel in decisions.items():
        lib = libs[t]
        mods = lib["design"]
        for arm, parts, count in [
            ("self", lib["parts"], sel.get("count")),
            ("original-same-choice", lib["before"], sel.get("count")),
            ("fixed-self", lib["parts"], len(mods)),
            ("fixed-original", lib["before"], len(mods)),
            ("binding-only", {}, 0),
        ]:
            if arm == "binding-only":
                page = empty
            elif lib["status"] != "valid":
                page = dict(status=lib["status"])
            elif count is None:
                page = dict(status=sel["status"])
            else:
                page = table.emit(
                    pub, mods, parts, count, OUT / "pages" / t / arm / str(count)
                )
            rows.append(
                dict(project="table", tag=t, task=n, arm=arm, count=count, **page)
            )
    core.save(
        sealed,
        dict(
            registration=sha(OUT / "registration.json"),
            empty=empty_check,
            rows=rows,
            libraries={
                t: {k: v for k, v in lib.items() if k not in ("before", "parts")}
                for t, lib in libs.items()
            },
        ),
    )


def run():
    reg = register()
    if not (arrays.OUT / "seal.json").is_file():
        return
    originals = read(origin.OUT / "seal.json")["libraries"]
    last = originals | read(arrays.OUT / "seal.json")["libraries"]
    selected = reg | {
        "models": {
            t: m
            for t, m in reg["models"].items()
            if t in last and last[t]["status"] == "build_failed"
        }
    }
    with patch.multiple(table, OUT=OUT, HERE=HERE):
        generate(selected)
        if not (HERE / "result.json").exists():
            table.score(selected)


if __name__ == "__main__":
    with browser.lock(OUT / "study.lock"):
        run()
