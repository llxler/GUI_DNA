"""Supply the router context required by model-written URL templates."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import subprocess
from unittest.mock import patch

from studies.public_library_transfer import browser
from studies.study_io import read, sha, now
from .. import evaluate, prepare as p
from ..component_contract import run as previous

HERE = Path(__file__).resolve().parent
PARENT = previous.OUT
OUT = p.ART / "duo-feature-routes-20261128"


def route_fields(code, brief):
    if not re.search(r'\buseParams\s*\(',code):
        return {}
    # Only the public request URL is used. The registered response and all assertions are ignored.
    urls = set(re.findall(r"""fetchMock\.(?:post|put|get|delete|patch)\(\s*['"]([^'"]+)['"]""",brief))
    result = {}
    for template in re.findall(r"""\bfetch\(\s*`([^`]+)`""",code):
        parts = re.split(r'\$\{([A-Za-z_$][\w$]*)\}',template)
        if len(parts) < 3:
            continue
        pattern = '([^/?&#]+)'.join(re.escape(t) for t in parts[::2])
        matches = {m.groups() for url in urls if (m := re.fullmatch(pattern,url))}
        if len(matches) != 1:
            continue
        for field, value in zip(parts[1::2],matches.pop(),strict=True):
            if field in result and result[field] != value:
                return {}
            result[field] = value
    return result


def mount(code, fields):
    # The feature implementation is a separate module and can retain its original React imports.
    original = next(iter(re.finditer(r'\bexport\s+default\s+',code)), None)
    if original is None or len(re.findall(r'\bexport\s+default\b',code))!=1:
        return None
    declaration = code[original.end():].lstrip()
    named = re.match(r'(?:function|class)\s+([\w$]+)',declaration)
    if named:
        component = named[1]
        original_code = code[:original.start()] + code[original.end():]
    else:
        component = "DuoResourceContent"
        original_code = code[:original.start()] + "const "+component+" = " + code[original.end():]
    names = list(fields)
    parts = [f'encodeURIComponent(inherited[{json.dumps(n)}] ?? props[{json.dumps(n)}] ?? {json.dumps(fields[n])})' for n in names]
    path = '/duo-resource/'+'/'.join(':'+name for name in names)
    return ("import {Routes as DuoRoutes, Route as DuoRoute, useParams as useDuoParams} from 'react-router-dom';\n" + original_code
            + "\nexport default function DuoResourceRoute(props) { const inherited=useDuoParams(); "
            + "const location='/duo-resource/' + " + " + '/' + ".join(parts)
            + "; return <DuoRoutes location={location}><DuoRoute path="+json.dumps(path)+" element={<"+component
            +" {...props} />} /></DuoRoutes>; }\n")


def feature(job):
    tag,group,name = job
    dest=OUT/"features"/tag/group/(name+".json")
    if dest.exists():
        return
    selected=read(PARENT/"features"/tag/group/(name+".json"))["selected"]
    events=[]
    if selected and not selected["public"]["passed"]:
        sources=[(selected["origin"],selected["source"])] if tag=="gpt5" else (
            (p.relative(path),code) for path,code in p.sources(tag,group,name))
        seen=set()
        brief=p.manifest(p.ORIGINAL.EXTRA/"build-inputs.json")[group][name]
        for origin,source in sources:
            fields=route_fields(source,brief)
            if not fields:
                continue
            variants=json.loads(subprocess.check_output(["node",str(previous.HERE/"adapt.cjs")],input=json.dumps({"source":source}),text=True))
            for variant,code in {"original":source,**variants}.items():
                hosted=mount(code,fields)
                if not hosted or p.checksum(hosted) in seen:
                    continue
                seen.add(p.checksum(hosted))
                check=p.measure(group,name,hosted)
                events.append(dict(check,origin=origin,variant=variant,route=fields))
                if check["passed"]:
                    selected=dict(source=hosted,origin=origin,public=check,variant=variant+"-route",route=fields)
                    break
            if selected["public"]["passed"]:
                break
    p.save(dest,dict(selected=selected,events=events))


def run():
    paths=[Path(__file__),HERE/"PROTOCOL.md",previous.HERE/"adapt.cjs",Path(evaluate.__file__),Path(p.__file__),
           PARENT/"library-seal.json",PARENT/"candidates.json",previous.HERE/"result.json",p.ORIGINAL.EXTRA/"build-inputs.json"]
    fields=dict(inputs={p.relative(f):sha(f) for f in paths},new_api_calls=0)
    reg=OUT/"registration.json"
    if not reg.exists():
        p.save(reg,dict(fields,utc=now()))
    assert all(read(reg)[k]==v for k,v in fields.items())
    with patch.multiple(p,OUT=OUT,HERE=HERE):
        jobs=[(t,g,n) for t in ("gpt5",*p.MODELS) for g,names in p.FEATURES.items() for n in names]
        with ThreadPoolExecutor(max_workers=5) as pool:
            list(pool.map(feature,jobs))
        files={p.relative(f):sha(f) for f in sorted((OUT/"features").glob("*/*/*.json"))}
        assert len(files)==len(jobs)
        p.save(OUT/"library-seal.json",dict(registration=sha(reg),features=files))
        new=evaluate.candidates()
        old=read(PARENT/"candidates.json")["candidates"]
        assert all(row["choice"]==old[m][n]["choice"] for m,targets in new["candidates"].items() for n,row in targets.items())
        evaluate.score()


if __name__=="__main__":
    with browser.lock(OUT/"study.lock"):
        run()
