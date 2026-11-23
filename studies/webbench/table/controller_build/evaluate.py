"""Freeze, grade and audit strict selection, first-example recovery, and fixed example."""
import argparse
import hashlib
import json
from pathlib import Path

from gui_dna.provider import parse_json
from studies.compatible_library_rebuild.sealed_evaluate_20261123 import four_cells, score_entry
from studies.interface_blind.core import write_files
from studies.library_refinement_table.adapter import score_pages
from studies.public_controller_build import build, planning
from studies.study_io import ROOT, digest, dump, now, read, sha, source_files
from studies.svg_chart_compact_local import local_planner as decoder
from studies.table_library_sources import core
from studies.table_library_sources.run import verify

OUT = build.OUT
EVAL = OUT/"evaluation"
RESULT = ROOT/"studies/results/public-controller-table-20261123.json"
CONTROL = ROOT/"studies/results/table-local-original-recovery-20261123.json"
OLD = ROOT/"studies/results/table-library-sources-20261123.json"
COMPATIBLE = ROOT/"artifacts/compatible-library-rebuild-20261123/evaluation"


def bundle(package, plan):
    files = core.render("ai", package, plan)
    manifest = {k: hashlib.sha256(v.encode()).hexdigest() for k,v in files.items()}
    key = digest(manifest)
    folder = EVAL/"pages"/key
    if not folder.exists():
        write_files(folder, files)
    assert source_files(folder) == manifest
    return key


def freeze():
    marker = EVAL/"candidates-sealed.json"
    if marker.exists():
        frozen = read(marker)
        verify(frozen["inputs"])
        return frozen
    if (EVAL/"scores").exists():
        raise ValueError("Official scoring must follow the candidate seal")
    sealed = read(OUT/"sealed.json")
    reg = read(OUT/"registered.json")
    public = read(OUT/"public.json")
    assert reg["protocol_sha256"] == sha(build.HERE/"PROTOCOL.md")
    assert reg["builder_sha256"] == sha(Path(build.__file__))
    assert reg["schema_sha256"] == sha(OUT/"response-schema.json")
    assert reg["public_sha256"] == sha(OUT/"public.json") and sealed["registered_sha256"] == sha(OUT/"registered.json")
    assert public == {"requirements":core.requirements("table"),"starter":core.starter()}
    paths = [OUT/f for f in ("sealed.json","registered.json","public.json","response-schema.json")]
    paths += [build.HERE/"PROTOCOL.md", Path(build.__file__), Path(planning.__file__), Path(__file__), Path(decoder.__file__),
              ROOT/"studies/library_refinement_table/adapter.py", ROOT/"studies/browser_jobs.py", ROOT/"studies/interface_blind/compile.cjs",
              ROOT/"studies/webbench_expand/core.py", ROOT/"studies/webbench_expand/schema.py", Path(core.__file__),
              ROOT/"studies/compatible_library_rebuild/sealed_evaluate_20261123.py", ROOT/"artifacts/webbench-expand-runtime-157/package-lock.json"]
    paths += [p for p in (core.SOURCE/"test").rglob("*") if p.is_file()]
    packages, sessions, runs = {},set(),{}
    for arm in build.ARMS:
        dest = OUT/arm
        status=read(dest/"status.json")
        assert sealed["status"][arm]==status and reg["prompt_sha256"][arm]==status["prompt_sha256"]==sha(dest/"prompt.txt")
        assert (dest/"prompt.txt").read_text() == build.PROMPT+"\n"+json.dumps(public,ensure_ascii=False)
        paths.extend([dest/"status.json",dest/"prompt.txt"])
        for f in ("reply.json","events.jsonl"):
            if f+"_sha256" in status:
                assert status[f+"_sha256"]==sha(dest/f)
                paths.append(dest/f)
        if status["status"] != "accepted":
            assert status["status"]=="failed"
            continue
        ev=[json.loads(x) for x in (dest/"events.jsonl").read_text().splitlines() if x]
        assert [e["thread_id"] for e in ev if e["type"]=="thread.started"] == [status["session"]]
        assert status["session"] not in sessions
        sessions.add(status["session"])
        assert [e["usage"] for e in ev if e["type"]=="turn.completed"]==status["usage"] and len(status["usage"])==1
        assert not [e for e in ev if "item" in e and e["item"].get("type") not in ("agent_message","reasoning","plan")]
        p=read(dest/"package.json")
        assert p==build.package(read(dest/"reply.json"),public) and sha(dest/"package.json")==status["package_sha256"]
        paths.append(dest/"package.json")
        q=dest/"planning"
        gen=read(q/"local-generation.json")
        cfg=read(q/"local-inputs.json")
        prereg=read(q/"registered.json")["inputs"]
        assert prereg["source_sha256"]==sha(Path(planning.__file__)) and prereg["package_sha256"]==status["package_sha256"]
        assert prereg["parent_seal_sha256"]==sha(OUT/"sealed.json") and gen["inputs_sha256"]==sha(q/"local-inputs.json")
        assert gen["requests_to_remote_apis"]==0 and cfg["model"]==decoder.MODEL and cfg["revision"]==decoder.REVISION
        assert cfg["batch_size"]==1 and cfg["worker_sha256"]==prereg["worker_sha256"]==sha(Path(decoder.__file__))
        assert cfg["generation_config"]==prereg["generation_config"]==decoder.GENERATION
        paths += [q/f for f in ("registered.json","local-generation.json","local-inputs.json")]
        if (q/"scheduler-admission.json").exists():
            admission=read(q/"scheduler-admission.json")
            sched=ROOT/"studies/svg_chart_compact_local/shared_worker.py"
            assert admission["scheduler_sha256"]==sha(sched) and admission["worker_sha256"]==cfg["worker_sha256"]
            assert admission["admission_sha256"]==sha(q/"scheduler-ready.json")
            paths += [q/"scheduler-admission.json",q/"scheduler-ready.json",sched]
        packages[arm]=p
        rows={}
        for n,task in enumerate(core.TASKS,1):
            prompt=q/"prompts"/(task+".json")
            expect={"requirements":public["requirements"][:n+1],"starter":public["starter"],"plan_schema":p["plan_schema"],
                    "documentation":p["plan_documentation"],"examples":p["examples"]}
            assert read(prompt)==[{"role":"system","content":planning.SYSTEM},
                                  {"role":"user","content":json.dumps(expect,ensure_ascii=False)}]
            assert cfg["prompt_sha256"][str(n)]==prereg["prompt_sha256"][prompt.name]==sha(prompt)
            paths.append(prompt)
            receipt=q/"runs"/task/"response.json"
            if str(n) not in gen["response_sha256"]:
                assert not receipt.exists()
                rows[task]={"status":"missing_response","reason":"No sealed response"}
                continue
            paths.append(receipt)
            r=read(receipt)
            assert gen["response_sha256"][str(n)]==sha(receipt) and r["prompt_sha256"]==sha(prompt)
            assert r["task"]==n and r["model"]==cfg["model"] and r["revision"]==cfg["revision"]
            assert r["generation_config"]==cfg["generation_config"] and r["output_tokens"]==len(r["generated_token_ids"])
            assert r["complete"]==(r["finish_reason"] in ("stop","length"))
            row={"status":"missing_response","receipt_sha256":sha(receipt),"finish_reason":r["finish_reason"]}
            if r["complete"]:
                try:
                    plan=parse_json(r["text"])
                    page=bundle(p,plan)
                except (ValueError,KeyError,TypeError) as err:
                    row.update(status="invalid", reason=str(err)[:300])
                else:
                    row.update(status="valid", plan=plan, page=page)
            rows[task]=row
        runs[arm]=rows
    fixed={a:bundle(p,p["examples"][0]["plan"]) for a,p in packages.items()}
    frozen={"sealed":now(),"build_status":sealed["status"],"runs":runs,"fixed":fixed,
            "inputs":{str(p.relative_to(ROOT)):sha(p) for p in paths}}
    dump(marker,frozen)
    return frozen


