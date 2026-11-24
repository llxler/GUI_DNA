"""Build real form modules, obtain independent plans and seal matched Direct pages."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import mimetypes
from pathlib import Path
import re
import subprocess
import threading
from unittest.mock import patch
from urllib.parse import urlparse

from gui_dna.budget import BudgetStop, Ledger
from gui_dna.provider import parse_json
from playwright.sync_api import sync_playwright
from studies.interface_blind.core import compile_plan
from studies.public_library_transfer import browser, core
from studies.public_library_transfer.self_refinement.duo_components import transport
from studies.public_library_transfer.self_refinement.form_registry import run as registry
from studies.study_io import ROOT, digest, now, read, sha

HERE=Path(__file__).resolve().parent
OUT=ROOT/"artifacts/form-independent-components-20261124"
PUB=registry.PUBLIC
COMPILER=ROOT/"studies/webbench/form/library_sources/compiler.js"
BALANCE=ROOT/"artifacts/form-components-balance-20261124.json"
END=datetime(2026,11,24,11,23,tzinfo=timezone.utc)
CAP=.50
MODEL=transport.MODELS["oss"][0]
TYPES=registry.TYPES
SUPPORT=("Contents","Survey","style")
SEEDS={"build-a":202611245,"build-b":202611246,"direct":202611245}
SLOTS=threading.BoundedSemaphore(3)
PLAN=("Return just a JSON object {questions:[{type: exported class name, args: constructor argument array,"
      "position: append or prepend}],surveyTitle: string or null,exportData: boolean}. Choose every needed "
      "concrete instance by public name, options/count and order. Supply actual strings/arrays/booleans, no placeholders. "
      "Survey mode instantiates Survey for insertion, contents and validation; null mounts roots directly. "
      "Do not generate source or task IDs.")
CODE_NOTE=("Implement functional ES modules for a local static page, no dependencies or network. Use explicit .js on "
           "local imports. Respect the real starting form and actual constructor/export names. ")


def register():
    sources=[HERE/"run.py",HERE/"PROTOCOL.md",PUB,COMPILER,BALANCE,registry.HERE/"probe.js",
             Path(browser.__file__),Path(core.__file__),Path(transport.__file__),ROOT/"studies/interface_blind/compile.cjs"]
    p=read(PUB)
    assert len(p["requirements"])==20 and read(BALANCE)["sufficient"]
    record={"sources":{str(x.relative_to(ROOT)):sha(x) for x in sources},"model":MODEL,"seeds":SEEDS,"cap_usd":CAP,
            "end":END.isoformat(),"project":"form","targets":list(range(1,21)),"types":list(TYPES),
            "official_contract":browser.verify_contract("form")}
    f=OUT/"registration.json"
    if not f.exists():core.save(f,{"utc":now(),"spec":record})
    assert read(f)["spec"]==record
    return p


def ask(folder,ledger,system,prompt,purpose,seed,limit,previous=None):
    messages=[{"role":"system","content":system},{"role":"user","content":prompt}]
    if previous:
        value,why=previous
        messages.extend([{"role":"assistant","content":value[:27000]},
                         {"role":"user","content":"Correct your complete output using only this public feedback: "+str(why)[:2300]}])
    try:
        raw=transport.request("oss",ledger,OUT,folder,messages,purpose,seed,limit)
        return raw,{"status":"returned","response_sha256":sha(folder/"response.json")}
    except (BudgetStop,transport.Unavailable) as e:
        return "",{"status":"missing","reason":str(e)}


def strip(raw):
    match=re.fullmatch(r"\s*```(?:javascript|js|css|json)?\s*\n([\s\S]*?)\n```\s*",raw,re.I)
    return match[1] if match else raw.strip()


def syntax(files):
    for key,src in files.items():
        if key.endswith((".js",".mjs")):
            p=subprocess.run(["node","--input-type=module","--check","-"],input=src,text=True,capture_output=True,timeout=8)
            if p.returncode:raise ValueError(key+" "+p.stderr[:450])


def observe(files,names,check_app=False):
    report={"types":{},"errors":[]}
    with SLOTS,sync_playwright() as pw:
        engine=pw.chromium.launch(env=browser.browser_env())
        ctx=engine.new_context(service_workers="block")
        def route(r):
            url=urlparse(r.request.url); k=url.path.lstrip("/") or "index.html"
            if url.netloc!="form.local" or k not in files:return r.abort()
            mime="application/javascript" if k.endswith((".js",".mjs")) else mimetypes.guess_type(k)[0] or "text/plain"
            return r.fulfill(status=200,body=files[k],content_type=mime)
        ctx.route("**/*",route)
        page=ctx.new_page()
        page.on("pageerror",lambda err:report["errors"].append(str(err)[:300]))
        page.goto("http://form.local/",wait_until="load",timeout=7000)
        if check_app:
            report["actual_questions"]=page.locator("form .q").count()
        for name in names:
            settings={"kind":"native","type":name,"entry":None,"modulePath":"/common/"+name+".js"}
            res=page.evaluate((registry.HERE/"probe.js").read_text(),settings)
            report["types"][name]=res
        ctx.close();engine.close()
    return report


def problem(obs):
    return (obs["errors"] or [k+":"+json.dumps(v) for k,v in obs["types"].items()
                              if not all(v.get(n) for n in ("exported","mounted","public_structure","control"))]
            or (["No generated question mounted in the public starter form"] if obs.get("actual_questions")==0 else []))


def module_code(job):
    rep,name,p,ledger,dependencies=job; folder=OUT/rep/"modules"/name
    if (folder/"status.json").exists(): return read(folder/"status.json")
    loc="index.css" if name=="style" else "common/"+name+".js"
    system=CODE_NOTE+("Return raw CSS only." if name=="style" else "Return one raw JavaScript module only, with an explicit named export class "+name+".")
    instructions=("Question defines root, body, legend, config panel, getValue(), validate(), toJSON(); preserve its public API. "
                  "Question subclasses must import the actual Question named export, use super(title,name), and share "
                  "its root, body, legend, and config panel. Contents and Survey handle form insertion, contents updates, order, "
                  "validation on submit, numbering, and serialization. Survey exports Survey(formSelector,title) with "
                  "prependQuestion, appendQuestion and toJSON. Consume actual available member names below, including getters. "
                  "The compiler handles export button wiring. Give stable CSS/layout for all publicly named classes.")
    deps={k:v for k,v in dependencies.items()}
    prompt=json.dumps({"write_only":loc,"starter":p["starter"],"public_requirements":p["requirements"],
        "integration_contract":instructions,"actual_dependency_sources":deps},ensure_ascii=False)
    result={"name":name,"status":"invalid","attempts":[]}; prior=None
    for i in range(2):
        attempt=folder/str(i)
        raw,receipt=ask(attempt/"call",ledger,system,prompt,f"prepare/{rep}/"+str(i),SEEDS[rep]+i,3000,prior)
        result["attempts"].append(receipt)
        if receipt["status"]=="missing":
            if i==0:result["status"]="missing"
            break
        try:
            code=strip(raw)
            if not code:raise ValueError("No module source")
            if name!="style" and not re.search(r"\bexport\s+(?:class\s+"+name+r"\b|\{[^}]*\b"+name+r"\b)",code):
                raise ValueError("Export the named class "+name+" so other ES modules can import it")
            syntax({loc:code})
            model_files=p["starter"] | deps | {loc:code}
            if name in TYPES:
                obs=observe(model_files,[name])
                core.save(attempt/"probe.json",obs)
                why=problem(obs)
            else:
                why=[]
            core.save(attempt/"code.json",{"source":code})
            result.update(status="valid",use=i,source_sha256=sha(attempt/"code.json"))
            if not why:break
        except (ValueError,TypeError) as e: why=str(e)
        receipt["public_feedback"]=why
        prior=(raw,why)
    core.save(folder/"status.json",result)
    return result


def module_files(rep):
    files={}
    for n in (*TYPES,*SUPPORT):
        folder=OUT/rep/"modules"/n
        if not (folder/"status.json").exists():continue
        s=read(folder/"status.json")
        if s["status"]!="valid":continue
        f=folder/str(s["use"])/"code.json";assert sha(f)==s["source_sha256"]
        files["index.css" if n=="style" else "common/"+n+".js"]=read(f)["source"]
    return files


def details(p,n):
    return [r["description"] for r in p["requirements"][:n]]


def make_plan(job):
    rep,n,kind,p,ledger=job;folder=OUT/rep/kind/str(n)
    if (folder/"status.json").exists():return read(folder/"status.json")
    files=module_files(rep)
    prompt=json.dumps({"public_requirements":details(p,n),"starting_form":p["starter"]["index.html"],
                       "compiler":COMPILER.read_text(),"actual_module_paths":list(files),
                       "purpose": "Full catalog first example. Include all required types." if kind=="fixed" else "Current deployment."})
    raw,receipt=ask(folder/"call",ledger,PLAN,prompt,f"{kind}/{rep}",SEEDS[rep],2500)
    out={"status":"missing" if receipt["status"]=="missing" else "invalid","call":receipt}
    if receipt["status"]=="returned":
        try:
            plan=parse_json(raw)
            rendered=compile_plan({"files":p["starter"] | files,"compiler":COMPILER.read_text()},plan)
            hashes=core.emit("form",rendered,folder/"page")
            out.update(status="valid",plan=plan,files=hashes)
        except (ValueError,KeyError,TypeError) as e:out["reason"]=str(e)[:600]
    core.save(folder/"status.json",out)
    return out


def direct_files(raw,p):
    parsed=parse_json(raw)
    if isinstance(parsed,dict) and "files" in parsed:
        supplied=parsed["files"]
    else:
        supplied=parsed
    if not isinstance(supplied,dict) or not supplied:raise ValueError("Expected a file map of complete source strings")
    sources=core.files_map([{"path":k,"content":v} for k,v in supplied.items()])
    syntax(sources)
    files=p["starter"] | sources
    if isinstance(parsed,dict) and "plan" in parsed:
        files=compile_plan({"files":files,"compiler":COMPILER.read_text()},parsed["plan"])
    return files


def direct(job):
    n,p,ledger=job;folder=OUT/"direct"/str(n)
    if (folder/"status.json").exists():return read(folder/"status.json")
    full=details(p,n);names=[]
    for name in TYPES:
        if any(re.search(r"\b(?:class|Class)\s+"+name+r"\b",x,re.I) for x in full):names.append(name)
    prompt=json.dumps({"public_requirements":full,"starter":p["starter"],"optional_generic_compiler":COMPILER.read_text(),
        "output":'Return JSON {"files":{relativePath:completeSource,...}}. You can freely write index.js and other files. '
           'Alternatively include a plan to compile against your OWN new ES modules. Make actual public DOM controls work.'})
    system=CODE_NOTE+"Implement the complete page from scratch. Return JSON. Use the supplied startup page and requested filenames."
    out={"task":n,"attempts":[],"status":"invalid"};prior=None
    for i in range(2):
        attempt=folder/str(i)
        raw,receipt=ask(attempt/"call",ledger,system,prompt,"direct/"+str(i),SEEDS["direct"]+i,6400,prior)
        out["attempts"].append(receipt)
        if receipt["status"]=="missing":
            if i==0:out["status"]="missing"
            break
        try:
            files=direct_files(raw,p)
            writes=core.emit("form",files,attempt/"page");receipt["files"]=writes
            obs=observe(files,names,True)
            core.save(attempt/"probe.json",obs)
            why=problem(obs)
            out.update(status="valid",use=i,files=writes)
            if not why:break
        except (ValueError,KeyError,TypeError) as e:why=str(e)
        receipt["public_feedback"]=why
        prior=(raw,why)
    core.save(folder/"status.json",out)
    return out


def generate():
    p=register()
    if (OUT/"seal.json").exists():return
    ledger=Ledger(OUT/"budget.sqlite3",CAP,CAP)
    reps=("build-a","build-b")
    with patch.object(transport,"END",END),ThreadPoolExecutor(max_workers=14) as pool:
        # Free code runs concurrently; build stages respect actual base and Survey dependencies.
        bases=list(pool.map(module_code,[(r,"Question",p,ledger,{}) for r in reps]))
        direct_futures=[pool.submit(direct,(n,p,ledger)) for n in range(1,21)]
        jobs=[(r,n,p,ledger,module_files(r)) for n in (*TYPES[1:],"Contents","style") for r in reps]
        list(pool.map(module_code,jobs))
        jobs=[(r,"Survey",p,ledger,{k:v for k,v in module_files(r).items() if k in ("common/Question.js","common/Contents.js")}) for r in reps]
        list(pool.map(module_code,jobs))
        fixed=list(pool.map(make_plan,[(r,20,"fixed",p,ledger) for r in reps]))
        jobs=[(r,n,"selected",p,ledger) for n in range(1,21) for r in reps]
        selected=list(pool.map(make_plan,jobs))
        direct_rows=[f.result() for f in direct_futures]
    core.save(OUT/"seal.json",{"utc":now(),"registration_sha256":sha(OUT/"registration.json"),
         "modules":{r:{n:read(OUT/r/"modules"/n/"status.json") for n in (*TYPES,*SUPPORT)} for r in reps},
         "fixed":dict(zip(reps,fixed,strict=True)),"plans":{r:selected[i::2] for i,r in enumerate(reps)},
         "direct":direct_rows,"bases":bases})


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase",choices=("register","generate"))
    {"register":register,"generate":generate}[parser.parse_args().phase]()
