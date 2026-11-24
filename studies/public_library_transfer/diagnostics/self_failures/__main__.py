"""Audit where the frozen Panel A Self pipeline lost its scheduled targets."""

import argparse
from collections import Counter, defaultdict

from studies.study_io import ROOT, cases_by_file, dump, read, sha

RESULTS = ROOT / "studies/results"
STAGES = ("matrix", "extension", "form")
ARMS = ("self", "fixed", "direct", "human", "gpt5-library")
OUTPUT = RESULTS / "self-failure-diagnosis-20261124.json"
CALIBRATION = RESULTS / "public-library-transfer-calibration-20261123.json"


def stage_path(stage):
    return RESULTS / f"backbone-{stage}-20261124.json"


def delivery(row):
    state = row["status"]
    if state == "valid":
        assert type(row["passed"]) is bool and row["report_sha256"] and row["files_digest"]
        return "page_passed" if row["passed"] else "page_failed"
    assert state in ("build_failed", "invalid", "missing")
    assert row["passed"] is (None if state == "missing" else False)
    return state


def summarize(rows):
    """The unit is one scheduled target, even when its library was rejected."""
    return {arm: dict(Counter(delivery(r) for r in rows if r["arm"] == arm)) for arm in ARMS}


def pair(rows, arm, require_pages):
    indexed = {(r["task"], r["arm"]): r for r in rows}
    passed = {(True, True): "both", (False, True): "comparator_only",
              (True, False): "self_only", (False, False): "neither"}
    groups = defaultdict(list)
    for n in sorted({r["task"] for r in rows}):
        left, right = indexed[n, "self"], indexed[n, arm]
        if require_pages and any(r["status"] != "valid" for r in (left, right)):
            continue
        if left["passed"] is None or right["passed"] is None:
            continue
        groups[passed[left["passed"], right["passed"]]].append(n)
    return dict(groups)


def audit_public():
    sources = {f.name: sha(f) for f in [*(stage_path(s) for s in STAGES), CALIBRATION]}
    models, unavailable = defaultdict(dict), defaultdict(dict)
    all_rows, builds, bucket = [], Counter(), defaultdict(list)
    matched = defaultdict(Counter)
    final_errors = Counter()
    for stage in STAGES:
        data = read(stage_path(stage))
        for model, record in data["models"].items():
            for project, build in record["builds"].items():
                rows = [r for r in record["rows"] if r["project"] == project]
                expected = {(n, arm) for n in data["target_ids"] for arm in ARMS}
                assert len(rows) == len(expected) and {(r["task"], r["arm"]) for r in rows} == expected
                if record["model_stop"]:
                    assert all(delivery(r) == "missing" for r in rows)
                    unavailable[model][project] = {"reason": record["model_stop"]["reason"],
                                                   "self_targets_missing": len(data["target_ids"])}
                    continue
                state = build["status"]
                assert state in ("valid", "build_failed") and project not in models[model]
                assert all((r["status"] == "build_failed") == (state == "build_failed")
                           for r in rows if r["arm"] in ("self", "fixed"))
                builds[state] += 1
                if state == "build_failed":
                    final_errors[build["public_errors"][-1]] += 1
                all_rows.extend(rows)
                bucket[project].extend(rows)
                comparisons = {}
                for arm in ARMS[1:]:
                    counts = {key: len(v) for key, v in pair(rows, arm, require_pages=True).items()}
                    matched[arm].update(counts)
                    comparisons[arm] = counts
                fixed = pair(rows, "fixed", require_pages=False)
                discordant = {key: fixed.get(key, []) for key in ("self_only", "comparator_only")}
                models[model][project] = {"self_build": state, "public_errors": build["public_errors"],
                    "scheduled_by_arm": summarize(rows), "both_pages_delivered": comparisons,
                    "fixed_vs_per_target_discordant_targets": discordant}
    calibration = {r["project"]: r["blank_passed"] for r in read(CALIBRATION)["projects"] if r["project"] in bucket}
    return {"sources_sha256": sources, "unavailable_routes": dict(unavailable),
            "self_library_builds": dict(builds), "final_rejection_messages": dict(final_errors),
            "scheduled_failure_location_counts": summarize(all_rows),
            "both_pages_delivered_by_comparator": dict(matched),
            "per_project_failure_locations": {p: summarize(r) for p, r in bucket.items()},
            "blank_control_passed": calibration, "by_deployer_and_project": dict(models)}


