"""Score three table interfaces under a fixed field-wise constrained decoder."""
import argparse
import json
import math
import re
from hashlib import sha256
from pathlib import Path

from studies.compatible_library_rebuild.sealed_evaluate_20261123 import four_cells, score_entry
from studies.interface_blind.core import write_files
from studies.library_refinement_table.adapter import score_pages
from studies.public_controller_build import build
from studies.schema_constrained_table import generate
from studies.study_io import ROOT, digest, dump, now, read, sha, source_files
from studies.table_library_sources import core
from studies.table_library_sources.run import verify
from studies.webbench_expand.schema import validate

HERE=Path(__file__).resolve().parent
OUT=ROOT/"artifacts/schema-constrained-table-20261123"
EVAL=OUT/"evaluation"
RESULT=ROOT/"studies/results/schema-constrained-table-20261123.json"
ORIGINAL=ROOT/"studies/results/table-local-original-recovery-20261123.json"
PUBLIC=ROOT/"studies/results/public-controller-table-20261123.json"
HISTORICAL=ROOT/"studies/results/table-library-sources-20261123.json"
COMPATIBLE=ROOT/"artifacts/compatible-library-rebuild-20261123/evaluation"
LOCAL=ROOT/"artifacts/compatible-table-local-plans-20261123/evaluation"
ARMS=("original",*build.ARMS)


def rel(path):
    return str(path.relative_to(ROOT))


def package_file(arm):
    return core.AI if arm=="original" else build.OUT/arm/"package.json"


def full_plan(schema,value):
    """Check that each optional leaf has a genuine boolean/enum value in the sealed plan."""
    validate(schema,value)
    if schema["type"]=="object":
        assert set(schema["properties"])==set(value)
        return sum(full_plan(child,value[k]) for k,child in schema["properties"].items())
    assert schema["type"] in ("boolean","string") and (schema["type"]=="boolean" or "enum" in schema)
    return 1


def page(package,plan):
    files=core.render("ai",package,plan)
    hashes={key:sha256(v.encode()).hexdigest() for key,v in files.items()}
    signature=digest(hashes)
    dest=EVAL/"pages"/signature
    if not dest.exists():
        write_files(dest,files)
    assert source_files(dest)==hashes
    return signature


def value_encoder(tokenizer):
    """Exact byte-level BPE for the ASCII-only JSON grammar and identifiers in this study."""
    vocab=tokenizer["model"]["vocab"]
    ranks={tuple(pair.split(" ")):i for i,pair in enumerate(tokenizer["model"]["merges"])}
    cache={}
    def encode(fragment):
        if fragment not in cache:
            assert fragment.isascii() and not any(c.isspace() for c in fragment)
            pieces=re.findall(r"[^A-Za-z0-9\s]?[A-Za-z]+|[0-9]|[^A-Za-z0-9\s]+",fragment)
            assert "".join(pieces)==fragment
            ids=[]
            for piece in pieces:
                units=list(piece)
                while len(units)>1:
                    choices=[(ranks[pair],n) for n,pair in enumerate(zip(units,units[1:])) if pair in ranks]
                    if not choices:
                        break
                    _,n=min(choices)
                    units[n:n+2]=[units[n]+units[n+1]]
                ids.extend(vocab[v] for v in units)
            cache[fragment]=ids
        return cache[fragment]
    return encode


def replay_tokens(schema,plan,receipt,encode):
    branches=iter(receipt["decisions"])
    emitted=[]
    def visit(node,value,path):
        if node["type"]=="object":
            emitted.extend(encode("{"))
            for i,(key,child) in enumerate(node["properties"].items()):
                emitted.extend(encode(("," if i else "")+json.dumps(key)+":"))
                visit(child,value[key],path+"."+key)
            emitted.extend(encode("}"))
            return
        options=[True,False] if node["type"]=="boolean" else node["enum"]
        seqs=[encode(json.dumps(v)) for v in options]
        chosen=[]
        while any(seqs):
            assert all(seqs)
            edges=sorted({s[0] for s in seqs})
            if len(edges)>1:
                branch=next(branches)
                logits=branch["logits"]
                assert branch["field"]==path and branch["tokens"]==edges
                assert len(logits)==len(edges) and all(math.isfinite(v) for v in logits)
                token=edges[max(range(len(edges)),key=logits.__getitem__)]
                assert token==branch["selected"]
            else:
                token=edges[0]
            chosen.append(token)
            seqs=[seq[1:] for seq in seqs if seq[0]==token]
        assert chosen==encode(json.dumps(value))
        emitted.extend(chosen)
    visit(schema,plan,"$")
    assert next(branches,None) is None and emitted==receipt["generated_token_ids"]
    assert json.loads(receipt["response"])==plan


