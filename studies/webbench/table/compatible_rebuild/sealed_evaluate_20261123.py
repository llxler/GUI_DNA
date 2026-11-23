"""Replay frozen first responses against independently rebuilt compatible table libraries."""
import argparse
import json
from hashlib import sha256
from pathlib import Path

from gui_dna.provider import parse_json
from studies.compatible_library_rebuild import build
from studies.interface_blind.core import write_files
from studies.library_refinement_table import run as previous
from studies.library_refinement_table.adapter import score_pages
from studies.study_io import ROOT, cases_by_file, digest, dump, now, read, sha, source_files
from studies.table_library_sources import core
from studies.table_library_sources.run import verify
from studies.webbench_expand.core import compile_plan

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/compatible-library-rebuild-20261123"
EVAL = OUT / "evaluation"
REPORT = ROOT / "studies/results/compatible-library-rebuild-20261123.json"
ARMS = ("plain-1", "contract-1", "plain-2", "contract-2")
ALL = ("original", *ARMS)


def track(evidence, path):
    evidence[previous.rel(path)] = sha(path)


def page_bundle(files):
    hashes = {n: sha256(v.encode()).hexdigest() for n, v in files.items()}
    key = digest(hashes)
    path = EVAL / "pages" / key
    if not path.exists():
        write_files(path, files)
    assert source_files(path) == hashes
    return key


def deploy(cohort, package, plan):
    if cohort == previous.COHORTS[0]:
        return core.render("ai", package, plan)
    return compile_plan(package, plan)


def freeze_candidates():
    path = EVAL / "candidates-sealed.json"
    if path.exists():
        manifest = read(path)
        verify(manifest["inputs"])
        return manifest
    if (EVAL / "scores").exists():
        raise ValueError("Cannot freeze new candidates after official scoring")
    original = read(core.AI)
    packages = {"original": original}
    evidence = previous.archive_inputs()
    for f in (OUT / "sealed.json", OUT / "registered.json", OUT / "public.json", OUT / "response-schema.json",
              HERE / "PROTOCOL.md", HERE / "build.py", HERE / "evaluate.py"):
        track(evidence, f)
    seal = read(OUT / "sealed.json")
    registration = read(OUT / "registered.json")
    assert seal["registered_sha256"] == sha(OUT / "registered.json")
    assert registration["public_sha256"] == sha(OUT / "public.json")
    assert registration["response_schema_sha256"] == sha(OUT / "response-schema.json")
    assert registration["protocol_sha256"] == sha(HERE / "PROTOCOL.md")
    assert registration["builder_sha256"] == sha(HERE / "build.py")
    assert tuple(registration["arms"]) == ARMS and set(seal["status"]) == set(ARMS)
    public = read(OUT / "public.json")
    assert public == build.public_inputs() and read(OUT / "response-schema.json") == build.SCHEMA
    assert registration["model"] == build.MODEL
    statuses = {}
    usage = {}
    sessions = {}
    for arm in ARMS:
        dest = OUT / arm
        status_path = dest / "status.json"
        track(evidence, status_path)
        status = read(status_path)
        assert status == seal["status"][arm] and status["model"] == build.MODEL and status["effort"] == "medium"
        prompt = dest / "prompt.txt"
        track(evidence, prompt)
        assert registration["prompt_sha256"][arm] == sha(prompt) == status["prompt_sha256"]
        instruction = build.CONTRACT if arm.startswith("contract") else build.PLAIN
        assert prompt.read_text() == build.COMMON + "\n" + instruction + "\n" + json.dumps(public, ensure_ascii=False)
        assert registration["registered"] <= status["started"] <= status["finished"] <= seal["sealed"]
        events_path = dest / "events.jsonl"
        track(evidence, events_path)
        events = [json.loads(line) for line in events_path.read_text().splitlines() if line.strip()]
        sessions[arm] = [e["thread_id"] for e in events if e["type"] == "thread.started"]
        if "reply_sha256" in status:
            track(evidence, dest / "reply.json")
            assert sha(dest / "reply.json") == status["reply_sha256"]
        statuses[arm] = status["status"]
        usage[arm] = [e["usage"] for e in events if e["type"] == "turn.completed"]
        if statuses[arm] == "accepted":
            package_path = dest / "package.json"
            track(evidence, package_path)
            assert status["package_sha256"] == sha(package_path)
            assert len(sessions[arm]) == 1
            assert usage[arm] and usage[arm] == status["usage"]
            assert not [e for e in events if isinstance(e.get("item"), dict)
                        and e["item"].get("type") not in ("agent_message", "reasoning", "plan")]
            package = read(package_path)
            assert package == build.build_package(read(dest / "reply.json"), public)
            for field in ("plan_schema", "plan_documentation", "examples"):
                assert package[field] == original[field], (arm, field)
            packages[arm] = package
        else:
            assert statuses[arm] == "failed", (arm, status)
    session_ids = [v for ids in sessions.values() for v in ids]
    assert len(session_ids) == len(set(session_ids)), "Sessions were not independent"
    cohorts = {}
    for cohort in previous.COHORTS:
        rows = {}
        for task in core.TASKS:
            raw, folder = previous.first(cohort, task, "ai", original, evidence)
            original_path = folder / ("page" if cohort == previous.COHORTS[0] else "version-0")
            try:
                if raw is None:
                    raise ValueError("Missing response")
                plan = parse_json(raw)
                original_page = page_bundle(deploy(cohort, original, plan))
            except (ValueError, KeyError, TypeError):
                original_page = None
            assert original_path.exists() == (original_page is not None), (cohort, task)
            if original_page:
                assert original_page == digest(source_files(original_path)), (cohort, task)
            pages = {"original": original_page}
            for name, package in packages.items():
                if name == "original":
                    continue
                if original_page:
                    try:
                        pages[name] = page_bundle(deploy(cohort, package, plan))
                    except (ValueError, KeyError, TypeError):
                        pages[name] = None
                else:
                    pages[name] = None
            rows[task] = {"raw_response_sha256": sha256(raw.encode()).hexdigest() if raw is not None else None,
                          "received": raw is not None, "original_plan_valid": original_page is not None, "pages": pages}
        cohorts[cohort] = rows
    fixed = {arm: page_bundle(deploy(previous.COHORTS[0], p, p["examples"][0]["plan"]))
             for arm, p in packages.items()}
    manifest = {"sealed_utc": now(), "inputs": evidence, "build_statuses": statuses, "build_usage": usage,
                "package_files": {k: sha(core.AI if k == "original" else OUT / k / "package.json") for k in packages},
                "cohorts": cohorts, "fixed_example_one": fixed}
    dump(path, manifest)
    return manifest


