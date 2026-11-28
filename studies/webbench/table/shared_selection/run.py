"""Build independent table-editor modules around one author-owned selection API."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from unittest.mock import patch

from gui_dna.budget import Ledger
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from studies.webbench.table.model_modules import run as table

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/table-self-actions-20261128pm"
CAP = 7
END = datetime(2026, 11, 28, 14, 25, tzinfo=timezone.utc)
TAGS = ("qwen", "oss", "mistral", "gemma", "qwen9", "deepseek-flash", "deepseek-pro")
TARGETS = tuple(range(1, 21))
API = table.model_api
MISSING = API.calc.action.typed.MISSING
# The core supplies the actual API. The loader only passes the starter table and two empty objects.
CONTRACT = """env.table is the actual .table HTMLTableElement with thead and tbody. env.state and env.api start as EMPTY ordinary objects, shared across installers. The table module defines exactly:
env.state.selected = Set of actual td/th elements; env.state.anchor, env.state.focus and env.state.editing = DOM cell or null.
env.api.setSelection(cells, anchor, focus) REPLACES the selection, synchronizes the .selected class, and sets both endpoints; cells is an array of live td/th; [] clears. env.api.rectangle(a,b) returns a flat array of all cells in the rectangle including the header; a,b are cell elements.
env.api.beginEdit(cell), env.api.endEdit() change contentEditable and selection. No other application helpers exist. Use native table.rows, row.cells, rowIndex and cellIndex. The menu, keyboard, rectangle drag, clipboard, resizing and reordering each have one separate event owner. Never invent helper imports. Keep ordinary text editable in edit mode. Use local browser JavaScript only."""
MODULES = {
    "table": ([4, 9, 11, 12], """Own selection state, click, double-click, shift-click and the four API functions. Initialize all fields and implement every declared function. Preserve the distinction between first click on a new cell and a subsequent click on an already selected cell. Only this module projects .selected onto cells. Apply visible highlighting with CSS. The keyboard module handles keydown. Start from unselected; clearing selection removes decorations."""),
    "menu": ([1, 2, 3, 7, 19, 20], """Own contextmenu, all menu items and menu dismissal. One document contextmenu handler branches inside or outside table. Keep a single menu anchored to the original cell; do not open and close it from the same bubbling event. Implement operations on actual row/section/cell nodes yourself, including minimum-size menu, item classes, real insertion/deletion in tbody or across rows, selection via setSelection, filtering and sorting. Left clicking menu whitespace or anywhere else dismisses; right clicking outside dismisses. Never intercept ordinary left clicks on cells. Work even if only core modules installed."""),
    "key": ([5, 6, 7, 8, 9, 11, 12], """Own keyboard navigation, selection shortcuts and editing shortcuts only. Implement arrow, Tab, Shift+Tab, Shift+arrow, Ctrl/Cmd+A, Escape, Delete/Backspace and Enter through the shared state/API. Treat headers as cells. Preserve anchor when growing/shrinking rectangles. With no selection arrows/Tab start at top-left. Handle editing mode and Escape distinctly. Other modules own clipboard shortcuts; leave them alone."""),
    "mouse": ([4, 9, 10, 11, 15, 16, 17, 18], """Own pressed-left-button movement for selecting a rectangle. Do not change selection at mousedown unless the pointer actually travels. Preserve simple click and editing; after a completed rectangle drag suppress only the synthetic trailing click which would collapse it. Yield resize handles and reorder gestures on a fully selected row/column. Do not implement sizing/reordering yourself."""),
    "clipboard": ([13, 14], """Own clipboard copy/paste for one or multiple selected cells. Preserve rectangular plain-text data and expand the real table as needed, with header and body cell types. Support real keyboard copy/paste and clipboard events, keep a local fallback for the same page and avoid double handling. Leave ordinary text editing intact."""),
    "layout": ([15, 16], """Own row/column boundary drag for resizing. Use real element geometry, include header boundaries, enforce public minimum sizes; all cells of a resized column stay aligned. Coordinate with selection and reordering by claiming boundary gestures before bubbling. Do not claim interior simple clicks."""),
    "drag": ([17, 18], """Handle moving a whole selected row/column according to pointer half of target; preserve values, selection and header/body structure. Only claim an actual drag started on a wholly selected body row or column. Cooperate with mouse rectangle and boundary resizing; do not consume stationary clicks."""),
}
CORE = ("table", "menu")


def registration():
    path = OUT / "registration.json"
    public = core.public_input("table")
    paths = [Path(__file__), HERE / "PROTOCOL.md", Path(table.__file__), Path(table.probes.__file__),
             Path(API.__file__), Path(API.calc.base.__file__), Path(browser.__file__)]
    sources = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    if not path.exists():
        balance = read(OUT / "credits.json")
        assert balance["effective_remaining_usd"] >= CAP and datetime.now(timezone.utc) < END
        core.save(OUT / "public.json", public)
        core.save(path, dict(utc=now(), deadline=END.isoformat(), cap=CAP, sources=sources,
                             targets=TARGETS, public_sha256=sha(OUT / "public.json"),
                             contract=browser.verify_contract("table"),
                             models={t: API.settings("table", t, "build")["model"] for t in TAGS}))
    reg = read(path)
    assert reg["sources"] == sources and read(OUT / "public.json") == public
    return reg


def design(parts):
    return [dict(file=f"common/{name}.js", name=name) for name in parts]


def page(public, parts, count, directory):
    files = {f"common/{name}.js": code for name, code in parts.items()}
    return table.emit(public, design(parts), files, count, directory)


def observe(public, parts, directory):
    candidate = page(public, parts, len(parts), directory / "page")
    return table.inspect(candidate, directory / "public")


def passed(check):
    return {k for k, ok in check["checks"].items() if ok}


def admitted(check):
    return not check["errors"] and set(table.REQUIRED) <= passed(check)


def author(tag, name, public, ledger, dest, trial, prior=None, observations=None):
    ids, role = MODULES[name]
    message = core.messages(
        "Return exactly one ES module: export default function install(env) { ... }. Implement the requested interactive behavior, not declarations or stubs. No imports, remote resources, wrappers or explanation.",
        dict(module=name, responsibility=role, shared_interface=CONTRACT,
             starter=public["starter"], public_changes=[public["requirements"][n - 1] for n in ids],
             your_previous_source=prior, observed_on_public_starter=observations),
    )
    return table.ask(ledger, tag, trial, dest, message, "build", table.source, 5400)


def build(tag, public, ledger):
    root = OUT / "libraries" / tag
    dest = root / "library.json"
    if dest.exists():
        return read(dest)
    history = []
    parts = {}
    check = None
    status = "build_failed"
    try:
        for trial in (1, 2):
            parts = {}
            folder = root / str(trial)
            try:
                for name in CORE:
                    parts[name] = author(tag, name, public, ledger, folder / name, trial)
                check = observe(public, parts, folder / "initial")
                history.append(dict(trial=trial, step="initial", public=check))
                for turn in (1, 2):
                    if admitted(check):
                        break
                    failed = set(table.REQUIRED) - passed(check)
                    owners = [n for n in CORE if check["errors"] or (
                        "click" in failed if n == "table" else failed - {"click"})]
                    for name in owners:
                        attempt = folder / f"repair-{turn}" / name
                        code = author(tag, name, public, ledger, attempt / "answer", trial, parts[name], check)
                        proposal = parts | {name: code}
                        observed = observe(public, proposal, attempt)
                        keep = (passed(check) & set(table.REQUIRED)) <= passed(observed) and (
                            len(observed["errors"]) <= len(check["errors"]))
                        history.append(dict(trial=trial, step="repair-" + name, retained=keep, public=observed))
                        if keep:
                            parts, check = proposal, observed
                        if admitted(check):
                            break
                if admitted(check):
                    status = "valid"
                    break
            except (ValueError, KeyError, TypeError) as exc:
                history.append(dict(trial=trial, step="core delivery", error=str(exc)))
        if status == "valid":
            profiles = [dict(count=len(parts), modules=list(parts), checks=sorted(passed(check)))]
            for name in list(MODULES)[len(CORE):]:
                original = None
                feedback = None
                for turn in (1, 2):
                    folder = root / "extensions" / name / str(turn)
                    try:
                        original = author(tag, name, public, ledger, folder / "answer", trial,
                                          original, feedback)
                        proposal = parts | {name: original}
                        feedback = observe(public, proposal, folder)
                        keep = not feedback["errors"] and passed(check) <= passed(feedback)
                    except (ValueError, KeyError, TypeError) as exc:
                        feedback, keep = dict(error=str(exc)), False
                    history.append(dict(step=name, revision=turn, retained=keep, public=feedback))
                    if keep:
                        parts, check = proposal, feedback
                        profiles.append(dict(count=len(parts), modules=list(parts), checks=sorted(passed(check))))
                        break
        else:
            profiles = []
    except MISSING as exc:
        status, profiles = "missing", []
        history.append(dict(step="transport", error=str(exc)))
    lib = dict(status=status, history=history, parts=parts, profiles=profiles)
    core.save(dest, lib)
    print("Prepared", tag, status, list(parts), flush=True)
    return lib


def plan(tag, n, public, lib, ledger):
    if lib["status"] != "valid":
        return dict(status=lib["status"])
    dest = OUT / "plans" / tag / str(n)
    path = dest / "choice.json"
    if path.exists():
        return read(path)
    profiles = lib["profiles"]
    allowed = {p["count"] for p in profiles}
    def parse(raw):
        value = API.calc.base.uncode(raw).strip()
        if not value.isdecimal() or int(value) not in allowed:
            raise ValueError(f"Return just one of {sorted(allowed)}")
        return int(value)
    prompt = core.messages("Choose one of your cumulative module profiles for the final public request and its prerequisites. Reply only with its integer count. An extension can interact with earlier inputs. Use the observed public actions and module responsibilities.",
                           dict(requirements=public["requirements"][:n], profiles=profiles,
                                responsibilities={k:v[1] for k,v in MODULES.items()}))
    try:
        outcome = dict(status="valid", count=table.ask(ledger, tag, 5, dest / "answer", prompt, "plan", parse, 650))
    except MISSING as exc:
        outcome = dict(status="missing", error=str(exc))
    except ValueError as exc:
        outcome = dict(status="invalid", error=str(exc))
    core.save(path, outcome)
    return outcome


def generate(reg):
    public = read(OUT / "public.json")
    ledger = Ledger(OUT / "budget.sqlite3", CAP, CAP)
    empty = page(public, {}, 0, OUT / "empty")
    baseline = table.inspect(empty, OUT / "empty-check")
    assert not passed(baseline).intersection(table.REQUIRED)
    with patch.multiple(API.calc.base, OUT=OUT, END=END, template=API.settings), ThreadPoolExecutor(max_workers=7) as pool:
        libs = dict(zip(TAGS, pool.map(lambda t: build(t, public, ledger), TAGS), strict=True))
        jobs = list(product(TAGS, TARGETS))
        def deploy(job):
            t, n = job
            return plan(t, n, public, libs[t], ledger)
        choices = dict(zip(jobs, pool.map(deploy, jobs), strict=True))
    rows = []
    for (tag, n), choice in choices.items():
        lib = libs[tag]
        for arm, state, count in [("self", choice["status"], choice.get("count")),
                                  ("fixed-self", lib["status"], len(lib["parts"])),
                                  ("binding-only", "valid", 0)]:
            record = dict(status=state)
            if state == "valid":
                record = page(public, lib["parts"], count, OUT / "pages" / tag / str(count)) if count else empty
            rows.append(dict(project="table", task=n, arm=arm, count=count, tag=tag, **record))
    summary = {t: {k:v for k,v in lib.items() if k != "parts"} for t,lib in libs.items()}
    core.save(OUT / "seal.json", dict(registration=sha(OUT / "registration.json"), libraries=summary,
                                      empty=baseline, rows=rows))


def score(reg):
    seal = read(OUT / "seal.json")
    assert reg["contract"] == browser.verify_contract("table") and seal["registration"] == sha(OUT / "registration.json")
    judged = browser.evaluate(seal["rows"], OUT, {"table":reg["contract"]}, 6)
    models = {}
    for r in judged:
        row = {k:r[k] for k in ("task","arm","count","status","passed","report_sha256")}
        if r["status"] == "invalid":
            row["passed"] = False
        if r["status"] == "valid":
            row["files_digest"] = browser.digest(r["files"])
        models.setdefault(reg["models"][r["tag"]], []).append(row)
    costs = {}
    for call in ledger_read.calls(OUT / "budget.sqlite3"):
        phase = call["purpose"].partition("/")[0]
        usd = call["actual"]
        group = costs.setdefault(call["model"], {}).setdefault(phase, dict(calls=0, settled_micro_usd=0, exposure_micro_usd=0))
        group["calls"] += 1
        group["settled_micro_usd"] += usd or 0
        group["exposure_micro_usd"] += call["reserved"] if usd is None else usd
    core.save(HERE / "result.json", dict(registration=seal["registration"],seal=sha(OUT / "seal.json"),
        sources=reg["sources"], targets=reg["targets"], models=models, libraries=seal["libraries"],
        generators=reg["models"], empty=seal["empty"], cost=ledger_read.totals(OUT/"budget.sqlite3"), by_model_phase=costs))


if __name__ == "__main__":
    with browser.lock(OUT / "study.lock"):
        registration_data = registration()
        if not (OUT / "seal.json").exists():
            generate(registration_data)
        if not (HERE / "result.json").exists():
            score(registration_data)