def jobs(frozen):
    result={}
    for arm,rows in frozen["runs"].items():
        for task,row in rows.items():
            keys={frozen["fixed"][arm]}
            if row["status"]=="valid":
                keys.add(row["page"])
            for key in keys:
                folder=EVAL/"pages"/key
                assert digest(source_files(folder))==key
                label=task+"-"+key
                result[label]=(label,task,folder)
    return result


def score(frozen, workers):
    dest=EVAL/"scores-complete.json"
    if dest.exists():
        return
    all_jobs=jobs(frozen)
    borrowed=read(COMPATIBLE/"scores-complete.json")["results"] if (COMPATIBLE/"scores-complete.json").is_file() else {}
    pending=[]; evidence={}
    for label,task,page in all_jobs.values():
        if label in borrowed:
            assert source_files(COMPATIBLE/"pages"/page.name)==source_files(page)
            q=ROOT/borrowed[label]["report_file"]
            assert borrowed[label]==score_entry(q.parent,task)
            evidence[label]=borrowed[label]
        else:
            pending.append((label,task,page))
    if pending:
        score_pages(EVAL,pending,workers=workers)
    for label,task,_ in pending:
        evidence[label]=score_entry(EVAL/"scores"/label,task)
    dump(dest,{"sealed":now(),"candidates_sha256":sha(EVAL/"candidates-sealed.json"),"reports":evidence})


