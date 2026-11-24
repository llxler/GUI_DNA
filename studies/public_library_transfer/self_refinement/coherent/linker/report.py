"""Verify the linked packages, shared Direct baseline and per-replicate accounting."""

import argparse
import re

from studies.ledger_read import calls
from studies.public_library_transfer import core
from studies.public_library_transfer.self_refinement.coherent import report as coherent
from studies.public_library_transfer.self_refinement.native import report as primary
from studies.public_library_transfer.self_refinement.native import transport
from studies.study_io import ROOT, digest, read, sha

from . import run

OUTPUT = ROOT / "studies/results/self-coherent-linker-20261124.json"


def reused_cost(project, group):
    phases = {}
    for source, names in ((run.source.ORIGINAL, ["design"]), (run.source.OUT, ["program", "style", "repair"])):
        by_purpose = {r["purpose"]: r for r in calls(source / project / "budget.sqlite3")}
        for phase in names:
            name = f"{project}/{group}/{phase}"
            if name not in by_purpose and phase == "repair":
                continue
            row = by_purpose[name]
            receipt = source / project / group / "build" / phase / "request.json"
            assert read(receipt)["call_id"] == row["id"]
            phases[phase] = {"included_in_linked_inputs": phase != "repair", "request_sha256": sha(receipt),
                             "settled_usd": (row["actual"] or 0) / 1e6, "exposure_usd":
                                 (row["actual"] if row["actual"] is not None else row["reserved"]) / 1e6}
    return phases


def source_controls(dest, sources, spec):
    controls = [c["id"] for c in spec["controls"]]
    fixed = {c["id"]: c["example"] for c in spec["controls"]}
    counts = {k: 0 for k in controls}
    occurrences = []
    for path, text in sources.items():
        for key in controls:
            counts[key] += len(re.findall(r"(?<![\w$])" + re.escape(key) + r"(?![\w$])", text))
        for n, line in enumerate(text.splitlines(), 1):
            if re.search(r"\bAPP_CONFIG\b|\bconfig\s*(?:\?\.|\.)", line):
                occurrences.append({"file": path, "line": n, "static_properties": re.findall(
                    r"\b(?:APP_CONFIG|config)\s*(?:\?\.|\.)([A-Za-z_$][\w$]*)", line)})
    targets = [read(f) for f in sorted((dest.parent / "targets").glob("*/status.json"))]
    plans = [r["plan"] for r in targets if r["status"] == "valid"]
    assert all(set(p) == set(controls) for p in plans)
    return {"declared_key_literal_occurrences_in_linked_js_css": counts,
            "configuration_reference_lines": occurrences, "valid_plans": len(plans),
            "distinct_plans": len({digest(p) for p in plans}), "equal_to_fixed_plan": sum(p == fixed for p in plans)}


def add_differences(model, earlier):
    joint = [(r["task"], r["self"]["passed"], e["self"]["passed"])
             for r, e in zip(model["rows"], earlier["rows"], strict=True)
             if r["self"]["passed"] is not None and e["self"]["passed"] is not None]
    model["relative_to_same_design"] = {"common": [n for n, _, _ in joint],
        "gained": [n for n, new, old in joint if new and not old], "lost": [n for n, new, old in joint if old and not new]}
    common = [r for r in model["rows"] if r["self"]["passed"] is not None and r["direct"]["passed"] is not None]
    model["paired_direct"] = {"common": [r["task"] for r in common],
        "direct": sum(r["direct"]["passed"] for r in common), "self": sum(r["self"]["passed"] for r in common)}


def check(data, earlier):
    coherent.check(data, earlier)
    assert sha(coherent.OUT) == data["coherent_results_sha256"] and sha(primary.RESULT) == data["native_results_sha256"]
    for project, record in data["projects"].items():
        assert all(r["purpose"].split("/")[2] == "target" for r in record["requests"])
        for group, model in record["replicas"].items():
            copy = dict(model)
            add_differences(copy, earlier["projects"][project]["replicas"][group])
            assert copy["paired_direct"] == model["paired_direct"]
            assert copy["relative_to_same_design"] == model["relative_to_same_design"]
            assert all(c["exposure_usd"] >= c["settled_usd"] for c in model["source_costs_usd"].values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "check-local"))
    action = parser.parse_args().action
    earlier = read(coherent.OUT)
    if action == "check":
        return check(read(OUTPUT), earlier)
    run.verify()
    regfile = run.OUT / "registered.json"
    reg = read(regfile)
    result = {"model": transport.MODEL, "registered_utc": reg["utc"], "end_utc": reg["end"],
              "registration_sha256": sha(regfile), "protocol_sha256": sha(run.HERE / "PROTOCOL.md"),
              "native_results_sha256": sha(primary.RESULT), "coherent_results_sha256": sha(coherent.OUT),
              "project_budget_usd": run.CAP, "projects": {}}
    for project in run.native.PROJECTS:
        block = primary.project_report(project, stage=run.OUT, schema_steps=("target",))
        for group, model in block["replicas"].items():
            src = run.source.OUT / project / group / "build/initial"
            dest = run.OUT / project / group / "build"
            spec = read(dest / "manifest.json")
            bundle = src / run.source.SHARED
            styles = {p: (src / p).read_text() for p in spec["files"] if p.endswith(".css")}
            model["archived_input_sha256"] = {"initial_js": sha(bundle), "manifest": sha(dest / "manifest.json"),
                "css": {p: sha(src / p) for p in styles}}
            model["source_costs_usd"] = reused_cost(project, group)
            try:
                sources, audit = run.modules.compile_sources(bundle.read_text(), styles, spec)
            except ValueError as exc:
                assert model["status"] == "invalid" and model["reason"] == str(exc)
                names, fences = run.modules.split(bundle.read_text(), spec)
                audit = {"sections": list(names), "removed_fence_lines": fences, "error": str(exc)}
            else:
                assert audit == read(dest / "link.json")
                if model["status"] == "valid":
                    assert read(dest / "package.json") == {"spec": spec, "sources": sources}
                    model["source_control_diagnostic"] = source_controls(dest, sources, spec)
            model["module_linking"] = audit
            add_differences(model, earlier["projects"][project]["replicas"][group])
        result["projects"][project] = block
    check(result, earlier)
    if action == "write":
        core.save(OUTPUT, result)
    else:
        assert read(OUTPUT) == result


if __name__ == "__main__":
    main()
