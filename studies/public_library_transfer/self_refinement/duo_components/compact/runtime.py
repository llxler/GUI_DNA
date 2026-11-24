"""Preserve a genuine process crash and require a real failed Jest report on replay."""
from datetime import datetime
import os
from pathlib import Path
import re
import shutil
import subprocess
from unittest.mock import patch

from studies.public_library_transfer import core
from studies.study_io import now, read, sha
from . import run

BASE_SINGLE = run.base.single
BASE_SCORE = run.base.original.evaluate.score
FAILURE = re.compile(r"^(?:ReferenceError|TypeError|SyntaxError|RangeError|Error):\s+.+", re.M)


def preserved(folder, test, cases):
    log = folder/"jest.log"
    saved = folder/"uncaught-original.log"
    if not saved.exists():
        shutil.copyfile(log,saved)
    evidence = saved.read_text(errors="replace")
    error = FAILURE.search(evidence)
    if not error or "Node.js v" not in evidence:
        raise RuntimeError("Runner stopped without identifiable candidate JavaScript error")
    stage = folder/"staging"
    assert sha(test) == sha(next((stage/"src/react").rglob(test.name)))
    env = {k:v for k,v in os.environ.items() if k not in ("OPENROUTER_API_KEY","OPENAI_API_KEY")}
    env.update(CI="true", NODE_OPTIONS=env.get("NODE_OPTIONS","")+" --unhandled-rejections=warn")
    report=folder/"jest.json"
    log2=folder/"uncaught-replay.log"
    spec=next((stage/"src/react").rglob(test.name))
    with log2.open("w") as output:
        rc=subprocess.run(["npm","test","--","--runInBand","--json",f"--outputFile={report}",
                           "--runTestsByPath",str(spec)], cwd=stage, env=env, stdout=output,
                          stderr=subprocess.STDOUT, timeout=150).returncode
    results=read(report)["testResults"]
    assert len(results)==1 and Path(results[0]["name"]).resolve()==spec
    rows=results[0]["assertionResults"]
    if rc==0 or len(rows)!=cases or not any(r["status"]=="failed" for r in rows):
        raise RuntimeError("Failing original process lacks a confirming failed assertion in its diagnostic replay")
    stamp={"original_log_sha256":sha(saved), "original_error":error.group(0)[:250],
           "replay_log_sha256":sha(log2),"report_sha256":sha(report),"replay_exit":rc}
    core.save(folder/"uncaught.json",stamp)
    return rows,stamp


def single(job):
    folder,group,feature,source=job
    # On resume retain the original process evidence before any ordinary invocation rewrites its log.
    if not (folder/"jest.log").exists() or (folder/"verdict.json").exists() or (folder/"jest.json").exists():
        try:
            return BASE_SINGLE(job)
        except FileNotFoundError as exc:
            if Path(exc.filename or "")!=folder/"jest.json":
                raise
    from experiments.webapp1k_probe import REPO
    spec=REPO/"tests/react"/group/(feature+".test.js")
    rows,stamp=preserved(folder,spec,2)
    import hashlib
    feedback=[{"public_case":x["title"],"error":str(x["failureMessages"][0])[:650]} for x in rows if x["status"]=="failed"]
    result={"passed":False,"feedback":feedback,"test_sha256":sha(spec),"source_sha256":hashlib.sha256(source.encode()).hexdigest(),
            "report_sha256":stamp["report_sha256"],"uncaught_process":stamp}
    core.save(folder/"verdict.json",result)
    return feature,result


def score(job):
    _,row,_,folder,_=job
    try:
        return BASE_SCORE(job)
    except FileNotFoundError as exc:
        if Path(exc.filename or "")!=folder/"jest.json":
            raise
    from studies.study_io import ROOT
    cases,stamp=preserved(folder,ROOT/row["test"],4)
    result={"passed":False,"official_tests":4,"assertion_statuses":[k["status"] for k in cases],
            "suite_error":stamp["original_error"],"report_sha256":stamp["report_sha256"],"uncaught_process":stamp}
    core.save(folder/"verdict.json",result)
    return result


def freeze_amendment():
    path=run.OUT/"runtime-registration.json"
    payload={"protocol_sha256":sha(run.HERE/"RUNTIME.md"),"code_sha256":sha(Path(__file__)),
             "original_registration_sha256":sha(run.OUT/"registration.json")}
    if not path.exists():
        core.save(path,{"utc":now(),"amendment":payload})
    assert read(path)["amendment"] == payload
    assert datetime.fromisoformat(read(path)["utc"]) >= datetime.fromisoformat(read(run.OUT/"registration.json")["utc"])


if __name__=="__main__":
    freeze_amendment()
    with patch.object(run.base,"single",single):
        run.generate()
