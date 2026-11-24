"""Reconstruct the compact-contract replication alongside the original Qwen batch."""
import argparse
from collections import Counter
import json
import re
from unittest.mock import patch

from studies.public_library_transfer import core
from studies.study_io import ROOT, read, sha
from .. import report as primary
from . import run, runtime

RESULT = run.HERE / "result.json"


def operations():
    public = read(run.OUT/"public-contracts.json")
    source = read(run.base.original.EXTRA/"build-inputs.json")
    targets = run.base.original.inputs()
    documents = [(g + "/" + n, source[g][n], records) for g,m in public["features"].items() for n,records in m.items()]
    documents.extend((t, targets[t]["public"]["jest"], records) for t,records in public["targets"].items())
    audit = {}
    for name, text, records in documents:
        actions = Counter(re.findall(r"fireEvent\.(\w+)\(", text))
        mocks = Counter(re.findall(r"fetchMock\.(post|get|put|patch|delete|head)\(", text))
        old_queries = set(re.findall(r"screen\.(\w+)\(", text))
        observed, requests = Counter(), Counter()
        for case in records:
            for row in case["sequence"]:
                if "user_action" in row:
                    observed[row["user_action"]] += 1
                if "network_method" in row:
                    requests[row["network_method"].lower()] += 1
        new_queries = set(re.findall(r"screen\.(\w+)\(", json.dumps(records)))
        assert actions == observed and mocks == requests and old_queries==new_queries, name
        audit[name] = {"n_cases":len(records), "actions":dict(observed), "requests":dict(requests),
                       "query_apis":sorted(new_queries)}
    return audit


def score(job):
    _, target, _, folder, _ = job
    try:
        return runtime.score(job)
    except RuntimeError as exc:
        if str(exc) != "Jest produced no report: " + str(folder/"jest.log"):
            raise
    rows, stamp = runtime.preserved(folder,ROOT/target["test"],4)
    value = {"passed":False,"official_tests":4,"assertion_statuses":[r["status"] for r in rows],
             "suite_error":stamp["original_error"],"report_sha256":stamp["report_sha256"],"uncaught_process":stamp}
    core.save(folder/"verdict.json",value)
    return value


def assemble():
    runtime.freeze_amendment()
    audit = operations()
    with run.stage(), patch.object(run.base,"register",run.register), patch.object(run.base.original.evaluate,"score",score):
        result = primary.assemble()
    result["preceding_batch_sha256"] = sha(primary.RESULT)
    result["public_contract_audit"] = audit
    result["runtime_amendment"] = read(run.OUT/"runtime-registration.json")
    result["uncaught_programs"] = {str(f.parent.relative_to(run.OUT)):read(f) for f in run.OUT.rglob("uncaught.json")}
    for path, data in result["uncaught_programs"].items():
        root=run.OUT/path
        assert data["report_sha256"] == sha(root/"jest.json")
        assert data["original_log_sha256"] == sha(root/"uncaught-original.log")
        assert data["replay_log_sha256"] == sha(root/"uncaught-replay.log")
    return result


def check(result):
    assert result["preceding_batch_sha256"] == sha(primary.RESULT)
    for f in (run.HERE/"PROTOCOL.md",run.HERE/"run.py",run.HERE/"contract.cjs"):
        assert sha(f) == result["registered"]["source_sha256"][str(f.relative_to(ROOT))]
    assert set(result["groups"]) == {"qwen/qwen3.5-9b"}
    assert len(result["public_contract_audit"]) == 25
    assert result["runtime_amendment"]["amendment"]["code_sha256"] == sha(run.HERE/"runtime.py")
    assert result["runtime_amendment"]["amendment"]["protocol_sha256"] == sha(run.HERE/"RUNTIME.md")
    with run.stage():
        primary.check(result)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase",choices=("score","check","check-local"))
    phase=parser.parse_args().phase
    result=read(RESULT) if phase=="check" else assemble()
    check(result)
    if phase=="score":
        core.save(RESULT,result)
    elif phase=="check-local":
        assert result==read(RESULT)