def verify_generation(seal,registration,rows,paths):
    assert seal["registered_sha256"]==sha(OUT/"registered.json") and seal["environment_sha256"]==sha(OUT/"environment.json")
    assert registration["generator_sha256"]==sha(Path(generate.__file__))
    assert registration["protocol_sha256"]==sha(HERE/"PROTOCOL.md") and tuple(registration["arms"])==ARMS
    assert seal["requests_to_remote_apis"]==0 and registration["registered"]<=seal["sealed"]
    verify(registration["sources"])
    paths += [ROOT/p for p in registration["sources"]]
    paths += [Path(generate.__file__),OUT/"environment.json"]
    interruption=OUT/"first-process-interruption.json"
    if interruption.exists():
        paths.extend((interruption,HERE/"recover.py"))
        event=read(interruption)
        assert not event["completed_before_stop"] and registration["registered"]<=event["utc"]<=seal["sealed"]
    env=read(OUT/"environment.json")
    assert env["model"]==registration["model"]==generate.MODEL and env["revision"]==registration["revision"]==generate.REVISION
    tokenfile=generate.SNAPSHOT/"tokenizer.json"
    assert sha(tokenfile)==env["weights_sha256"]["tokenizer.json"]
    encode=value_encoder(read(tokenfile))
    expected={}
    for arm in ARMS:
        host,pkgpath=generate.source(arm)
        assert pkgpath==package_file(arm)
        schema=read(pkgpath)["plan_schema"]
        for index,task in enumerate(core.TASKS,1):
            q=OUT/arm/(task+".json")
            r=read(q)
            prev=host/"runs"/task/"response.json"
            paths.append(prev)
            orig=read(prev)
            assert (r["model"],r["revision"],r["arm"],r["task"],r["complete"])==(generate.MODEL,generate.REVISION,arm,index,True)
            assert r["input_token_ids_sha256"]==orig["input_ids_sha256"] and r["input_tokens"]==orig["input_tokens"]
            assert r["package_sha256"]==sha(pkgpath) and r["prompt_sha256"]==sha(host/"prompts"/(task+".json"))
            assert registration["registered"]<=r["utc"]<=seal["sealed"]
            replay_tokens(schema,rows[arm][task]["plan"],r,encode)
            expected[str(q.relative_to(OUT))]=sha(q)
    assert expected==seal["response_sha256"]


def freeze():
    path=EVAL/"candidates-sealed.json"
    if path.exists():
        m=read(path)
        verify(m["inputs"])
        return m
    if (EVAL/"scores").exists():
        raise ValueError("Official test reports predate candidate seal")
    generation=read(OUT/"sealed.json")
    registration=read(OUT/"registered.json")
    paths=[HERE/"PROTOCOL.md",Path(__file__),OUT/"registered.json",OUT/"sealed.json",build.OUT/"sealed.json",
           Path(core.__file__),ROOT/"studies/browser_jobs.py",ROOT/"studies/library_refinement_table/adapter.py",
           ROOT/"studies/interface_blind/compile.cjs",ROOT/"studies/webbench_expand/core.py",ROOT/"studies/webbench_expand/schema.py",
           ROOT/"artifacts/webbench-expand-runtime-157/package-lock.json", ROOT/"studies/compatible_library_rebuild/sealed_evaluate_20261123.py",
           ORIGINAL,PUBLIC,HISTORICAL]
    paths += [p for p in (core.SOURCE/"test").rglob("*") if p.is_file()]
    rows,fixed={}, {}
    for arm in ARMS:
        pkgpath=package_file(arm)
        paths.append(pkgpath)
        pkg=read(pkgpath)
        if arm in build.ARMS:
            assert sha(pkgpath)==read(build.OUT/"sealed.json")["status"][arm]["package_sha256"]
        fixed[arm]=page(pkg,pkg["examples"][0]["plan"])
        rows[arm]={}
        for task in core.TASKS:
            f=OUT/arm/(task+".json")
            assert f.exists(), "All sixty responses must be sealed before scoring"
            paths.append(f)
            receipt=read(f)
            plan=receipt["plan"]
            count=full_plan(pkg["plan_schema"],plan)
            candidate=page(pkg,plan)
            rows[arm][task]={"plan":plan,"fields_chosen":count,"page":candidate,"receipt_sha256":sha(f)}
    verify_generation(generation, registration, rows, paths)
    m={"sealed":now(),"inputs":{rel(f):sha(f) for f in paths},"rows":rows,"fixed":fixed}
    dump(path,m)
    return m