def response_info(path):
    value = read(path)
    choice = value["choices"][0]
    content = choice["message"].get("content") or ""
    return {"response_sha256": sha(path), "visible_characters": len(content),
            "finish_reason": choice["finish_reason"],
            "completion_tokens": value["usage"]["completion_tokens"]}


def report_cases(base, row):
    path = base / "browser/scores" / row["project"] / f"task-{row['task']}" / row["files_digest"] / "score.json"
    receipt = read(path)
    assert receipt["passed"] == row["passed"] and receipt["files_digest"] == row["files_digest"]
    report = base / receipt["report"]
    assert sha(report) == receipt["report_sha256"] == row["report_sha256"]
    cases = cases_by_file(read(report))[f"task-{row['task']}"]
    return {"project": row["project"], "task": row["task"], "report_sha256": sha(report),
            "files_digest": row["files_digest"], "failed_cases": [r["title"] for r in cases
                if "failed" in r["statuses"] or "timedOut" in r["statuses"]]}


def audit_local():
    from gui_dna.provider import parse_json

    attempts, invalid, examples, interfaces = [], [], [], {}
    # Purposefully selected to illustrate distinct symptoms, never to estimate prevalence.
    chosen = {("extension", "deepseek-flash", "svg-chart", 2), ("form", "qwen", "form", 1),
              ("form", "oss", "form", 6), ("matrix", "mistral", "table", 2)}
    for stage in STAGES:
        data = read(stage_path(stage))
        base = ROOT / "artifacts" / stage_path(stage).stem
        registry = base / "registered.json"
        assert sha(registry) == data["registration_sha256"]
        for tag, (model, *_) in read(registry)["models"].items():
            record = data["models"][model]
            if record["model_stop"]:
                continue
            seal = base / tag / "seal.json"
            assert sha(seal) == record["seal_sha256"]
            sealed = {(r["project"], r["task"], r["arm"]): r for r in read(seal)["rows"]}
            for project, build in record["builds"].items():
                folder = base / tag / project / "build"
                assert read(folder / "status.json") == build
                responses = sorted(folder.glob("attempt-*/response.json"))
                assert len(responses) == len(build["public_errors"]) + int(build["status"] == "valid")
                audit = {"builder": model, "project": project, "attempts": [response_info(p) for p in responses]}
                if build["status"] == "valid":
                    path = folder / "package.json"
                    assert sha(path) == build["package_sha256"]
                    audit["package_sha256"] = sha(path)
                    audit["control_ids"] = [c["id"] for c in read(path)["controls"]]
                attempts.append(audit)
                library_files = interfaces.setdefault(project, {})
                for arm in ("human", "gpt5-library"):
                    path = base / "inputs" / project / f"{arm}.json"
                    fingerprint = sha(path)
                    assert fingerprint == data["registration_inputs"][str(path.relative_to(ROOT))]
                    candidate = {"package_sha256": fingerprint, "files": list(read(path)["files"])}
                    assert library_files.setdefault(arm, candidate) == candidate
            for r in record["rows"]:
                p, n, arm = r["project"], r["task"], r["arm"]
                if (stage, tag, p, n) in chosen and r["status"] == "valid" and not r["passed"] and arm in ("self", "gpt5-library"):
                    examples.append({"deployer": model, "arm": arm, **report_cases(base, r)})
                if arm != "self" or r["status"] != "invalid":
                    continue
                original = sealed[p, n, arm]
                path = base / tag / p / "self" / str(n) / "call/response.json"
                response = response_info(path)
                assert response["response_sha256"] == original["response_sha256"] == r["response_sha256"]
                detail = {"deployer": model, "project": p, "task": n, "reason": original["reason"], **response}
                if response["visible_characters"]:
                    content = read(path)["choices"][0]["message"]["content"]
                    detail["returned_top_level_keys"] = sorted(parse_json(content))
                invalid.append(detail)
    return {"self_build_responses": attempts, "self_invalid_plans": invalid,
            "invalid_plan_reason_counts": dict(Counter(r["reason"] for r in invalid)),
            "frozen_library_files": interfaces, "illustrative_browser_failures": examples}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "check-local", "write"), nargs="?", default="check")
    action = parser.parse_args().action
    public = audit_public()
    if action == "write":
        dump(OUTPUT, {"public": public, "archived_receipts": audit_local()})
    else:
        stored = read(OUTPUT)
        assert stored["public"] == public
        if action == "check-local":
            assert stored["archived_receipts"] == audit_local()
    print(f"{action}: {public['self_library_builds']}; {public['scheduled_failure_location_counts']['self']}")


if __name__ == "__main__":
    main()
