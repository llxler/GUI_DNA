"""Compare mounted renderers with the original Self library, Direct and fixed pages."""
import argparse
from pathlib import Path

from studies.public_library_transfer import browser, core
from studies.study_io import digest, read, sha
from .. import report as selection
from . import run

RESULT = Path(__file__).with_name("result.json")


def counts(rows, tasks):
    return selection.comparisons([{"task": r["task"], "arms": {
        "selected" if name == "repaired_selected" else name: cell
        for name, cell in r["arms"].items()
    }} for r in rows], tasks)


def assemble():
    seal = run.freeze()
    old = read(selection.RESULT)
    scores = read(run.OUT / "scores.json")
    groups = {}
    for model, block in seal["groups"].items():
        rows = []
        history = old["groups"][model]
        assert history["library_sha256"] == block["library_sha256"]
        for r, prev in zip(block["rows"], history["rows"], strict=True):
            n = r["task"]
            assert prev["task"] == n
            arms = {k: prev["arms"][k] for k in ("direct", "model_plan", "fixed_first", "selected")}
            arms["original_selected"] = arms.pop("selected")
            for k, page in r["choices"].items():
                key = digest(block["pages"][page])
                value = scores[f"{n}/{key}"]
                path = run.OUT / f"browser/scores/{run.CHART}/task-{n}/{key}/score.json"
                expected = dict(project=run.CHART, task=n, files_digest=key, contract_digest=digest(seal["contract"]))
                raw = browser.verify_receipt(run.OUT, path, expected)
                assert selection.compact(raw) == value
                arms[k] = value
            rows.append({"task": n, "arms": arms})
        groups[model] = {
            "builder": history["builder"], "original_target_model": history["original_target_model"],
            "library_sha256": block["library_sha256"], "public_observations": block["observed"],
            "public_error_edits": block["edits"], "rows": rows, "vs_repaired_selected": counts(rows, run.selection.TASKS),
            "blank_discriminating": counts(rows, run.selection.TASKS[1:]),
        }
    return {"new_api_calls": 0, "researcher_added_code": "SVG lifecycle mounting; public scope-error repair",
            "original_comparators_sha256": sha(selection.RESULT),
            "registration_utc": seal["registration_utc"], "sealed_utc": seal["utc"],
            "seal_sha256": sha(run.OUT / "sealed.json"), "protocol_sha256": sha(run.HERE / "PROTOCOL.md"),
            "repair_sha256": sha(run.HERE / "hoist.cjs"), "harness_contract_sha256": digest(seal["contract"]),
            "groups": groups}


def check(report):
    assert report["original_comparators_sha256"] == sha(selection.RESULT)
    assert report["protocol_sha256"] == sha(run.HERE / "PROTOCOL.md")
    assert report["repair_sha256"] == sha(run.HERE / "hoist.cjs")
    assert report["new_api_calls"] == 0 and set(report["groups"]) == set(run.MODELS)
    old = read(selection.RESULT)
    assert report["harness_contract_sha256"] == old["chart_official_contract_sha256"]
    for model, group in report["groups"].items():
        assert group["library_sha256"] == old["groups"][model]["library_sha256"]
        rows = group["rows"]
        assert [r["task"] for r in rows] == list(run.selection.TASKS)
        assert all(len(seq) == 2 and seq[0] == seq[1] for seq in group["public_observations"].values())
        assert group["vs_repaired_selected"] == counts(rows, run.selection.TASKS)
        assert group["blank_discriminating"] == counts(rows, run.selection.TASKS[1:])
        for r, before in zip(rows, old["groups"][model]["rows"], strict=True):
            for name, original in (("direct","direct"),("model_plan","model_plan"),("fixed_first","fixed_first"),
                                   ("original_selected","selected")):
                assert r["arms"][name] == before["arms"][original]
        print(model, {name: (v["selected"], v["other"], len(v["tasks"]))
                      for name, v in group["vs_repaired_selected"].items()})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("write", "check", "check-local"))
    phase = parser.parse_args().phase
    value = read(RESULT) if phase == "check" else assemble()
    check(value)
    if phase == "write":
        core.save(RESULT, value)
    elif phase == "check-local":
        assert value == read(RESULT)
