"""Validate typed calculator results and identify gains shared by the domain-only linker."""
import argparse
from collections import Counter
from pathlib import Path

from studies.public_library_transfer import core
from studies.study_io import ROOT, now, read, sha
from ..probe import observe
from ..report import compact, passed_ids
from ..templates import descriptions
from . import grammar
from .run import FIRST, HERE, OUT, SEEDS, TASKS


def freeze_rule():
    path = OUT / "order-control-registration.json"
    contract = {"rule_sha256": sha(HERE / "ORDER.md"), "implementation_sha256": sha(Path(__file__)),
                "parent_sha256": sha(OUT / "registered.json")}
    if path.exists():
        if read(path)["contract"] != contract:
            raise ValueError("Changed rule after registration")
    else:
        core.save(path, {"registered": now(), "contract": contract})


def public_observations():
    for tag in SEEDS:
        pkg = read(OUT / "builds" / tag / "library.json")
        for arm, endpoint in pkg["endpoints"].items():
            path = OUT / "public-probes" / tag / f"{arm}.json"
            if not path.exists():
                obs = observe(ROOT / endpoint["page"], list(pkg["inventory"]))
                core.save(path, {"files": endpoint["files"], "obs": obs})


def summarize(rows, settings):
    direct = [r for r in rows if r["arm"] == "direct"]
    if sorted(r["task"] for r in direct) != list(TASKS):
        raise ValueError("Incomplete direct arm")
    out = {"direct_passed": passed_ids(direct), "direct_rendered": sum(r["status"] == "valid" for r in direct), "builds": {}}
    seen = set(out["direct_passed"])
    for tag in SEEDS:
        groups = {arm: [r for r in rows if r["arm"] == arm and r["rep"] == tag]
                  for arm in ("self", "fixed-A", "fixed-B", "linker")}
        if any(sorted(r["task"] for r in grp) != list(TASKS) for grp in groups.values()):
            raise ValueError("Incomplete generation arm")
        self_rows = groups["self"]
        rule_passed = []
        for r in self_rows:
            expected = next(v for v in groups["fixed-" + r["setting"]] if r["task"] == v["task"])
            if (expected["passed"], expected["report_sha256"]) != (r["passed"], r["report_sha256"]):
                raise ValueError("Planned page does not match the selected fixed endpoint")
            rule = next(v for v in groups["fixed-" + settings[r["task"] - 1]] if r["task"] == v["task"])
            if rule["passed"]:
                rule_passed.append(r["task"])
        success = set(passed_ids(self_rows))
        linker = set(passed_ids(groups["linker"]))
        out["builds"][tag] = {"passed": {arm: passed_ids(grp) for arm, grp in groups.items()},
                              "public_rule_passed": rule_passed, "only_self_vs_direct": sorted(success - seen),
                              "only_direct_vs_self": sorted(seen - success), "both_self_direct": sorted(success & seen),
                              "only_self_vs_linker": sorted(success - linker), "only_linker_vs_self": sorted(linker - success),
                              "model_setting_counts": dict(Counter(r["setting"] for r in self_rows))}
    return out


