"""Audit public option witnesses, original pages, matched outcomes and the finite space."""

import argparse
from collections import defaultdict

from studies.public_library_transfer import browser, core
from studies.public_library_transfer.self_refinement.native import report as primary
from studies.public_library_transfer.self_refinement.coherent.linker import report as previous
from studies.study_io import ROOT, digest, read, sha

from . import run

OUTPUT = ROOT / "studies/results/self-executable-options-20261124.json"


def public_candidate(row):
    out = {k: v for k, v in row.items() if k != "candidate"}
    if "candidate" not in row:
        return out
    c = row["candidate"]
    out["option"] = {k: v for k, v in c.items() if k not in ("original_fragment", "alternative_fragment")}
    for key in ("original_fragment", "alternative_fragment"):
        out["option"][key + "_digest"] = digest(c[key])
    return out


def space(rows):
    by_setting = defaultdict(list)
    tasks = set()
    for row in rows:
        by_setting[row["setting"]].append(row)
        if row["passed"]:
            tasks.add(row["task"])
    return {"configurations": len(by_setting), "tested_pairs": len(rows), "reachable_targets": sorted(tasks),
        "per_configuration": {k: [r["task"] for r in rs if r["passed"]] for k, rs in by_setting.items()},
        "rows": rows}


def paired(rows, arm):
    common = [r for r in rows if r["self"]["passed"] is not None and r[arm]["passed"] is not None]
    return {"tasks": [r["task"] for r in common], "self_passed": sum(r["self"]["passed"] for r in common),
            "comparator_passed": sum(r[arm]["passed"] for r in common),
            "self_only": [r["task"] for r in common if r["self"]["passed"] and not r[arm]["passed"]],
            "comparator_only": [r["task"] for r in common if r[arm]["passed"] and not r["self"]["passed"]]}


def check(result):
    project = result["projects"]["table"]
    assert result["source_linker_results_sha256"] == sha(previous.OUTPUT)
    old = read(previous.OUTPUT)["projects"]["table"]
    assert old["direct_seal_sha256"] == project["direct_seal_sha256"]
    assert project["ledger"]["exposure_usd"] <= result["project_budget_usd"] == .65
    for g, group in project["replicas"].items():
        assert group["comparison"] == primary.comparison(group["rows"])
        assert group["original_package_sha256"] == old["replicas"][g]["package_sha256"]
        confirmed = [r for r in group["candidate_witnesses"] if r.get("accepted")]
        assert [r["option"]["id"] for r in confirmed] == [c["id"] for c in group["controls"]]
        for row in confirmed:
            a, b = row["observations"]["original"], row["observations"]["alternative"]
            assert len(a) == len(b) == 2
            assert a[0]["after"] == a[1]["after"] and b[0]["after"] == b[1]["after"] and a[0]["after"] != b[0]["after"]
        for arm in ("direct", "fixed"):
            assert group["paired_" + arm] == paired(group["rows"], arm)
        for r, before in zip(group["rows"], old["replicas"][g]["rows"], strict=True):
            for arm in ("direct", "fixed"):
                assert all(r[arm].get(k) == before[arm].get(k) for k in ("files_digest", "status", "passed"))
        enum = group["enumeration"]
        assert space(enum["rows"]) == enum
        assert enum["configurations"] == 2 ** len(group["controls"])
        assert all(sorted(r["task"] for r in enum["rows"] if r["setting"] == k) == list(run.native.TASKS)
                   for k in enum["per_configuration"])
        known = {(r["task"], r["files_digest"]): (r["passed"], r["report_sha256"]) for r in enum["rows"]}
        for r in group["rows"]:
            for arm in ("self", "fixed"):
                if r[arm]["status"] == "valid":
                    assert known[r["task"], r[arm]["files_digest"]] == (r[arm]["passed"], r[arm]["report_sha256"])
        print(g, len(confirmed), "confirmed;", group["paired_fixed"], "reachable", enum["reachable_targets"])


def assemble():
    run.verify()
    reg = run.OUT / "registered.json"
    record = primary.project_report("table", stage=run.OUT, schema_steps=("target", "design", "repair"))
    all_rows = read(run.BASE / "enumeration.json")
    contract = digest(read(run.BASE / "browser.json"))
    for group, block in record["replicas"].items():
        src = run.BASE / group / "build"
        state, package = read(src / "status.json"), read(src / "package.json")
        block.update(selection_status=state["selection_status"], original_package_sha256=package["source_sha256"],
            candidate_witnesses=[public_candidate(r) for r in state["proposal_log"]], transport_interruption=state["transport_interruption"],
            paired_fixed=paired(block["rows"], "fixed"), paired_direct=paired(block["rows"], "direct"))
        rows = [r for r in all_rows if r["group"] == group]
        for row in rows:
            task, key = row["task"], row["files_digest"]
            file = run.BASE / "browser/scores/table" / f"task-{task}" / key / "score.json"
            expected = dict(project="table", task=task, files_digest=key, contract_digest=contract)
            verified = browser.verify_receipt(run.BASE, file, expected)
            assert verified["passed"] == row["passed"] and verified["report_sha256"] == row["report_sha256"]
        block["enumeration"] = space(rows)
    return {"model": run.transport.MODEL, "registered_utc": read(reg)["utc"],
        "design_registration_utc": read(run.OUT / "design-registration.json")["utc"],
        "registration_sha256": sha(reg), "protocol_sha256": sha(run.HERE / "PROTOCOL.md"),
        "source_linker_results_sha256": sha(previous.OUTPUT), "project_budget_usd": run.CAP,
        "end_utc": run.transport.END.isoformat(), "projects": {"table": record}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "check-local"))
    action = parser.parse_args().action
    data = read(OUTPUT) if action == "check" else assemble()
    check(data)
    if action == "write":
        core.save(OUTPUT, data)
    elif action == "check-local":
        assert data == read(OUTPUT)


if __name__ == "__main__":
    main()
