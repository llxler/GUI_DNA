"""Deploy real Final Form components from per-model schemas and the shared feature choices."""
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import digest, read, sha, now
from .. import prepare as p
from ..author_completion import run as author
from . import setup, schema

HERE,OUT=setup.HERE,setup.OUT
CAP=2.5


def register():
    sources=[HERE/"PROTOCOL.md",HERE/"host.jsx",HERE/"transport.test.js",Path(__file__),Path(setup.__file__),
             Path(schema.__file__),HERE/"bundle.cjs",HERE/"calibrate.py",OUT/"sdk-receipt.json",OUT/"calibration.json",
             author.OUT/"registration.json",author.PUBLIC]
    fields=dict(sources={p.relative(path):sha(path) for path in sources},models=p.MODELS,cap=CAP,deadline=author.END.isoformat())
    assert author.CAP+CAP<=10
    dest=OUT/"registration.json"
    if not dest.exists():
        balance=check_credits(CAP)
        assert balance["sufficient"]
        p.save(dest,dict(fields,utc=now(),balance=balance))
    assert all(read(dest)[k]==v for k,v in fields.items())


def one(job):
    tag,g,name,ledger=job
    folder=OUT/"bindings"/tag/g/name
    record=folder/"result.json"
    if record.exists():return
    feedback=[]
    selected=None
    attempts=[]
    for i in (1,2):
        system=("Configure an off-the-shelf React Final Form SDK using ONLY the following JSON interface. The host performs real HTTP and interpolation, "
                "and the SDK manages fields and async submission. Do not write code. "
                "Give fields the labels, placeholders, IDs, defaults and options requested by the public user workflow. "
                "Bind typed-in values to the request, and use response fields for dynamic output. "
                "For edit requests the actual resource can be provided via props with a documented initial fallback in defaults. "
                "Only generate a request on mount when the workflow calls for it. Never submit an extra request to satisfy an assertion. "+schema.FORMAT)
        msg=core.messages(system,dict(feature=name,public_single=p.manifest(author.PUBLIC)["features"][g][name],
                                      previous=selected and selected["config"],public_errors=feedback))
        try:
            raw=author.action.compact.base.request(ledger,("table",tag,"a"),folder/str(i)/"call",msg,"build",3200)
        except author.action.typed.MISSING as exc:
            attempts.append(dict(attempt=i,status="missing",reason=str(exc)[:150]))
            break
        try: cfg=schema.parse(raw)
        except (ValueError,TypeError,KeyError) as exc:
            feedback=[str(exc)[:210]]
            attempts.append(dict(attempt=i,status="invalid",message=feedback[0]))
            continue
        code=setup.source(cfg)
        check=p.measure(g,name,code)
        feedback=read(OUT/"public"/g/name/p.checksum(code)/"verdict.json")["feedback"]
        selected=dict(config=cfg,public=check,attempt=i)
        attempts.append(dict(check,status="admitted" if check["passed"] else "public_failed",attempt=i))
        if check["passed"] or name=="postPerformanceReport":break
    p.save(record,dict(selected=selected,attempts=attempts))


def generate():
    register()
    ledger=Ledger(OUT/"budget.sqlite3",CAP,CAP)
    jobs=[(tag,g,n,ledger) for g,names in p.FEATURES.items() for n in names for tag in p.MODELS]
    with patch.multiple(author.action.compact.base,OUT=OUT,END=author.END,template=author.action.settings),patch.object(p,"OUT",OUT):
        with ThreadPoolExecutor(max_workers=5) as pool:list(pool.map(one,jobs))
    files={p.relative(f):sha(f) for f in sorted((OUT/"bindings").glob("*/*/*/result.json"))}
    assert len(files)==len(jobs)
    p.save(OUT/"binding-seal.json",dict(registration=sha(OUT/"registration.json"),bindings=files))


