"""Preregister ten new official pairs by name, build genuine one-feature libraries, and grade all three methods."""
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from pathlib import Path
import argparse
import importlib
from unittest.mock import patch

from experiments.webapp1k_probe import REPO
from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser,core
from studies.study_io import digest,now,read,sha
from .. import prepare as p
from ..author_completion import run as author
from ..form_sdk import run as sdk
from ..form_sdk.declared_config import run as bindings

HERE=Path(__file__).resolve().parent
OUT=p.ART/"duo-unseen-pairs-20261128"
CAP=2.45
PREFIX="gui-dna-duo-novel-20261128-v1/"
BUILDERS=("deepseek-flash","gpt5")


def register():
    controls=read(p.donor.OUT/"libraries.json")
    old=set(p.ORIGINAL.inputs())
    groups={}
    rows={}
    briefs={}
    for g,previous in p.FEATURES.items():
        excluded=set(previous)|{n for donor in controls[g]["modules"] for n in donor.split("_")}
        files={f.name.removesuffix(".test.js"):f for f in (REPO/"duo_tests/react"/g).glob("*.test.js")}
        ordered=sorted((n for n in files if n not in old and excluded.isdisjoint(n.split("_"))),key=lambda n:p.checksum(PREFIX+g+"/"+n))
        selected=ordered[:5]
        assert len(selected)==5
        names=sorted({feature for pair in selected for feature in pair.split("_")})
        groups[g]=dict(excluded=sorted(excluded),eligible=len(ordered),targets=selected,features=names)
        briefs[g]={}
        for n in names:
            src=REPO/"tests/react"/g/(n+".test.js")
            briefs[g][n]=src.read_text()
        for n in selected:
            rows[n]=dict(group=g,test=p.relative(files[n]),test_sha256=sha(files[n]),public=dict(module=n))
    p.save(OUT/"build-inputs.json",briefs)
    sources=[HERE/"PROTOCOL.md",Path(__file__),p.donor.HERE/"result.json",author.HERE/"PROTOCOL.md",OUT/"build-inputs.json"]
    fields=dict(groups=groups,targets=rows,sources={p.relative(f):sha(f) for f in sources},deadline=author.END.isoformat(),cap=CAP)
    f=OUT/"registration.json"
    if not f.exists():
        balance=check_credits(CAP)
        assert balance["sufficient"] and CAP+bindings.CAP+sdk.CAP+author.CAP<=10
        p.save(f,dict(fields,utc=now(),balance=balance))
    assert all(read(f)[k]==v for k,v in fields.items())
    return read(f)


def make(job):
    ledger,tag,group,n,names,direct=job
    arm="direct" if direct else "library"
    root=OUT/arm/tag/group/n
    dest=root/"record.json"
    if dest.exists():return
    briefs=p.manifest(OUT/"build-inputs.json")[group]
    prefix="Implement the requested features together on one new React page, from scratch." if direct else "Implement one reusable React feature in isolation from other features."
    source=None
    selected=None
    feedback=[]
    history=[]
    for attempt in range(1,4):
        folder=root/str(attempt)
        msg=core.messages(prefix+" Return a complete raw JSX module with a default export. Only react and react-router-dom imports. "
             "Provide user-operable fields with the specified accessible names, correct initial resource context and real HTTP calls. "
             "Handle server successes and failures. No test facilities, no fake data, redundant requests, or branches triggered by a test. "
             "The parent supplies a MemoryRouter and only the documented props. Use documented initial IDs if no resource is provided.",
             dict(required_features=list(names),public_single_requirements={k:briefs[k] for k in names},prior_page=source,single_feature_feedback=feedback))
        try:raw=author.action.compact.base.request(ledger,("table",tag,"a"),folder/"call",msg,"plan" if direct else "build",5800)
        except author.action.typed.MISSING as err:
            history.append(dict(status="missing",reason=str(err)[:160]));break
        candidate=p.donor.components.extract(raw)
        if not candidate:
            history.append(dict(status="invalid"));feedback=["Only a complete default-export React component."];continue
        source=candidate
        src=folder/"source.json";p.save(src,dict(source=source))
        checks={}
        feedback=[]
        for name in names:
            checks[name]=p.measure(group,name,source)
            if not checks[name]["passed"]:
                feedback.extend(read(OUT/"public"/group/name/p.checksum(source)/"verdict.json")["feedback"])
        current=dict(file=p.relative(src),source_sha256=p.checksum(source),public=checks,attempt=attempt)
        history.append(dict(status="valid",**current))
        good=all(c["passed"] for c in checks.values())
        if good or selected is None:selected=current
        if good:break
    if selected: status="valid"
    else: status="missing" if any(h["status"]=="missing" for h in history) else "invalid"
    p.save(dest,dict(status=status,selected=selected,history=history))


