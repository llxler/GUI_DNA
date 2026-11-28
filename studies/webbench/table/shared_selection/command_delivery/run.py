"""Recover small author-written callbacks and bind the browser event under its declared names."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from itertools import product
from pathlib import Path
from unittest.mock import patch
import json
import time

from gui_dna.budget import Ledger
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from .. import run as base
from ..event_routing import run as routing

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/table-self-commands-20261128pm"
CAP = 2.0
ARGUMENTS = "event,table,state,api,selected,focus,anchor"
FIRST = base.OUT
SECOND = routing.OUT


def register():
    dst = OUT / "registration.json"
    files = [Path(__file__), HERE/"PROTOCOL.md", Path(routing.__file__), Path(base.__file__),
             FIRST/"seal.json", SECOND/"registration.json", routing.HERE/"keys.js", routing.HERE/"menu.js"]
    hashes = {str(p.relative_to(ROOT)):sha(p) for p in files}
    if not dst.exists():
        used = ledger_read.totals(FIRST/"budget.sqlite3")["exposure_usd"]
        assert used + routing.CAP + CAP <= 10 and read(OUT/"credits.json")["effective_remaining_usd"] >= CAP
        previous = read(SECOND/"registration.json")
        core.save(dst, {**previous,"utc":now(),"sources":hashes,"cap":CAP,"closed_first_exposure":used})
    assert read(dst)["sources"] == hashes
    return read(dst)


def short(tag, ledger, folder, name, args, request, trial=44):
    msg = core.messages("Complete ONE JavaScript function body. Return only statements between its braces. All arguments are supplied. No outer installer, no style, no other functions or listeners unless local to this body. Use vanilla DOM. Keep it short and complete.",
                        dict(function=f"function {name}({args})", task=request))
    return base.table.ask(ledger,tag,trial,folder,msg,"build",lambda raw:routing.function_body(raw,args),1450)


def saved_body(folder, args):
    for p in sorted(folder.glob("*/transmission-*/settled.json")):
        response = p.with_name("response.json")
        assert sha(response) == read(p)["response_sha256"]
        raw = read(response)["choices"][0]["message"].get("content") or ""
        try:
            return routing.function_body(raw,args)
        except (ValueError,TypeError):
            continue
    return None


def select_module(tag, ledger, folder):
    specs = [
        ("setSelection","cells,anchor,focus","Replace the selected cells with the supplied array, remove stale .selected classes and assign .selected to each new cell. state.selected is a Set; state.anchor and state.focus are DOM cells. Update these three fields, style highlight via the selected class."),
        ("rectangle","a,b","Return an array of td/th cells in the rectangle between cell a and b, including both. table.rows includes header."),
        ("beginEdit","cell","Set cell contentEditable true, set state.editing, focus it; ensure only cell is selected with api.setSelection([cell],cell,cell)."),
        ("endEdit","","If state.editing is set, switch it to readonly and keep it selected, then clear state.editing."),
        ("click","event,cell","Handle clicking cell. For shift click select api.rectangle(state.anchor,cell). If a previously selected cell is clicked again, begin editing via api.beginEdit(cell). Otherwise end previous editing and call api.setSelection([cell],cell,cell). Double click should begin editing directly."),
    ]
    src = ["export default function install(env){const {table,state,api}=env;",
           "Object.assign(state,{selected:new Set(),anchor:null,focus:null,editing:null});"]
    for name,args,desc in specs:
        code = short(tag,ledger,folder/name,name,args,"In scope: table is the real table, state and api are its shared objects. "+desc)
        src.append(f"api.{name}=function({args}){{\n{code}\n}};")
    src.append("for(const kind of ['click','dblclick']) table.addEventListener(kind,event=>{const cell=event.target.closest('td,th'); if(cell)api.click(event,cell);});\n}")
    return "\n".join(src)


def core_recovery(tag, public, lib, ledger, root, history):
    prior = SECOND/"libraries"/tag/"core"
    schema = None
    for f in sorted((prior/"menu-schema").glob("*/transmission-*/settled.json")):
        raw = f.with_name("response.json")
        assert sha(raw) == read(f)["response_sha256"]
        try:
            schema = routing.schema(read(raw)["choices"][0]["message"].get("content") or "")
            break
        except (ValueError,KeyError,TypeError):
            continue
    if schema is None:
        reqs = [public["requirements"][n-1] for n in routing.MENU_IDS]
        prompt = core.messages('Return JSON {"items":[{"scope":"td","label":"caption","className":"menu-item-..."}]} for the menu of this spreadsheet. Use th for header. Include the requested exact CSS class for every command.',reqs)
        schema = base.table.ask(ledger,tag,40,root/"schema",prompt,"build",routing.schema,2000)
    args = "table,cell,state,api,event"
    insert = "menu-item-insert-row-above"
    order = sorted(schema,key=lambda e:e["className"]!=insert)
    bodies = {}
    for e in order:
        name = e["className"]
        old = saved_body(prior/"items"/name,args)
        # The rejected installer may have been syntactically legal but never inserted a row.
        if name != insert and old is not None:
            bodies[name] = old
            continue
        desc = f"Perform only '{e['label']}' on the supplied actual HTML table. cell is the right-clicked {e['scope']}. Directly mutate the live DOM in a few statements."
        if name == insert:
            desc += " Insert a fresh body row immediately above cell.parentElement in that row's own tbody, with one td for each existing column."
        if "select" in name:
            desc += " Use api.setSelection(arrayOfCells, firstCell, lastCell)."
        try:
            bodies[name] = short(tag,ledger,root/"items"/name,"operate",args,desc)
        except ValueError as exc:
            history.append(dict(step=name,retained=False,error=str(exc)))
            if name == insert:
                raise
    shell = routing.menu_source(schema,{})
    parts = {k:v for k,v in lib["parts"].items() if k=="table"}
    parts["menu"] = routing.menu_source(schema,bodies)
    if "table" not in parts:
        parts = {"table":select_module(tag,ledger,root/"selection"),"menu":parts["menu"]}
    checked = base.observe(public,parts,root/"assembled")
    history.append(dict(step="core",public=checked))
    if not base.admitted(checked):
        if not checked["checks"]["click"] or checked["errors"]:
            parts["table"] = select_module(tag,ledger,root/"selection-repair")
        if not checked["checks"]["insert"]:
            bodies[insert] = short(tag,ledger,root/"retry-insert","insertAbove",args,
                dict(request="Insert a new row immediately before cell.parentElement in its own parent tbody. Copy the current number of td cells. Use only DOM; actual supplied names exactly table and cell.",
                     previous=bodies[insert], public=checked))
            parts["menu"] = routing.menu_source(schema,bodies)
        checked = base.observe(public,parts,root/"repaired")
        history.append(dict(step="core-repair",public=checked))
    return parts,checked,shell


def compose_keys(bodies):
    funcs = []
    for name,body in bodies.items():
        keys,_ = routing.KEYS[name]
        # Keep the model's body intact. Both e and event refer to the same live input.
        fn = f"function(e,table,state,api,selected,focus,anchor){{return function(event){{\n{body}\n}}(e);}}"
        funcs.append("["+json.dumps(keys.split())+","+fn+"]")
    result = (routing.HERE/"keys.js").read_text().replace("/*HANDLERS*/","["+",".join(funcs)+"]")
    return base.table.source(result)


def keyboard(tag, public, parts, checked, ledger, folder, history):
    existing = SECOND/"libraries"/tag/"keys"
    active = {}
    goals = {"move":{"right","tab","reverse"},"select":{"clear"},"edit":{"edit"}}
    def trial(bodies, location):
        proposal = {**parts,"key":compose_keys(bodies)}
        proposal = {k:proposal[k] for k in base.MODULES if k in proposal}
        obs = base.observe(public,proposal,location)
        return proposal,obs
    for turn in (1,2):
        old = {n:saved_body(existing/str(turn)/n,ARGUMENTS) for n in routing.KEYS}
        if not all(old.values()):
            continue
        proposal,obs = trial(old, folder/f"alias-{turn}")
        keep = not obs["errors"] and base.passed(checked)<base.passed(obs)
        history.append(dict(step="bind-e-and-event",revision=turn,retained=keep,public=obs))
        if keep:
            parts,checked,active = proposal,obs,old
            break
    if routing.NEEDED <= base.passed(checked):
        return parts,checked
    bodies = dict(active)
    for name,(keys,ids) in routing.KEYS.items():
        if name in active and goals[name]<=base.passed(checked):
            continue
        brief = [public["requirements"][n-1]["description"] for n in ids]
        request = dict(receives="The live event is event (alias e), current actual cell focus or null, anchor or null, selected ARRAY, table.rows and each row.cells. Use api.setSelection(cells,anchor,focus), api.rectangle(a,b), api.beginEdit(cell), api.endEdit(). No other helpers. Never attach a listener or reset state.",
                       keys=keys,requirements=brief)
        try:
            bodies[name] = short(tag,ledger,folder/"compact"/name,"handle",ARGUMENTS,request)
        except ValueError as exc:
            history.append(dict(step="compact-"+name,retained=False,error=str(exc)))
            continue
        proposed,obs = trial(bodies,folder/"compact"/name/"composed")
        keep = not obs["errors"] and base.passed(checked)<base.passed(obs)
        history.append(dict(step="compact-"+name,retained=keep,public=obs))
        if keep:
            parts,checked,active = proposed,obs,dict(bodies)
        elif active:
            bodies = dict(active)
    return parts,checked


def prepare(tag, public, ledger):
    dst = OUT/"libraries"/tag/"library.json"
    if dst.exists():
        return read(dst)
    old = read(SECOND/"libraries"/tag/"library.json")
    parts, shell, history = dict(old["parts"]),old.get("shell"),[]
    status = old["status"]
    valid_before = status == "valid"
    changed = False
    try:
        if status == "build_failed":
            parts,check,shell = core_recovery(tag,public,old,ledger,dst.parent/"core",history)
            if base.admitted(check):
                status,changed = "valid",True
        elif valid_before:
            check = base.observe(public,parts,dst.parent/"baseline")
            assert base.admitted(check)
        if status == "valid" and not routing.NEEDED<=base.passed(check):
            prior = dict(parts)
            parts,check = keyboard(tag,public,parts,check,ledger,dst.parent/"keys",history)
            changed |= parts != prior
        if status == "valid" and not valid_before:
            for name in list(base.MODULES)[3:]:
                loc = dst.parent/"extensions"/name
                try:
                    candidate = parts | {name:base.author(tag,name,public,ledger,loc/"answer",45)}
                    obs = base.observe(public,candidate,loc)
                    keep = not obs["errors"] and base.passed(check)<=base.passed(obs)
                    history.append(dict(step=name,retained=keep,public=obs))
                    if keep:
                        parts,check = candidate,obs
                except ValueError as exc:
                    history.append(dict(step=name,retained=False,error=str(exc)))
    except (*base.MISSING,ValueError,TypeError,KeyError) as exc:
        history.append(dict(step="not adopted",error=str(exc)))
        if not changed:
            parts = dict(old["parts"])
            if not valid_before and isinstance(exc,base.MISSING):
                status = "missing"
    if changed and status=="valid":
        with_profiles = []
        names = list(parts)
        for n in range(2,len(names)+1):
            obs = base.observe(public,{k:parts[k] for k in names[:n]},OUT/"profiles"/tag/str(n))
            with_profiles.append(dict(count=n,modules=names[:n],checks=sorted(base.passed(obs))))
    else:
        with_profiles = old["profiles"] if valid_before else []
    lib = dict(status=status,changed=changed,parts=parts,shell=shell,profiles=with_profiles,
               history=history,parent_status=old["status"],parent_library=sha(SECOND/"libraries"/tag/"library.json"))
    core.save(dst,lib)
    print("Command delivery",tag,status,"changed",changed,flush=True)
    return lib


def generate(reg):
    pub = read(FIRST/"public.json")
    ledger = Ledger(OUT/"budget.sqlite3",CAP,CAP)
    jobs = list(product(base.TAGS,base.TARGETS))
    with patch.multiple(base.API.calc.base,OUT=OUT,END=base.END,template=base.API.settings),ThreadPoolExecutor(max_workers=7) as pool:
        libs = dict(zip(base.TAGS,pool.map(lambda t:prepare(t,pub,ledger),base.TAGS),strict=True))
        def choose(j):
            t,n = j
            lib = libs[t]
            if lib["status"]!="valid":
                return dict(status=lib["status"])
            if not lib["changed"]:
                prior = read(SECOND/"libraries"/t/"library.json")
                source = SECOND if prior["changed"] else FIRST
                return read(source/"plans"/t/str(n)/"choice.json")
            return base.plan(t,n,pub,lib,ledger)
        with patch.object(base,"OUT",OUT):
            choices = dict(zip(jobs,pool.map(choose,jobs),strict=True))
    rows = []
    empty = base.page(pub,{},0,OUT/"empty")
    for (t,n),choice in choices.items():
        lib = libs[t]
        groups = [("self",choice["status"],choice.get("count"),lib["parts"]),
                  ("fixed-self",lib["status"],len(lib["parts"]),lib["parts"]),("binding-only","valid",0,{})]
        if lib["shell"]:
            groups.append(("menu-shell","valid",1,{"menu":lib["shell"]}))
        for arm,state,count,parts in groups:
            candidate = dict(status=state)
            if state=="valid":
                candidate = base.page(pub,parts,count,OUT/"pages"/t/(arm if arm=="menu-shell" else str(count))) if count else empty
            rows.append(dict(project="table",tag=t,task=n,arm=arm,count=count,**candidate))
    core.save(OUT/"seal.json",dict(rows=rows,empty=read(FIRST/"seal.json")["empty"],
              registration=sha(OUT/"registration.json"),parent_seal=sha(SECOND/"seal.json"),
              libraries={t:{k:v for k,v in lib.items() if k not in ("parts","shell")} for t,lib in libs.items()}))


if __name__=="__main__":
    with browser.lock(OUT/"study.lock"):
        reg = register()
        while not (SECOND/"seal.json").exists():
            if datetime.now(base.timezone.utc)>=base.END:
                raise TimeoutError("Parent not sealed by deadline")
            time.sleep(3)
        if not (OUT/"seal.json").exists():
            generate(reg)
        if not (HERE/"result.json").exists():
            with patch.multiple(base,OUT=OUT,HERE=HERE):
                base.score(reg)
