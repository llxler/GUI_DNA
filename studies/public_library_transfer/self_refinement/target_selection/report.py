"""Verify published comparisons; optionally replay their private browser receipts."""
import argparse
import re
from pathlib import Path

from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, digest, read, sha
from . import run
from .select import feature_plan

RESULT = Path(__file__).with_name("result.json")
HIST = ROOT / "studies/results"


def compact(old):
    result = {k: old[k] for k in ("passed", "report_sha256", "files_digest", "status") if k in old}
    if "page_digest" in old:
        result["files_digest"] = old["page_digest"]
    return result


def historical(group, src):
    if group == "frozen-gpt5":
        return {
            int(t): {label: compact(src["cells"][key][t]) for label, key in (("direct", "direct"), ("model_plan", "ai"))}
            for t in src["cells"]["direct"]
        }
    rows = src["models"][run.MODEL[group]]["rows"]
    old = {t: {} for t in run.TASKS}
    for row in rows:
        if row["project"] == run.CHART and row["arm"] in ("self", "direct"):
            old[row["task"]]["model_plan" if row["arm"] == "self" else "direct"] = compact(row)
    return old


def comparisons(rows, tasks):
    out = {}
    names = set.union(*(set(row["arms"]) for row in rows))
    for arm in sorted(names - {"selected"}):
        both = [r for r in rows if r["task"] in tasks and arm in r["arms"]
                and r["arms"][arm]["passed"] is not None and r["arms"]["selected"]["passed"] is not None]
        a = [r["task"] for r in both if r["arms"]["selected"]["passed"]]
        b = [r["task"] for r in both if r["arms"][arm]["passed"]]
        out[arm] = dict(tasks=[r["task"] for r in both], selected=len(a), other=len(b),
                        selected_only=sorted(set(a)-set(b)), other_only=sorted(set(b)-set(a)))
    return out


def chart_results(seal, receipts, group, data, history):
    rows = []
    public = read(run.DATA / f"{run.CHART}.json")["requirements"]
    for row, requirement in zip(data["rows"], public, strict=True):
        task = row["task"]
        assert requirement["id"] == f"task-{task}"
        arms = dict(history[task])
        for arm, plan in row["plans"].items():
            key = digest(data["files"][plan])
            item = receipts[f"{task}/{key}"]
            receipt_path = ROOT / item["receipt"]
            root = next(p for p in (run.OUT, run.MATRIX, run.EXTENSION) if p in receipt_path.parents)
            expected = dict(project=run.CHART, task=task, files_digest=key, contract_digest=digest(seal["contract"]))
            raw = browser.verify_receipt(root, receipt_path, expected)
            assert item["report_sha256"] == raw["report_sha256"] and item["passed"] is raw["passed"]
            arms[arm] = compact(raw) | {"plan_digest": plan}
        inputs = sorted(set(re.findall(r"\boptions\.([a-zA-Z_]\w*)", requirement["description"])))
        rows.append({"task": task, "public_prefix_digest": row["prefix_digest"],
                     "public_option_names_in_current_brief": inputs, "arms": arms})
    return {
        "project": run.CHART, "builder": "openai/gpt-5" if group == "frozen-gpt5" else run.MODEL[group],
        "original_target_model": "mistralai/mistral-small-3.2-24b-instruct" if group == "frozen-gpt5" else run.MODEL[group],
        "library_sha256": data["library_sha256"], "plans": data["plans"], "rows": rows,
        "vs_selected": comparisons(rows, run.TASKS), "blank_discriminating": comparisons(rows, run.TASKS[1:]),
    }


def table_results(group, selected, historical_group):
    index = {(r["task"], r["setting"]): r for r in historical_group["enumeration"]["rows"]}
    contract_hash = digest(read(run.TABLE / "browser.json"))
    rows = []
    for row, selected_key in zip(historical_group["rows"], selected, strict=True):
        task = row["task"]
        arms = {label: compact(row[key]) for label, key in
                (("fixed_first", "fixed"), ("direct", "direct"), ("model_plan", "self"))}
        settings = {"selected": selected_key}
        if historical_group["controls"]:
            assert len(historical_group["controls"]) == 1
            settings.update(fixed_off="0", fixed_on="1")
        for arm, key in settings.items():
            if key is None:
                arms[arm] = {"passed": False, "status": "no_verified_option"}
                continue
            lookup = index[task, key]
            page = lookup["files_digest"]
            file = run.TABLE / f"browser/scores/table/task-{task}/{page}/score.json"
            raw = browser.verify_receipt(run.TABLE, file, dict(project="table", task=task, files_digest=page,
                                                               contract_digest=contract_hash))
            assert raw["passed"] is lookup["passed"] and raw["report_sha256"] == lookup["report_sha256"]
            arms[arm] = compact(raw) | {"setting": key}
        rows.append({"task": task, "arms": arms})
    witnesses = [{"option": r["option"]["id"], "probe": r["option"]["probe"], "observations": r["observations"]}
                 for r in historical_group["candidate_witnesses"] if r.get("accepted")]
    return {
        "project": "table", "builder": "qwen/qwen3.5-9b", "original_target_model": "qwen/qwen3.5-9b",
        "library_sha256": historical_group["original_package_sha256"], "witnesses": witnesses,
        "rows": rows, "vs_selected": comparisons(rows, run.TASKS),
    }


