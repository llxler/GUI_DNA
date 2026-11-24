"""Score the frozen TodoMVC controller variants and verify their same-target comparisons."""

import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.public_library_transfer.other_benchmarks import evaluate
from studies.public_library_transfer.self_refinement.coherent.linker.executable_options.report import public_candidate
from studies.todomvc_dna import domain
from studies.study_io import read, sha

from . import run


def verification(report, target):
    selected = set(domain.hidden_subset(target["features"]))
    executions = {}
    def walk(suite, parents):
        for spec in suite.get("specs", []):
            name = (parents[-1] if parents else "", spec["title"])
            if name not in selected:
                continue
            runs = [r for test in spec["tests"] for r in test.get("results", [])]
            executions[name] = runs[-1]["status"] if runs else "skipped"
        for nested in suite.get("suites", []):
            walk(nested, parents + [nested["title"]])
    for suite in report["suites"]:
        walk(suite, [])
    if any(s in ("failed","timedOut") for s in executions.values()):
        return False, len(selected)
    if set(executions) == selected and all(s == "passed" for s in executions.values()):
        return True, len(selected)
    raise ValueError("Official report has neither a recorded failure nor all required passes")


def one(row, target, server, scoring):
    out = {**row, "passed": None if row["status"] == "missing" else False}
    if row["status"] != "valid":
        return out
    file = run.OUT / row["group"] / row["arm"] / row["task"] / "files.json"
    assert sha(file)==row["files_sha256"]
    where = run.OUT / "scores" / row["task"] / row["files_sha256"]
    if scoring:
        with browser.lock(where/".lock"), browser.browser_slot():
            evaluate.score(("todomvc",target,read(file),where,server))
    result=read(where/"verdict.json")
    raw=where/"playwright.json"
    assert sha(raw)==result["report_sha256"]
    assert verification(read(raw),target)==(result["passed"],result["official_tests"])
    out.update({k:result[k] for k in ("passed","official_tests","report_sha256")})
    return out


def agreement(rows, group, other):
    by_id={(r["group"],r["arm"],r["task"]):r["passed"] for r in rows}
    ref_group="direct" if other=="direct" else group
    both=[(t,by_id[group,"self",t],by_id[ref_group,other,t]) for t in run.original.TASKS]
    known=[v for v in both if None not in v[1:]]
    return {"tasks":[t for t,_,_ in known],"self_passed":sum(a for _,a,_ in known),
            "comparator_passed":sum(b for _,_,b in known),
            "self_only":[t for t,a,b in known if a and not b],"comparator_only":[t for t,a,b in known if b and not a]}


def summary(rows):
    return {g:{a:{"passed":[r["task"] for r in rows if r["group"]==g and r["arm"]==a and r["passed"] is True],
                  "missing":[r["task"] for r in rows if r["group"]==g and r["arm"]==a and r["passed"] is None]}
               for a in (("direct",) if g=="direct" else ("self","fixed"))}
            for g in ("direct",*run.GROUPS)}


def spending():
    counts=ledger_read.calls(run.OUT/"budget.sqlite3")
    receipts={}
    by_phase=defaultdict(lambda:{"calls":0,"settled_microusd":0,"exposure_microusd":0})
    registered={r["id"]:r for r in counts}
    for f in sorted(run.OUT.rglob("request.json")):
        req=read(f); row=registered[req["call_id"]]
        group,phase,step=row["purpose"].split("/",2)
        scope=group+"/"+("controller" if step.startswith("source") else "options" if phase=="build" else "targets")
        spent=by_phase[scope]
        assert req["call_id"] not in receipts and row["model"]==req["body"]["model"]==run.transport.MODEL
        assert req["body"]["seed"]==run.original.SEEDS[group] and req["body"]["reasoning"]=={"enabled":False}
        qty=row["actual"] if row["actual"] is not None else row["reserved"]
        spent["calls"]+=1
        spent["settled_microusd"]+=row["actual"] or 0
        spent["exposure_microusd"]+=qty
        response=f.parent/"response.json"
        if (f.parent/"settled.json").exists():
            ack=read(f.parent/"settled.json")
            assert ack["ticket"]==row["id"] and ack["response_sha256"]==sha(response)
        receipts[row["id"]]={"purpose":row["purpose"],"request_sha256":sha(f),"response_sha256":sha(response) if response.exists() else None}
    assert set(registered)==set(receipts)
    return {"budget":ledger_read.totals(run.OUT/"budget.sqlite3"),"cost_by_stage":dict(by_phase),"requests":list(receipts.values())}


