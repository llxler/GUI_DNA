"""Verify delivered Direct pages, score only changed current targets, and pair with frozen libraries."""
import argparse
import json
from pathlib import Path
import subprocess

from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, digest, read, sha
from ..report import normalize, paired, per_arm

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/qwen-svg-source-delivery-20261124"
BASE = ROOT / "artifacts/qwen-svg-renderers-20261124"
RAW = HERE.parent / "result.json"
PUBLISHED = HERE / "result.json"
COMPARISONS = HERE / "comparisons.json"
TARGETS = tuple(range(1, 21))
SCOPES = {"original": RAW, "linked": HERE.parent / "module_linking/result.json",
          "runtime_patch": HERE.parent / "runtime_patch/result.json", "dom_tokens": HERE.parent / "dom_tokens/result.json"}


def verify_seal():
    reg = read(OUT / "registration.json")
    seal = read(OUT / "seal.json")
    if seal["registration_sha256"] != sha(OUT / "registration.json"):
        raise ValueError("Delivery registration changed")
    for name, stamp in reg["sources"].items():
        if sha(ROOT / name) != stamp:
            raise ValueError("Frozen parser, inputs or source SHA changed")
    for name, stamp in reg["responses"].items():
        if sha(BASE / name) != stamp:
            raise ValueError("Original provider response changed")
    for name, stamp in seal["candidate_records_sha256"].items():
        if sha(OUT / name) != stamp:
            raise ValueError("Public selection record changed")
    return seal


def select_jobs(seal):
    before = read(BASE / "seal.json")
    known = {(r["task"], digest(r["files"])) for r in before["rows"] if r["status"] == "valid"}
    return [r for r in seal["rows"] if r["arm"] == "final" and r["status"] == "valid"
            and (r["task"], digest(r["files"])) not in known]


def score():
    seal = verify_seal()
    jobs = select_jobs(seal)
    contract = browser.verify_contract("svg-chart")
    if contract != read(BASE / "registration.json")["harness"]:
        raise ValueError("Original and delivery scoring contracts differ")
    measured = browser.evaluate(jobs, OUT, {"svg-chart": contract}, 4)
    records = [{"task":r["task"], "page_digest":digest(r["files"]), "passed":r["passed"],
                "report_sha256":r["report_sha256"]} for r in measured]
    core.save(OUT / "scores.json", {"seal_sha256":sha(OUT / "seal.json"), "contract_digest":digest(contract),
              "new_final_pages":records})
    print("New current-target browser receipts", len(records), flush=True)


def as_column(rows):
    return {r["task"]: {"passed":normalize(r)[0], "classification":normalize(r)[1]} for r in rows}


def matrix(rows, direct):
    endpoints = {}
    for group in ("A", "B"):
        endpoints[group] = {}
        for arm in ("planned","fixed"):
            select = [r for r in rows if r["group"] == group and r["arm"] == arm]
            if {r["task"] for r in select} != set(TARGETS) or len(select) != len(TARGETS):
                raise ValueError("Missing Self or fixed target positions")
            column = as_column(select)
            endpoints[group][arm] = {"vs_delivered_direct":paired(column, direct),
                                    "vs_delivered_direct_excluding_asset":paired(column, direct, TARGETS[1:])}
    return endpoints


