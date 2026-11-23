"""Chart layout requirements measured at identical data and viewport."""
from __future__ import annotations

import argparse
import copy
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

from studies.interface_blind.core import browser_env, compile_plan, write_files
from studies.study_io import ROOT, UPSTREAM, digest, dump, now, read, sha, source_files
from studies.svg_chart_sources.run import files_under, materialize
from studies.webbench_draw.browser import RUNTIME, Server

HERE = Path(__file__).resolve().parent
PROJECT = UPSTREAM / "projects/svg-chart"
OLD = ROOT / "artifacts/svg-chart-sources-20261121"
MATCHED = ROOT / "artifacts/svg-chart-interfaces-20261123"
OUT = ROOT / "artifacts/svg-chart-requirement-conflict-20261123"
RESULT = ROOT / "studies/results/svg-chart-requirement-conflict-20261123.json"
ARMS = ("reference_prose", "reference_typed", "ai", "direct")
STEPS = (3, 4, 20)
GEOMETRY = (HERE / "geometry.js").read_text()
EPS = .5


def freeze_inputs():
    paths = [HERE / "run.py", HERE / "geometry.js", HERE / "PROTOCOL.md",
             OLD / "ai-package.json", OLD / "reference-package.json", OLD / "freeze.json",
             MATCHED / "freeze.json", PROJECT / "tasks.yml", PROJECT / "package.json", ROOT / "uv.lock",
             RUNTIME / "package-lock.json", ROOT / "studies/study_io.py",
             ROOT / "studies/interface_blind/core.py", ROOT / "studies/interface_blind/compile.cjs",
             ROOT / "studies/svg_chart_sources/run.py", ROOT / "studies/svg_chart_sources/compiler.js",
             ROOT / "studies/webbench_draw/browser.py", ROOT / "studies/webbench_draw/server.mjs"]
    for directory in ("src", "src-init", "assets"):
        paths.extend(p for p in (PROJECT / directory).rglob("*") if p.is_file())
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(paths)}


def verify():
    entry = read(OUT / "freeze.json")
    if entry["sha256"] != freeze_inputs():
        raise ValueError("Frozen sources changed")
    return entry


def outcome(raw):
    if raw["chartCount"] != 1:
        return "missing_chart"
    lines = raw["lines"]
    if raw["viewBox"] != [0, 0, 100, 70] or len(lines) != 3:
        return "invalid_line_chart"
    if any(not line["visible"] or len(line["points"]) != 5 for line in lines):
        return "invalid_line_chart"
    points = [p for line in lines for p in line["points"]]
    left, right = min(p[0] for p in points), max(p[0] for p in points)
    top, bottom = min(p[1] for p in points), max(p[1] for p in points)
    if max(abs(left), abs(right - 100), abs(top), abs(bottom - 70)) <= EPS:
        return "full"
    if not (EPS < left < right <= 100 + EPS and -EPS <= top < bottom < 70 - EPS):
        return "neither"
    x_axis, y_axis = raw["xAxis"], raw["yAxis"]
    if not x_axis or not y_axis:
        return "neither"
    (x1, y1), (x2, y2) = x_axis
    (a1, b1), (a2, b2) = y_axis
    if (abs(y1 - y2) <= EPS and abs(x1 - x2) > EPS and abs(a1 - a2) <= EPS and abs(b1 - b2) > EPS
        and bottom <= min(y1, y2) + EPS and left >= max(a1, a2) - EPS):
        return "inset_with_axes"
    return "neither"


def label(observations):
    answers = [outcome(raw) for raw in observations]
    if len(answers) != 2:
        raise ValueError("Two independent observations required")
    return answers[0] if answers[0] == answers[1] else "unstable"