def report(frozen):
    scored=read(EVAL/"scores-complete.json")
    assert scored["candidates_sha256"]==sha(EVAL/"candidates-sealed.json")
    all_jobs=jobs(frozen)
    assert set(all_jobs)==set(scored["reports"])
    for key,task,page in all_jobs.values():
        item=scored["reports"][key]
        path=ROOT/item["report_file"]
        assert path.parent.name==key and path.name=="report.json" and score_entry(path.parent,task)==item
    old=read(CONTROL)
    verify(old["inputs"])
    hist=read(OLD)
    assert sum(e["ai"]["first"]["passed"] is True for e in hist["targets"].values())==3
    assert set(old["targets"])==set(core.TASKS) and old["observed"]==20 and old["planner"]==decoder.MODEL
    result={}
    metrics=("strict","recovered","fixed")
    for arm in build.ARMS:
        rows={}
        for task in core.TASKS:
            if arm not in frozen["runs"]:
                rows[task]={"status":"preparation_failed","strict":None,"recovered":None,"fixed":None,"used_fallback":False}
                continue
            row=frozen["runs"][arm][task]
            fx=scored["reports"][task+"-"+frozen["fixed"][arm]]
            valid=row["status"]=="valid"
            invalid=row["status"]=="invalid"
            strict=scored["reports"][task+"-"+row["page"]] if valid else None
            passed=strict["passed"] if valid else (False if invalid else None)
            rows[task]={**row,"strict":passed,"used_fallback":invalid,"recovered":fx["passed"] if invalid else passed,
                        "fixed":fx["passed"],"fixed_page":frozen["fixed"][arm],"fixed_report_sha256":fx["report_sha256"],
                        "plan_report_sha256":strict["report_sha256"] if valid else None}
        summary={metric:{"passed":sum(row[metric] is True for row in rows.values()) if any(row[metric] is not None for row in rows.values()) else None,
                         "observed":sum(row[metric] is not None for row in rows.values())} for metric in metrics}
        result[arm]={"targets":rows,"summary":summary,"planned":len(rows),
                     "valid":sum(r["status"]=="valid" for r in rows.values()),"invalid_used_fallback":sum(r["used_fallback"] for r in rows.values()),
                     "missing_response":sum(r["status"]=="missing_response" for r in rows.values()),
                     "preparation_blocked":sum(r["status"]=="preparation_failed" for r in rows.values()),
                     "distinct_valid_plans":len({digest(r["plan"]) for r in rows.values() if r["status"]=="valid"})}
        paired={}
        for metric in metrics:
            left={t:{"passed":old["targets"][t][metric]} for t in rows}
            right={t:{"passed":r[metric]} for t,r in rows.items()}
            paired[metric]=four_cells(left,right)
        result[arm]["paired_vs_original_qwen"]=paired
        result[arm]["eligible"]=frozen["build_status"][arm]["status"]=="accepted" and summary["strict"]["observed"]==20 and (
            summary["strict"]["passed"]>max(3,old["totals"]["strict"]) and summary["recovered"]["passed"]>old["totals"]["recovered"])
    return {"study":OUT.name,"project":"table","library_builder":build.MODEL,"planner":decoder.MODEL,"planner_revision":decoder.REVISION,
            "builds":frozen["build_status"],"repeats":result,"original_qwen":{"observed":old["observed"],"totals":old["totals"],"source_sha256":sha(CONTROL)},
            "historical_mistral":{"passed":3,"observed":20,"source_sha256":sha(OLD)},
            "confirmation":{"qualified_for_retesting":all(r["eligible"] for r in result.values()),"rule":"Both independent accepted public-only builds must receive 20 plans, each strict count above both 3 and the original Qwen count, and recovered count above the original Qwen recovery."},
            "limitations":"Registered after observing prior compatible-backend totals. Both repetitions use identical project targets. The builder model, upstream information, interface and implementation changed; default-example, recovered, and strict selection outcomes are distinct.",
            "verification":{"build_seal_sha256":sha(OUT/"sealed.json"),"candidate_seal_sha256":sha(EVAL/"candidates-sealed.json"),
                            "score_seal_sha256":sha(EVAL/"scores-complete.json"),"score_sealed_utc":scored["sealed"],
                            "unique_official_reports":len(all_jobs),"remote_api_requests":0}}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode",choices=("freeze","score","report","check"))
    p.add_argument("--workers",type=int,default=2)
    args=p.parse_args()
    if args.mode=="check" and not (EVAL/"candidates-sealed.json").exists():
        raise ValueError("Missing candidate seal")
    m=freeze()
    if args.mode=="score":
        score(m,args.workers)
    if args.mode in ("report","check"):
        result=report(m)
        if args.mode=="report" and not RESULT.exists():
            dump(RESULT,result)
        else:
            assert read(RESULT)==result
        print({a:v["summary"] for a,v in result["repeats"].items()},result["confirmation"])