def output():
    seal = verify_seal()
    raw = read(RAW)
    strict_rows = [r for r in raw["rows"] if r["group"] == "direct" and r["arm"] == "final"]
    baseline = as_column(strict_rows)
    old_pages = {}
    for row in raw["rows"]:
        if row["status"] == "valid":
            key = row["task"], row["page_digest"]
            outcome = row["passed"], row["report_sha256"]
            if key in old_pages and old_pages[key] != outcome:
                raise ValueError("Same original target/page has contradictory receipts")
            old_pages[key] = outcome
    scored = read(OUT / "scores.json")
    if scored["seal_sha256"] != sha(OUT / "seal.json"):
        raise ValueError("Scores are not from the frozen Direct pages")
    new_pages = {(r["task"],r["page_digest"]):(r["passed"],r["report_sha256"]) for r in scored["new_final_pages"]}
    jobs = select_jobs(seal)
    contract = digest(browser.verify_contract("svg-chart"))
    if set(new_pages) != {(r["task"],digest(r["files"])) for r in jobs} or contract != scored["contract_digest"]:
        raise ValueError("New browser scores do not cover exactly the changed page-target pairs")
    for row in jobs:
        task, page = row["task"], digest(row["files"])
        browser.verify_page(ROOT / row["page"], row["files"], "svg-chart")
        expected = {"task":task, "project":"svg-chart", "files_digest":page, "contract_digest":contract}
        path = OUT / "browser/scores/svg-chart" / f"task-{task}" / page / "score.json"
        receipt = browser.verify_receipt(OUT, path, expected)
        if (receipt["passed"],receipt["report_sha256"]) != new_pages[task,page]:
            raise ValueError("Changed delivery score differs from its official receipt")
    final = []
    records = []
    for row in (r for r in seal["rows"] if r["arm"] == "final"):
        n = row["task"]
        decision = read(OUT / "direct" / str(n) / "decision.json")
        digest_now = digest(row["files"]) if row["status"] == "valid" else None
        current = {"group":"direct", "arm":"final", "task":n, "status":row["status"], "page_digest":digest_now,
                   "passed":None if row["status"] == "missing" else False, "report_sha256":None}
        if row["status"] == "valid":
            lookup = n,digest_now
            location = "original" if lookup in old_pages else "new"
            pair = old_pages[lookup] if location == "original" else new_pages[lookup]
            current.update(passed=pair[0], report_sha256=pair[1], receipt_source=location)
        final.append(current)
        candidates = []
        for a in decision["candidates"]:
            candidates.append({k:a[k] for k in ("status","delivery","discarded_public_assets","response_sha256","reason",
                        "old_rejection","public") if k in a} | {"files_digest": digest(a["files"]) if a.get("files") else None})
        records.append({"task":n, "strict_final_status":decision["strict_status"],
                        "strict_final_page_digest":digest(decision["strict_files"]) if decision["strict_files"] else None,
                        "selected_attempt":decision["chosen_attempt"], "would_trigger_repair":decision["would_request_public_repair_after_relaxed_first"],
                        "actually_received_second":decision["old_trigger_actually_obtained_second_response"], "attempts":candidates})
    corrected = as_column(final)
    observed = paired(corrected, baseline)
    audit = seal["library_audit"]
    from ..module_linking import run as linker

    module_edits = {}
    for row in (r for r in seal["rows"] if r["arm"] == "final" and r["status"] == "valid"):
        page = ROOT / row["page"]
        scripts = {p:(page/p).read_text() for p in row["files"] if p.endswith((".js",".mjs")) and not p.startswith("assets/")}
        links = json.loads(subprocess.check_output(["node", str(linker.HERE/"link.cjs"), str(linker.PARSER)],
                                                   input=json.dumps(scripts), text=True))
        module_edits[str(row["task"])] = sum(map(len,links.values()))
    return {"model":raw["model"], "project":"svg-chart", "targets":list(TARGETS),
            "remote_calls":0, "additional_api_usd":0, "registered_utc":read(OUT / "registration.json")["utc"], "sealed_utc":seal["utc"],
            "sources_sha256":{str(p.relative_to(ROOT)):sha(p) for p in [HERE/"PROTOCOL.md",HERE/"run.py",HERE/"report.py",RAW,linker.HERE/"link.cjs"]},
            "registration_sha256":sha(OUT/"registration.json"), "seal_sha256":sha(OUT/"seal.json"),
            "scores_sha256":sha(OUT/"scores.json"), "new_browser_targets":sorted(n for n,_ in new_pages),
            "rows":final, "strict_direct_rows":strict_rows, "direct_comparisons":{"recovered_vs_strict":observed,
                    "recovered_vs_strict_excluding_asset":paired(corrected,baseline,TARGETS[1:]),
                    "recovered_observations":per_arm(corrected), "strict_observations":per_arm(baseline)},
            "deliveries":records, "library_audit":audit,
            "declared_module_link_edits_by_delivered_direct_target":module_edits,
            "newly_accepted_library_attempts":[r["sample"] for r in audit if not r["strict_valid"] and r["relaxed_valid"]],
            "original_library_comparisons":matrix(raw["rows"],corrected)}


