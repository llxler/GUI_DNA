"""Exhaustive browser diagnostic for incompatible card layouts in Web-Bench flex."""
from __future__ import annotations

import argparse
import itertools
import math
import tempfile
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

from studies.interface_blind.core import Server, browser_env, write_files
from studies.study_io import ROOT, UPSTREAM, digest, dump, now, read, sha, source_files
from studies.webbench_expand.core import compile_plan

HERE = Path(__file__).resolve().parent
PROJECT = UPSTREAM / "projects/flex"
ARCHIVE = ROOT / "artifacts/matched-flex-20261118"
OUT = ROOT / "artifacts/flex-requirement-conflict-20261123"
RESULT = ROOT / "studies/results/flex-requirement-conflict-20261123.json"
WIDTHS = (900, 550)
TARGETS = {900: (3, 2), 550: (2, 1)}
GROUPS = ("plan-1", "plan-2", "free-1", "free-2")
STEPS = (12, 16, 20)

RECTANGLES = """() => {
  function visible(el) {
    const rect = el.getBoundingClientRect();
    return el.checkVisibility({opacityProperty: true, visibilityProperty: true})
      && rect.width > 0 && rect.height > 0;
  }
  const containers = [...document.querySelectorAll('.content')].filter(visible);
  const cards = containers.length === 1 ? [...containers[0].querySelectorAll('.card')] : [];
  return {viewport: [innerWidth, innerHeight], containers: containers.length,
    cards: cards.map(el => {
      const r = el.getBoundingClientRect();
      return {left: r.left, top: r.top, right: r.right, bottom: r.bottom, visible: visible(el)};
    })};
}"""


def plan_space(schema):
    if schema["type"] == "string":
        return schema["enum"]
    fields = schema["properties"]
    if schema["type"] != "object" or schema["additionalProperties"] or set(schema["required"]) != set(fields):
        raise ValueError("Expected required nested enum fields in a closed object")
    return [dict(zip(fields, values, strict=True)) for values in
            itertools.product(*(plan_space(child) for child in fields.values()))]


def frozen_inputs():
    files = [HERE / "PROTOCOL.md", HERE / "run.py", ROOT / "uv.lock",
             ROOT / "studies/study_io.py", ROOT / "studies/webbench_expand/core.py",
             ROOT / "studies/webbench_expand/schema.py", ROOT / "studies/interface_blind/core.py",
             ROOT / "studies/interface_blind/compile.cjs", ROOT / "studies/matched_flex/PROTOCOL.md",
             ARCHIVE / "protocol-freeze.json", ARCHIVE / "generated.json", PROJECT / "tasks.jsonl",
             ARCHIVE / "public/flex/tasks.jsonl", PROJECT / "src/index.html"]
    if sha(PROJECT / "tasks.jsonl") != sha(ARCHIVE / "public/flex/tasks.jsonl"):
        raise ValueError("Matched workflow used different public requirements")
    for replica in (1, 2):
        files.append(ARCHIVE / f"plan-{replica}/prepare/frozen.json")
    for group, step in itertools.product(GROUPS, STEPS):
        record = ARCHIVE / group / f"task-{step}/result.json"
        folder = ROOT / read(record)["page"]
        files.extend([record, *(path for path in folder.rglob("*") if path.is_file())])
    hashes = {str(path.relative_to(ROOT)): sha(path) for path in sorted(files)}
    generated = read(ARCHIVE / "generated.json")["sha256"]
    group_dirs = tuple(f"{ARCHIVE.relative_to(ROOT)}/{group}/" for group in GROUPS)
    for name, value in hashes.items():
        if name.startswith(group_dirs) and generated.get(name) != value:
            raise ValueError(f"Input differs from the original generation manifest: {name}")
    return hashes


def verify_freeze():
    freeze = read(OUT / "freeze.json")
    if frozen_inputs() != freeze["sha256"]:
        raise ValueError("Frozen input or diagnostic code changed")
    return freeze


