"""Reconstruct outcomes and verify which public requirements reached each API call."""
import argparse

from studies.ledger_read import calls, totals
from studies.study_io import ROOT, digest, dump, read, sha, source_files
from studies.table_library_sources.report import paired
from .run import ARMS, EARLY, HERE, LATE, OLD, OUT, core, locked, public_preparation, repaired_prompt

RESULT = ROOT / "studies/results/expression-editor-unseen-20261123.json"


def validate_receipts(prep):
    early, prep_messages = public_preparation()
    if read(OUT / "public/first-ten.json") != early or prep_messages["ai"][1] != prep_messages["direct"][1]:
        raise ValueError("Preparation arms did not receive the identical ten public rows")
    ledger = {row["id"]:row for row in calls(OUT / "budget.sqlite3")}
    seen = set()
    accounting = {}
    for group, area in (("preparation","preparation"), ("deployment","candidates")):
        accounting[group] = {}
        for arm in ARMS:
            local = []
            for req_path in sorted((OUT / area / arm).rglob("request.json")):
                req = read(req_path)
                current = req_path.parent.parent
                body = req["body"]
                stage = current.name
                if group == "preparation":
                    expected = prep_messages[arm]
                    model, maximum = core.BUILDER, 16000
                else:
                    task = current.parent.name
                    artifact = read(OUT / "preparation" / arm / "artifact.json")
                    expected = core.target_prompt(arm,task,artifact)
                    if read(OUT / "inputs" / arm / f"{task}.json") != expected or task not in LATE:
                        raise ValueError("Unexpected deployment prefix or artifact")
                    model, maximum = core.MODEL, 8192
                if stage == "repair":
                    expected = repaired_prompt(current.parent / "first")
                record = read(current / "record.json")
                row = ledger[req["call_id"]]
                if (req["call_id"] in seen or expected != body["messages"] or digest(expected) != record["prompt_sha256"]
                    or body["model"] != model or row["model"] != model or body["max_tokens"] != maximum):
                    raise ValueError(f"Request differs from expected frozen condition: {current}")
                seen.add(req["call_id"])
                local.append(row)
            accounting[group][arm] = {"requests":len(local),
                "settled_usd":sum(r["actual"] or 0 for r in local)/1e6,
                "exposure_usd":sum(r["actual"] if r["actual"] is not None else r["reserved"] for r in local)/1e6,
                "unsettled_calls":sum(r["actual"] is None for r in local)}
    if seen != set(ledger) or set(prep["arms"]) != set(ARMS):
        raise ValueError("Incomplete receipt audit")
    return accounting


def score_value(root, where, key, task, summary):
    folder = root / where / key
    row = read(folder / "score.json")
    if not (row["report_sha256"] == summary["report_sha256"] == sha(folder / "report.json")
            and row["all_passed"] == summary["passed"] and set(row["tests"]) == {task}):
        raise ValueError(f"Invalid official current-file report: {folder}")
    return row["all_passed"]


def compare(targets, stage):
    results = {a:{t:targets[t][a][stage]["passed"] for t in LATE} for a in ARMS}
    fixed = {t:targets[t]["controls"]["ai_example"] for t in LATE}
    comparison = paired(results["ai"], results["direct"], LATE)
    common = [t for t in LATE if all(results[a][t] is not None for a in ARMS)]
    calibrated = [t for t in common if targets[t]["calibrated"]]
    return {"common_targets":common,"ai_vs_notes":comparison,"ai_vs_fixed_example":paired(results["ai"],fixed,LATE),
            "calibrated_common_targets":calibrated,"ai_vs_notes_calibrated":paired(results["ai"],results["direct"],calibrated),
            "per_arm":{a:{"planned":len(LATE),"observed":sum(v is not None for v in results[a].values()),
                          "passed":sum(v is True for v in results[a].values()),
                          "valid_pages":sum(targets[t][a][stage]["valid"] for t in LATE)} for a in ARMS}}