def check(value):
    for file, stamp in value["sources_sha256"].items():
        if sha(ROOT / file) != stamp:
            raise ValueError("Source-delivery inputs changed")
    raw = read(RAW)
    original = [r for r in raw["rows"] if r["group"] == "direct" and r["arm"] == "final"]
    if original != value["strict_direct_rows"] or len(value["rows"]) != 20 or sorted(r["task"] for r in value["rows"]) != list(TARGETS):
        raise ValueError("Incomplete or unpaired delivery comparison")
    actual, strict = as_column(value["rows"]), as_column(original)
    if (value["direct_comparisons"]["recovered_vs_strict"] != paired(actual,strict)
        or value["direct_comparisons"]["recovered_vs_strict_excluding_asset"] != paired(actual,strict,TARGETS[1:])
        or matrix(raw["rows"], actual) != value["original_library_comparisons"]):
        raise ValueError("Delivery metrics differ from task-level receipts")
    for r in value["rows"]:
        if r["status"] == "valid" and (r.get("receipt_source") not in ("new","original") or len(r["report_sha256"]) != 64):
            raise ValueError("Rendered final Direct has no verified receipt")
    changed = [r["sample"] for r in value["library_audit"] if not r["strict_valid"] and r["relaxed_valid"]]
    if changed != value["newly_accepted_library_attempts"]:
        raise ValueError("Library delivery audit differs")


def compare(which):
    value = read(PUBLISHED)
    check(value)
    direct = as_column(value["rows"])
    selected = {key:path for key,path in SCOPES.items() if key in which}
    if set(selected) != set(which) or "original" not in selected:
        raise ValueError("Select original and each completed library study")
    stages = {}
    for label,path in selected.items():
        rows = read(path)["rows"]
        cohort = {"source_sha256":sha(path), "vs_delivered_direct":matrix(rows,direct)}
        if label == "linked" and any(value["declared_module_link_edits_by_delivered_direct_target"].values()):
            raise ValueError("Delivered Direct requires independent official module-link testing")
        if label in ("runtime_patch", "dom_tokens"):
            comparator = "delivery" if label == "dom_tokens" else "final"
            arm = as_column([r for r in rows if r["group"] == "direct" and r["arm"] == comparator])
            cohort.update(stage_direct_arm=f"direct/{comparator}", vs_stage_direct=matrix(rows,arm))
        stages[label] = cohort
    return {"direct_sha256":sha(PUBLISHED), "direct_arm":"Recovered original responses on unmodified public assets",
            "targets":list(TARGETS), "stages":stages,
            "scope":"For the paid runtime patch, the stage Direct received the same optional repair as Self on emitted "
                    "pages. Source delivery also recovers originally rejected Direct pages, for which that paid repair "
                    "was unavailable. The DOM-token stage applies its public error-triggered rewrite to recovered Direct."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action",choices=["score","publish","check","check-local","compare","check-comparisons"])
    parser.add_argument("--stages", nargs="+", choices=list(SCOPES), default=list(SCOPES))
    args = parser.parse_args()
    if args.action == "score":
        score()
        return
    if args.action == "compare":
        core.save(COMPARISONS,compare(args.stages))
        return
    if args.action == "check-comparisons":
        stored = read(COMPARISONS)
        if stored != compare(stored["stages"]):
            raise ValueError("Cross-stage paired populations changed")
        return
    if args.action == "publish":
        new = output()
        check(new)
        core.save(PUBLISHED,new)
    else:
        new = read(PUBLISHED)
        check(new)
        if args.action == "check-local" and new != output():
            raise ValueError("Published Direct differs from raw evidence")
    p = new["direct_comparisons"]["recovered_vs_strict"]
    print("Recovered Direct vs original",len(p["left_passed"]),len(p["right_passed"]),len(p["common_targets"]))


if __name__ == "__main__":
    main()
