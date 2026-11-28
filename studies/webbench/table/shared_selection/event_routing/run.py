"""Repair only publicly observed menu and key-routing failures of the same author."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from itertools import product
from pathlib import Path
from unittest.mock import patch
import json
import re

from gui_dna.budget import Ledger
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from .. import run as base

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/table-self-routing-20261128pm"
CAP = 2.90
KEYS = {
    "move": ("arrowleft arrowright arrowup arrowdown tab", [5, 6, 9]),
    "select": ("a delete backspace", [7, 8]),
    "edit": ("enter escape", [7, 11, 12]),
}
MENU_IDS = [1, 2, 3, 7, 19, 20]
NEEDED = {"right", "tab", "reverse", "edit", "clear"}


def register():
    path = OUT / "registration.json"
    files = [Path(__file__), HERE / "PROTOCOL.md", HERE / "menu.js", HERE / "keys.js",
             Path(base.__file__), base.OUT / "registration.json"]
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in files}
    parent = read(base.OUT / "registration.json")
    if not path.exists():
        assert base.CAP + CAP <= 10 and read(OUT / "credits.json")["effective_remaining_usd"] >= CAP
        core.save(path, {**parent, "utc":now(), "cap":CAP, "sources":hashes,
                         "parent_registration":sha(base.OUT / "registration.json")})
    assert read(path)["sources"] == hashes
    return read(path)


def schema(raw):
    value = json.loads(base.API.calc.base.uncode(raw))
    entries = value["items"] if isinstance(value, dict) else value
    if not isinstance(entries, list) or not 3 <= len(entries) <= 20:
        raise ValueError("Supply a flat list of menu items, one per operation")
    names = set()
    for e in entries:
        if (not isinstance(e, dict) or e.get("scope") not in ("td","th") or
            not re.fullmatch(r"menu-item-[a-z-]+", str(e.get("className", ""))) or
            not isinstance(e.get("label"), str) or not e["label"].strip() or e["className"] in names):
            raise ValueError("Each item needs td/th scope, unique public className and visible label")
        names.add(e["className"])
    if not any(e["scope"] == "td" and e["className"] == "menu-item-insert-row-above" for e in entries):
        raise ValueError("The public body Insert Row Above entry is missing")
    return entries


def function_body(raw, arguments):
    code = base.API.calc.base.uncode(raw).strip()
    wrapped = re.fullmatch(r"(?:export default )?function(?:\s+\w+)?\s*\([^)]*\)\s*\{(.*)\}\s*;?", code, re.S)
    if wrapped:
        code = wrapped[1].strip()
    if not code:
        raise ValueError("Empty function body")
    base.table.source("export default function install(env){const callback=function(" + arguments + "){" + code + "\n};}")
    return code


def ask(tag, destination, name, args, payload, ledger):
    prompt = core.messages(
        "Implement just the JavaScript statements inside this ONE callback. Do not install listeners or a second controller, return JSON, invent globals or give explanations. All the arguments below are provided by the host. Use real DOM nodes. Use only functions actually present in your own selection module. Implement the public behavior yourself.",
        dict(callback=name, arguments=args, **payload))
    return base.table.ask(ledger, tag, 31, destination, prompt, "build",
                          lambda raw: function_body(raw, args), 2000)


def menu_source(items, bodies):
    funcs = ",".join(json.dumps(key) + ":function(table,cell,state,api,event){\n" + body + "\n}"
                     for key,body in bodies.items())
    return (HERE / "menu.js").read_text().replace("/*ITEMS*/", json.dumps(items)).replace("/*ACTIONS*/","{" + funcs + "}")


def menu_recovery(tag, public, prior, ledger, root, history):
    selector = prior.get("table")
    reqs = [public["requirements"][n-1] for n in MENU_IDS]
    prompt = core.messages('List the menu items in the public requirements. Return JSON {"items":[{"scope":"td","label":"visible caption","className":"exact CSS class"}]}. For header-only items use scope th. One entry per distinct command.', reqs)
    entries = base.table.ask(ledger, tag, 30, root / "menu-schema", prompt, "build", schema, 2100)
    bodies = {}
    for entry in entries:
        name = entry["className"]
        bodies[name] = ask(tag, root / "items" / name, name, "table,cell,state,api,event",
                           dict(item=entry, public_requirements=reqs, your_selection_source=selector,
                                instructions="cell is the right-clicked td or th; table is the actual HTMLTableElement. Mutate real row/column DOM or selection. Insertions use the actual section parent and the correct cell types; keep other rows aligned."), ledger)
    if not selector:
        selector = base.author(tag,"table",public,ledger,root / "selection",3)
    shell = menu_source(entries, {})
    parts = {"table":selector, "menu":menu_source(entries,bodies)}
    checked = base.observe(public,parts,root / "assembled")
    history.append(dict(step="menu", public=checked))
    if not base.admitted(checked):
        flags = checked["checks"]
        if not flags["click"] or checked["errors"]:
            parts["table"] = base.author(tag,"table",public,ledger,root / "repair-selection",3,parts["table"],checked)
        if not flags["insert"]:
            name = "menu-item-insert-row-above"
            bodies[name] = ask(tag,root / "repair-insert",name,"table,cell,state,api,event",
                               dict(public_requirements=reqs, previous=bodies[name], public_observations=checked,
                                    instructions="cell.parentElement is the original tr. Insert a NEW tr immediately before it into that same tbody with equally many td children."), ledger)
            parts["menu"] = menu_source(entries,bodies)
        checked = base.observe(public,parts,root / "repaired")
        history.append(dict(step="menu-repair", public=checked))
    return parts, checked, shell


def keyboard(tag, public, parts, before, ledger, root):
    handlers = []
    for name,(keys,ids) in KEYS.items():
        arguments = "event,table,state,api,selected,focus,anchor"
        payload = dict(keys=keys, public_changes=[public["requirements"][n-1] for n in ids],
                       your_selection_module=parts["table"], previous_keyboard=parts.get("key",""),
                       browser=before, contract="The host calls you on document keydown for the given keys. selected is a fresh ARRAY of actual selected cell DOM nodes. focus/anchor are actual cells or null. No need to subscribe to events or initialize or replace state/api. Navigation includes header and body. Execute directly; preventDefault when handling your keys.")
        body = ask(tag,root / name,name,arguments,payload,ledger)
        handlers.append("[" + json.dumps(keys.split()) + ",function(" + arguments + "){\n" + body + "\n}]")
    return (HERE/"keys.js").read_text().replace("/*HANDLERS*/","[" + ",".join(handlers) + "]")


def profiles_for(tag, public, parts):
    names = list(parts)
    profiles = []
    for n in range(2,len(names)+1):
        subset = {k:parts[k] for k in names[:n]}
        check = base.observe(public, subset, OUT/"profiles"/tag/str(n))
        profiles.append(dict(count=n, modules=names[:n], checks=sorted(base.passed(check))))
    return profiles


def prepare(tag, public, ledger):
    dst = OUT/"libraries"/tag/"library.json"
    if dst.exists():
        return read(dst)
    folder = dst.parent
    old = read(base.OUT/"libraries"/tag/"library.json")
    valid_parent = old["status"] == "valid"
    parts = dict(old["parts"])
    history = []
    shell = None
    changed = False
    status = old["status"]
    try:
        if valid_parent:
            check = base.observe(public,parts,folder/"baseline")
            assert base.admitted(check)
        elif status == "build_failed":
            parts,check,shell = menu_recovery(tag,public,parts,ledger,folder/"core",history)
            if base.admitted(check):
                changed,status = True,"valid"
        if status == "valid" and not NEEDED <= base.passed(check):
            # Preserve the original order when replacing a registered key installer.
            before = check
            for turn in (1, 2):
                stage = folder/"keys"/str(turn)
                code = keyboard(tag,public,parts,before,ledger,stage)
                proposal = dict(parts)
                proposal["key"] = code
                proposal = {k:proposal[k] for k in base.MODULES if k in proposal}
                observed = base.observe(public,proposal,stage)
                keep = not observed["errors"] and base.passed(check) < base.passed(observed)
                history.append(dict(step="keys",revision=turn,retained=keep,public=observed))
                if keep:
                    parts,check,changed = proposal,observed,True
                    break
                before = observed
        if status == "valid" and not valid_parent:
            for name in list(base.MODULES)[3:]:
                stage = folder/"extensions"/name
                try:
                    proposed = parts | {name:base.author(tag,name,public,ledger,stage/"answer",4)}
                    observed = base.observe(public,proposed,stage)
                    keep = not observed["errors"] and base.passed(check) <= base.passed(observed)
                    history.append(dict(step=name,retained=keep,public=observed))
                    if keep:
                        parts,check = proposed,observed
                except ValueError as exc:
                    history.append(dict(step=name,retained=False,error=str(exc)))
    except (*base.MISSING, ValueError, KeyError, TypeError) as exc:
        history.append(dict(step="not adopted",error=str(exc)))
        if not changed:
            if not valid_parent and isinstance(exc,base.MISSING):
                status = "missing"
            parts = dict(old["parts"])
    if status == "valid" and changed:
        profiles = profiles_for(tag,public,parts)
    else:
        profiles = old["profiles"] if valid_parent else []
    lib = dict(status=status,changed=changed,parts=parts,profiles=profiles,shell=shell,history=history,
               parent_status=old["status"],parent_library=sha(base.OUT/"libraries"/tag/"library.json"))
    core.save(dst,lib)
    print("Routed",tag,status,"changed",changed,flush=True)
    return lib


@contextmanager
def requests():
    with patch.multiple(base.API.calc.base,OUT=OUT,END=base.END,template=base.API.settings):
        yield


def generate(reg):
    public = read(base.OUT / "public.json")
    ledger = Ledger(OUT/"budget.sqlite3",CAP,CAP)
    with requests(), ThreadPoolExecutor(max_workers=7) as pool:
        libs = dict(zip(base.TAGS,pool.map(lambda t: prepare(t,public,ledger),base.TAGS),strict=True))
        jobs = list(product(base.TAGS,base.TARGETS))
        def deploy(job):
            t,n = job
            lib = libs[t]
            if lib["status"] != "valid":
                return dict(status=lib["status"])
            if not lib["changed"]:
                return read(base.OUT/"plans"/t/str(n)/"choice.json")
            with_out = OUT/"plans"/t/str(n)
            if not (with_out/"choice.json").exists():
                # plan() writes to its module's OUT. Call with the study-wide override below.
                return base.plan(t,n,public,lib,ledger)
            return read(with_out/"choice.json")
        parent_dir = base.OUT
        parent_choices = {(t,n):read(parent_dir/"plans"/t/str(n)/"choice.json") for t,n in jobs
                          if libs[t]["status"]=="valid" and not libs[t]["changed"]}
        with patch.object(base,"OUT",OUT):
            choices = dict(zip(jobs,pool.map(lambda j: parent_choices[j] if j in parent_choices else deploy(j),jobs),strict=True))
    rows = []
    empty = base.page(public,{},0,OUT/"empty")
    for (tag,n),choice in choices.items():
        lib = libs[tag]
        arms = [("self",choice["status"],choice.get("count"),lib["parts"]),
                ("fixed-self",lib["status"],len(lib["parts"]),lib["parts"]),
                ("binding-only","valid",0,{})]
        if lib["shell"]:
            arms.append(("menu-shell","valid",1,{"menu":lib["shell"]}))
        for arm,state,count,parts in arms:
            obj = dict(status=state)
            if state == "valid":
                obj = base.page(public,parts,count,OUT/"pages"/tag/("menu-shell" if arm=="menu-shell" else str(count))) if count else empty
            rows.append(dict(project="table",tag=tag,task=n,arm=arm,count=count,**obj))
    core.save(OUT/"seal.json",dict(registration=sha(OUT/"registration.json"),parent_seal=sha(base.OUT/"seal.json"),
                                  empty=read(base.OUT/"seal.json")["empty"],rows=rows,
                                  libraries={t:{k:v for k,v in lib.items() if k not in ("parts","shell")} for t,lib in libs.items()}))


if __name__ == "__main__":
    import time
    with browser.lock(OUT/"study.lock"):
        reg = register()
        while not (base.OUT/"seal.json").exists() and not (OUT/"seal.json").exists():
            if __import__("datetime").datetime.now(base.timezone.utc) >= base.END:
                raise TimeoutError("Parent did not seal before deadline")
            time.sleep(3)
        if not (OUT/"seal.json").exists():
            generate(reg)
        if not (HERE/"result.json").exists():
            with patch.multiple(base,OUT=OUT,HERE=HERE):
                base.score(reg)