def candidates():
    binding=OUT/"binding-seal.json"
    assert all(sha(p.ROOT/file)==stamp for file,stamp in read(binding)["bindings"].items())
    auth=author.OUT/"candidates.json"
    records=read(auth)["candidates"]
    manifest={}
    pages={}
    counts={}
    for tag,model in p.MODELS.items():
        manifest[model]={}
        counts[model]={}
        for group,features in p.FEATURES.items():
            configs={n:read(OUT/"bindings"/tag/group/n/"result.json")["selected"] for n in features}
            valid=any(c and c["public"]["passed"] for c in configs.values())
            counts[model][group]={n:None if x is None else x["public"]["passed"] for n,x in configs.items()}
            modules={n:setup.source(c["config"]) for n,c in configs.items() if c}
            for task,row in p.ORIGINAL.inputs().items():
                if row["group"]!=group:continue
                choice=records[model][task]["choice"]
                arms={}
                for arm,names in (("human",choice.get("names")),("human-names",task.split("_")),("human-fixed",features[:2])):
                    if not valid:
                        arms[arm]=dict(status="build_failed")
                    elif names is None:
                        arms[arm]=dict(status=choice["status"])
                    else:
                        selected=[n for n in names if n in modules]
                        slots=selected+["NONE","NONE"]
                        files=p.donor.components.bundle(row["public"]["module"],dict(components=[dict(id=n,source=modules[n]) for n in selected]),
                                                       dict(first=slots[0],second=slots[1]))
                        key=digest(files)
                        file=OUT/"pages"/(key+".json")
                        if key not in pages:
                            p.save(file,files)
                            pages[key]=sha(file)
                        arms[arm]=dict(status="valid",file=key,missing=[n for n in names if n not in modules])
                manifest[model][task]=dict(choice=choice,arms=arms)
    frozen=OUT/"candidates.json"
    p.save(frozen,dict(binding=sha(binding),choices_source=sha(auth),pages=pages,candidates=manifest,public=counts))
    return read(frozen)


def score():
    frozen=candidates()
    tasks=p.ORIGINAL.inputs()
    rows={}
    jobs=defaultdict(list)
    for m, targets in frozen["candidates"].items():
        rows[m]=[]
        for n,v in targets.items():
            for a,t in v["arms"].items():
                rec=dict(task=n,arm=a,**t)
                rows[m].append(rec)
                if t["status"]=="valid":
                    jobs[n,t["file"]].append(rec)
                else:rec["passed"]=False if t["status"]=="invalid" else None
    def grade(job):
        (n,key),items=job
        f=OUT/"pages"/(key+".json")
        assert sha(f)==frozen["pages"][key]
        dest=OUT/"scores"/n/key
        v=p.runtime.score((tasks[n]["group"],tasks[n],read(f),dest,None))
        assert v["report_sha256"]==sha(dest/"jest.json")
        for rec in items:rec.update(passed=v["passed"],report_sha256=v["report_sha256"],official_cases_passed=v["assertion_statuses"].count("passed"))
    with ThreadPoolExecutor(max_workers=5) as pool:list(pool.map(grade,jobs.items()))
    # Publish finite model configurations so the SDK source and every binding can be inspected separately.
    configs={m:{n:read(OUT/"bindings"/tag/g/n/"result.json") for g,features in p.FEATURES.items() for n in features} for tag,m in p.MODELS.items()}
    p.save(HERE/"result.json",dict(registration=sha(OUT/"registration.json"), candidate_seal=sha(OUT/"candidates.json"),
        choices_source=sha(author.OUT/"candidates.json"),sdk=read(OUT/"sdk-receipt.json"), calibration=read(OUT/"calibration.json"),
        public=frozen["public"], bindings=configs, models=rows, cost=ledger_read.totals(OUT/"budget.sqlite3")))


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("phase",choices=["generate","score"])
    with browser.lock(OUT/"study.lock"):
        if parser.parse_args().phase=="generate":generate()
        else:score()
