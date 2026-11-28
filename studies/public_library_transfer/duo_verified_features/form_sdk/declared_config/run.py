"""Accept a single unambiguous model-authored JSON binding and preserve prior real configurations."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import now, read, sha
from ... import prepare as p
from ...author_completion import run as author
from .. import run as parent, schema, setup

HERE=Path(__file__).resolve().parent
OUT=p.ART/"duo-form-config-20261128"
CAP=1.0


def receive(raw):
    try:return schema.parse(raw)
    except (ValueError,TypeError): pass
    candidates={}
    for block in re.findall(r"```(?:json)?[ \t]*\n([\s\S]*?)\n[ \t]*```",raw,re.I):
        try: cfg=schema.parse(block)
        except (ValueError,TypeError):continue
        candidates[json.dumps(cfg,sort_keys=True)]=cfg
    if len(candidates)!=1:
        raise ValueError("A single complete valid JSON configuration is required")
    return next(iter(candidates.values()))


def bind(job):
    tag,g,n,ledger=job
    rel=Path("bindings")/tag/g/n
    dest=OUT/rel/"result.json"
    if dest.exists():return
    initial=read(setup.OUT/rel/"result.json")
    selected=initial["selected"]
    events=[]
    def check(cfg,source):
        code=setup.source(cfg)
        verdict=p.measure(g,n,code)
        events.append(dict(verdict,status="received",source=p.relative(source),sha256=sha(source)))
        return dict(config=cfg,public=verdict,source=p.relative(source))
    if selected is None:
        for i in (1,2):
            responses=sorted((setup.OUT/rel/str(i)/"call").glob("*/response.json"))
            for r in responses:
                data=read(r)
                try:cfg=receive(data["choices"][0]["message"].get("content") or "")
                except (ValueError,TypeError):continue
                selected=check(cfg,r)
                break
            if selected:break
        if selected is None:
            feedback=[]
            for i in (1,2):
                msg=core.messages("Your output is DATA consumed by a form configuration parser. Start with { and end with }. "
                    "Fill the actual desired field values for this one feature. Do not describe the task or include prose. "
                    "Do not write scripts; wire user values and the real response status. "+schema.FORMAT,
                    dict(feature=n,single_workflow=p.manifest(author.PUBLIC)["features"][g][n],feedback=feedback,
                         previous_config=selected and selected["config"]))
                folder=OUT/rel/str(i)/"call"
                try:raw=author.action.compact.base.request(ledger,("table",tag,"a"),folder,msg,"build",3600)
                except author.action.typed.MISSING as ex:
                    events.append(dict(status="missing",reason=str(ex)[:140]));break
                try:cfg=receive(raw)
                except (TypeError,ValueError) as ex:
                    feedback=[str(ex)];events.append(dict(status="invalid",reason=str(ex)));continue
                response=next(r for r in sorted(folder.glob("*/response.json")) if read(r)["choices"][0]["message"].get("content")==raw)
                selected=check(cfg,response)
                if selected["public"]["passed"] or n=="postPerformanceReport":break
                s=selected["public"]["source_sha256"]
                feedback=read(OUT/"public"/g/n/s/"verdict.json")["feedback"]
    p.save(dest,dict(selected=selected,attempts=events,previous=p.relative(setup.OUT/rel/"result.json")))


def run(phase):
    if phase=="score":
        with patch.multiple(parent,OUT=OUT,HERE=HERE):
            parent.score()
        return
    reg=OUT/"registration.json"
    inputs=[Path(__file__),HERE/"PROTOCOL.md",Path(parent.__file__),Path(schema.__file__),setup.OUT/"binding-seal.json",setup.OUT/"sdk-receipt.json",author.PUBLIC]
    fields=dict(sources={p.relative(f):sha(f) for f in inputs},cap=CAP,deadline=author.END.isoformat())
    if not reg.exists():
        balance=check_credits(CAP)
        assert balance["sufficient"] and CAP+parent.CAP+author.CAP<=10
        p.save(reg,dict(fields,utc=now(),balance=balance))
    assert all(read(reg)[k]==v for k,v in fields.items())
    ledger=Ledger(OUT/"budget.sqlite3",CAP,CAP)
    jobs=[(t,g,n,ledger) for t in p.MODELS for g,features in p.FEATURES.items() for n in features]
    with patch.multiple(author.action.compact.base,OUT=OUT,END=author.END,template=author.action.settings),patch.object(p,"OUT",OUT):
        with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(bind,jobs))
    receipts={p.relative(f):sha(f) for f in sorted((OUT/"bindings").glob("*/*/*/result.json"))}
    assert len(receipts)==len(jobs)
    p.save(OUT/"binding-seal.json",dict(registration=sha(reg),bindings=receipts))
    for n in ["calibration.json","sdk-receipt.json"]:p.save(OUT/n,read(setup.OUT/n))


if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("phase",choices=["generate","score"])
    with browser.lock(OUT/"study.lock"):run(parser.parse_args().phase)