def choice(task,g,options,ledger):
    path=OUT/"plans"/task
    f=path/"result.json"
    if f.exists():return read(f)
    msg=core.messages("Choose two distinct registered feature names for this requested application. JSON array of exactly two strings only.",
                      dict(requested_module=task,registered=options))
    for i in (1,2):
        try:raw=author.action.compact.base.request(ledger,("table","deepseek-flash","a"),path/str(i),msg,"plan",900)
        except author.action.typed.MISSING as err:
            p.save(f,dict(status="missing",reason=str(err)[:140]));return read(f)
        setting=p.donor.components.parse_plan(raw,options)
        if setting:
            p.save(f,dict(status="valid",names=[setting["first"],setting["second"]]));return read(f)
        msg=msg+[dict(role="user",content="Return two names from the supplied list in one JSON array.")]
    p.save(f,dict(status="invalid"));return read(f)


def generate(reg):
    specs=reg["targets"]
    ledger=Ledger(OUT/"budget.sqlite3",CAP,CAP)
    jobs=[(ledger,tag,g,n,[n],False) for g,conf in reg["groups"].items() for n in conf["features"] for tag in BUILDERS]
    jobs += [(ledger,"deepseek-flash",v["group"],n,n.split("_"),True) for n,v in specs.items()]
    public_runner=importlib.import_module(p.runtime.BASE_SINGLE.__module__)
    with patch.object(public_runner,"OUT",OUT),patch.object(p,"OUT",OUT),patch.multiple(author.action.compact.base,OUT=OUT,END=author.END,template=author.action.settings):
        with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(make,jobs))
        def get_choice(k):return choice(k,specs[k]["group"],reg["groups"][specs[k]["group"]]["features"],ledger)
        with ThreadPoolExecutor(max_workers=3) as pool:plans=dict(zip(specs,pool.map(get_choice,specs),strict=True))
    records={}
    srcs={}
    def store(files):
        key=digest(files)
        f=OUT/"pages"/(key+".json");p.save(f,files);srcs[key]=sha(f)
        return dict(status="valid",file=key)
    def recover(r):
        file=p.ROOT/r["file"];code=read(file)["source"];assert p.checksum(code)==r["source_sha256"];return code
    for task,r in specs.items():
        g=r["group"];options=reg["groups"][g]["features"];direct=read(OUT/"direct/deepseek-flash"/g/task/"record.json")
        selected=direct["selected"];row=records[task]={}
        row["direct"]=store({task+".js":recover(selected)}) if selected else dict(status=direct["status"])
        for tag in BUILDERS:
            prefix="self" if tag=="deepseek-flash" else "gpt5-library"
            implementations={n:read(OUT/"library"/tag/g/n/"record.json")["selected"] for n in options}
            valid=any(v and v["public"][n]["passed"] for n,v in implementations.items())
            for arm,names in ((prefix,plans[task].get("names")),(prefix+"-fixed",options[:2])):
                if not valid:row[arm]=dict(status="build_failed");continue
                if names is None:row[arm]=dict(status=plans[task]["status"]);continue
                modules=[dict(id=n,source=recover(implementations[n])) for n in names if implementations[n]]
                slots=[m["id"] for m in modules]+["NONE","NONE"]
                files=p.donor.components.bundle(task,dict(components=modules),dict(first=slots[0],second=slots[1]))
                row[arm]=store(files)
    traces={p.relative(f):sha(f) for k in ("direct","library") for f in sorted((OUT/k).glob("*/*/*/record.json"))}
    p.save(OUT/"seal.json",dict(registration=sha(OUT/"registration.json"),records=records,plans=plans,files=srcs,traces=traces))


def score(reg):
    seal=read(OUT/"seal.json")
    assert seal["registration"]==sha(OUT/"registration.json") and all(sha(p.ROOT/f)==h for f,h in seal["traces"].items())
    jobs=defaultdict(list)
    rows=[]
    for n,arms in seal["records"].items():
        for a,v in arms.items():
            rec=dict(task=n,arm=a,**v);rows.append(rec)
            if v["status"]=="valid":jobs[n,v["file"]].append(rec)
            else:rec["passed"]=False if v["status"]=="invalid" else None
    def grade(job):
        (n,key),records=job
        r=reg["targets"][n]
        f=OUT/"pages"/(key+".json")
        assert sha(f)==seal["files"][key]
        dest=OUT/"scores"/n/key
        v=p.runtime.score((r["group"],r,read(f),dest,None))
        assert sha(dest/"jest.json")==v["report_sha256"]
        for rec in records:rec.update(passed=v["passed"],official_cases=v["assertion_statuses"],report_sha256=v["report_sha256"])
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(grade,jobs.items()))
    p.save(HERE/"result.json",dict(registration=sha(OUT/"registration.json"),seal=sha(OUT/"seal.json"),groups=reg["groups"],
        test_files={n:{"path":r["test"],"sha256":r["test_sha256"]} for n,r in reg["targets"].items()},
        choices=seal["plans"],receipts={f:read(p.ROOT/f) for f in seal["traces"]},models={"deepseek/deepseek-v4-flash":rows},
        cost=ledger_read.totals(OUT/"budget.sqlite3")))


if __name__=="__main__":
    with browser.lock(OUT/"study.lock"):
        reg=register();generate(reg);score(reg)