def jobs(manifest):
    result = {}
    for task in core.TASKS:
        pages = set(manifest["fixed_example_one"].values())
        for cohort in manifest["cohorts"].values():
            pages.update(p for p in cohort[task]["pages"].values() if p)
        for page in sorted(pages):
            path = EVAL / "pages" / page
            assert digest(source_files(path)) == page
            key = f"{task}-{page}"
            result[key] = (key, task, path)
    return result


def score_entry(directory, task):
    raw_file = directory / "report.json"
    raw = read(raw_file)
    rec = read(directory / "score.json")
    assert sha(raw_file) == rec["report_sha256"]
    assert rec["candidate_outcome_exact"]
    assert not [e for e in raw.get("errors", []) if "maximum allowed failures" not in e.get("message", "")]
    cases = cases_by_file(raw)
    assert set(cases) == {task} and cases == rec["tests"] and cases[task]
    passed = all(c["passed"] for c in cases[task])
    assert passed or any(s in ("failed", "timedOut") for c in cases[task] for s in c["statuses"])
    assert passed == rec["all_passed"]
    return {"passed": passed, "report_sha256": rec["report_sha256"], "report_file": previous.rel(raw_file)}


def score(manifest, workers):
    output = EVAL / "scores-complete.json"
    if output.exists():
        return
    pending = jobs(manifest)
    results = {}
    # Reuse only sealed, replay-verified reports from the identical runtime and test contract.
    prior_scores = previous.OUT / "scores-complete.json"
    prior_hash = None
    prior_freeze = previous.OUT / "freeze.json"
    old_manifest = read(prior_freeze) if prior_freeze.exists() else {}
    common_dependencies_match = all(manifest["inputs"][k] == v for k, v in old_manifest.get("inputs_sha256", {}).items()
                                    if k in manifest["inputs"])
    if prior_scores.exists() and common_dependencies_match:
        old = read(prior_scores)
        assert old["freeze_sha256"] == sha(prior_freeze)
        old_jobs = {k: (t, p) for k, t, p in previous.grade_jobs(old_manifest)}
        prior_hash = sha(prior_scores)
        for key in list(pending):
            if key not in old_jobs:
                continue
            _, task, page = pending[key]
            old_task, old_page = old_jobs[key]
            assert task == old_task and source_files(page) == source_files(old_page)
            item = score_entry(previous.OUT / "scores" / key, task)
            assert {k: item[k] for k in ("passed", "report_sha256")} == old["unique_scores"][key]
            results[key] = item
            pending.pop(key)
    if pending:
        score_pages(EVAL, list(pending.values()), workers)
    for key, task, _ in pending.values():
        results[key] = score_entry(EVAL / "scores" / key, task)
    dump(output, {"candidate_manifest_sha256": sha(EVAL / "candidates-sealed.json"), "closed_utc": now(),
                  "prior_score_manifest_sha256": prior_hash, "results": results})