def classify(rects):
    if rects["containers"] != 1:
        return "container_count"
    cards = rects["cards"]
    if len(cards) != 12:
        return "card_count"
    if any(not c["visible"] or not all(math.isfinite(c[k]) for k in ("left", "top", "right", "bottom"))
           for c in cards):
        return "invisible_card"
    rows = []
    for card in sorted(cards, key=lambda c: (c["top"], c["left"])):
        if not rows or card["top"] - rows[-1][0]["top"] > 1:
            rows.append([])
        rows[-1].append(card)
    for row in rows:
        row.sort(key=lambda c: c["left"])
        if any(a["right"] - b["left"] > 1 for a, b in zip(row, row[1:])):
            return "overlap"
    counts = {len(row) for row in rows}
    return str(counts.pop()) if len(counts) == 1 else "uneven_rows"


def observe(browser, folder):
    server = Server(folder)
    try:
        result = {}
        for width in WIDTHS:
            samples = []
            for _ in range(2):
                context = browser.new_context(viewport={"width": width, "height": 800},
                                              device_scale_factor=1, service_workers="block")
                try:
                    def restrict(route):
                        url = urlsplit(route.request.url)
                        if (url.scheme in {"data", "blob", "about"} or
                            (url.hostname == "127.0.0.1" and url.port == server.port)):
                            route.continue_()
                        else:
                            route.abort()
                    context.route("**/*", restrict)
                    page = context.new_page()
                    page.on("dialog", lambda dialog: dialog.dismiss())
                    response = page.goto(f"http://127.0.0.1:{server.port}/index.html", timeout=15000)
                    if not response or not response.ok:
                        raise RuntimeError("Page did not load")
                    page.evaluate("async () => {await document.fonts.ready; await new Promise(done => "
                                  "requestAnimationFrame(() => requestAnimationFrame(done)))}")
                    rects = page.evaluate(RECTANGLES)
                    if rects["viewport"] != [width, 800]:
                        raise ValueError("Unexpected actual browser viewport")
                    samples.append(rects)
                finally:
                    context.close()
            result[str(width)] = samples
        return result
    finally:
        server.close()


def control_html(columns=1, count=12, overlap=False):
    css = f".content {{display: flex; flex-wrap: wrap}} .card {{flex: 0 0 {100 / columns - .01}%; height: 100px}}"
    if overlap:
        css += ".content {min-height: 200px} .card {position:absolute; top:0; left:0; width:50px}"
    return '<!doctype html><style>' + css + '</style><div class="content">' + (
        '<div class="card"></div>' * count) + '</div>'


def layout(samples):
    answers = [classify(rects) for rects in samples]
    if len(answers) != 2:
        raise ValueError("Each viewport requires two fresh loads")
    return answers[0] if answers[0] == answers[1] else "unstable"


def compact(observations):
    return {width: layout(samples) for width, samples in observations.items()}


def control_targets():
    return {"one": ["1", "1"], "two": ["2", "2"], "three": ["3", "3"],
            "blank": ["container_count"] * 2, "eleven": ["card_count"] * 2,
            "overlap": ["overlap"] * 2, "reference": ["2", "1"]}


def calibrate(controls, pages):
    if set(controls) != set(control_targets()):
        raise ValueError("Missing calibration pages")
    for label, expected in control_targets().items():
        actual = compact(pages[controls[label]])
        if [actual[str(w)] for w in WIDTHS] != expected:
            raise ValueError(f"Control {label}: observed {actual}, expected {expected}")


def collect(out):
    verify_freeze()
    raw_path = out / "observations.json"
    if raw_path.exists():
        raise FileExistsError("Raw data already exist; use check or replay")
    pages, plans, archived, controls = {}, {}, {}, {}
    with tempfile.TemporaryDirectory() as temporary, sync_playwright() as pw:
        browser = pw.chromium.launch(env=browser_env())
        def measure(folder):
            key = digest(source_files(folder))
            if key not in pages:
                pages[key] = observe(browser, folder)
            return key
        def measure_files(files):
            folder = Path(temporary) / digest(files)
            if not folder.exists():
                write_files(folder, files)
            return measure(folder)
        for label, html in {"one": control_html(), "two": control_html(2), "three": control_html(3),
                            "blank": "<!doctype html><title>Blank</title>",
                            "eleven": control_html(count=11), "overlap": control_html(overlap=True)}.items():
            controls[label] = measure_files({"index.html": html})
        controls["reference"] = measure(PROJECT / "src")
        calibration_path = out / "calibration.json"
        dump(calibration_path, {label: pages[key] for label, key in controls.items()})
        calibrate(controls, pages)
        for replica, expected in ((1, 8), (2, 32)):
            key = f"plan-{replica}"
            package = read(ARCHIVE / key / "prepare/frozen.json")
            variants = plan_space(package["plan_schema"])
            if len(variants) != expected or len({digest(p) for p in variants}) != expected:
                raise ValueError("Unexpected legal plan space")
            plans[key] = []
            for plan in variants:
                try:
                    files = compile_plan(package, plan)
                except (ValueError, TypeError, KeyError) as error:
                    plans[key].append({"plan": plan, "page": None, "error": str(error)})
                else:
                    plans[key].append({"plan": plan, "page": measure_files(files)})
        for group in GROUPS:
            archived[group] = {}
            for step in STEPS:
                folder = ROOT / read(ARCHIVE / group / f"task-{step}/result.json")["page"]
                archived[group][str(step)] = measure(folder)
        version = browser.version
        browser.close()
    dump(raw_path, {"browser_version": version, "controls": controls, "pages": pages,
                    "plans": plans, "archived": archived})