def reconstruct():
    freeze = locked("freeze.json")
    prep = locked("preparation-complete.json")
    deploy = locked("planning-freeze.json")
    gen = locked("generation-complete.json")
    scored = locked("scores-complete.json")["rows"]
    original = read(OLD / "controls-complete.json")["rows"]
    records = {(a,t,s):r for a,t,s,r in gen["rows"]}
    if (len(records) != len(gen["rows"])
        or {(a,t) for a,t,s in records if s == "first"} != {(a,t) for a in deploy["available"] for t in LATE}
        or {(a,t) for a,t,s in records if s=="repair"} !=
        {(a,t) for (a,t,s),r in records.items() if s=="first" and r["received"] and not r["valid"]}):
        raise ValueError("Unexpected task disposition")
    targets = {}
    for task in LATE:
        controls = {c:score_value(OLD,"calibration",c+"/"+task,task,original[c+"/"+task])
                    for c in ("upstream_final","blank","starter")}
        key = "fixed/" + task
        controls["ai_example"] = score_value(OUT,"calibration",key,task,scored[key]) if key in scored else None
        current = {"controls":controls,"calibrated":task in freeze["calibrated_targets"]}
        for arm in ARMS:
            available = arm in deploy["available"]
            prep_attempt = prep["arms"][arm]
            last_prep = prep_attempt.get("repair",prep_attempt["first"])
            states = {}
            for name, phase in (("first","first"),("final","repair" if (arm,task,"repair") in records else "first")):
                row = records.get((arm,task,phase))
                if not available:
                    states[name] = {"status":"invalid_preparation" if last_prep["received"] else "missing_preparation",
                                    "valid":False, "passed":False if last_prep["received"] else None}
                    continue
                key = "/".join((arm, task, phase))
                if row["valid"]:
                    status = "scored"
                    if source_files(OUT / "candidates" / key / "page") != row["files_sha256"]:
                        raise ValueError(f"Candidate source differs: {key}")
                    passed = score_value(OUT,"scores",key,task,scored[key])
                else:
                    status = "invalid_response" if row["received"] else "missing_response"
                    passed = False if row["received"] else None
                states[name] = {"status":status,"valid":row["valid"],"passed":passed,"phase":phase,
                                "official_report_sha256":scored[key]["report_sha256"] if row["valid"] else None}
            current[arm] = states
        targets[task] = current
    money = validate_receipts(prep)
    ledger = totals(OUT / "budget.sqlite3")
    if ledger["exposure_usd"] > ledger["cap_usd"] or ledger["cap_usd"] != freeze["budget_usd"]:
        raise ValueError("Stage limits differ")
    return {"project":"expression-editor","scope":"Half-brief preparation; individual unseen current-task files.",
            "primary_comparison":"ai_vs_notes","prepared_through":EARLY[-1],
            "preparation_requirements":list(EARLY),"deployment_requirements":list(LATE),
            "model":core.MODEL, "preparation_model":core.BUILDER,
            "registered_utc":read(OUT/"registration.json")["registered_utc"],
            "preparation_closed_utc":prep["utc"],"deployment_prompts_frozen_utc":deploy["utc"],
            "generation_closed_utc":gen["utc"],"blinding_audit":"Exact match of initial messages and public-only repairs against all actual request receipts.",
            "common_preparation_user_sha256":digest(public_preparation()[1]["ai"][1]),
            "starter_sha256":source_files(core.SOURCE/"src-init"), "targets":targets,
            "comparisons":{k:compare(targets,k) for k in ("first","final")},
            "standalone_controls":{k:{"observed":sum(targets[t]["controls"][k] is not None for t in LATE),
                                      "passed":sum(targets[t]["controls"][k] is True for t in LATE)}
                                   for k in ("upstream_final","blank","starter","ai_example")},
            "cost_by_phase_and_arm":money,"ledger":ledger,
            "stage_sha256":{p:sha(OUT/p) for p in ("registration.json","freeze.json","preparation-complete.json",
                                                   "planning-freeze.json","generation-complete.json","scores-complete.json")}}


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write",action="store_true")
    args=parser.parse_args()
    data=reconstruct()
    if args.write:
        if RESULT.exists() and read(RESULT) != data:
            raise ValueError("Refusing to replace a different published summary")
        dump(RESULT,data)
    elif data != read(RESULT):
        raise ValueError("Report differs from frozen evidence")
