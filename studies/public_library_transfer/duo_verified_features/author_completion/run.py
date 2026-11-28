"""Let the original author repair uncovered single features, then select and score the same target pairs."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import json
import threading
from unittest.mock import patch

import httpx
from gui_dna.budget import Ledger
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from studies.webbench.table.action_library import run as action
from .. import evaluate, prepare as p
from ..resource_routes import run as routes

HERE=Path(__file__).resolve().parent
OUT=p.ART/"duo-author-completion-20261128"
PARENT=routes.OUT
BASE=p.donor.original
CAP=4.0
END=datetime(2026,11,28,15,5,tzinfo=timezone.utc)
CREDIT=p.OUT/"new-credit-check.json"
MODEL_IDS={**p.MODELS,"gpt5":"openai/gpt-5"}
LOCAL=threading.local()
PUBLIC=p.ART/"duo-compact-components-20261124/public-contracts.json"


def register():
    paths=[Path(__file__),HERE/"PROTOCOL.md",Path(p.__file__),Path(evaluate.__file__),routes.HERE/"result.json",
           PARENT/"library-seal.json",PARENT/"candidates.json",PUBLIC,CREDIT,Path(action.compact.base.__file__)]
    reg=dict(sources={p.relative(x):sha(x) for x in paths},cap=CAP,deadline=END.isoformat(),model_ids=MODEL_IDS,
             required_total=10,balance=read(CREDIT))
    assert reg["balance"]["sufficient"] and reg["balance"]["required_usd"]==10
    dest=OUT/"registration.json"
    if not dest.exists():
        assert datetime.now(timezone.utc)<END
        p.save(dest,dict(reg,utc=now()))
    assert all(read(dest)[k]==v for k,v in reg.items())


def ask(tag,folder,msg,kind,limit):
    LOCAL.tag=tag
    return action.compact.base.request(LOCAL.ledger,("table",tag,"a"),folder,msg,kind,limit)


def feature(tag,group,name,ledger):
    LOCAL.ledger=ledger
    dest=OUT/"features"/tag/group/(name+".json")
    if dest.exists():return
    prior=read(PARENT/"features"/tag/group/(name+".json"))["selected"]
    selected=prior
    events=[]
    if not selected or not selected["public"]["passed"]:
        source=prior["source"] if prior else None
        feedback=[]
        for attempt in range(1,2 if name=="postPerformanceReport" else 4):
            folder=OUT/"builds"/tag/group/name/str(attempt)
            msg=core.messages(
                "Implement one reusable, standalone React feature from its public specification. Return a complete default-export JSX file. "
                "The enclosing application supplies a MemoryRouter, and provides only the props shown in the brief. Make optional notifications optional. "
                "Use real user input, a single documented HTTP request per action, and the actual response status or JSON. "
                "Use accessible field names, exact documented button captions and announced success or error messages. "
                "If editing a resource without a matched route, allow a supplied resource ID and use the documented initial resource as a fallback. "
                "A select must offer the documented choices; a text field accepts other values, too. Keep unrelated controls out of this component. "
                "Verify variable scope and React imports. Only react and react-router-dom imports. Never import test utilities, inspect mocks, or send redundant requests.",
                dict(feature=name,public_single_steps=p.manifest(PUBLIC)["features"][group][name],
                     previous_implementation=source,public_single_feedback=feedback))
            try:
                raw=ask(tag,folder/"call",msg,"build",5400)
            except action.typed.MISSING as err:
                events.append(dict(attempt=attempt,status="missing",reason=str(err)[:160]))
                break
            code=p.donor.components.extract(raw)
            if not code:
                events.append(dict(attempt=attempt,status="invalid"))
                feedback=["Return one complete standalone default export. No extra files, explanation or external packages."]
                continue
            check=p.measure(group,name,code)
            verdict=read(OUT/"public"/group/name/p.checksum(code)/"verdict.json")
            events.append(dict(check,attempt=attempt,status="admitted" if check["passed"] else "failed_public"))
            p.save(folder/"source.json",dict(source=code))
            if check["passed"]:
                selected=dict(source=code,origin=p.relative(folder/"source.json"),public=check)
                break
            source,feedback=code,verdict["feedback"]
    p.save(dest,dict(selected=selected,events=events))


def selections(tag,task,group,ledger):
    LOCAL.ledger=ledger
    folder=OUT/"selections"/tag/task
    dest=folder/"result.json"
    if dest.exists():return
    msg=core.messages("Choose two different registered feature identifiers for this public React feature request. Return only a JSON array of their exact names in render order.",
                      dict(requested_module=task,registered_features=p.FEATURES[group]))
    for i in (1,2):
        try:
            raw=ask(tag,folder/str(i),msg,"plan",900)
        except action.typed.MISSING as exc:
            p.save(dest,dict(status="missing",reason=str(exc)[:160]))
            return
        plan=p.donor.components.parse_plan(raw,p.FEATURES[group])
        if plan:
            p.save(dest,dict(status="valid",names=[plan["first"],plan["second"]],attempt=i))
            return
        msg=msg+[dict(role="user",content="Use two distinct exact strings from the registered list, in one JSON array.")]
    p.save(dest,dict(status="invalid",attempt=2))


def choice(tag, task, group):
    path=OUT/"selections"/tag/task/"result.json"
    return dict(read(path),source=p.relative(path),sha256=sha(path))


def run():
    register()
    ledger=Ledger(OUT/"budget.sqlite3",CAP,CAP)
    getter=httpx.post
    def log_post(*args,**kwargs):
        response=getter(*args,**kwargs)
        if response.status_code in (401,402,403,404):
            tag=LOCAL.tag
            dest=OUT/("vendor-"+tag+".json")
            with browser.lock(OUT/("vendor-"+tag+".lock")):
                if not dest.exists():
                    try: msg=str(response.json()["error"]["message"])[:240]
                    except (ValueError,TypeError,KeyError): msg="Provider rejected request"
                    p.save(dest,dict(status=response.status_code,message=msg))
        return response
    def build(tag):
        order={"approveOrRejectTaskReview":0,"addCommentToTask":1}
        jobs=sorted(((g,n) for g,ns in p.FEATURES.items() for n in ns),key=lambda x:(order.get(x[1],2),x[1]))
        for g,n in jobs:feature(tag,g,n,ledger)
    with patch.multiple(action.compact.base,OUT=OUT,END=END,template=action.settings),patch.object(httpx,"post",log_post),patch.multiple(p,OUT=OUT,HERE=HERE):
        with ThreadPoolExecutor(max_workers=5) as pool:list(pool.map(build,("gpt5",*p.MODELS)))
        jobs=[(t,n,r["group"],ledger) for t in p.MODELS for n,r in p.ORIGINAL.inputs().items()]
        with ThreadPoolExecutor(max_workers=5) as pool:list(pool.map(lambda args:selections(*args),jobs))
        files={p.relative(f):sha(f) for f in sorted((OUT/"features").glob("*/*/*.json"))}
        assert len(files)==105
        p.save(OUT/"library-seal.json",dict(registration=sha(OUT/"registration.json"),features=files))
        with patch.object(evaluate,"first_choice",choice):
            evaluate.candidates()
            # The shared score writer records zero for offline studies. Save its output in a distinct file before adding metered provenance.
            from tempfile import TemporaryDirectory
            with TemporaryDirectory(dir=OUT) as temp, patch.object(p,"HERE",Path(temp)):
                evaluate.score()
                result=read(Path(temp)/"result.json")
            costs=ledger_read.totals(OUT/"budget.sqlite3")
            result.pop("new_api_calls")
            result.pop("new_usd")
            result.update(cost=costs, provider_messages={f.stem[7:]:read(f) for f in sorted(OUT.glob("vendor-*.json"))})
            p.save(HERE/"result.json",result)


if __name__=="__main__":
    with browser.lock(OUT/"study.lock"):
        run()