def four_cells(left, right):
    cells = {"gained": [], "lost": [], "both_pass": [], "both_fail": [], "unknown": []}
    labels = {(False, True): "gained", (True, False): "lost", (True, True): "both_pass", (False, False): "both_fail"}
    for task in core.TASKS:
        old, new = left[task]["passed"], right[task]["passed"]
        cells[labels.get((old, new), "unknown")].append(task)
    return {"matched": len(core.TASKS) - len(cells["unknown"]), "counts": {k: len(v) for k, v in cells.items()},
            "tasks": cells}


def summarize(rows):
    observed = [r for r in rows.values() if r["passed"] is not None]
    return {"planned": len(rows), "preparation_blocked": sum(v["status"] == "preparation_failed" for v in rows.values()),
            "missing_response": sum(v["status"] == "no_response" for v in rows.values()),
            "invalid_original_response": sum(v["status"] == "invalid_original_response" for v in rows.values()),
            "compiler_failure": sum(v["status"] == "compiler_failure" for v in rows.values()),
            "valid": sum(v["status"] == "executable" for v in rows.values()), "observed": len(observed),
            "passed": sum(v["passed"] for v in observed) if observed else None}


def report(manifest):
    records_file = EVAL / "scores-complete.json"
    record = read(records_file)
    assert record["candidate_manifest_sha256"] == sha(EVAL / "candidates-sealed.json")
    all_jobs = jobs(manifest)
    assert set(all_jobs) == set(record["results"])
    if record["prior_score_manifest_sha256"]:
        old = previous.OUT / "scores-complete.json"
        assert sha(old) == record["prior_score_manifest_sha256"]
    for key, task, _ in all_jobs.values():
        data = record["results"][key]
        path = ROOT / data["report_file"]
        assert path in (EVAL / "scores" / key / "report.json", previous.OUT / "scores" / key / "report.json")
        assert data == score_entry(path.parent, task)
    def value(task, arm, row):
        if arm not in row["pages"]:
            return {"status": "preparation_failed", "passed": None}
        if not row["received"]:
            return {"status": "no_response", "passed": None}
        page = row["pages"][arm]
        if page is None:
            reason = "compiler_failure" if row["original_plan_valid"] else "invalid_original_response"
            return {"status": reason, "passed": False}
        item = record["results"][f"{task}-{page}"]
        return {"status": "executable", "page_manifest_sha256": page, "passed": item["passed"],
                "official_report_sha256": item["report_sha256"]}
    cohorts = {}
    comparisons = [("original", name) for name in ARMS] + [(f"plain-{i}", f"contract-{i}") for i in (1, 2)]
    for cohort, rows in manifest["cohorts"].items():
        arms = {arm: {t: value(t, arm, row) for t, row in rows.items()} for arm in ALL}
        cohorts[cohort] = {"summary": {a: summarize(v) for a, v in arms.items()}, "targets": arms,
                           "paired": {f"{b}_vs_{a}": four_cells(arms[a], arms[b]) for a, b in comparisons}}
    primary, archive = (cohorts[c] for c in previous.COHORTS)
    historic = read(previous.PREVIOUS)
    for task in core.TASKS:
        old = historic["targets"][task]["ai"]["first"]
        row = primary["targets"]["original"][task]
        assert (row["passed"], row["status"] == "executable") == (old["passed"], old["valid"])
    assert primary["summary"]["original"]["passed"] == 3
    fixed = {a: {t: value(t, a, {"pages": manifest["fixed_example_one"], "received": True,
                                  "original_plan_valid": True}) for t in core.TASKS} for a in ALL}
    def complete_gain(cohort, arm, control, strict):
        data = cohort["paired"][f"{arm}_vs_{control}"]
        gained, lost = (data["counts"][k] for k in ("gained", "lost"))
        return data["matched"] == len(core.TASKS) and gained > 0 and (gained > lost if strict else gained >= lost)
    backend_by_run = {a: complete_gain(primary, a, "original", True) and complete_gain(archive, a, "original", False)
                      for a in ARMS}
    contrasts = {f"contract-{i}": complete_gain(primary, f"contract-{i}", f"plain-{i}", True) for i in (1, 2)}
    qualifies = all(backend_by_run[a] and contrasts[a] for a in contrasts)
    return {"study": OUT.name, "project": "table", "planner": core.MODEL,
            "estimand": "Counterfactual backend substitution on two archived first-response cohorts. "
                        "Planners originally saw the GPT-5 package; the rebuilt packages share its plan interface.",
            "build_statuses": manifest["build_statuses"], "new_library_builder": build.MODEL,
            "build_compute": {"billing": "ChatGPT subscription, separate from metered OpenRouter calls",
                              "usage_by_build": manifest["build_usage"]},
            "library_package_sha256": manifest["package_files"],
            "cohorts": cohorts, "fixed_documentation_example_1": {"plan": {}, "deployment_contract": previous.COHORTS[0],
                "summary": {a: summarize(v) for a, v in fixed.items()}, "targets": fixed},
            "confirmation": {"rule": "Within each repeat compare contract with its ordinary-prompt sibling and the original "
                            "library on all 20 primary targets (strict increases). The held-out response cohort must also "
                            "have all 20 observed, no net decline versus original, and at least one newly passed target "
                            "in each contract repeat.", "backend_vs_original_primary_up_archive_nondecline_and_gain": backend_by_run,
                            "primary_contract_strictly_above_its_plain_sibling": contrasts, "qualified_for_retesting": qualifies},
            "verification": {"candidate_seal_utc": manifest["sealed_utc"], "candidate_seal_sha256": record["candidate_manifest_sha256"],
                             "builder_seal_sha256": sha(OUT / "sealed.json"), "official_evaluation_complete_utc": record["closed_utc"],
                             "original_source_summary_sha256": sha(previous.PREVIOUS), "official_reports": len(all_jobs),
                             "reused_reports": sum(i["report_file"].startswith(previous.rel(previous.OUT) + "/")
                                                   for i in record["results"].values()),
                             "runtime": historic["evaluation_runtime"], "new_planner_api_calls": 0},
            "limitations": "The original builder used a different model and information. A primary gain shared by both "
                           "new prompts supports a rebuilt backend, not a prompt-specific advantage. Both cohorts cover "
                           "the same project and the same task IDs. Fixed example 1 is a separate control."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("freeze", "score", "report", "check"))
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be positive")
    if args.stage == "check" and not (EVAL / "candidates-sealed.json").is_file():
        raise ValueError("No sealed candidates")
    frozen = freeze_candidates()
    if args.stage == "score":
        score(frozen, args.workers)
    if args.stage in ("report", "check"):
        result = report(frozen)
        if args.stage == "report" and not REPORT.exists():
            dump(REPORT, result)
        else:
            assert read(REPORT) == result, "Public summary differs from the offline reconstruction"
        print({c: {a: r["passed"] for a, r in data["summary"].items()} for c, data in result["cohorts"].items()})
        print(result["confirmation"])
