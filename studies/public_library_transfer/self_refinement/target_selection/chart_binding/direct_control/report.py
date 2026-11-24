"""Audit paired Direct sensitivity against the original and remounted AI library."""
import argparse
from collections import Counter
from pathlib import Path

from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, digest, read, sha
from .. import report as binding
from . import run

RESULT = Path(__file__).with_name("result.json")


def summary(rows):
    normalized = [{"task": r["task"], "arms": {("selected" if k == "library_repaired" else k): v
                  for k, v in r["arms"].items()}} for r in rows]
    return binding.selection.comparisons(normalized, run.TASKS)


def assemble():
    seal = run.freeze()
    scores = read(run.OUT / "scores.json")
    old = read(binding.RESULT)
    groups = {}
    for model, inputs in seal["groups"].items():
        rows = []
        before = old["groups"][model]
        for row, source in zip(inputs, before["rows"], strict=True):
            t = row["task"]
            assert t == source["task"]
            arms = {label: source["arms"][key] for label, key in (
                ("direct_strict", "direct"), ("library_original", "model_plan"),
                ("library_repaired", "repaired_selected"), ("library_repaired_fixed", "repaired_first")
            )}
            for variant in ("wrapped", "repaired"):
                name = "direct_" + variant
                if variant not in row["pages"]:
                    arms[name] = {"passed": None if row["delivery"] == "missing" else False,
                                  "status": row["delivery"]}
                    continue
                files = row["pages"][variant]
                page_id = digest(files)
                receipt = scores[f"{t}/{page_id}"]
                path = ROOT / receipt["receipt"]
                root = next(p for p in (run.OUT, run.binding.selection.MATRIX, run.binding.selection.EXTENSION)
                            if p in path.parents)
                expected = dict(project=run.CHART, task=t, files_digest=page_id, contract_digest=digest(seal["contract"]))
                raw = browser.verify_receipt(root, path, expected)
                arms[name] = {k: raw[k] for k in ("passed", "files_digest", "report_sha256")}
                assert all(arms[name][key] == receipt[key] for key in arms[name])
            rows.append({k: v for k, v in row.items() if k != "pages"} | {"arms": arms})
        groups[model] = {
            "builder": before["builder"], "original_target_model": before["original_target_model"],
            "library_sha256": before["library_sha256"], "rows": rows, "vs_library_repaired": summary(rows),
            "direct_delivery": dict(Counter(r["delivery"] for r in rows)),
        }
    return {"utc_registered": read(run.OUT / "registered.json")["utc"], "utc_sealed": seal["utc"],
            "new_api_calls": 0, "registered_sha256": seal["registered_sha256"],
            "seal_sha256": sha(run.OUT / "sealed.json"), "protocol_sha256": sha(run.HERE / "PROTOCOL.md"),
            "lifecycle_report_sha256": sha(binding.RESULT), "groups": groups}


def check(report):
    assert report["new_api_calls"] == 0 and set(report["groups"]) == set(run.ROOTS)
    assert sha(binding.RESULT) == report["lifecycle_report_sha256"]
    assert sha(run.HERE / "PROTOCOL.md") == report["protocol_sha256"]
    old = read(binding.RESULT)
    for name, block in report["groups"].items():
        rows = block["rows"]
        assert [r["task"] for r in rows] == list(run.TASKS)
        assert block["vs_library_repaired"] == summary(rows)
        assert block["direct_delivery"] == dict(Counter(r["delivery"] for r in rows))
        source = old["groups"][name]
        assert source["library_sha256"] == block["library_sha256"]
        for r, prev in zip(rows, source["rows"], strict=True):
            assert r["arms"]["direct_strict"] == prev["arms"]["direct"]
            assert r["arms"]["library_repaired"] == prev["arms"]["repaired_selected"]
            assert r["arms"]["library_repaired_fixed"] == prev["arms"]["repaired_first"]
            assert r["arms"]["library_original"] == prev["arms"]["model_plan"]
        print(name, block["direct_delivery"],
              {arm: (v["selected"], v["other"], len(v["tasks"])) for arm, v in block["vs_library_repaired"].items()})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("write", "check", "check-local"))
    phase = parser.parse_args().phase
    report = read(RESULT) if phase == "check" else assemble()
    check(report)
    if phase == "write":
        core.save(RESULT, report)
    elif phase == "check-local":
        assert report == read(RESULT)