def summarize(raw, freeze):
    pages = {key: compact(samples) for key, samples in raw["pages"].items()}
    calibrate(raw["controls"], raw["pages"])
    result = {"project": "flex", "scope": "Public card-column diagnostic; two calibration widths. No official scores.",
              "new_api_cost_usd": 0, "builder_and_generator": "openai/gpt-5 (medium)",
              "upstream_commit": "7b31ca2b786eef120dd49ce63dd03d0c0006046d",
              "freeze_utc": freeze["utc"], "input_sha256": freeze["sha256"],
              "browser_version": raw["browser_version"], "observations_sha256": sha(OUT / "observations.json"),
              "widths_px": {"900": {"tasks": [12, 13], "required_columns": [3, 2]},
                            "550": {"tasks": [13, 14], "required_columns": [2, 1]}},
              "repeated_loads": 2, "controls": {k: pages[v] for k, v in raw["controls"].items()},
              "libraries": {}, "archived_workflows": {}}
    for group, variants in raw["plans"].items():
        data = {"plans_tested": len(variants), "distinct_pages": len({v["page"] for v in variants if v["page"]}),
                "widths": {}}
        for width, goals in TARGETS.items():
            labels = [pages[v["page"]][str(width)] if v["page"] else "compile_error" for v in variants]
            counts = Counter(labels)
            witnesses = {str(goal): next((v["plan"] for v, label in zip(variants, labels)
                                          if label == str(goal)), None) for goal in goals}
            data["widths"][str(width)] = {
                "layout_counts": dict(sorted(counts.items())),
                "goals_witnessed": sum(str(g) in counts for g in goals),
                "best_fixed_goals": max(sum(label == str(g) for g in goals) for label in labels),
                "first_witness_plan": witnesses,
            }
        result["libraries"][group] = data
    for group, saved in raw["archived"].items():
        views = {s: pages[key] for s, key in saved.items()}
        sequences = {}
        for width, late in ((900, 2), (550, 1)):
            w = str(width)
            goals = ("3", str(late))
            observed = [views[s][w] for s in ("12", "16")]
            fixed = views["20"][w]
            sequences[w] = {"target_columns": list(map(int, goals)), "task12_and_task16_columns": observed,
                            "goals_met_by_archived_pair": sum(a == b for a, b in zip(observed, goals)),
                            "fixed_task20_columns": fixed, "goals_met_by_fixed_task20": goals.count(fixed)}
        result["archived_workflows"][group] = sequences
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "check", "replay"))
    args = parser.parse_args()
    if args.action == "freeze":
        path = OUT / "freeze.json"
        if not path.exists():
            dump(path, {"utc": now(), "sha256": frozen_inputs()})
        verify_freeze()
        return
    freeze = verify_freeze()
    if args.action == "run":
        collect(OUT)
    result = summarize(read(OUT / "observations.json"), freeze)
    if args.action == "run":
        if RESULT.exists():
            raise FileExistsError(RESULT)
        dump(RESULT, result)
    elif result != read(RESULT):
        raise ValueError("Archived report differs from observations")
    if args.action == "replay":
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            collect(out)
            replay = read(out / "observations.json")
            saved = read(OUT / "observations.json")
            if replay != saved:
                raise ValueError("Independent browser replay differs from recorded observations")


if __name__ == "__main__":
    main()