def measure(browser, folder):
    with Server(folder) as server:
        rows = []
        for _ in range(2):
            with browser.new_context(viewport={"width": 1000, "height": 800},
                                     device_scale_factor=1, service_workers="block") as context:
                origin = urlsplit(server.url).netloc
                context.route("**/*", lambda route: route.continue_()
                              if urlsplit(route.request.url).netloc in ("", origin) else route.abort())
                page = context.new_page()
                page.on("dialog", lambda dialog: dialog.dismiss())
                response = page.goto(server.url, wait_until="networkidle", timeout=20000)
                if not response or not response.ok:
                    raise RuntimeError("Local Vite failed to serve root")
                page.evaluate("async () => {await document.fonts.ready; await new Promise(r => "
                              "requestAnimationFrame(() => requestAnimationFrame(r)))}")
                rows.append(page.evaluate(GEOMETRY))
        return rows


def fixture(inset, axes):
    x0, xmax, ymax = (10, 98, 60) if inset else (0, 100, 70)
    rows = []
    for values in ((0, .3, .5, .7, 1), (.5, .4, .3, .2, .1), (.2, .4, .3, .4, .2)):
        points = " ".join(f"{x0 + (xmax-x0)*i/4},{ymax*y}" for i, y in enumerate(values))
        rows.append(f'<polyline class="dataset" points="{points}"/>')
    axis = ""
    if axes:
        axis = ('<g class="axes-x"><line class="axis-x" x1="10" x2="98" y1="60" y2="60"/></g>'
                '<g class="axes-y"><line class="axis-y" x1="10" x2="10" y1="60" y2="0"/></g>')
    return ('<!doctype html><svg id="lineAxes" viewBox="0 0 100 70" width="400" height="280" '
            'stroke="black" fill="none"><g class="datasets">' + "".join(rows) + "</g>" + axis + "</svg>")


def variants():
    ref = read(OLD / "reference-package.json")
    classes = sorted(Path(k).stem for k in ref["files"] if re.fullmatch(r"common/\w+Chart\.js", k))
    if "LineChart" not in classes:
        raise ValueError("Missing upstream line renderer")
    for renderer in [None, *classes]:
        yield "reference", renderer or "omitted", ref, {"renderers": {"line":renderer} if renderer else {}}
    ai = read(OLD / "ai-package.json")
    for enabled in (False, True):
        plan = copy.deepcopy(ai["examples"][0]["plan"])
        plan["defaults"]["axes"] = enabled
        yield "ai", "axes_" + str(enabled).lower(), ai, plan


def collect(out):
    verify()
    if (out / "variants.json").exists():
        raise FileExistsError(out / "variants.json")
    rows = {"reference": {}, "ai": {}}
    with TemporaryDirectory() as tmp, sync_playwright() as pw:
        temporary = Path(tmp)
        (temporary / "package.json").write_bytes((PROJECT / "package.json").read_bytes())
        (temporary / "node_modules").symlink_to(RUNTIME / "node_modules", target_is_directory=True)
        controls, data = {}, {}
        browser = pw.chromium.launch(env=browser_env())
        fixtures = {"full":fixture(False, False), "inset":fixture(True, True),
                    "no_axes":fixture(True, False), "blank":"<!doctype html><title>Blank</title>"}
        for name, html in fixtures.items():
            base = temporary / name
            write_files(base, {"index.html":html})
            controls[name] = measure(browser, base)
        controls["reference"] = measure(browser, OLD / "calibration-pages/reference")
        dump(out / "calibration.json", controls)
        expected = {"full":"full", "inset":"inset_with_axes", "no_axes":"neither",
                    "blank":"missing_chart", "reference":"inset_with_axes"}
        if {k:label(v) for k,v in controls.items()} != expected:
            raise ValueError("Calibration failed; examine calibration.json")
        starter = files_under(PROJECT / "src-init")
        for source, name, package, plan in variants():
            folder = temporary / (source + "-" + name)
            files = materialize(folder, starter | compile_plan(package, plan))
            key = digest(files)
            if key not in data:
                data[key] = measure(browser, folder)
            rows[source][name] = {"plan":plan, "page":key}
        dump(out / "variants.json", {"browser_version":browser.version, "pages":data, "variants":rows})
        browser.close()