def assemble(scoring):
    run.verify()
    seal=read(run.OUT/"seal.json")
    assert seal["registered_sha256"]==sha(run.OUT/"registered.json")
    targets=read(run.OUT/"targets.json")
    server=evaluate.todo.Server(run.OUT) if scoring else None
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            rows=list(pool.map(lambda r:one(r,targets[r["task"]],server,scoring),seal["rows"]))
    finally:
        if server:
            server.close()
    baseline=[r for r in read(run.original.RESULT)["rows"] if r["group"]=="direct"]
    for r in baseline:
        if r["status"]=="valid":
            raw=run.original.OUT/"scores"/r["task"]/r["files_sha256"]/"playwright.json"
            f=run.original.OUT/"direct/direct"/r["task"]/"files.json"
            assert sha(f)==r["files_sha256"] and sha(raw)==r["report_sha256"]
            assert verification(read(raw),targets[r["task"]])==(r["passed"],r["official_tests"])
    rows=baseline+rows
    replicas={}
    for group in run.GROUPS:
        folder=run.OUT/group/"build"
        state=seal["builds"][group]
        assert state==read(folder/"status.json") and sha(folder/"package.json")==state["package_sha256"]
        pkg=read(folder/"package.json")
        if pkg["base_files_sha256"]:
            base=read(folder/"original.json")["candidate.js"]
            assert sha(folder/"original.json")==pkg["base_files_sha256"]
            for r in rows:
                if r["group"]!=group or r["status"]!="valid":
                    continue
                selected=[k for k,v in r.get("plan",{}).items() if v=="alternative"]
                file=run.OUT/group/r["arm"]/r["task"]/"files.json"
                assert read(file)=={"candidate.js":run.patched(base,pkg["options"],selected)}
        replicas[group]={"base_status":state["base_status"],"selection_status":state["selection_status"],"reason":state["reason"],
            "package_sha256":state["package_sha256"],"base_files_sha256":pkg["base_files_sha256"],
            "public_admissions":state["public_admissions"],"certified_options":[o["id"] for o in pkg["options"]],
            "candidate_witnesses":[public_candidate(r) for r in state["candidate_witnesses"]],
            "paired_fixed":agreement(rows,group,"fixed"),"paired_direct":agreement(rows,group,"direct")}
    return {"model":run.transport.MODEL,"registered_utc":read(run.OUT/"registered.json")["utc"],"end_utc":run.transport.END.isoformat(),
            "registration_sha256":sha(run.OUT/"registered.json"),"seal_sha256":sha(run.OUT/"seal.json"),
            "protocol_sha256":sha(run.HERE/"PROTOCOL.md"), "reused_direct_results_sha256":sha(run.original.RESULT),
            "reused_direct_cost":read(run.original.RESULT)["cost_by_stage"]["direct/targets"],
            "tasks":list(run.original.TASKS),"seeds":run.original.SEEDS,"replicas":replicas,"summary":summary(rows),"rows":rows,**spending()}


def check(data):
    assert data["reused_direct_results_sha256"]==sha(run.original.RESULT)
    assert [r for r in data["rows"] if r["group"]=="direct"]==[r for r in read(run.original.RESULT)["rows"] if r["group"]=="direct"]
    assert data["summary"]==summary(data["rows"]) and data["budget"]["exposure_usd"]<=data["budget"]["cap_usd"]==run.CAP
    assert len(data["requests"])==data["budget"]["calls"]
    assert len(data["rows"])==len({(r["task"],r["group"],r["arm"]) for r in data["rows"]})==40
    for group, replica in data["replicas"].items():
        for arm in ("fixed","direct"):
            assert replica["paired_"+arm]==agreement(data["rows"],group,arm)
        confirmed=[r for r in replica["candidate_witnesses"] if r.get("accepted")]
        assert [r["option"]["id"] for r in confirmed]==replica["certified_options"]
        for entry in confirmed:
            a,b=entry["observations"]["original"],entry["observations"]["alternative"]
            assert len(a)==len(b)==2 and a[0]==a[1] and b[0]==b[1] and a[0]!=b[0]
        for r in data["rows"]:
            if r["group"]==group and r["arm"]=="fixed" and r["status"]=="valid":
                assert r["files_sha256"]==replica["base_files_sha256"]
        print(group,replica["certified_options"],replica["paired_fixed"],replica["paired_direct"])


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("action",choices=("score","check-local","check"))
    action=cli.parse_args().action
    data=read(run.RESULT) if action=="check" else assemble(action=="score")
    check(data)
    if action=="score":
        core.save(run.RESULT,data)
    elif action=="check-local":
        assert data==read(run.RESULT)


if __name__=="__main__":
    main()
