"""Link declared module dependencies symmetrically and score the same frozen SVG targets."""
import argparse
import json
from pathlib import Path
import subprocess

from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, digest, now, read, sha
from .. import components as comp, run as cohort

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/qwen-svg-module-linking-20261124"
RESULT = HERE / "result.json"
PARSER = browser.contract(comp.CHART)[1] / "node_modules/rollup/dist/parseAst.js"


def register():
    sources = (HERE / "PROTOCOL.md", HERE / "link.cjs", Path(__file__), PARSER,
               Path(cohort.__file__), Path(comp.__file__), Path(browser.__file__), cohort.OUT / "registration.json")
    fingerprints = {str(p.relative_to(ROOT)): sha(p) for p in sources}
    dest = OUT / "registration.json"
    if not dest.exists():
        assert not (cohort.OUT / "seal.json").exists()
        core.save(dest, {"utc": now(), "sources": fingerprints, "remote_calls": 0})
    assert read(dest)["sources"] == fingerprints


def link(row):
    original = ROOT / row["page"]
    browser.verify_page(original, row["files"], comp.CHART)
    source = {p: (original / p).read_text() for p in row["files"] if not p.startswith("assets/")}
    scripts = {p: v for p, v in source.items() if p.endswith((".js", ".mjs"))}
    edits = json.loads(subprocess.check_output(["node", str(HERE / "link.cjs"), str(PARSER)],
                                              input=json.dumps(scripts), text=True))
    if not edits:
        return {"page": row["page"], "files": row["files"], "edits": {}}
    for filename, links in edits.items():
        lines = [f'import {{ {e["name"]} }} from {json.dumps(e["from"])};' for e in links]
        source[filename] = "\n".join([*lines, source[filename]])
    folder = OUT / "pages" / digest(row["files"])
    files = core.emit(comp.CHART, source, folder)
    assert set(files) == set(row["files"])
    assert {p for p, h in files.items() if h != row["files"][p]} == set(edits)
    return {"page": str(folder.relative_to(ROOT)), "files": files, "edits": edits}


def freeze():
    register()
    base = cohort.OUT / "seal.json"
    dest = OUT / "seal.json"
    if dest.exists():
        assert read(dest)["base_sha256"] == sha(base)
        return
    pages, rows, public = {}, [], {}
    for row in read(base)["rows"]:
        if row["status"] == "valid":
            key = digest(row["files"])
            if key not in pages:
                pages[key] = link(row)
            linked = pages[key]
            row = {**row, "page": linked["page"], "files": linked["files"], "original_digest": key}
            label = (row["group"], row["arm"])
            if label in (("A", "fixed"), ("B", "fixed"), ("host", "only")) and row["task"] == 1:
                public["/".join(label)] = comp.observe(OUT, ROOT / row["page"], row["files"])
        rows.append(row)
    core.save(dest, {"utc": now(), "registration_sha256": sha(OUT / "registration.json"), "base_sha256": sha(base),
                     "public": public, "edits": {key: page["edits"] for key, page in pages.items()}, "rows": rows})


def score():
    freeze()
    base = read(cohort.RESULT)
    seal = read(OUT / "seal.json")
    assert base["seal_sha256"] == seal["base_sha256"]
    originals = {(r["group"], r["arm"], r["task"]): r for r in base["rows"]}
    changed = [r for r in seal["rows"] if r["status"] == "valid" and digest(r["files"]) != r["original_digest"]]
    browser.OUT = OUT
    scored = browser.evaluate(changed, OUT, {comp.CHART: browser.verify_contract(comp.CHART)}, 6)
    new = {(r["group"], r["arm"], r["task"]): r for r in scored}
    rows = []
    for key, first in originals.items():
        other = new.get(key)
        if other:
            row = {**first, "passed": other["passed"], "report_sha256": other["report_sha256"],
                   "page_digest": digest(other["files"])}
        else:
            row = dict(first)
        if row["status"] in ("invalid", "build_failed"):
            row["passed"] = False
        rows.append({**row, "changed": other is not None, "original_report_sha256": first["report_sha256"]})
    core.save(RESULT, {"registered_utc": read(OUT / "registration.json")["utc"], "sealed_utc": seal["utc"],
                       "base_result_sha256": sha(cohort.RESULT), "registration_sha256": seal["registration_sha256"],
                       "seal_sha256": sha(OUT / "seal.json"), "protocol_sha256": sha(HERE / "PROTOCOL.md"),
                       "public": seal["public"], "edits_by_input_digest": seal["edits"], "rows": rows,
                       "paired": cohort.compare(rows), "remote_calls": 0})
    check()


def check():
    data = read(RESULT)
    base = read(cohort.RESULT)
    assert data["protocol_sha256"] == sha(HERE / "PROTOCOL.md") and data["base_result_sha256"] == sha(cohort.RESULT)
    assert data["registered_utc"] < base["sealed_utc"] and data["remote_calls"] == 0
    assert len(data["rows"]) == len({(r["group"], r["arm"], r["task"]) for r in data["rows"]}) == 180
    for row, old in zip(data["rows"], base["rows"], strict=True):
        assert all(row[k] == old[k] for k in ("arm","group","task","status","plan"))
        assert row["original_report_sha256"] == old["report_sha256"]
        if not row["changed"] and row["status"] == "valid":
            assert all(row[k] == old[k] for k in ("passed", "report_sha256", "page_digest"))
        assert row["passed"] is None if row["status"] == "missing" else type(row["passed"]) is bool
    assert data["paired"] == cohort.compare(data["rows"])
    print({g: {k: len(v) for k,v in c["passed"].items()} for g,c in data["paired"].items()})


if __name__ == "__main__":
    actions = {"register": register, "freeze": freeze, "score": score, "check": check}
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("action", choices=actions)
    actions[cli.parse_args().action]()
