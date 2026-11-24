"""A separate Qwen registration using a concise view of the same public specifications."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, contextmanager
import json
from pathlib import Path
import subprocess
from unittest.mock import patch

from gui_dna.budget import Ledger
from studies import ledger_read
from studies.public_library_transfer import core
from studies.study_io import ROOT, now, read, sha
from .. import run as base

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/duo-compact-components-20261124"
FIRST = base.OUT
BALANCE = ROOT / "artifacts/duo-compact-balance-20261124.json"
SEEDS = {"build-a":202611243,"build-b":202611244,"direct":202611243}
QWEN = (base.api.MODELS["qwen9"][0], .55, *base.api.MODELS["qwen9"][2:])
SYSTEM = """Write the shortest complete functioning React JSX module that meets the supplied public behavior contract. Output just valid JavaScript JSX with one default-exported function, import React from 'react', and use React.useState or React.useEffect with that namespace. No TypeScript, styling, CSS objects, extra headings, generic dashboard, router wrapper, example content or commentary. The parent already supplies the router. Each case mounts the same real component with fresh state. Use exactly the visible names, placeholders, semantic controls, data-testid and prop values required by the given cases; a text query must have a unique match. Only add UI used by a case. Perform the specified fetch once at the shown action or mount, with the given URL and HTTP method; display the exact success and failure messages. Handle empty HTTP bodies without trying to parse JSON unless payload data is needed. Inputs and buttons must work normally. Do not import any test library, mock, or outside code. Do not implement per-case branches."""


@contextmanager
def stage():
    # The frozen primary workers use module-level paths. Bind them only inside this
    # independent process and restore those paths before returning to callers.
    with ExitStack() as stack:
        for obj,key,value in ((base,"OUT",OUT),(base,"SEEDS",SEEDS),(base,"SYS",SYSTEM),
                              (base.api,"MODELS",{"qwen9":QWEN})):
            stack.enter_context(patch.object(obj,key,value))
        yield


def compact(text):
    p=subprocess.run(["node",str(HERE/"contract.cjs")],cwd=ROOT,input=json.dumps(text),text=True,
                     capture_output=True,check=True,timeout=15)
    return json.loads(p.stdout)


def register():
    original_inputs = read(base.original.EXTRA/"build-inputs.json")
    suites = {g: original_inputs[g] for g in base.original.GROUPS}
    tasks = base.original.inputs()
    files = [HERE/"PROTOCOL.md",HERE/"contract.cjs",HERE/"run.py",BALANCE,FIRST/"seal.json",
             FIRST/"registration.json",base.HERE/"PROTOCOL.md",base.HERE/"run.py",base.HERE/"transport.py",
             base.original.EXTRA/"build-inputs.json",base.original.EXTRA/"targets.json",base.original.OVERLAP]
    sums = {t:ledger_read.totals(FIRST/t/"budget.sqlite3") for t in ("qwen9","oss")}
    assert read(BALANCE)["sufficient"] and sum(v["exposure_usd"] for v in sums.values())+QWEN[1] <= 1.95
    public = OUT/"public-contracts.json"
    if not public.exists():
        core.save(public, {"features":{g:{n:compact(src) for n,src in content.items()} for g,content in suites.items()},
                           "targets":{t:compact(d["public"]["jest"]) for t,d in tasks.items()}})
    files.append(public)
    spec = read(public)
    for g,features in suites.items():
        assert set(spec["features"][g])==set(features)
        assert all(len(v)==2 for v in spec["features"][g].values())
    assert set(spec["targets"])==set(tasks) and all(len(v)==4 for v in spec["targets"].values())
    metadata = {"source_sha256":{str(p.relative_to(ROOT)):sha(p) for p in files},
                "end":base.api.END.isoformat(),"seeds":SEEDS,"models":{"qwen9":list(QWEN)},
                "prior_cost":sums,"features":{g:sorted(b) for g,b in suites.items()},
                "targets":{t:{"group":d["group"],"test_sha256":d["test_sha256"]} for t,d in tasks.items()}}
    reg=OUT/"registration.json"
    if not reg.exists():
        core.save(reg,{"utc":now(),"protocol":metadata})
    assert metadata==read(reg)["protocol"]
    return suites,tasks


def generate():
    suites,tasks=register()
    if (OUT/"seal.json").exists():
        return
    spec=read(OUT/"public-contracts.json")
    ledger=Ledger(OUT/"qwen9"/"budget.sqlite3",QWEN[1],QWEN[1])
    jobs=[]
    for t,row in tasks.items():
        prompt="Implement this combined target from scratch. Public contract:\n"+json.dumps(spec["targets"][t])
        jobs.append(("qwen9","direct",row["group"],t,prompt,t.split("_"),ledger))
    for g,features in suites.items():
        for name in sorted(features):
            prompt="Implement the reusable standalone feature "+name+". Public contract:\n"+json.dumps(spec["features"][g][name])
            for rep in ("build-a","build-b"):
                jobs.append(("qwen9",rep,g,name,prompt,[name],ledger))
    with stage(), ThreadPoolExecutor(max_workers=9) as pool:
        components=list(pool.map(base.produce,jobs))
        new_targets={t:{**d,"public":{**d["public"],"jest":json.dumps(spec["targets"][t])}} for t,d in tasks.items()}
        plans=list(pool.map(base.plan_task,[("qwen9",rep,t,d,suites,ledger) for t,d in new_targets.items()
                                            for rep in ("build-a","build-b")]))
    paths=[f for f in OUT.rglob("*.json") if not ({"staging","singles"} & set(f.relative_to(OUT).parts))]
    core.save(OUT/"seal.json", {"utc":now(),"registration_sha256":sha(OUT/"registration.json"),
              "files":{str(f.relative_to(OUT)):sha(f) for f in sorted(paths)},"components":components,"plans":plans})


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase",choices=("register","generate"))
    {"register":register,"generate":generate}[parser.parse_args().phase]()