def jobs(manifest):
    out={}
    for arm,rows in manifest["rows"].items():
        for task,row in rows.items():
            for signature in {row["page"],manifest["fixed"][arm]}:
                folder=EVAL/"pages"/signature
                assert digest(source_files(folder))==signature
                label=task+"-"+signature
                out[label]=(label,task,folder)
    return out


def old_scores():
    scores={}
    for out, name, field in [(build.OUT/"evaluation","scores-complete.json","reports"),
                              (COMPATIBLE,"scores-complete.json","results"), (LOCAL,"scored.json","reports")]:
        marker=out/name
        if not marker.is_file():
            continue
        data=read(marker)
        for key,r in data[field].items():
            report_file=r["report_file"] if isinstance(r,dict) else r
            scores.setdefault(key, (out, ROOT/report_file, r if isinstance(r,dict) else None, marker))
    return scores


def score(m,workers):
    path=EVAL/"scores-complete.json"
    if path.exists():
        return
    old=old_scores()
    pending=[]
    reports={}
    sources={}
    for job,task,folder in jobs(m).values():
        if job not in old:
            pending.append((job,task,folder))
            continue
        d,r,rec,marker=old[job]
        assert source_files(d/"pages"/folder.name)==source_files(folder)
        entry=score_entry(r.parent,task)
        assert rec is None or rec==entry
        reports[job]=entry
        sources[rel(marker)]=sha(marker)
    if pending:
        score_pages(EVAL,pending,workers=workers)
    for job,task,_ in pending:
        reports[job]=score_entry(EVAL/"scores"/job,task)
    dump(path,{"sealed":now(),"candidate_seal_sha256":sha(EVAL/"candidates-sealed.json"),
               "reused_score_sources":sources,"new_official_reports":len(pending),"reports":reports})


def row_metric(rows,name):
    return {t:{"passed":r[name]} for t,r in rows.items()}