def make():
    freeze_rule()
    primary = read(FIRST / "scores.json")
    generated = read(OUT / "seal.json")
    rows = [compact(r) for r in read(OUT / "scores.json")["rows"]]
    infos = {}
    calls = 0
    input_tokens = 0
    output_tokens = 0
    lines = descriptions(read(FIRST / "public.json"))
    settings = ["B" if grammar.inventory(lines[:n])[1] else "A" for n in TASKS]
    for tag in SEEDS:
        base = OUT / "builds" / tag
        pkg = read(base / "library.json")
        for name in sorted(base.glob("*.json")):
            value = read(name)
            if "output_ids" in value:
                calls += len(value["outputs"])
                input_tokens += sum(value["input_tokens"])
                output_tokens += sum(len(seq) for seq in value["output_ids"])
            elif "selected_index" in value:
                calls += 1
                input_tokens += value["input_tokens"]
                output_tokens += value["output_tokens"]
        a, b = [read(OUT / "public-probes" / tag / f"{arm}.json")["obs"] for arm in ("A", "B")]
        probes = {mode: v for mode, v in [("A", a), ("B", b),
                  ("linker", read(OUT / "public-probes" / tag / "linker.json")["obs"])]}
        properties = {}
        for arm, observations in probes.items():
            empty = observations["null"]
            properties[arm] = {"initial_button_order": [s[1] for s in empty["states"]],
                               "initial_errors": empty["errors"],
                               "press_after_4": {k: {"display": v["after"], "errors": v["errors"]}
                                                 for k, v in observations.items() if k != "null"}}
        infos[tag] = {"domain_linked": pkg["direct_links"], "model_operations": pkg["model_operations"],
                      "accepted_model_panels": [bool(x) for x in pkg["model_panels"]],
                      "different_public_probes": [k for k in a if a[k] != b[k]], "public_observations": properties}
    plans = [read(f)["response"] for f in (OUT / "plans").rglob("*.json")]
    direct_rows = [compact(r) for r in primary["rows"] if r["arm"] == "direct"]
    evidence = [OUT / "registered.json", OUT / "order-control-registration.json", OUT / "seal.json",
                OUT / "scores.json", FIRST / "scores.json", FIRST / "generation-seal.json"]
    return {"study": "Local domain grammar, literal math linker, seeded model completion and constrained plan",
            "project": "calculator", "model": read(FIRST / "registered.json")["contract"]["model"],
            "revision": read(FIRST / "registered.json")["contract"]["revision"], "targets": list(TASKS),
            "target_rows": rows, "strict_direct_passed": passed_ids(direct_rows),
            "public_rule_settings": settings, "summary": summarize(rows, settings), "library_properties": infos,
            "accounting": {"api_usd": 0, "remote_calls": 0, "build_requests": calls, "build_input_tokens": input_tokens,
                           "build_output_tokens": output_tokens, "planner_requests": len(plans),
                           "planner_input_tokens": sum(p["input_tokens"] for p in plans),
                           "planner_output_tokens": sum(len(p["generated_token_ids"]) for p in plans),
                           "direct": "same 20 source responses as primary study, with more permissive page extraction"},
            "evidence_sha256": {str(f.relative_to(ROOT)): sha(f) for f in evidence},
            "sources_sha256": read(OUT / "registered.json")["contract"]["sources"] | {
                str(f.relative_to(ROOT)): sha(f) for f in [HERE / "ORDER.md", HERE / "report.py"]}}


def check(result):
    for path, digest in result["sources_sha256"].items():
        if sha(ROOT / path) != digest:
            raise ValueError("Frozen study code differs")
    rows = result["target_rows"]
    if len(rows) != 180 or any(r["status"] not in ("valid", "invalid") for r in rows):
        raise ValueError("Missing observations")
    for r in rows:
        if (r["status"] == "valid") != (type(r["passed"]) is bool and isinstance(r["report_sha256"], str)
                                            and len(r["report_sha256"]) == 64):
            raise ValueError("Invalid observation/report pairing")
    if result["summary"] != summarize(rows, result["public_rule_settings"]):
        raise ValueError("Published aggregate differs")
    if result["summary"]["builds"]["A"]["passed"]["linker"] != result["summary"]["builds"]["B"]["passed"]["linker"]:
        raise ValueError("One unchanged domain linker has conflicting outcomes")


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("action", choices=["freeze", "probe", "write", "check", "rebuild"])
    action = cli.parse_args().action
    if action == "freeze":
        freeze_rule()
        return
    if action == "probe":
        public_observations()
        return
    dest = HERE / "result.json"
    if action == "write":
        core.save(dest, make())
    result = read(dest)
    check(result)
    if action == "rebuild" and make() != result:
        raise ValueError("Public coverage differs from raw reports")
    print("Verified typed calculator Self, matched direct, fixed endpoints and linker controls.")


if __name__ == "__main__":
    main()
