"""Audit an admission recovery alongside the single preregistered earlier AI-library arm."""
import argparse

from studies.expression_editor_unseen_requirements import report as baseline
from studies.ledger_read import calls, totals
from studies.study_io import ROOT, digest, dump, read, sha
from studies.table_library_sources.report import paired
from .run import ORIGINAL, OUT, core, locked, original

RESULT = ROOT/"studies/results/expression-editor-unseen-notes-admission-20261123.json"


def inspect_receipts():
    ledger=OUT/"budget.sqlite3"
    charges={r["id"]:r for r in calls(ledger)} if ledger.exists() else {}
    seen=set()
    money={}
    for phase in ("preparation","candidates"):
        ids=[]
        for path in (OUT/phase).rglob("request.json"):
            req=read(path)
            dest=path.parent.parent
            stage=dest.name
            if phase=="preparation":
                expected=read(OUT/"prep-prompt.json")
                model, limit=core.BUILDER,16000
            else:
                task=dest.parent.name
                if task not in original.LATE:
                    raise ValueError(task)
                expected=core.target_prompt("direct",task,read(OUT/"preparation/direct/artifact.json"))
                if expected!=read(OUT/"inputs"/(task+".json")):
                    raise ValueError("Wrong deployment prefix")
                model,limit=core.MODEL,8192
            if stage=="repair":
                expected=original.repaired_prompt(dest.parent/"first")
            key=req["call_id"]
            if (key in seen or req["body"]["messages"]!=expected or req["body"]["max_tokens"]!=limit
                or charges[key]["model"]!=model or req["body"]["model"]!=model
                or digest(expected)!=read(dest/"record.json")["prompt_sha256"]):
                raise ValueError("Unmatched receipt")
            seen.add(key)
            ids.append(key)
        money[phase]={"requests":len(ids),"settled_usd":sum(charges[k]["actual"] or 0 for k in ids)/1e6,
           "exposure_usd":sum(charges[k]["actual"] if charges[k]["actual"] is not None else charges[k]["reserved"] for k in ids)/1e6,
           "unsettled_calls":sum(charges[k]["actual"] is None for k in ids)}
    if seen!=set(charges):
        raise ValueError("Unmatched ledger reservation")
    rejections=[p for d in ("preparation","candidates") for p in (OUT/d).rglob("error.json")
                if read(p).get("http_status")==402]
    if len(rejections)>1:
        raise ValueError("Admission repeated after rejection")
    return money


def reconstruct():
    opening=locked("freeze.json")
    final=locked("paid-closed.json")
    scored=locked("scores-complete.json")["scores"]
    original_result=baseline.reconstruct()
    if original_result!=read(baseline.RESULT):
        raise ValueError("Paired source no longer equals the published original")
    records={(t,s):r for t,s,r in final["target_rows"]}
    if len(records)!=len(final["target_rows"]) or not set(t for t,s in records).issubset(original.LATE):
        raise ValueError("Duplicate or unexpected target record")
    attempts=final["preparation"]
    valid_memo=bool(attempts and attempts[-1][1]["valid"])
    targets={}
    for task in original.LATE:
        old=original_result["targets"][task]
        if any(old["direct"][s]["passed"] is not None for s in ("first","final")):
            raise ValueError("Original rejection did not remain missing")
        current={"original_ai":old["ai"],"controls":old["controls"],"calibrated":old["calibrated"]}
        notes={}
        for name, phase in (("first","first"),("final","repair" if (task,"repair") in records else "first")):
            row=records.get((task,phase))
            if row and row["valid"]:
                key="direct/"+task+"/"+phase
                state={"passed":baseline.score_value(OUT,"scores",key,task,scored[key]),"status":"scored",
                       "valid":True,"official_report_sha256":scored[key]["report_sha256"]}
            elif row:
                state={"passed":False if row["received"] else None,
                       "status":"invalid_response" if row["received"] else "missing_response","valid":False}
            elif not valid_memo and attempts and attempts[-1][1]["received"]:
                state={"passed":False,"status":"invalid_preparation","valid":False}
            else:
                state={"passed":None,"status":"not_deployed","valid":False}
            notes[name]=state
        targets[task]=current|{"supplementary_notes":notes}
    comparison={}
    for stage in ("first","final"):
        a={t:targets[t]["original_ai"][stage]["passed"] for t in original.LATE}
        b={t:targets[t]["supplementary_notes"][stage]["passed"] for t in original.LATE}
        common=[t for t in original.LATE if a[t] is not None and b[t] is not None]
        calibrated=[t for t in common if targets[t]["calibrated"]]
        comparison[stage]={"common_observed":common,"ai_vs_notes":paired(a,b,original.LATE),
            "calibrated_common":calibrated,"calibrated_ai_vs_notes":paired(a,b,calibrated)}
    money=inspect_receipts()
    old_ledger=totals(ORIGINAL/"budget.sqlite3")
    if old_ledger!=opening["prior_ledgers"][ORIGINAL.name]:
        raise ValueError("Original arm continued spending after admission freeze")
    return {"project":"expression-editor","protocol":"Separately registered recovery of one explicit no-content HTTP 402 admission refusal.",
        "prepared_tasks":list(original.EARLY),"deployment_tasks":list(original.LATE),
        "registered_utc":read(OUT/"registration.json")["registered_utc"],"paid_closed_utc":final["utc"],
        "recovery_status":final["reason"],"original_ai_result_sha256":sha(baseline.RESULT),
        "original_missing_notes_preserved":True,"earlier_ai_workflow_records_reused":True,
        "original_ai_first_deployments_attempted":sum(a=="ai" and stage=="first"
            for a,t,stage,row in original.locked("generation-complete.json")["rows"]),
        "original_ai_valid_final_pages":sum(r["original_ai"]["final"]["valid"] for r in targets.values()),
        "supplementary_preparation_valid":valid_memo,"targets":targets,"comparisons":comparison,
        "budget_usd":opening["budget_usd"],"supplementary_ledger":final["ledger"],"supplementary_cost_by_phase":money,
        "original_ledger":old_ledger,"combined_exposure_usd":final["combined_exposure_usd"],
        "stage_sha256":{n:sha(OUT/n) for n in ("registration.json","freeze.json","paid-closed.json","scores-complete.json")}}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write",action="store_true")
    args=parser.parse_args()
    result=reconstruct()
    if args.write:
        if RESULT.exists() and result!=read(RESULT):
            raise ValueError("Refusing to replace previous results")
        dump(RESULT,result)
    elif result!=read(RESULT):
        raise ValueError("Published report differs")
