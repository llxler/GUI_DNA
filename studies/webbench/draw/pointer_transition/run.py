"""Replay a fixed short pointer stroke on previously generated Web-Bench drawing pages."""
import argparse
import math
from pathlib import Path
import shutil
from urllib.parse import urlsplit

from playwright.sync_api import Error as BrowserError, sync_playwright

from studies.interface_blind.core import browser_env, write_files
from studies.study_io import ROOT, UPSTREAM, digest, dump, now, read, sha, source_files
from studies.table_library_sources.run import file_hashes, verify
from studies.webbench_draw.browser import Server
from studies.webbench_draw.core import BUILD, compile_plan, slug

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/draw-pointer-transition-20261123"
PUBLIC = ROOT / "studies/results/draw-pointer-transition-20261123.json"
PROJECT = UPSTREAM / "projects/draw"
AUDIT = ROOT / "studies/results/draw-interface-audit-20261117.json"
PRIMARY = ROOT / "studies/results/end_to_end.json"
PROBE = "([phase, distance]) => {" + (HERE / "probe.js").read_text() + "}"
DISTANCES = (3, 18)
TOLERANCE = 0.6


def freeze():
    if (OUT / "freeze.json").exists():
        verify(read(OUT / "freeze.json")["inputs"])
        return
    ref = BUILD / "libraries" / slug("openai/gpt-5") / "package.json"
    package, audit = read(ref), read(AUDIT)
    assert sha(ref) == audit["package_sha256"] and len(audit["rows"]) == 162
    paths = [HERE / "PROTOCOL.md", HERE / "run.py", HERE / "probe.js", PRIMARY, AUDIT, ref, PROJECT / "tasks.jsonl",
             ROOT / "studies/webbench_draw/server.mjs", ROOT / "studies/webbench_draw/browser.py"]
    lookup = {}
    def add(label, folder):
        hashes = source_files(folder)
        paths.extend(folder / n for n in hashes)
        lookup[label] = {"folder": str(folder.relative_to(ROOT)), "files": hashes, "digest": digest(hashes)}
    for name, sub in [("reference", "src"), ("starter", "src-init")]:
        folder = OUT / "controls" / name
        shutil.copytree(PROJECT / sub, folder, dirs_exist_ok=True)
        assert source_files(folder) == source_files(PROJECT / sub)
        add("control/" + name, folder)
    blank = OUT / "controls/blank"
    write_files(blank, {"index.html": "<!doctype html><title>Blank</title><body></body>"})
    add("control/blank", blank)
    for i, r in enumerate(audit["rows"]):
        result = compile_plan(package, r["plan"])
        assert digest(result) == r["output_sha256"]
        folder = OUT / "settings" / str(i)
        write_files(folder, result)
        add(f"setting/{i}", folder)
    for r in read(PRIMARY)["records"]:
        if r["cohort"] != "draw" or r["task"] not in ("task-8", "task-12") or r["method"] not in ("free", "plan"):
            continue
        path = ROOT / r["record"]
        paths.append(path)
        attempt = read(path)["attempts"][-1]
        key = "/".join(["candidate", slug(r["model"]), slug(r["builder"]) if r["builder"] else "direct", r["task"]])
        assert key not in lookup
        if attempt.get("version"):
            add(key, path.parent / attempt["version"])
        else:
            lookup[key] = {"folder": None}
    assert len(lookup) == 3 + 162 + 12
    dump(OUT / "freeze.json", {"utc": now(), "inputs": file_hashes(paths), "pages": lookup})


def gesture(browser, url, distance):
    with browser.new_context(viewport={"width": 900, "height": 700}, device_scale_factor=1,
                             service_workers="block") as context:
        origin = urlsplit(url).netloc
        context.route("**/*", lambda r: r.continue_() if urlsplit(r.request.url).netloc == origin else r.abort())
        page = context.new_page()
        page.set_default_timeout(5000)
        page.goto(url, wait_until="networkidle")
        result = page.evaluate(PROBE, ["prepare", distance])
        if result["status"] != "ready":
            return result
        page.mouse.move(*result["start"])
        page.mouse.down()
        page.mouse.move(*result["end"], steps=3)
        page.mouse.up()
        page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
        return page.evaluate(PROBE, ["measure", distance])


