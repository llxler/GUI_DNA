"""Mount model-authored renderers and repair one browser-observed lexical binding."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, digest, now, read, sha
from .. import run as selection

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/svg-chart-model-binding-20261124"
CHART = selection.CHART
MODELS = ("qwen-self", "deepseek-self")
ROLLUP = browser.contract(CHART)[1] / "node_modules/rollup/dist/parseAst.js"
NEW_ARMS = ("mounted", "repaired_first", "repaired_selected", "repaired_off", "repaired_on")


def mounted_package(pkg, starter):
    owned = dict(pkg["files"])
    code = owned.get("index.js", starter["index.js"])
    pattern = r"(?m)^(?P<indent>[ \t]*)chart\s*=\s*new\s+[$\w]+\(config\)\s*;?[ \t]*(?=\n)"
    # Keep the public starter's iteration and type-to-constructor dispatch.
    if (not re.search(r"\b(?:const|let) root\s*=", code) or re.search(r"\bchart\.draw\s*\(|\broot\.append", code)
            or not re.search(pattern, code)):
        return pkg
    def apply(match):
        indent = match["indent"]
        return (match.group().rstrip() + "\n" + indent + "if (chart.svg instanceof SVGElement) {\n"
                + indent + "  root.appendChild(chart.svg);\n" + indent + "  chart.draw?.();\n" + indent + "}")
    owned["index.js"] = re.sub(pattern, apply, code)
    return dict(pkg, files=owned)


def observe(page, files):
    page = browser.served_page(OUT, CHART, page, files)
    with browser.serve(CHART, page) as url, sync_playwright() as pw:
        engine = pw.chromium.launch(env=browser.browser_env())
        observations = []
        for _ in range(2):
            context = engine.new_context(service_workers="block")
            context.route("**/*", lambda r: r.continue_() if urlsplit(r.request.url).netloc
                          in ("", urlsplit(url).netloc) else r.abort())
            tab = context.new_page()
            errors = []
            tab.on("pageerror", lambda error: errors.append({"name": error.name, "message": error.message}))
            tab.goto(url, wait_until="networkidle")
            counts = tab.evaluate("""() => ({
                mountedSvg:document.querySelectorAll('.root svg').length,
                graphics:document.querySelectorAll('.root svg :is(path,polyline,rect,line,circle,polygon)').length
            })""")
            observations.append(dict(counts, errors=errors))
            context.close()
        engine.close()
    return observations


def correct(pkg, witness):
    if witness[0] != witness[1] or not witness[0]["errors"]:
        return pkg, []
    error = witness[0]["errors"][0]
    missing = re.fullmatch(r"([a-zA-Z_$][\w$]*) is not defined", error["message"])
    if error["name"] != "ReferenceError" or not missing:
        return pkg, []
    data = json.dumps({"files": pkg["files"], "missing": missing.group(1)})
    result = json.loads(subprocess.check_output(["node", str(HERE / "hoist.cjs"), str(ROLLUP)],
                                                input=data, text=True))
    if not result:
        return pkg, []
    return dict(pkg, files=pkg["files"] | {result["file"]: result["source"]}), [
        {"missing": missing.group(1), "file": result["file"], "moved": result["moved"]}]


def local_inputs():
    paths = [HERE / name for name in ("run.py", "hoist.cjs", "PROTOCOL.md")]
    paths.extend([ROLLUP, selection.DATA / f"{CHART}.json", Path(core.__file__), Path(browser.__file__),
                  selection.OUT / "sealed.json", *(selection.PACKAGES[g] for g in MODELS)])
    return {str(p.relative_to(ROOT)): sha(p) for p in paths}


def freeze():
    seal = OUT / "sealed.json"
    inputs = local_inputs()
    contract = browser.verify_contract(CHART)
    if seal.exists():
        previous = read(seal)
        assert previous["inputs"] == inputs and previous["contract"] == contract
        return previous
    public = read(selection.DATA / f"{CHART}.json")
    previous = read(selection.OUT / "sealed.json")["selection"]["charts"]
    registration = OUT / "registered.json"
    if not registration.exists():
        core.save(registration, {"utc": now(), "inputs": inputs})
    assert read(registration)["inputs"] == inputs
    groups = {}
    for name in MODELS:
        pkg = read(selection.PACKAGES[name])
        example = pkg["examples"][0]["plan"]
        folder = OUT / "candidates" / name
        observed = {}
        def first(version, package):
            page = folder / version / digest(example)
            files = core.materialize(CHART, package, example, page)
            observed[version] = observe(page, files)
            return observed[version]
        first("original", pkg)
        mounted = mounted_package(pkg, public["starter"])
        repair, edits = correct(mounted, first("mounted", mounted))
        first("repaired", repair)
        rows, pages = [], {}
        code = {"mounted": mounted, "repaired": repair}
        for old in previous[name]["rows"]:
            task, choices = old["task"], {}
            for arm, version, rule in (("mounted", "mounted", "fixed_first"),
                                      ("repaired_first", "repaired", "fixed_first"),
                                      ("repaired_selected", "repaired", "selected"),
                                      ("repaired_off", "repaired", "fixed_off"),
                                      ("repaired_on", "repaired", "fixed_on")):
                plan = previous[name]["plans"][old["plans"][rule]]
                key = f"{version}/{digest(plan)}"
                if key not in pages:
                    files = core.materialize(CHART, code[version], plan, folder / key)
                    pages[key] = files
                choices[arm] = key
            rows.append({"task": task, "choices": choices})
        groups[name] = {"observed": observed, "edits": edits, "rows": rows, "pages": pages,
                        "library_sha256": sha(selection.PACKAGES[name])}
    result = {"utc": now(), "registration_utc": read(registration)["utc"], "inputs": inputs,
              "contract": contract, "groups": groups}
    core.save(seal, result)
    return result


def score(seal):
    browser.OUT = OUT
    jobs = {}
    for name, group in seal["groups"].items():
        for row in group["rows"]:
            for key in row["choices"].values():
                files = group["pages"][key]
                jobs[(row["task"], digest(files))] = (row["task"], OUT/"candidates"/name/key, files)
    def one(job):
        task, page, files = job
        receipt = browser.run_one(OUT, CHART, task, page, files, seal["contract"])
        return f"{task}/{digest(files)}", {k: receipt[k] for k in ("passed", "report_sha256", "files_digest")}
    with ThreadPoolExecutor(max_workers=3) as workers:
        core.save(OUT / "scores.json", dict(workers.map(one, jobs.values())))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("freeze", "score"))
    args = parser.parse_args()
    data = freeze()
    if args.phase == "score":
        score(data)
