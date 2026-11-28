"""Ask the original library author to implement pure keyboard state transitions."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from itertools import product
from pathlib import Path
from unittest.mock import patch
import json
import re
import subprocess

from gui_dna.budget import Ledger
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from .. import run as base
from ..event_routing import run as routed
from ..command_delivery import run as commands
from ..core_recovery import run as recovery

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/table-self-key-transitions-20261128pm"
CAP = 2.0
STAGES = (base.OUT, routed.OUT, commands.OUT, recovery.OUT)
NOOP = "export default function install(env) {}"
GROUPS = {
    "arrows": (["arrowleft", "arrowright", "arrowup", "arrowdown"],
               "Move one cell, clamp at the edge. When empty choose top-left. Shift extends or shrinks a rectangle from the existing anchor to the new focus. Return selection, focus, anchor. While editing leave text movement alone."),
    "tab": (["tab"], "Tab moves forward in row-major order with wraparound, Shift+Tab backwards. Empty selection starts at top-left either way. End editing and select exactly one cell with new anchor and focus."),
    "selection": (["a", "backspace", "delete"], "Ctrl/Meta+A selects every cell, including header. Delete/Backspace clears text in every selected cell by returning writes. Text editing and ordinary typing should remain native."),
    "editing": (["enter", "escape"], "Enter starts editing a focused selected cell. Enter or Escape while editing ends editing, keeping its cell selected. Escape outside editing clears selection. Return null for unhandled keys."),
}
SCHEMA = """Write the body of function transition(s). All indices are zero-based; header counts as row 0. Inputs: s.key (e.g. 'ArrowRight' or 'Tab'), s.shift, s.ctrl (includes Meta), s.rows, s.cols, s.focus, s.anchor, s.editing (each null or [row,col]), s.selected (array of [row,col]). Output null for unhandled or a plain object containing any of: selection (FULL array of [row,col]), focus, anchor, writes (array of [row,col,string]), editing ([row,col] or null to end editing). Return patches; do not mutate input. No DOM, events, globals, or external helpers. Return only JS statements, no function wrapper."""


def parent(tag):
    return next(p for p in reversed(STAGES) if (p / "libraries" / tag / "library.json").exists())


def choice_stage(tag):
    for p in reversed(STAGES):
        path = p / "libraries" / tag / "library.json"
        if path.exists() and read(path).get("changed", True):
            return p
    raise ValueError(f"No parent configuration for {tag}")


def register():
    files = [Path(__file__), HERE / "PROTOCOL.md", HERE / "host.js", HERE / "check.cjs",
             Path(base.__file__), Path(routed.__file__), Path(commands.__file__), Path(recovery.__file__)]
    sources = {str(p.relative_to(ROOT)): sha(p) for p in files}
    parents = {p.name: sha(p / "seal.json") for p in STAGES}
    path = OUT / "registration.json"
    if not path.exists():
        exposure = sum(ledger_read.totals(p / "budget.sqlite3")["exposure_usd"] for p in STAGES)
        assert exposure + CAP <= 10 and read(OUT / "credits.json")["effective_remaining_usd"] >= CAP
        assert datetime.now(base.timezone.utc) < base.END
        core.save(path, read(STAGES[0] / "registration.json") | dict(
            utc=now(), cap=CAP, sources=sources, parent_seals=parents, closed_exposure=exposure))
    reg = read(path)
    assert reg["sources"] == sources and reg["parent_seals"] == parents
    return reg


def unit(group, body):
    checked = subprocess.run(["node", str(HERE / "check.cjs")], input=json.dumps(dict(group=group, body=body)),
                             text=True, timeout=8, capture_output=True, check=True)
    return json.loads(checked.stdout)


def generate_group(tag, group, folder, ledger):
    feedback = None
    for attempt in (1, 2):
        prompt = core.messages(SCHEMA, dict(group=group, task=GROUPS[group][1], previous_public_feedback=feedback))
        try:
            body = base.table.ask(ledger, tag, 60 + attempt, folder / str(attempt) / "call", prompt, "build",
                                  lambda raw: routed.function_body(raw, "s"), 2200)
            cases = unit(group, body)
            core.save(folder / str(attempt) / "unit.json", cases)
            if all(c["pass"] for c in cases):
                return body
            feedback = dict(previous_body=body, failing_public_examples=[c for c in cases if not c["pass"]])
        except ValueError as err:
            feedback = str(err)
        except base.MISSING:
            break
    return None


def ordered(parts, key):
    with_key = dict(parts, key=key)
    return {name: with_key[name] for name in base.MODULES if name in with_key}


def candidate(old, bodies):
    original = old.get("key", NOOP)
    original, found = re.subn(r"export\s+default\s+function(?:\s+\w+)?\s*\(", "function originalKeyboard(", original, count=1)
    assert found == 1
    programs = ",".join("{keys:" + json.dumps(GROUPS[name][0]) + ",apply:function(s){const state=s;return (function(){\n" + body + "\n})();}}" for name, body in bodies.items())
    key = (HERE / "host.js").read_text() + "\n" + original + "\nexport default function install(env){mountTransitions(env,[" + programs + "]);originalKeyboard(env);}"
    return ordered(old, key)


def prepare(tag, pub, ledger):
    root = OUT / "libraries" / tag
    dst = root / "library.json"
    if dst.exists():
        return read(dst)
    path = parent(tag) / "libraries" / tag / "library.json"
    old = read(path)
    assert old["status"] == "valid"
    parts, profiles = old["parts"], old["profiles"]
    before = base.observe(pub, parts, root / "before")
    assert base.admitted(before)
    original_checks = base.passed(before)
    history = [dict(step="original", public=before)]
    selected = {}
    if routed.NEEDED - original_checks:
        authored = {}
        for group in GROUPS:
            body = generate_group(tag, group, root / "functions" / group, ledger)
            if body is not None:
                authored[group] = body
        if authored:
            proposal = candidate(parts, authored)
            all_checks = base.observe(pub, proposal, root / "all")
            history.append(dict(step="all", groups=list(authored), public=all_checks))
            if not all_checks["errors"] and original_checks < base.passed(all_checks):
                selected = authored
            else:
                retained = original_checks
                for name, body in authored.items():
                    attempt = selected | {name: body}
                    observed = base.observe(pub, candidate(parts, attempt), root / "incremental" / name)
                    history.append(dict(step=name, groups=list(attempt), public=observed))
                    if not observed["errors"] and retained <= base.passed(observed):
                        retained, selected = base.passed(observed), attempt
                if retained == original_checks:
                    selected = {}
    if selected:
        parts = candidate(parts, selected)
        profiles = []
        for n in range(2, len(parts) + 1):
            view = dict(list(parts.items())[:n])
            observed = base.observe(pub, view, root / "profiles" / str(n))
            profiles.append(dict(count=n, modules=list(view), checks=sorted(base.passed(observed))))
    library = dict(status="valid", changed=bool(selected), parts=parts, profiles=profiles, shell=old["shell"],
                   history=history, retained=list(selected), parent_library=sha(path), parent_status=old["status"])
    core.save(dst, library)
    print("Keyboard transitions", tag, list(selected), flush=True)
    return library


def generate(reg):
    pub = read(STAGES[0] / "public.json")
    ledger = Ledger(OUT / "budget.sqlite3", CAP, CAP)
    jobs = list(product(reg["models"], base.TARGETS))
    with patch.multiple(base.API.calc.base, OUT=OUT, END=base.END, template=base.API.settings), ThreadPoolExecutor(max_workers=7) as pool:
        libs = dict(zip(reg["models"], pool.map(lambda t: prepare(t, pub, ledger), reg["models"]), strict=True))
        def choose(job):
            tag, n = job
            if libs[tag]["changed"]:
                return base.plan(tag, n, pub, libs[tag], ledger)
            return read(choice_stage(tag) / "plans" / tag / str(n) / "choice.json")
        with patch.object(base, "OUT", OUT):
            choices = dict(zip(jobs, pool.map(choose, jobs), strict=True))
    empty = base.page(pub, {}, 0, OUT / "empty")
    rows = []
    for (tag, n), choice in choices.items():
        lib = libs[tag]
        prior = read(parent(tag) / "libraries" / tag / "library.json")["parts"]
        comparison = {k: prior.get(k, NOOP) for k in lib["parts"]}
        groups = [("self", lib["parts"], choice["status"], choice.get("count")),
                  ("old-same-choice", comparison, choice["status"], choice.get("count")),
                  ("fixed-self", lib["parts"], "valid", len(lib["parts"])), ("binding-only", {}, "valid", 0)]
        if lib["shell"]:
            groups.append(("menu-shell", {"menu": lib["shell"]}, "valid", 1))
        for arm, parts, state, count in groups:
            page = dict(status=state)
            if state == "valid":
                page = base.page(pub, parts, count, OUT / "pages" / tag / arm / str(count)) if count else empty
            rows.append(dict(project="table", tag=tag, task=n, arm=arm, count=count, **page))
    core.save(OUT / "seal.json", dict(rows=rows, empty=read(STAGES[0] / "seal.json")["empty"],
              registration=sha(OUT / "registration.json"), parent_seals=reg["parent_seals"],
              libraries={t: {k:v for k,v in lib.items() if k not in ("parts","shell")} for t,lib in libs.items()}))


if __name__ == "__main__":
    with browser.lock(OUT / "study.lock"):
        reg = register()
        if not (OUT / "seal.json").exists():
            generate(reg)
        if not (HERE / "result.json").exists():
            with patch.multiple(base, OUT=OUT, HERE=HERE):
                base.score(reg)
