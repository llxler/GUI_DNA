"""Verify sealed component and Direct candidates, score unchanged Duo suites, audit charges."""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import hashlib

from studies import ledger_read
from studies.public_library_transfer import core
from studies.study_io import ROOT, digest, read, sha
from . import run

RESULT = run.HERE / "result.json"
ARMS = ("direct_first", "direct_repaired", "self", "by_name", "fixed")


def direct_candidate(entry, arm, target):
    if arm == "direct_first":
        item = entry["attempts"]["first"]
        use = "first"
        status = "missing" if item["status"]=="missing" else "valid" if "source_sha256" in item else "invalid"
        fingerprint = item.get("source_sha256")
    else:
        use, status, fingerprint = entry.get("use"), entry["status"], entry.get("source_sha256")
    if status != "valid":
        return {"status":status}, None
    tag = next(k for k,m in run.api.MODELS.items() if m[0]==entry["model"])
    path = run.OUT/tag/"direct"/entry["group"]/entry["target"]/use/"source.json"
    assert sha(path) == fingerprint
    return {"status":"valid", "source_sha256":fingerprint}, {target["public"]["module"]+".js": read(path)["source"]}


def audit_single(entry):
    tag = next(k for k,m in run.api.MODELS.items() if m[0]==entry["model"])
    folder = run.OUT/tag/entry["replica"]/entry["group"]/entry["target"]
    stages = {}
    for attempt, state in entry["attempts"].items():
        out = {k:v for k,v in state.items() if k != "single_results"}
        out["single_results"] = {}
        for feature, val in state.get("single_results",{}).items():
            raw = folder/attempt/"singles"/feature/"jest.json"
            assert sha(raw) == val["report_sha256"]
            source = read(folder/attempt/"source.json")["source"]
            assert hashlib.sha256(source.encode()).hexdigest() == val["source_sha256"]
            assertions = read(raw)["testResults"][0]["assertionResults"]
            successes = sum(r["status"]=="passed" for r in assertions)
            assert val["passed"] == (len(assertions)==2 and successes==2)
            out["single_results"][feature] = {k:v for k,v in val.items() if k!="feedback"} | {
                "cases_passed":successes, "public_cases":2}
        stages[attempt] = out
    return {k:v for k,v in entry.items() if k!="attempts"} | {"attempts":stages}


def bills(tag):
    base = run.OUT/tag
    rows = ledger_read.calls(base/"budget.sqlite3")
    source = {r["id"]:r for r in rows}
    phases = {}
    recorded = set()
    for req in base.rglob("request.json"):
        if req.parent.name != "call":
            continue
        request = read(req)
        row = source[request["call_id"]]
        assert row["model"] == run.api.MODELS[tag][0] == request["body"]["model"]
        assert abs(row["reserved"]/1e6 - request["reserved_usd"]) < .0000011
        recorded.add(row["id"])
        values = phases.setdefault(row["purpose"], dict(calls=0,settled_microusd=0,exposure_microusd=0,
                                                       unresolved=0,prompt_tokens=0,completion_tokens=0))
        values["calls"] += 1
        values["exposure_microusd"] += row["reserved"] if row["actual"] is None else row["actual"]
        if row["actual"] is None:
            values["unresolved"] += 1
        else:
            receipt = req.with_name("response.json")
            usage = read(receipt)["usage"]
            assert abs(row["actual"]/1e6 - float(usage["cost"])) < .0000011
            values["settled_microusd"] += row["actual"]
            values["prompt_tokens"] += usage.get("prompt_tokens",0)
            values["completion_tokens"] += usage.get("completion_tokens",0)
    assert recorded == set(source)
    total = ledger_read.totals(base/"budget.sqlite3")
    assert total["calls"] == sum(v["calls"] for v in phases.values())
    assert round(total["exposure_usd"]*1e6) == sum(v["exposure_microusd"] for v in phases.values())
    return {"total":total,"per_stage":phases}


def paired(rows):
    out = {}
    for arm in ("self","by_name","fixed"):
        data = {}
        for other in (k for k in ("direct_first", "direct_repaired", "fixed", "by_name") if k!=arm):
            common = [r for r in rows if all(r["arms"][k]["passed"] is not None for k in (arm,other))]
            a, b = ({r["task"] for r in common if r["arms"][k]["passed"]} for k in (arm, other))
            data[other] = {"common":[r["task"] for r in common], "passed":len(a), "other_passed":len(b),
                           "only":sorted(a-b), "other_only":sorted(b-a)}
        out[arm] = data
    return out


def preparation(rows):
    by_group = defaultdict(list)
    for r in rows:
        by_group[r["replica"]].append(r)
    result = {}
    for rep, subset in by_group.items():
        target = {}
        for label in ("first","final"):
            acceptable, passed = [], []
            for row in subset:
                step = "first" if label=="first" else row.get("use")
                trial = row["attempts"].get(step, {})
                if trial.get("source_sha256"):
                    acceptable.append(row["target"])
                    if all(v["passed"] for v in trial["single_results"].values()):
                        passed.append(row["target"])
            target[label] = {"valid":len(acceptable),"all_public_single_cases_passed":len(passed),"passed_ids":passed}
        target.update(total=len(subset), repair_requests=sum("repair" in r["attempts"] for r in subset),
                      final_status=dict(Counter(r["status"] for r in subset)))
        result[rep] = target
    return result


