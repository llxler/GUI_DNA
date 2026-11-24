"""Derive strict, source-paired SVG outcomes and a separate hypothetical fixed-page fallback."""
import argparse
from hashlib import sha256
import re
from pathlib import Path

from studies.public_library_transfer import core
from studies.study_io import ROOT, digest, read, sha

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "result.json"
DEST = HERE / "report.json"
ART = ROOT / "artifacts/qwen-svg-renderers-20261124"
TARGETS = tuple(range(1, 21))
REPLICAS = ("A", "B")
CALIBRATION = ROOT / "studies/results/public-library-transfer-calibration-20261123.json"


def normalize(row):
    status, score = row["status"], row.get("passed")
    if status in ("invalid", "invalid_plan", "build_failed"):
        if score is True or row.get("report_sha256"):
            raise ValueError("Nonmaterialized candidate has a browser success or receipt")
        return False, "received_pipeline_failure"
    if status == "missing":
        if score is not None:
            raise ValueError("Unobserved generation has a verdict")
        return None, "generation_missing"
    if status in ("evaluator_error", "evaluation_missing") or (status == "valid" and score is None):
        return None, "evaluation_missing"
    if status == "valid" and type(score) is bool and len(row["report_sha256"]) == 64:
        return score, "official_current_test"
    raise ValueError(f"Unexpected SVG candidate {status!r} / {score!r}")


def indexed(rows):
    viewed = {}
    for r in rows:
        key = r["group"], r["arm"], r["task"]
        if key in viewed:
            raise ValueError("Repeated SVG observation")
        score, origin = normalize(r)
        viewed[key] = {"passed": score, "classification": origin, "candidate_status": r["status"],
                       "page_digest": r.get("page_digest")}
    return viewed


def intersection(arms, targets=TARGETS):
    return [n for n in targets if all(c[n]["passed"] is not None for c in arms.values())]


def joint(arms, targets=TARGETS):
    common = intersection(arms, targets)
    return {"targets": common, "passed": {name: [n for n in common if column[n]["passed"]] for name, column in arms.items()}}


def paired(left, right, targets=TARGETS):
    shared = intersection({"left": left, "right": right}, targets)
    buckets = {name: [] for name in ("both", "left_only", "right_only", "neither")}
    for n in shared:
        a, b = left[n]["passed"], right[n]["passed"]
        bucket = "both" if a and b else "left_only" if a else "right_only" if b else "neither"
        buckets[bucket].append(n)
    return {"common_targets": shared, "left_passed": [n for n in shared if left[n]["passed"]],
            "right_passed": [n for n in shared if right[n]["passed"]], **buckets}


def per_arm(column):
    return {"observed": [t for t in TARGETS if column[t]["passed"] is not None],
            "passed": [t for t in TARGETS if column[t]["passed"]],
            "excluded": {kind: [t for t in TARGETS if column[t]["classification"] == kind]
                         for kind in ("generation_missing", "evaluation_missing")},
            "received_pipeline_failures": [t for t in TARGETS if column[t]["classification"] == "received_pipeline_failure"]}


def repair(build):
    obs = build.get("observations", {})
    if "first" not in obs:
        return {"admitted": False, "module_status": build["states"], "public_repair": "unavailable"}
    first, selected = obs["first"], obs["selected"]
    proposed = build.get("proposed_observation")
    why, accepted = "no_changed_proposal", False
    if proposed is not None:
        previous = {k for k,n in first["drawn"].items() if n > 0}
        updated = {k for k,n in proposed["drawn"].items() if n > 0}
        errors_before, errors_after = len(first["errors"]), len(proposed["errors"])
        if previous < updated and errors_after <= errors_before:
            why, accepted = "added_drawable_types_without_more_errors", True
        elif previous == updated and errors_after < errors_before:
            why, accepted = "same_drawable_types_fewer_errors", True
        else:
            why = "proposal_did_not_meet_registered_program_criterion"
    if selected != (proposed if accepted else first):
        raise ValueError("Selected library differs from the implemented public repair rule")
    return {"admitted": True, "public_repair": why, "accepted": accepted,
            "initial_drawable": sorted(k for k,n in first["drawn"].items() if n > 0),
            "selected_drawable": sorted(k for k,n in selected["drawn"].items() if n > 0),
            "initial_errors": first["errors"], "selected_errors": selected["errors"]}


