"""Seal prefix-based settings, then score their full pages on current files."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from studies.interface_blind.core import compile_plan
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, digest, now, read, sha
from studies.webbench.svg_chart.library_sources.run import materialize

from .select import feature_plan, witnessed_setting

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/requirement-option-selection-20261124"
TABLE = ROOT / "artifacts/executable-self-options-20261124/table"
DATA = ROOT / "artifacts/public-library-transfer-20261123/inputs"
CHART = "svg-chart"
MATRIX = ROOT / "artifacts/backbone-matrix-20261124"
EXTENSION = ROOT / "artifacts/backbone-extension-20261124"
PACKAGES = {
    "frozen-gpt5": ROOT / "artifacts/svg-chart-interfaces-20261123/packages/ai.json",
    "qwen-self": MATRIX / "qwen" / CHART / "build/package.json",
    "deepseek-self": EXTENSION / "deepseek-flash" / CHART / "build/package.json",
}
SCORE_SOURCES = {
    "frozen-gpt5": "svg-chart-interfaces-20261123.json",
    "qwen-self": "backbone-matrix-20261124.json",
    "deepseek-self": "backbone-extension-20261124.json",
    "table": "self-executable-options-20261124.json",
    "geometry": "svg-chart-requirement-conflict-20261123.json",
}
MODEL = {"qwen-self": "qwen/qwen3-coder-30b-a3b-instruct", "deepseek-self": "deepseek/deepseek-v4-flash"}
ARMS = ("selected", "fixed_first", "fixed_off", "fixed_on")
TASKS = tuple(range(1, 21))


def prefixes(project):
    description = []
    rows = read(DATA / f"{project}.json")["requirements"]
    for task, row in zip(TASKS, rows, strict=True):
        assert row["id"] == f"task-{task}"
        description.append(row["description"])
        yield task, "\n".join(description)


def selection():
    chart, tables = {}, {}
    for group, path in PACKAGES.items():
        pkg = read(path)
        nested = group == "frozen-gpt5"
        initial = pkg["examples"][0]["plan"]
        plans, pages, rows = {}, {}, []
        for task, prefix in prefixes(CHART):
            arms = {}
            for arm, plan in (
                ("fixed_first", initial),
                ("fixed_off", feature_plan(initial, prefix, nested=nested, constant=False)),
                ("fixed_on", feature_plan(initial, prefix, nested=nested, constant=True)),
                ("selected", feature_plan(initial, prefix, nested=nested)),
            ):
                key = digest(plan)
                if key not in plans:
                    target = OUT / "candidates" / group / key
                    if nested:
                        starter = read(DATA / f"{CHART}.json")["starter"]
                        files = materialize(target, starter | compile_plan(pkg, plan))
                    else:
                        files = core.materialize(CHART, pkg, plan, target)
                    plans[key], pages[key] = plan, files
                arms[arm] = key
            rows.append({"task": task, "prefix_digest": digest(prefix), "plans": arms})
        chart[group] = {"library_sha256": sha(path), "plans": plans, "files": pages, "rows": rows}
    for group in ("build-a", "build-b"):
        source = TABLE / group / "build/status.json"
        options = [row for row in read(source)["proposal_log"] if row["accepted"]]
        tables[group] = {"public_status_sha256": sha(source),
                         "selected": [witnessed_setting(options, p) for _, p in prefixes("table")]}
    return {"charts": chart, "tables": tables}


def protocol_inputs():
    inputs = [HERE / "PROTOCOL.md", HERE / "run.py", HERE / "select.py", *PACKAGES.values(),
              DATA / f"{CHART}.json", DATA / "table.json",
              *(TABLE / k / "build/status.json" for k in ("build-a", "build-b")),
              Path(core.__file__), Path(browser.__file__),
              ROOT / "studies/webbench/svg_chart/library_sources/run.py",
              ROOT / "studies/interface_blind/compile.cjs", ROOT / "studies/interface_blind/core.py",
              ROOT / "studies/webbench/svg_chart/plot_geometry/geometry.js",
              ROOT / "studies/webbench/svg_chart/plot_geometry/run.py"]
    return {str(path.relative_to(ROOT)): sha(path) for path in inputs}


def freeze():
    sealed = OUT / "sealed.json"
    inputs = protocol_inputs()
    if sealed.exists():
        rec = read(sealed)
        if rec["sources"] != inputs or rec["selection"] != selection():
            raise ValueError("Sealed inputs or plans differ")
        return rec
    assert {p for root in (MATRIX, EXTENSION) for p in root.glob("*/svg-chart/build/package.json")} == {
        PACKAGES["qwen-self"], PACKAGES["deepseek-self"]}
    rec = {"utc": now(), "sources": inputs, "contract": browser.verify_contract(CHART), "selection": selection()}
    core.save(sealed, rec)
    return rec


def run_charts(seal):
    browser.OUT = OUT
    contract = browser.verify_contract(CHART)
    assert contract == seal["contract"]
    unique_jobs = {}
    for name, group in seal["selection"]["charts"].items():
        for row in group["rows"]:
            for plan in row["plans"].values():
                files = group["files"][plan]
                job = (row["task"], digest(files))
                unique_jobs[job] = (row["task"], OUT / "candidates" / name / plan, files)
    def one(job):
        task, page, files = job
        key = digest(files)
        original = Path("browser/scores") / CHART / f"task-{task}" / key / "score.json"
        expected = dict(project=CHART, task=task, files_digest=key, contract_digest=digest(contract))
        for root in (MATRIX, EXTENSION):
            if (root / original).exists():
                browser.verify_page(page, files, CHART)
                receipt = browser.verify_receipt(root, root / original, expected)
                break
        else:
            root = OUT
            receipt = browser.run_one(OUT, CHART, task, page, files, contract)
        return f"{task}/{key}", {"passed": receipt["passed"], "files_digest": key,
                                "report_sha256": receipt["report_sha256"], "receipt": str((root / original).relative_to(ROOT))}
    with ThreadPoolExecutor(max_workers=3) as workers:
        rows = dict(workers.map(one, unique_jobs.values()))
    core.save(OUT / "chart-receipts.json", rows)


def run_geometry(seal):
    from playwright.sync_api import sync_playwright
    from studies.webbench.svg_chart.plot_geometry import run as geom
    group = seal["selection"]["charts"]["frozen-gpt5"]
    outcomes = {}
    # The legacy metric uses the same pinned Vite runtime and unchanged public data.
    with sync_playwright() as pw:
        engine = pw.chromium.launch(env=geom.browser_env())
        for task in (3, 4):
            for arm in ARMS:
                key = group["rows"][task - 1]["plans"][arm]
                if key not in outcomes:
                    page = OUT / "candidates/frozen-gpt5" / key
                    page = browser.served_page(OUT, CHART, page, group["files"][key])
                    observations = geom.measure(engine, page)
                    outcomes[key] = {"label": geom.label(observations), "observations": observations}
        engine.close()
    core.save(OUT / "geometry.json", outcomes)


if __name__ == "__main__":
    action = argparse.ArgumentParser(description=__doc__)
    action.add_argument("phase", choices=("freeze", "score", "geometry"))
    phase = action.parse_args().phase
    seal = freeze()
    if phase == "score":
        run_charts(seal)
    elif phase == "geometry":
        run_geometry(seal)