def matched_replay(out):
    verify()
    completed = MATCHED / "generation-complete.json"
    if not completed.exists():
        raise RuntimeError("Wait for full generation manifest before reading any candidate")
    if (out / "matched.json").exists():
        raise FileExistsError(out / "matched.json")
    items = {arm:{} for arm in ARMS}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(env=browser_env())
        for row in read(completed)["rows"]:
            if row["task"] not in STEPS:
                continue
            group, step = row["arm"], str(row["task"])
            if step in items[group]:
                raise ValueError("Duplicate archived candidate")
            item = {"response":row["response"], "page_files":row.get("files"), "samples":None}
            if row.get("files"):
                folder = MATCHED / "runs" / group / f"task-{step}" / "page"
                if source_files(folder) != row["files"]:
                    raise ValueError(f"Saved page differs from manifest: {group} {step}")
                item["samples"] = measure(browser, folder)
            items[group][step] = item
        browser.close()
    if any(set(values) != set(map(str, STEPS)) for values in items.values()):
        raise ValueError("Missing target record")
    dump(out / "matched.json", {"generation_sha256":sha(completed), "arms":items})


def report(out):
    freeze = verify()
    controls, raw = read(out / "calibration.json"), read(out / "variants.json")
    result = {"project":"svg-chart", "chart_id":"lineAxes", "tasks":[3,4],
              "new_diagnostic_api_cost_usd":0, "official_scores_used":False, "freeze_utc":freeze["utc"],
              "input_sha256":freeze["sha256"], "browser_version":raw["browser_version"],
              "calibration_sha256":sha(out / "calibration.json"), "variant_raw_sha256":sha(out / "variants.json"),
              "controls":{k:label(v) for k,v in controls.items()}, "target_order":["full", "inset_with_axes"],
              "libraries":{}}
    goals = result["target_order"]
    for source, variants_data in raw["variants"].items():
        states = {name:label(raw["pages"][record["page"]]) for name, record in variants_data.items()}
        result["libraries"][source] = {"tested":states, "first_witness":{g:next(
            (k for k,v in states.items() if v == g), None) for g in goals},
            "goals_witnessed":sum(g in states.values() for g in goals),
            "best_fixed_goals":max(goals.count(v) for v in states.values())}
    if (out / "matched.json").exists():
        matched = read(out / "matched.json")
        result["matched_raw_sha256"] = sha(out / "matched.json")
        result["matched_generation_sha256"] = matched["generation_sha256"]
        result["matched_arms"] = {}
        for arm, rows in matched["arms"].items():
            states = {s: (label(v["samples"]) if v["samples"] else
                          ("invalid_output" if v["response"] else "missing_response")) for s,v in rows.items()}
            early_late = [states["3"], states["4"]]
            result["matched_arms"][arm] = {"page_states":states,
                "paired_goals_met":None if "missing_response" in early_late else
                    sum(v == g for v,g in zip(early_late,goals)),
                "fixed_task20_goals_met":None if states["20"] == "missing_response" else goals.count(states["20"])}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze","run","matched","check","replay"))
    args = parser.parse_args()
    if args.action == "freeze":
        if not (OUT / "freeze.json").exists():
            dump(OUT / "freeze.json", {"utc":now(), "sha256":freeze_inputs()})
        verify()
    elif args.action == "run":
        collect(OUT)
        dump(RESULT, report(OUT))
    elif args.action == "matched":
        matched_replay(OUT)
        dump(RESULT, report(OUT))
    elif args.action == "check":
        if read(RESULT) != report(OUT):
            raise ValueError("Report differs from observations")
    else:
        with TemporaryDirectory() as tmp:
            out = Path(tmp)
            collect(out)
            if (OUT / "matched.json").exists():
                matched_replay(out)
            if report(out) != read(RESULT):
                raise ValueError("Independent browser replay differs")


if __name__ == "__main__":
    main()