def derive():
    raw = read(SOURCE)
    view = indexed(raw["rows"])

    def for_arm(group, arm):
        return {n: view[group, arm, n] for n in TARGETS}

    main = {}
    all_arms = {}
    for rep in REPLICAS:
        arms = {"strict_self": for_arm(rep, "planned"), "fixed_all": for_arm(rep, "fixed"),
                "initial_fixed": for_arm(rep, "initial_fixed"), "direct_repaired": for_arm("direct", "final"),
                "direct_first": for_arm("direct", "first"), "host_only": for_arm("host", "only")}
        all_arms.update({(name + "_" + rep if name in ("strict_self", "fixed_all", "initial_fixed") else name): v
                         for name, v in arms.items()})
        plan, fixed = arms["strict_self"], arms["fixed_all"]
        fallback = {}
        substituted = []
        for n in TARGETS:
            # No retroactive replacement of an officially failed, valid plan. The fallback
            # only answers what the already frozen fixed page did if no valid plan arrived.
            if (plan[n]["classification"] in ("received_pipeline_failure", "generation_missing")
                    and fixed[n]["candidate_status"] == "valid"):
                fallback[n] = fixed[n]
                substituted.append(n)
            else:
                fallback[n] = plan[n]
        main[rep] = {
            "all_six_common": joint(arms),
            "all_six_excluding_public_asset_target": joint(arms, TARGETS[1:]),
            "by_arm": {name: per_arm(v) for name, v in arms.items()},
            "strict_self_vs_repaired_direct": paired(plan, arms["direct_repaired"]),
            "strict_self_vs_repaired_direct_no_asset_target": paired(plan, arms["direct_repaired"], TARGETS[1:]),
            "fixed_all_vs_repaired_direct": paired(fixed, arms["direct_repaired"]),
            "strict_self_vs_fixed_all": paired(plan, fixed), "strict_self_vs_host": paired(plan, arms["host_only"]),
            "fixed_all_vs_host": paired(fixed, arms["host_only"]),
            "first_vs_repaired_direct": paired(arms["direct_first"], arms["direct_repaired"]),
            "same_rendered_page_as_fixed": [n for n in TARGETS if plan[n]["page_digest"] is not None
                                            and plan[n]["page_digest"] == fixed[n]["page_digest"]],
            "delivered_plan_count": sum(r.get("plan") is not None for r in raw["rows"] if r["group"] == rep and r["arm"] == "planned"),
            "hypothetical_fixed_fallback": {"substituted_targets": substituted, "by_arm": per_arm(fallback),
                                            "vs_repaired_direct": paired(fallback, arms["direct_repaired"])},
            "public_preparation": repair(raw["builds"][rep]),
        }
        actual = raw["paired"][rep]["common_targets"]
        corrected = set(main[rep]["all_six_common"]["targets"])
        if not set(actual) <= corrected:
            raise ValueError("Corrected scope unexpectedly drops an original observation")
        main[rep]["legacy_browser_verdict_only_omitted"] = sorted(corrected - set(actual))
    if len(view) != 180:
        raise ValueError("Expected nine scheduled arms on twenty targets")
    benchmark = next(p for p in read(CALIBRATION)["projects"] if p["project"] == "svg-chart")
    if benchmark["tested_tasks"] != list(TARGETS):
        raise ValueError("Calibration does not use the same targets")
    calibration = {"source_sha256": sha(CALIBRATION), "blank_passed": benchmark["blank_passed"],
                   "reference_failed": benchmark["reference_failed"]}
    return {"project": "Web-Bench svg-chart", "model": raw["model"], "source_sha256": sha(SOURCE),
            "benchmark_calibration": calibration,
            "protocol_sha256": raw["protocol_sha256"], "seal_sha256": raw["seal_sha256"],
            "definition": {"strict": "Only transmission/absence of generation or absence of an evaluator verdict is unobserved. "
                          "A received invalid schema, invalid source or unadmitted build is an observed pipeline failure.",
                          "controls": "The fixed page enables every supplied renderer. The host-only page retains the public "
                          "starter classes and the identical researcher-provided data-type lookup, mounting and draw calls.",
                          "fallback": "Additional offline estimate. If no valid plan was delivered, reuse the already frozen fixed "
                          "page where available. The original strict generator performs no automatic fallback.",
                          "repair": "The implemented rule also accepts unchanged drawable types with fewer public errors. "
                          "Adding types requires no increase in the number of errors."},
            "scheduled_targets": list(TARGETS), "replicas": main, "both_replicas_all_arms": joint(all_arms)}


