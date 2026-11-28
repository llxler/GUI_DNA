"""Bind declared resource props and accessible fields to actual model implementations."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import re
import subprocess
from unittest.mock import patch

from studies.public_library_transfer import browser
from studies.study_io import read, sha, now
from .. import evaluate, prepare as p
from ..author_completion import run as author
from ..component_contract import run as contract
from ..resource_routes import run as routes

HERE=Path(__file__).resolve().parent
OUT=p.ART/"duo-field-bindings-20261128"


def props_source(code, fields):
    if not fields:return code
    m=re.search(r'\bexport\s+default\s+',code)
    if not m:return code
    rest=code[m.end():]
    matched=re.match(r'(?:function|class)\s+([\w$]+)',rest)
    if matched:label=matched[1]; kept=code[:m.start()]+rest
    else:label="DuoBoundResource";kept=code[:m.start()]+"const "+label+" = "+rest
    return kept+"\nexport default function DuoPropHost(props){ return <"+label+" {..."+json.dumps(fields)+"} {...props} />; }\n"


def actions(steps):
    result=[]
    for step in steps[0]["sequence"]:
        if (kind:=step.get("user_action")) not in ("change","click"):continue
        expr=step["query_and_input"][0]
        m=re.search(r"""getBy(LabelText|Text|TestId|PlaceholderText)\(\s*(?:['"]([^'"]+)['"]|/([\w -]+)/i?)""",expr)
        if m:by,text=m[1],m[2] or m[3]
        else:
            m=re.search(r"""getByRole\(['"]button['"].*?name:\s*(?:['"]([^'"]+)['"]|/([\w -]+)/i?)""",expr)
            if not m:return []
            by,text="Role",m[1] or m[2]
        result.append(dict(kind=kind,by=by,text=text))
    return result


def feature(job):
    tag,g,n=job
    file=OUT/"features"/tag/g/(n+".json")
    if file.exists():return
    prior=read(author.OUT/"features"/tag/g/(n+".json"))
    old=prior["selected"]
    selected=old
    events=[]
    if (not old or not old["public"]["passed"]) and n!="postPerformanceReport":
        sources=[]
        if old:sources.append((old["origin"],old["source"]))
        if tag!="gpt5":sources.extend((p.relative(f),s) for f,s in p.sources(tag,g,n))
        for f in sorted((author.OUT/"builds"/tag/g/n).glob("*/source.json")):sources.append((p.relative(f),read(f)["source"]))
        brief=p.manifest(p.ORIGINAL.EXTRA/"build-inputs.json")[g][n]
        steps=actions(p.manifest(author.PUBLIC)["features"][g][n])
        seen_raw=set()
        seen=set()
        for origin,raw in sources:
            if p.checksum(raw) in seen_raw:continue
            seen_raw.add(p.checksum(raw))
            fields=routes.route_fields("useParams();\n"+raw,brief)
            previous=json.loads(subprocess.check_output(["node",str(contract.HERE/"adapt.cjs")],input=json.dumps(dict(source=raw)),text=True))
            for prefix,base in {"plain":raw,**previous}.items():
                bound=subprocess.check_output(["node",str(HERE/"attributes.cjs")],input=json.dumps(dict(source=base,actions=steps)),text=True)
                for k,code in (("props",props_source(base,fields)),("fields",bound),("both",props_source(bound,fields))):
                    key=p.checksum(code)
                    if key==p.checksum(raw) or key in seen:continue
                    seen.add(key)
                    check=p.measure(g,n,code)
                    events.append(dict(check,origin=origin,variant=prefix+"-"+k,props=fields))
                    if check["passed"]:
                        selected=dict(source=code,origin=origin,public=check,variant=prefix+"-"+k)
                        break
                if selected and selected["public"]["passed"]:break
            if selected and selected["public"]["passed"]:break
    p.save(file,dict(selected=selected,events=events))


def run():
    files=[Path(__file__),HERE/"PROTOCOL.md",HERE/"attributes.cjs",contract.HERE/"adapt.cjs",Path(routes.__file__),
           Path(evaluate.__file__),Path(author.__file__),author.OUT/"library-seal.json",author.OUT/"candidates.json",
           author.PUBLIC,p.ORIGINAL.EXTRA/"build-inputs.json"]
    reg=OUT/"registration.json"
    fields=dict(source={p.relative(f):sha(f) for f in files},new_api_calls=0)
    if not reg.exists():p.save(reg,dict(fields,utc=now()))
    assert all(read(reg)[k]==v for k,v in fields.items())
    with patch.multiple(p,OUT=OUT,HERE=HERE),patch.object(evaluate,"first_choice",author.choice):
        jobs=[(t,g,n) for t in ("gpt5",*p.MODELS) for g,ns in p.FEATURES.items() for n in ns]
        with ThreadPoolExecutor(max_workers=5) as pool:list(pool.map(feature,jobs))
        receipts={p.relative(f):sha(f) for f in sorted((OUT/"features").glob("*/*/*.json"))}
        assert len(receipts)==len(jobs)
        p.save(OUT/"library-seal.json",dict(registration=sha(reg),features=receipts))
        base=read(author.OUT/"candidates.json")["candidates"]
        new=evaluate.candidates()["candidates"]
        assert all(base[m][n]["choice"]==r["choice"] for m,targets in new.items() for n,r in targets.items())
        evaluate.score()


if __name__=="__main__":
    with browser.lock(OUT/"study.lock"):run()