def report(m):
    sc=read(EVAL/"scores-complete.json")
    assert sc["candidate_seal_sha256"]==sha(EVAL/"candidates-sealed.json")
    verify(sc["reused_score_sources"])
    all_jobs=jobs(m)
    assert set(sc["reports"])==set(all_jobs)
    for key,task,folder in all_jobs.values():
        entry=sc["reports"][key]
        r=ROOT/entry["report_file"]
        assert r.parent.name==key and r.name=="report.json" and score_entry(r.parent,task)==entry
    f=read(PUBLIC)
    original=read(ORIGINAL)
    verify(original["inputs"])
    assert original["observed"]==20 and sum(r["ai"]["first"]["passed"] is True for r in read(HISTORICAL)["targets"].values())==3
    refs={"original":original["targets"],**{a:f["repeats"][a]["targets"] for a in build.ARMS}}
    arms={}
    for a in ARMS:
        targets={}
        for task,r in m["rows"][a].items():
            item=sc["reports"][task+"-"+r["page"]]
            fx=sc["reports"][task+"-"+m["fixed"][a]]
            ref=refs[a][task]
            assert fx["passed"]==ref["fixed"]
            targets[task]={**r,"strict":item["passed"],"fixed":fx["passed"],"free_strict":ref["strict"],
                           "free_recovered":ref["recovered"],"official_report_sha256":item["report_sha256"],
                           "fixed_page":m["fixed"][a],"fixed_report_sha256":fx["report_sha256"]}
        arms[a]={"targets":targets,"received":len(targets),"valid":len(targets),
                 "distinct_plans":len({digest(r["plan"]) for r in targets.values()}),
                 "page_equal_to_fixed":sum(r["page"]==m["fixed"][a] for r in targets.values()),
                 "passed":{k:sum(r[k] is True for r in targets.values()) for k in ("strict","fixed","free_strict","free_recovered")},
                 "paired_vs_own_free_strict":four_cells(row_metric(targets,"free_strict"),row_metric(targets,"strict")),
                 "paired_vs_own_fixed":four_cells(row_metric(targets,"fixed"),row_metric(targets,"strict"))}
    eligible={}
    baseline=arms["original"]["passed"]["strict"]
    for a in build.ARMS:
        pv=arms[a]["passed"]
        arms[a]["paired_vs_constrained_original"]=four_cells(row_metric(arms["original"]["targets"],"strict"),
                                                             row_metric(arms[a]["targets"],"strict"))
        eligible[a]=arms[a]["valid"]==20 and pv["strict"]>max(baseline,3) and pv["strict"]>=pv["free_strict"]
    improved=any(arms[a]["passed"]["strict"]>arms[a]["passed"]["free_strict"] for a in build.ARMS)
    return {"study":OUT.name,"project":"table","builder_by_arm":{"original":"openai/gpt-5",**{a:build.MODEL for a in build.ARMS}},
            "planner":f["planner"],"planner_revision":f["planner_revision"],"arms":arms,
            "historic_mistral_original":{"passed":3,"observed":20,"source_sha256":sha(HISTORICAL)},
            "confirmation":{"per_new_library_gate":eligible,"at_least_one_strictly_above_own_free":improved,
                            "qualified_for_retesting": all(eligible.values()) and improved,
                            "rule":"Each independent new library must receive 20 valid genuine selections, beat historical 3/20 and "
                                   "the current constrained original library, and match or exceed its free strict result. "
                                   "One or both must strictly improve over their own free strict result."},
            "limitations":"Preregistered after observing failures of unconstrained parsing on this same benchmark. Model selects each "
                          "boolean or enum value while the decoder fixes the JSON structure and field order. The two independent "
                          "libraries share the same 20 target IDs. Other field types and project-specific transfer are untested.",
            "verification":{"candidate_seal_sha256":sc["candidate_seal_sha256"], "generation_seal_sha256":sha(OUT/"sealed.json"),
                            "official_reports":len(all_jobs),"fresh_official_reports":sc["new_official_reports"],
                            "report_seal_sha256":sha(EVAL/"scores-complete.json"),"score_sealed_utc":sc["sealed"],
                            "free_baseline_sources":{rel(p):sha(p) for p in (PUBLIC,ORIGINAL)},"additional_api_cost_usd":0,
                            "inference_interruption":read(OUT/"first-process-interruption.json") if (OUT/"first-process-interruption.json").exists() else None}}


if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode",choices=("freeze","score","report","check"))
    ap.add_argument("--workers",type=int,default=3)
    args=ap.parse_args()
    if args.mode=="check" and not (EVAL/"candidates-sealed.json").exists():
        raise ValueError("No sealed candidates")
    frozen=freeze()
    if args.mode=="check":
        verify_generation(read(OUT/"sealed.json"),read(OUT/"registered.json"),frozen["rows"],[])
        for arm, rows in frozen["rows"].items():
            pkg=read(package_file(arm))
            plans=[(r["page"],r["plan"]) for r in rows.values()]
            plans.append((frozen["fixed"][arm],pkg["examples"][0]["plan"]))
            for signature,plan in plans:
                files=core.render("ai",pkg,plan)
                hashes={n:sha256(v.encode()).hexdigest() for n,v in files.items()}
                assert signature==digest(hashes) and source_files(EVAL/"pages"/signature)==hashes
    if args.mode=="score":
        score(frozen,args.workers)
    if args.mode in ("report","check"):
        study=report(frozen)
        if args.mode=="report" and not RESULT.exists():
            dump(RESULT,study)
        else:
            assert read(RESULT)==study
        print({a:v["passed"] for a,v in study["arms"].items()},study["confirmation"])
