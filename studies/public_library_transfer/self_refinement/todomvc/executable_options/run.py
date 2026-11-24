"""Build plain TodoMVC controllers then certify candidate-owned finite source modifications."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from gui_dna.budget import BudgetStop, Ledger
from scripts.check_openrouter_credits import check_credits
from studies.public_library_transfer import browser, core
from studies.public_library_transfer.other_benchmarks import evaluate
from studies.public_library_transfer.self_refinement.coherent.linker.executable_options import options
from studies.public_library_transfer.self_refinement.native import transport
from studies.public_library_transfer.self_refinement.todomvc import run as original
from studies.study_io import ROOT, digest, read, sha

from . import host

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/todomvc-executable-options-20261124"
RESULT = ROOT / "studies/results/self-todomvc-executable-options-20261124.json"
GROUPS = ("build-a", "build-b")
CAP = .80
INVALID = (ValueError, KeyError, TypeError, IndexError, AttributeError)
MISSING = (BudgetStop, transport.Unavailable)
SAVE = core.save


def verify():
    for name, value in read(OUT / "registered.json")["files"].items():
        assert sha(ROOT / name) == value, name


def register():
    if (OUT / "registered.json").exists():
        return verify()
    balance = check_credits(CAP)
    if not balance["sufficient"]:
        raise BudgetStop("Insufficient credit")
    paths = [HERE / "PROTOCOL.md", Path(__file__), Path(host.__file__), Path(options.__file__), Path(transport.__file__),
             Path(original.__file__), Path(evaluate.__file__), evaluate.todo.SHELL, original.RESULT,
             original.OUT / "registered.json", original.OUT / "seal.json", ROOT / "src/gui_dna/budget.py"]
    for name in ("public-build.json", "targets.json"):
        dest = OUT / name
        SAVE(dest, read(original.OUT / name))
        paths.extend([dest, original.OUT / name])
    SAVE(OUT / "registered.json", {"utc":core.now(), "end":transport.END.isoformat(), "model":transport.MODEL,
         "seeds":original.SEEDS, "tasks":original.TASKS, "budget_usd":CAP, "balance":balance,
         "files":{str(p.relative_to(ROOT)):sha(p) for p in paths}})


def ask(dest, ledger, group, step, msgs, tokens, schema=None):
    return transport.request(dest, ledger, msgs, f"{group}/{step}", tokens, seed=original.SEEDS[group], schema=schema)


def patched(text, variants, selected):
    return options.replace({"candidate.js":text}, variants, set(selected))["candidate.js"]


def controller(folder, group, ledger, public, server):
    messages = core.messages(original.DIRECT, public)
    attempts = []
    for step in ("source","source-repair"):
        raw = ask(folder/step,ledger,group,"build/"+step,messages,8192)
        try:
            text = original.source(raw)
            host.check(text,folder/(step+"-host"),server)
            attempts.append({"attempt":step,"passed":True})
            return text,attempts
        except INVALID as exc:
            attempts.append({"attempt":step,"passed":False,"reason":str(exc)[:800]})
            messages = core.messages(original.DIRECT, public)+[{"role":"assistant","content":raw},
                {"role":"user","content":"Public TodoMVC shell feedback: "+str(exc)[:800]+". Correct the entire plain JavaScript controller."}]
    return None,attempts


def confirm(c, accepted, text, dest, server):
    opt=host.anchor(c,text,accepted)
    alternate=patched(text,[opt],[opt["id"]])
    host.check(alternate,dest/"alternative-gate",server)
    a=host.check(text,dest/"original-probe",server,opt["probe"])
    b=host.check(alternate,dest/"alternative-probe",server,opt["probe"])
    SAVE(dest/"witness.json",{"original":a,"alternative":b})
    if digest(a[0])!=digest(a[1]) or digest(b[0])!=digest(b[1]) or digest(a[0])==digest(b[0]):
        raise ValueError("No stable distinct view: "+str([a,b])[:450])
    for mask in range(1,2**len(accepted)):
        active=[v["id"] for i,v in enumerate(accepted) if mask & (1<<i)]+[opt["id"]]
        host.check(patched(text,accepted+[opt],active), dest/f"combined-{mask}",server)
    return opt


def prepare(group, ledger, public, server):
    folder=OUT/group/"build"
    if (folder/"status.json").exists():
        return read(folder/"status.json")
    attempts,proposals,accepted=[],[],[]
    base_status, option_status, reason="missing","missing",None
    try:
        text,attempts=controller(folder,group,ledger,public,server)
        base_status="valid" if text is not None else "invalid"
        if text is None:
            raise ValueError("Plain controller failed both public admissions")
        SAVE(folder/"original.json",{"candidate.js":text})
        quota,feedback=3,[]
        for step in ("options","options-repair"):
            payload={"public":public,"candidate.js":text,"maximum_options":quota,
                     "accepted_ids":[v["id"] for v in accepted],"previous_public_feedback":feedback}
            raw=ask(folder/step,ledger,group,"build/"+step,core.messages(host.DESIGN,payload),5100,host.SCHEMA)
            try:
                entries=core.parse(raw)["options"]
                if not isinstance(entries,list) or not 1<=len(entries)<=quota:
                    raise ValueError("Wrong number of option proposals")
            except INVALID as exc:
                feedback=[{"error":str(exc)}]
                proposals.append({"round":step,"error":str(exc)})
                continue
            feedback=[]
            for index,c in enumerate(entries,1):
                dest=folder/f"{step}-{index}"
                row={"round":step,"candidate":c}
                try:
                    accepted.append(confirm(c,accepted,text,dest,server))
                    row["accepted"]=True
                except INVALID as exc:
                    row.update(accepted=False,reason=str(exc)[:800])
                    feedback.append({"rejected":c,"reason":row["reason"]})
                if (dest/"witness.json").exists():
                    row["observations"]=read(dest/"witness.json")
                proposals.append(row)
            quota=min(3-len(accepted),len(feedback))
            if not quota:
                break
        option_status="valid" if accepted else "invalid"
    except MISSING as exc:
        reason=str(exc)
        option_status="valid" if accepted else "missing"
    except INVALID as exc:
        reason=str(exc)
        option_status="invalid"
    package={"base_files_sha256":sha(folder/"original.json") if (folder/"original.json").exists() else None,"options":accepted}
    SAVE(folder/"package.json",package)
    row={"base_status":base_status,"selection_status":option_status,"reason":reason,
         "package_sha256":sha(folder/"package.json"),"public_admissions":attempts,"candidate_witnesses":proposals}
    SAVE(folder/"status.json",row)
    print(group,base_status,option_status,len(accepted),flush=True)
    return row


def candidate(group,arm,task,ledger,targets,built):
    folder=OUT/group/arm/task
    path=folder/"candidate.json"
    if path.exists():
        return read(path)
    status=built["base_status"] if arm=="fixed" else built["selection_status"]
    r={"group":group,"arm":arm,"task":task,"status":status}
    if status=="valid":
        base=OUT/group/"build"
        pkg=read(base/"package.json")
        assert sha(base/"package.json")==built["package_sha256"] and sha(base/"original.json")==pkg["base_files_sha256"]
        text=read(base/"original.json")["candidate.js"]
        try:
            if arm=="self":
                iface=[{"id":v["id"],"original":v["original_behavior"],"alternative":v["alternative_behavior"]} for v in pkg["options"]]
                schema=core.obj({v["id"]:{"type":"string","enum":["original","alternative"]} for v in iface})
                payload={"current_public_target":targets[task]["public"],"choices":iface,
                         "original_page":{v["id"]:"original" for v in iface}}
                raw=ask(folder/"call",ledger,group,"target/"+task,core.messages(options.PLAN,payload),1024,schema)
                plan=core.parse(raw)
                if not isinstance(plan,dict) or set(plan)!=set(schema["properties"]) or any(v not in ("original","alternative") for v in plan.values()):
                    raise ValueError("Invalid configuration")
                text=patched(text,pkg["options"],[k for k,v in plan.items() if v=="alternative"])
                r["plan"]=plan
            SAVE(folder/"files.json",{"candidate.js":text})
            r["files_sha256"]=sha(folder/"files.json")
            if arm=="fixed":
                assert r["files_sha256"]==pkg["base_files_sha256"]
        except MISSING as exc:
            r.update(status="missing",reason=str(exc))
        except INVALID as exc:
            r.update(status="invalid",reason=str(exc))
    else:
        r["reason"]=built.get("reason") or "No public-admitted controller or certified control"
    SAVE(path,r)
    return r


def generate():
    verify()
    if (OUT/"seal.json").exists():
        return
    ledger=Ledger(OUT/"budget.sqlite3",CAP,CAP)
    server=evaluate.todo.Server(OUT)
    public,targets=read(OUT/"public-build.json"),read(OUT/"targets.json")
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            builds=dict(zip(GROUPS,pool.map(lambda g:prepare(g,ledger,public,server),GROUPS)))
    finally:
        server.close()
    jobs=[(g,a,t) for t in original.TASKS for g in GROUPS for a in ("fixed","self")]
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows=list(pool.map(lambda j:candidate(*j,ledger,targets,builds[j[0]]),jobs))
    SAVE(OUT/"seal.json",{"utc":core.now(),"registered_sha256":sha(OUT/"registered.json"),"builds":builds,"rows":rows})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("action",choices=("register","generate"))
    action=p.parse_args().action
    if action=="register":
        register()
    else:
        with browser.lock(OUT/"generation.lock"):
            generate()


if __name__=="__main__":
    main()
