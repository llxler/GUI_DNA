"""Generate and publicly verify one component per feature before sealing Duo plans."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import subprocess
import threading

from gui_dna.budget import BudgetStop, Ledger
from studies.public_library_transfer import core
from studies.public_library_transfer.other_benchmarks.duo_admission import single
from studies.public_library_transfer.other_benchmarks.duo_original_results import bundle
from studies.public_library_transfer.self_refinement.duo_composition import declaration, run as original
from studies.study_io import ROOT, now, read, sha
from . import transport as api

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/duo-independent-components-20261124"
BALANCE = ROOT / "artifacts/duo-components-balance-20261124.json"
SEEDS = {"build-a": 202611241, "build-b": 202611242, "direct": 202611241}
SINGLE_SLOTS = threading.BoundedSemaphore(3)
SYS = ("Return one complete raw JavaScript JSX module with a default-exported React component. "
       "Only imports from react and react-router-dom. Implement the actual user behavior with real React state, "
       "semantic labels and controls, Web fetch against the documented endpoints, success and error branches. "
       "Do not import mocks or tests. No JSON wrapper, explanations, test branches, or tooling.")


def track():
    paths = [HERE/"PROTOCOL.md", HERE/"run.py", HERE/"transport.py", BALANCE, original.EXTRA/"build-inputs.json",
             original.EXTRA/"targets.json", original.OVERLAP, original.HERE/"direct.cjs", Path(declaration.__file__),
             Path(single.__code__.co_filename), Path(bundle.__code__.co_filename), Path(original.evaluate.__file__),
             ROOT/"src/gui_dna/budget.py"]
    return {str(p.relative_to(ROOT)): sha(p) for p in paths}


def register():
    inputs = read(original.EXTRA/"build-inputs.json")
    suites = {g: inputs[g] for g in original.GROUPS}
    tasks = original.inputs()
    assert sum(map(len, suites.values())) == 15 and len(tasks) == 10
    for t, d in tasks.items():
        assert len(t.split("_")) == 2 and set(t.split("_")) <= set(suites[d["group"]])
        assert sha(ROOT/d["test"]) == d["test_sha256"]
    balance = read(BALANCE)
    assert balance["sufficient"] and balance["required_usd"] >= sum(m[1] for m in api.MODELS.values())
    metadata = {"source_sha256": track(), "end": api.END.isoformat(), "seeds": SEEDS,
                "models": {k:list(v) for k,v in api.MODELS.items()}, "features": {g: sorted(x) for g,x in suites.items()},
                "targets": {t: {"group": d["group"], "test_sha256": d["test_sha256"]} for t,d in tasks.items()}}
    path = OUT/"registration.json"
    if not path.exists():
        core.save(path, {"utc": now(), "protocol": metadata})
    assert read(path)["protocol"] == metadata
    return suites, tasks


def ask(tag, ledger, folder, msg, purpose, seed, limit):
    try:
        raw = api.request(tag, ledger, OUT/tag, folder, msg, purpose, seed, limit)
        return raw, {"status":"returned", "response_sha256":sha(folder/"response.json")}
    except (BudgetStop, api.Unavailable) as error:
        return "", {"status":"missing", "reason":str(error)}


def extract(text):
    if not text:
        return None
    versions = [text, *re.findall(r"```(?:jsx|javascript|js)?\s*\n([\s\S]*?)\n```", text, re.I)]
    normalized = [v for x in versions if (v := declaration.normalize(x))]
    for value in [text, *normalized]:
        job = subprocess.run(["node", str(original.HERE/"direct.cjs")], cwd=ROOT,
            input=json.dumps({"original": None, "raw": value}), text=True, check=True, capture_output=True, timeout=10)
        result = json.loads(job.stdout)
        if result:
            return result["source"]
    return None


def grade_singles(folder, group, names, source):
    with SINGLE_SLOTS:
        return {name: single((folder/name, group, name, source))[1] for name in names}


def produce(work):
    tag, replica, group, name, prompt, singles, ledger = work
    path = OUT/tag/replica/group/name
    status = path/"status.json"
    if status.exists():
        return read(status)
    seed = SEEDS[replica]
    purpose = "direct" if replica == "direct" else "prepare"
    msg = [{"role":"system","content":SYS},{"role":"user","content":prompt}]
    stages = {}
    choice = {"status": "invalid"}
    for attempt, label in enumerate(("first","repair")):
        folder = path/label
        raw, delivery = ask(tag, ledger, folder/"call", msg, purpose+"/"+replica+"/"+label, seed+attempt, 3200)
        stage = stages[label] = dict(delivery)
        if delivery["status"] == "missing":
            if attempt == 0:
                choice = {"status":"missing"}
            break
        code = extract(raw)
        if code:
            core.save(folder/"source.json", {"source":code})
            public = grade_singles(folder/"singles", group, singles, code)
            stage.update(source_sha256=sha(folder/"source.json"), single_results=public)
            choice = {"status":"valid", "use":label, "source_sha256":stage["source_sha256"]}
            if all(row["passed"] for row in public.values()):
                break
            feedback = {n: row["feedback"] for n,row in public.items() if not row["passed"]}
        else:
            feedback = "No parseable module was delivered. Use export default and allowed imports in one raw JSX module."
        if attempt == 0:
            msg = msg + [{"role":"assistant","content":raw[:24000]},
                         {"role":"user","content":"Only public single-feature validation feedback: "
                          +json.dumps(feedback,ensure_ascii=False)[:5500]+". Return your full corrected React module."}]
    record = {"model":api.MODELS[tag][0],"group":group,"target":name,"replica":replica,"attempts":stages,**choice}
    core.save(status, record)
    return record


def parse_plan(raw, names):
    content = raw.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", content, re.S)
    if match:
        content = match[1]
    try:
        plan = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(plan,list) or len(plan)!=2 or not all(isinstance(v,str) for v in plan):
        return None
    if len(set(plan)) != 2 or not set(plan) <= set(names):
        return None
    return {"first":plan[0],"second":plan[1]}


def plan_task(job):
    tag, replica, task, info, briefs, ledger = job
    group = info["group"]
    path = OUT/tag/replica/"plans"/task
    names = sorted(briefs[group])
    public = info["public"]
    modules, states = {}, {}
    for name in names:
        b = OUT/tag/replica/group/name
        source = read(b/"status.json")
        states[name] = source["status"]
        if source["status"] == "valid":
            file = b/source["use"]/"source.json"
            assert sha(file) == source["source_sha256"]
            modules[name] = read(file)["source"]
    note = ("Choose two registered component identifiers that jointly satisfy this public React module. "
            "Return only a JSON array of the two exact identifiers in the desired rendering order.")
    msg = [{"role":"system","content":note},{"role":"user","content":json.dumps(
        {"module":public["module"],"public_requirements":public["jest"],"registered":states},ensure_ascii=False)}]
    raw, receipt = ask(tag, ledger, path/"call", msg, "plan/"+replica, SEEDS[replica], 700)
    chosen = parse_plan(raw, names) if receipt["status"]=="returned" else None
    n1,n2 = task.split("_")
    candidates = {"self":chosen, "by_name":{"first":n1,"second":n2},
                  "fixed":{"first":names[0],"second":names[1]}}
    record = {}
    for arm, setting in candidates.items():
        out = {"plan":setting}
        if setting is None:
            out["status"] = "missing" if receipt["status"]=="missing" else "invalid_plan"
        elif any(states[k]=="missing" for k in setting.values()):
            out["status"] = "missing"
        elif not all(k in modules for k in setting.values()):
            out["status"] = "unavailable_module"
        else:
            files = bundle(public["module"],{"components":[{"id":k,"source":v} for k,v in modules.items()]},setting)
            file = path/(arm+".json")
            core.save(file, files)
            out.update(status="valid", files_sha256=sha(file), file=str(file.relative_to(OUT)))
        record[arm] = out
    result = {"task":task, "model":api.MODELS[tag][0], "group":group, "replica":replica,
              "plan_delivery":receipt,"arms":record}
    core.save(path/"status.json", result)
    return result


def generate():
    suites, tasks = register()
    if (OUT/"seal.json").exists():
        return
    ledgers = {tag:Ledger(OUT/tag/"budget.sqlite3", m[1], m[1]) for tag,m in api.MODELS.items()}
    work = []
    for t, row in tasks.items():
        g = row["group"]
        for tag, ledger in ledgers.items():
            work.append((tag, "direct", g, t,
                         "Implement the complete target module from scratch. Its public contract follows.\n"
                         +row["public"]["jest"], t.split("_"), ledger))
    for group in original.GROUPS:
        for name, brief in sorted(suites[group].items()):
            for rep in ("build-a","build-b"):
                for tag, ledger in ledgers.items():
                    work.append((tag,rep,group,name,"Build the reusable standalone feature "+name+
                             ". It will later share a React tree with other features. Preserve provided props, "
                             "lazy operations and isolated state. The public feature contract follows.\n"+brief,[name],ledger))
    with ThreadPoolExecutor(max_workers=12) as pool:
        components = list(pool.map(produce, work))
    plan_jobs = [(tag,rep,t,d,suites,ledger) for t,d in tasks.items()
                 for tag,ledger in ledgers.items() for rep in ("build-a","build-b")]
    with ThreadPoolExecutor(max_workers=10) as pool:
        plans = list(pool.map(plan_task, plan_jobs))
    paths = [f for f in OUT.rglob("*.json") if not ({"staging","singles"} & set(f.relative_to(OUT).parts))]
    core.save(OUT/"seal.json",{"utc":now(),"registration_sha256":sha(OUT/"registration.json"),
              "files":{str(f.relative_to(OUT)):sha(f) for f in sorted(paths)},"components":components,"plans":plans})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase",choices=("register","generate"))
    {"register":register,"generate":generate}[parser.parse_args().phase]()