def verify_receipts():
    from studies.public_library_transfer import browser
    raw = read(SOURCE)
    seal = read(ART / "seal.json")
    reg = read(ART / "registration.json")
    if sha(ART / "seal.json") != raw["seal_sha256"] or sha(ART / "registration.json") != raw["registration_sha256"]:
        raise ValueError("Changed raw registration or seal")
    cases = {(r["group"], r["arm"], r["task"]):r for r in seal["rows"]}
    if browser.verify_contract("svg-chart") != reg["harness"]:
        raise ValueError("Original Web-Bench scoring environment changed")
    checked = {}
    checked_pages = set()
    for row in raw["rows"]:
        key = row["group"], row["arm"], row["task"]
        original = cases[key]
        if original["status"] != row["status"] or original.get("plan") != row.get("plan"):
            raise ValueError("Published status differs from sealed generation")
        outcome, origin = normalize(row)
        if origin != "official_current_test":
            continue
        page_id = digest(original["files"])
        page_key = original["page"], page_id
        if page_key not in checked_pages:
            browser.verify_page(ROOT / original["page"], original["files"], "svg-chart")
            checked_pages.add(page_key)
        receipt = ART / "browser/scores/svg-chart" / f"task-{row['task']}" / page_id / "score.json"
        if receipt not in checked:
            checked[receipt] = browser.verify_receipt(ART, receipt, {"project": "svg-chart", "task": row["task"],
                    "files_digest": page_id, "contract_digest": digest(reg["harness"])})
        record = checked[receipt]
        if (record["passed"], record["report_sha256"], page_id) != (outcome, row["report_sha256"], row["page_digest"]):
            raise ValueError("Published verdict differs from raw Playwright report")
    return len(checked)


def module_inspection(raw):
    facts = {}
    for tag in REPLICAS:
        file = ART / tag / "modules.json"
        if sha(file) != raw["builds"][tag]["modules_sha256"]:
            raise ValueError("Selected module bundle differs from sealed preparation")
        modules = {}
        for name, source in read(file).items():
            parents = sorted(set(re.findall(r"\bclass\s+[\w$]+\s+extends\s+([\w$]+)", source)))
            # This is a lexical diagnostic for missing imports. The separate browser
            # observation shows whether the whole graph actually mounted and drew.
            static_import = bool(re.search(r"^\s*import(?:\s|\{)[^()]", source, re.M))
            modules[name] = {"sha256": sha256(source.encode()).hexdigest(), "extends": parents,
                             "contains_static_import_declaration": static_import}
        facts[tag] = {"bundle_sha256": sha(file), "modules": modules}
    return facts


def check_module_inspection(facts, raw):
    if set(facts) != set(REPLICAS):
        raise ValueError("Incomplete SVG module inspection")
    for tag, record in facts.items():
        if record["bundle_sha256"] != raw["builds"][tag]["modules_sha256"]:
            raise ValueError("Module inspection belongs to a different selected bundle")
        for name, module in record["modules"].items():
            if (not name.startswith("common/") or not name.endswith(".js") or len(module["sha256"]) != 64
                    or type(module["contains_static_import_declaration"]) is not bool or not isinstance(module["extends"], list)):
                raise ValueError("Invalid module observation")

def incomplete_records(raw):
    sealed = {(r["group"], r["arm"], r["task"]): r for r in read(ART / "seal.json")["rows"]}
    records = []
    for row in raw["rows"]:
        value, origin = normalize(row)
        if origin == "official_current_test":
            continue
        key = row["group"], row["arm"], row["task"]
        source = sealed[key]
        item = {"group": key[0], "arm": key[1], "task": key[2], "source_status": row["status"],
                "classification": origin, "strict_outcome": value, "generation_note": source.get("reason")}
        if origin == "generation_missing":
            root = ART / "calls"
            if key[0] in REPLICAS and key[1] == "planned":
                paths = [root / key[0] / "plan" / str(key[2]) / "error.json"]
            elif key[0] == "direct":
                paths = sorted((root / "direct" / str(key[2])).glob("*/error.json"))
            else:
                paths = []
            item["transport_errors_on_this_target"] = [read(p)["reason"] for p in paths if p.is_file()]
        records.append(item)
    return records


def validate_incomplete(records, raw):
    expected = []
    for r in raw["rows"]:
        value, origin = normalize(r)
        if origin != "official_current_test":
            expected.append((r["group"],r["arm"],r["task"],r["status"],origin,value))
    found = [(r["group"],r["arm"],r["task"],r["source_status"],r["classification"],r["strict_outcome"]) for r in records]
    if expected != found:
        raise ValueError("Failure and missing-observation notes do not match the full scheduled matrix")

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["write", "check", "check-local"])
    action = p.parse_args().action
    if action in ("write", "check-local"):
        print("Verified unique raw SVG task/page browser receipts", verify_receipts())
    value = derive()
    raw = read(SOURCE)
    facts = read(DEST)["module_inspection"] if action == "check" else module_inspection(raw)
    check_module_inspection(facts, raw)
    value["module_inspection"] = facts
    notes = read(DEST)["incomplete_observations"] if action == "check" else incomplete_records(raw)
    validate_incomplete(notes, raw)
    value["incomplete_observations"] = notes
    if action == "write":
        core.save(DEST, value)
    if read(DEST) != value:
        raise ValueError("SVG report differs from the scheduled arms")
    for rep, summary in value["replicas"].items():
        print(rep, {k: (len(v["passed"]),len(v["observed"])) for k,v in summary["by_arm"].items()})


if __name__ == "__main__":
    main()