def assemble():
    seal = run.freeze()
    historical_data = {k: read(HIST / name) for k, name in run.SCORE_SOURCES.items()}
    receipts = read(run.OUT / "chart-receipts.json")
    groups = {}
    for group, value in seal["selection"]["charts"].items():
        groups[group] = chart_results(seal, receipts, group, value, historical(group, historical_data[group]))
    for group, value in seal["selection"]["tables"].items():
        old = historical_data["table"]["projects"]["table"]["replicas"][group]
        groups[f"table-{group}"] = table_results(group, value["selected"], old)
    geom = read(run.OUT / "geometry.json")
    legacy = historical_data["geometry"]["matched_arms"]
    checks = {}
    chart = seal["selection"]["charts"]["frozen-gpt5"]
    for arm in run.ARMS:
        checks[arm] = {str(t): geom[chart["rows"][t-1]["plans"][arm]]["label"] for t in (3, 4)}
    for arm, prev in (("direct", "direct"), ("model_plan", "ai")):
        checks[arm] = {t: value for t, value in legacy[prev]["page_states"].items() if t in ("3", "4")}
    return {
        "selected_by": "deterministic public prefix rule", "new_api_calls": 0,
        "matrix_svg_original_build_status": {
            model: block["builds"][run.CHART]["status"]
            for k in ("qwen-self", "deepseek-self") for model, block in historical_data[k]["models"].items()
        },
        "sealed_utc": seal["utc"], "seal_sha256": sha(run.OUT / "sealed.json"),
        "source_sha256": {name: sha(HIST / name) for name in run.SCORE_SOURCES.values()},
        "protocol_sha256": sha(run.HERE / "PROTOCOL.md"), "selection_code_sha256": sha(run.HERE / "select.py"),
        "chart_official_contract_sha256": digest(seal["contract"]),
        "frozen_gpt5_geometry": {"states": checks, "observations_sha256": sha(run.OUT / "geometry.json")},
        "groups": groups,
    }


def check(result):
    assert result["new_api_calls"] == 0
    assert set(result["groups"]) == {*run.PACKAGES, "table-build-a", "table-build-b"}
    builds = {m: v["builds"][run.CHART]["status"]
              for k in ("qwen-self", "deepseek-self")
              for m, v in read(HIST / run.SCORE_SOURCES[k])["models"].items()}
    assert result["matrix_svg_original_build_status"] == builds
    assert {m for m, state in builds.items() if state == "valid"} == set(run.MODEL.values())
    for name, expected in result["source_sha256"].items():
        assert sha(HIST / name) == expected, name
    assert result["protocol_sha256"] == sha(run.HERE / "PROTOCOL.md")
    assert result["selection_code_sha256"] == sha(run.HERE / "select.py")
    for name, group in result["groups"].items():
        rows = group["rows"]
        assert [r["task"] for r in rows] == list(run.TASKS)
        assert group["vs_selected"] == comparisons(rows, run.TASKS)
        if group["project"] == run.CHART:
            assert group["blank_discriminating"] == comparisons(rows, run.TASKS[1:])
            assert set(group["plans"]) == {digest(v) for v in group["plans"].values()}
            fields = set()
            for r in rows:
                fields.update(r["public_option_names_in_current_brief"])
                plans = group["plans"]
                first = plans[r["arms"]["fixed_first"]["plan_digest"]]
                selected = plans[r["arms"]["selected"]["plan_digest"]]
                prefix = " ".join("options." + field for field in sorted(fields))
                assert selected == feature_plan(first, prefix, nested=name == "frozen-gpt5")
                for arm, const in (("fixed_on", True), ("fixed_off", False)):
                    assert plans[r["arms"][arm]["plan_digest"]] == feature_plan(
                        first, "", nested=name == "frozen-gpt5", constant=const)
            old = historical(name, read(HIST / run.SCORE_SOURCES[name]))
        else:
            historic = read(HIST / run.SCORE_SOURCES["table"])["projects"]["table"]["replicas"][name.removeprefix("table-")]
            old = {r["task"]: {"model_plan": compact(r["self"]), "direct": compact(r["direct"])} for r in historic["rows"]}
        for row in rows:
            assert all(row["arms"][k] == item for k, item in old[row["task"]].items())
        print(name, {a: (v["selected"], v["other"], len(v["tasks"])) for a, v in group["vs_selected"].items()})
    states = result["frozen_gpt5_geometry"]["states"]
    print("Geometry:", {k: int(r["3"] == "full") + int(r["4"] == "inset_with_axes") for k, r in states.items()})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("write", "check", "check-local"))
    phase = parser.parse_args().phase
    result = read(RESULT) if phase == "check" else assemble()
    check(result)
    if phase == "write":
        core.save(RESULT, result)
    elif phase == "check-local":
        assert result == read(RESULT)