def mode(rows):
    def exact(row, n):
        if row["status"] != "line":
            return False
        a, b = row["start"], row["end"]
        return any(math.dist(x, (80, 80)) <= TOLERANCE and math.dist(y, (80 + n, 80)) <= TOLERANCE
                   for x, y in ((a, b), (b, a)))
    if not all(exact(r, 18) for r in rows["18"]):
        return "long control unavailable"
    modes = []
    for r in rows["3"]:
        if exact(r, 3):
            modes.append("release position")
        elif r["status"] == "line" and abs(math.dist(r["start"], r["end"]) - 9) <= TOLERANCE:
            modes.append("minimum length")
        elif r["status"] == "line":
            modes.append("other length")
        else:
            modes.append("short stroke unavailable")
    return modes[0] if modes[0] == modes[1] else "inconsistent"


def run():
    frozen = read(OUT / "freeze.json")
    verify(frozen["inputs"])
    with sync_playwright() as pw:
        browser = pw.chromium.launch(env=browser_env())
        for label, page in frozen["pages"].items():
            if page["folder"] is None:
                continue
            out = OUT / "measurements" / (page["digest"] + ".json")
            if not out.exists():
                with Server(ROOT / page["folder"]) as server:
                    rows = {}
                    for distance in DISTANCES:
                        pairs = []
                        for _ in range(2):
                            try:
                                pairs.append(gesture(browser, server.url, distance))
                            except BrowserError as e:
                                pairs.append({"status": "browser interaction error", "detail": str(e)[:250]})
                        rows[str(distance)] = pairs
                dump(out, {"page_digest": page["digest"], "browser": browser.version, "rows": rows, "mode": mode(rows)})
            result = read(out)
            if label == "control/reference":
                assert result["mode"] != "long control unavailable", result
            elif label in ("control/starter", "control/blank"):
                assert result["mode"] == "long control unavailable", result
        browser.close()


def report():
    frozen = read(OUT / "freeze.json")
    verify(frozen["inputs"])
    modes, raw = {}, {}
    for label, p in frozen["pages"].items():
        if p["folder"] is None:
            modes[label] = "invalid saved response"
            continue
        path = OUT / "measurements" / (p["digest"] + ".json")
        x = read(path)
        assert x["page_digest"] == p["digest"] and x["mode"] == mode(x["rows"])
        modes[label] = x["mode"]
        raw[label] = {"digest": p["digest"], "raw_sha256": sha(path)}
    settings = [v for k,v in modes.items() if k.startswith("setting/")]
    pairs = {}
    for k, v in modes.items():
        if k.startswith("candidate/") and k.endswith("task-8"):
            group = k.rsplit("/", 1)[0]
            late = modes[group + "/task-12"]
            pairs[group.removeprefix("candidate/")] = {"task_8": v, "task_12": late,
                         "goals_met": int(v == "release position") + int(late == "minimum length")}
    return {"project": "draw", "requirements": [3, 9], "saved_targets": [8, 12], "new_model_calls": 0,
            "controls": {k.split("/")[1]:v for k,v in modes.items() if k.startswith("control/")},
            "settings": {v: settings.count(v) for v in sorted(set(settings))}, "pairs": pairs, "by_page": modes,
            "measurement_receipts": raw, "unique_file_sets": len({r["digest"] for r in raw.values()}),
            "freeze_sha256": sha(OUT / "freeze.json"), "protocol_sha256": sha(HERE / "PROTOCOL.md")}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["freeze", "run", "report", "check"])
    action = ap.parse_args().action
    if action == "freeze":
        freeze()
    elif action == "run":
        run()
    else:
        value = report()
        if action == "report" and not PUBLIC.exists():
            dump(PUBLIC, value)
        assert value == read(PUBLIC)
        print({k:value[k] for k in ("controls", "settings", "pairs")})
