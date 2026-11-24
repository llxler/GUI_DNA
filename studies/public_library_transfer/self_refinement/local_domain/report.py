"""Reproduce published local calculator comparisons from individual current-target receipts."""
import argparse
from collections import Counter
from pathlib import Path

from studies.public_library_transfer import core
from studies.study_io import ROOT, read, sha
from .run import HERE, OUT, SEEDS, TASKS

PUBLISHED = HERE / "result.json"


def compact(row):
    return {key: row.get(key) for key in ("task", "arm", "rep", "setting", "status", "passed", "report_sha256")}


def passed_ids(rows):
    return [r["task"] for r in rows if r["passed"] is True]


def summarize(rows):
    direct = [r for r in rows if r["arm"] == "direct"]
    if sorted(r["task"] for r in direct) != list(TASKS):
        raise ValueError("Expected one direct page observation per task")
    targets = set(passed_ids(direct))
    out = {"direct": {"passed": sorted(targets), "delivered": sum(r["status"] == "valid" for r in direct)}, "builds": {}}
    for tag in SEEDS:
        by_arm = {}
        for arm in ("self", "fixed-A", "fixed-B", "fixed-components"):
            group = [r for r in rows if r["arm"] == arm and r["rep"] == tag]
            if sorted(r["task"] for r in group) != list(TASKS):
                raise ValueError(f"Incomplete positions: {tag}/{arm}")
            by_arm[arm] = group
        current = set(passed_ids(by_arm["self"]))
        for row in by_arm["self"]:
            if row["status"] != "valid":
                continue
            same = next(r for r in by_arm["fixed-" + row["setting"]] if r["task"] == row["task"])
            if (same["passed"], same["report_sha256"]) != (row["passed"], row["report_sha256"]):
                raise ValueError("Planned page and selected fixed endpoint differ")
        out["builds"][tag] = {
            "passed": {arm: passed_ids(group) for arm, group in by_arm.items()},
            "selected": dict(Counter(r["setting"] for r in by_arm["self"] if r["setting"])),
            "only_self": sorted(current - targets), "only_direct": sorted(targets - current),
            "both": sorted(current & targets), "neither": sorted(set(TASKS) - targets - current),
        }
    return out


def verify(result):
    rows = result["target_rows"]
    if len(rows) != 180 or result["targets"] != list(TASKS):
        raise ValueError("Unexpected registered target matrix")
    for row in rows:
        if row["status"] not in ("valid", "build_failed", "invalid"):
            raise ValueError("Unobserved rows are not known pipeline failures")
        if (row["status"] == "valid") != (type(row["passed"]) is bool and
                                           isinstance(row["report_sha256"], str) and len(row["report_sha256"]) == 64):
            raise ValueError("Page/evidence mismatch")
    if result["summary"] != summarize(rows):
        raise ValueError("Published summary differs from individual results")
    for key, name in [("generation_sources_sha256", None), ("probe_sources_sha256", None)]:
        for path, digest in result[key].items():
            if sha(ROOT / path) != digest:
                raise ValueError(f"Changed study source {path}")


def build_result():
    rows = [compact(row) for src in [OUT / "scores.json", OUT / "probe" / "scores.json"] for row in read(src)["rows"]]
    builds = {}
    for tag in SEEDS:
        folder = OUT / "builds" / tag
        pkg = read(folder / "library.json")
        ends = read(folder / "endpoints.json")
        endpoint_obs = {}
        for p in sorted((OUT / "probe" / tag).glob("observed-*.json")):
            obs = read(p)["observations"]
            endpoint_obs[p.stem.removeprefix("observed-")] = obs
        keys = list(pkg["actions"])
        differences = None
        if "A" in endpoint_obs and "B" in endpoint_obs:
            differences = [label for label in endpoint_obs["A"] if endpoint_obs["A"][label] != endpoint_obs["B"][label]]
        builds[tag] = {"axis": pkg["axis"], "admitted": pkg["valid"], "labels": keys, "valid_expressions":
                       [k for k in keys if pkg["actions"][k]], "admitted_panels": [bool(x) for x in pkg["panels"]],
                       "endpoint_load_errors": {k: v["public_load_errors"] for k, v in ends.items()},
                       "different_public_probes": differences,
                       "component_probe": {key: {"before": item["before"], "after": item["after"], "errors": item["errors"]}
                                           for key, item in endpoint_obs["components"].items()}}
    inference_logs = [read(f) for f in (OUT / "builds").rglob("*.json") if "output_ids" in read(f)]
    direct_logs = [read(f) for f in (OUT / "direct").glob("batch-*.json")]
    planned = [read(f)["response"] for f in (OUT / "plans").rglob("*.json")]
    accounting = {"remote_calls": 0, "api_usd": 0, "weight_revision": read(OUT / "registered.json")["contract"]["revision"]}
    for name, logs in [("build", inference_logs), ("direct", direct_logs)]:
        accounting[name] = {"requests": sum(len(x["outputs"]) for x in logs),
                            "input_tokens": sum(sum(x["input_tokens"]) for x in logs),
                            "output_tokens": sum(len(seq) for x in logs for seq in x["output_ids"])}
    accounting["plan"] = {"requests": len(planned), "input_tokens": sum(p["input_tokens"] for p in planned),
                          "output_tokens": sum(len(p["generated_token_ids"]) for p in planned)}
    evidence = [OUT / "generation-seal.json", OUT / "registered.json", OUT / "environment.json",
                OUT / "scores.json", OUT / "probe" / "registered.json", OUT / "probe" / "scores.json"]
    result = {"project": "calculator", "model": read(OUT / "registered.json")["contract"]["model"], "targets": list(TASKS),
              "protocol": "Domain-scaffolded local Self; fresh raw HTML direct; fixed endpoints and fixed components",
              "generation_sources_sha256": read(OUT / "registered.json")["contract"]["sources"],
              "probe_sources_sha256": {str(p.relative_to(ROOT)): sha(p) for p in [HERE / "PROBE.md", HERE / "probe.py"]},
              "evidence_sha256": {str(f.relative_to(ROOT)): sha(f) for f in evidence},
              "accounting": accounting, "library_properties": builds, "summary": summarize(rows), "target_rows": rows}
    verify(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["check", "write", "rebuild"])
    args = parser.parse_args()
    if args.mode == "write":
        core.save(PUBLISHED, build_result())
    result = read(PUBLISHED)
    verify(result)
    if args.mode == "rebuild" and build_result() != result:
        raise ValueError("Raw artifact comparison differs from published result")
    print("Verified two local builds and 20 matched direct targets.")


if __name__ == "__main__":
    main()