def assemble():
    suites, tasks = run.register()
    seal = read(run.OUT/"seal.json")
    assert seal["registration_sha256"] == sha(run.OUT/"registration.json")
    for path, val in seal["files"].items():
        assert val == sha(run.OUT/path), path
    old = read(run.original.OLD)["models"]
    groups = {}
    work = {}
    for tag, cfg in run.api.MODELS.items():
        model = cfg[0]
        components = [audit_single(r) for r in seal["components"] if r["model"]==model]
        direct = {r["target"]:r for r in components if r["replica"]=="direct"}
        history = {k:{r["task"]:r["passed"] for r in old[model]["rows"] if r["arm"]==k and r["group"] in suites}
                   for k in ("direct","self")}
        repeats = {}
        for rep in ("build-a","build-b"):
            rows = []
            for item in seal["plans"]:
                if item["model"]!=model or item["replica"]!=rep:
                    continue
                t = item["task"]
                raw = tasks[t]
                arm_cells = {}
                for arm in ARMS:
                    if arm in ("direct_first","direct_repaired"):
                        cell, files = direct_candidate(direct[t],arm,raw)
                    else:
                        data = item["arms"][arm]
                        cell = {k:v for k,v in data.items() if k!="file"}
                        files = None
                        if cell["status"]=="valid":
                            f = run.OUT/data["file"]
                            assert sha(f) == cell["files_sha256"]
                            files = read(f)
                    if files:
                        key = digest(files)
                        cell["files_digest"] = key
                        work.setdefault((t,key),(raw,files,[]))[2].append(cell)
                    else:
                        cell["passed"] = None if cell["status"]=="missing" else False
                    arm_cells[arm] = cell
                rows.append({"task":t,"group":raw["group"],"plan_delivery":item["plan_delivery"],"arms":arm_cells})
            repeats[rep] = {"rows":rows}
        groups[model] = {"components_and_direct":components, "single_preparation":preparation(components),
                         "repeats":repeats,"old_protocol":history,"billing":bills(tag)}
    def grade(item):
        (t,key),(target,files,cells) = item
        folder = run.OUT/"scores"/t/key
        verdict = run.original.evaluate.score((target["group"],target,files,folder,None))
        assert sha(folder/"jest.json") == verdict["report_sha256"]
        raw = read(folder/"jest.json")["testResults"][0]
        statuses = [a["status"] for a in raw["assertionResults"]]
        assert statuses==verdict["assertion_statuses"] and verdict["passed"] == (statuses==["passed"]*4)
        for cell in cells:
            cell.update(passed=verdict["passed"], official_cases_passed=statuses.count("passed"),
                        report_sha256=verdict["report_sha256"])
    with ThreadPoolExecutor(max_workers=3) as workers:
        list(workers.map(grade, work.items()))
    for group in groups.values():
        for block in group["repeats"].values():
            block["paired"] = paired(block["rows"])
    reg = read(run.OUT/"registration.json")
    return {"registered_utc":reg["utc"],"sealed_utc":seal["utc"],"seal_sha256":sha(run.OUT/"seal.json"),
            "registration_sha256":seal["registration_sha256"],"registered":reg["protocol"],
            "source_overlap_sha256":sha(run.original.OVERLAP),"old_protocol_sha256":sha(run.original.OLD),
            "calibrated_unit":"one Duo test file with four public-overlapping assertions", "groups":groups}


def check(result):
    assert sha(run.original.OLD) == result["old_protocol_sha256"]
    assert sha(run.original.OVERLAP) == result["source_overlap_sha256"]
    reg = result["registered"]
    for f in (run.HERE/"PROTOCOL.md",run.HERE/"run.py",run.HERE/"transport.py"):
        assert sha(f) == reg["source_sha256"][str(f.relative_to(ROOT))]
    assert set(result["groups"]) == {item[0] for item in run.api.MODELS.values()}
    for tag, cfg in run.api.MODELS.items():
        group = result["groups"][cfg[0]]
        prep = group["components_and_direct"]
        assert len(prep) == len({(r["replica"],r["target"]) for r in prep}) == 40
        assert group["single_preparation"] == preparation(prep)
        billing = group["billing"]
        assert billing["total"]["cap_usd"]==cfg[1] and billing["total"]["exposure_usd"]<=cfg[1]
        assert billing["total"]["calls"] == sum(v["calls"] for v in billing["per_stage"].values())
        old = read(run.original.OLD)["models"][cfg[0]]["rows"]
        assert group["old_protocol"]=={k:{r["task"]:r["passed"] for r in old if r["arm"]==k
                                        and r["group"] in reg["features"]} for k in ("direct","self")}
        for rep, block in group["repeats"].items():
            rows=block["rows"]
            assert len(rows)==10 and {r["task"] for r in rows}==set(reg["targets"])
            assert all(set(r["arms"])==set(ARMS) for r in rows)
            assert block["paired"] == paired(rows)
            for r in rows:
                if r["arms"]["by_name"]["plan"]:
                    assert list(r["arms"]["by_name"]["plan"].values()) == r["task"].split("_")
                for c in r["arms"].values():
                    if c["status"]=="valid":
                        assert bool(c["report_sha256"]) and c["passed"]==(c["official_cases_passed"]==4)
            print(tag,rep,{a:sum(r["arms"][a]["passed"] is True for r in rows) for a in ARMS},
                  "observed",{a:sum(r["arms"][a]["passed"] is not None for r in rows) for a in ARMS})
        print(tag,"preparation",[(r,d["first"]["all_public_single_cases_passed"],d["final"]["all_public_single_cases_passed"])
                                for r,d in group["single_preparation"].items()],billing["total"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase",choices=("score","check","check-local"))
    phase = parser.parse_args().phase
    result = read(RESULT) if phase=="check" else assemble()
    check(result)
    if phase=="score":
        core.save(RESULT, result)
    elif phase=="check-local":
        assert read(RESULT)==result
