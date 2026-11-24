"""Measure the effect of matching a model's class-name strings to the DOM token API."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess

from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, digest, now, read, sha
from .. import components as comp
from ..module_linking import run as links
from ..runtime_patch import run as stage, observe

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/qwen-svg-dom-tokens-20261124"
DELIVERY = ROOT / "artifacts/qwen-svg-source-delivery-20261124/seal.json"
RESULT = HERE / "result.json"
TASKS = range(1,21)


def register():
    inputs = (HERE / "PROTOCOL.md", HERE / "arguments.cjs", Path(__file__), Path(observe.__file__),
              stage.OUT / "seal.json", stage.OUT / "registration.json", links.PARSER)
    values = {str(p.relative_to(ROOT)): sha(p) for p in inputs}
    destination = OUT / "registration.json"
    if not destination.exists():
        assert not stage.RESULT.exists()
        core.save(destination, {"utc":now(),"sources":values,"remote_calls":0})
    assert read(destination)["sources"] == values


def witnessed(ob):
    return any("DOMTokenList" in text and "space" in text for text in ob["errors"])


def correct(row, enabled):
    if not enabled or row["status"] != "valid":
        return row, {}
    src = stage.source(row)
    js = {name:body for name,body in src.items() if name.endswith((".mjs",".js"))}
    result = json.loads(subprocess.check_output(["node", str(HERE/"arguments.cjs"), str(links.PARSER)],
                                                input=json.dumps(js), text=True))
    if not result:
        return row, {}
    folder = OUT / "pages" / digest(row["files"])
    with browser.lock(folder.parent / (folder.name + ".lock")):
        pages = stage.candidate(folder, src | {name:item["source"] for name,item in result.items()})
    assert {name for name,h in pages["files"].items() if h != row["files"][name]} == set(result)
    return {**row, **pages}, {name:item["calls"] for name,item in result.items()}


def freeze():
    register()
    dest = OUT / "seal.json"
    if dest.exists():
        assert read(dest)["delivery_sha256"] == sha(DELIVERY)
        return
    previous = read(stage.OUT / "seal.json")
    official = {(r["group"],r["arm"],r["task"]):r for r in previous["rows"]}
    direct = {r["task"]:r for r in read(DELIVERY)["rows"] if r["group"]=="direct" and r["arm"]=="final"}
    assert set(direct) == set(TASKS)
    public, unique, fixed = {}, {}, {}
    def witness(row):
        if row["status"] != "valid":
            return False
        key = digest(row["files"])
        with browser.lock(OUT/"public-locks"/(key+".lock")):
            if key not in public:
                public[key] = observe.observe(OUT,ROOT/row["page"],row["files"])
            return witnessed(public[key])
    for g in ("A","B"):
        fixed[g] = witness(official[g,"fixed",1])
    jobs = []
    for n in TASKS:
        for g, arm, row in (("direct","patch",official["direct","final",n]),("direct","delivery",direct[n]),
                            ("host","only",official["host","only",n])):
            jobs.append((g,arm,row,None))
        for g in ("A","B"):
            for arm in ("planned","fixed"):
                jobs.append((g,arm,official[g,arm,n],fixed[g]))
    def emitted(job):
        g,arm,row,flag = job
        enabled = witness(row) if flag is None else flag
        key = (digest(row["files"]),enabled) if row["status"]=="valid" else None
        if key:
            with browser.lock(OUT/"edit-locks"/(key[0]+str(enabled)+".lock")):
                if key not in unique:
                    edited, changes = correct(row,enabled)
                    unique[key] = (edited["page"], edited["files"], changes)
                page,files,changes = unique[key]
            return {**row,"group":g,"arm":arm,"page":page,"files":files,"token_edits":changes,"witness":enabled}
        return {**row,"group":g,"arm":arm,"token_edits":{},"witness":False}
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(emitted,jobs))
    facts = {}
    for g in ("A","B"):
        r = next(r for r in rows if (r["group"],r["arm"],r["task"])==(g,"fixed",1))
        if r["status"]=="valid":
            facts[g]=observe.observe(OUT,ROOT/r["page"],r["files"])
    core.save(dest, {"utc":now(),"registration_sha256":sha(OUT/"registration.json"),"delivery_sha256":sha(DELIVERY),
                     "public_before":public,"public_fixed_after":facts,"rows":rows})


def summarize(rows):
    idx={(r["group"],r["arm"],r["task"]):r["passed"] for r in rows}
    assert len(idx)==140
    result={}
    for g in ("A","B"):
        common = [n for n in TASKS if all(idx[h,k,n] is not None for h,k in
                   ((g,"planned"),(g,"fixed"),("direct","patch"),("direct","delivery"),("host","only")))]
        def passing(h,k):
            return {n for n in common if idx[h,k,n]}
        chosen, baseline, delivery = passing(g,"planned"), passing("direct","patch"), passing("direct","delivery")
        sets = {"planned":chosen,"fixed":passing(g,"fixed"),"direct_patch":baseline,"direct_delivery":delivery,
                "direct_oracle_union":baseline|delivery,"host":passing("host","only")}
        result[g]={"common":common,"passed":{k:sorted(v) for k,v in sets.items()},
                   "non_asset":{k:sorted(v-{1}) for k,v in sets.items()},
                   "only_plan_vs_delivery":sorted(chosen-delivery),"only_delivery_vs_plan":sorted(delivery-chosen)}
    return result


def score():
    seal=read(OUT/"seal.json")
    assert seal["registration_sha256"]==sha(OUT/"registration.json") and seal["delivery_sha256"]==sha(DELIVERY)
    browser.OUT=OUT
    verified=browser.verify_contract(comp.CHART)
    values=browser.evaluate(seal["rows"],OUT,{comp.CHART:verified},5)
    rows=[]
    for r in values:
        v={k:r.get(k) for k in ("group","arm","task","status","plan","report_sha256","token_edits","witness")}
        v["page_digest"]=digest(r["files"]) if r.get("files") else None
        v["passed"]=False if r["status"] in ("invalid","build_failed") else r["passed"]
        rows.append(v)
    core.save(RESULT,{"registered_utc":read(OUT/"registration.json")["utc"],"sealed_utc":seal["utc"],
                      "seal_sha256":sha(OUT/"seal.json"),"protocol_sha256":sha(HERE/"PROTOCOL.md"),"remote_calls":0,
                      "rows":rows,"paired":summarize(rows),"fixed_public":seal["public_fixed_after"]})
    check()


def check():
    data=read(RESULT)
    assert data["protocol_sha256"]==sha(HERE/"PROTOCOL.md") and data["paired"]==summarize(data["rows"])
    for r in data["rows"]:
        assert (type(r["passed"]) is bool and len(r["report_sha256"])==64) if r["status"]=="valid" else (
               r["passed"] is None if r["status"]=="missing" else r["passed"] is False)
    print({g:{k:len(v) for k,v in d["passed"].items()} for g,d in data["paired"].items()})


if __name__=="__main__":
    actions={"register":register,"freeze":freeze,"score":score,"check":check}
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("action",choices=actions)
    actions[cli.parse_args().action]()
