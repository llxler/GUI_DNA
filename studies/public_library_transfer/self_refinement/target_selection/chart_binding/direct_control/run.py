"""Recover inert file map envelopes and apply identical public-only lifecycle checks."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from gui_dna.provider import parse_json
from studies.interface_blind.core import validate_files
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, digest, now, read, sha
from .. import run as binding

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/svg-chart-direct-filemap-20261124"
CHART = binding.CHART
ROOTS = {"qwen-self": binding.selection.MATRIX / "qwen" / CHART / "direct",
         "deepseek-self": binding.selection.EXTENSION / "deepseek-flash" / CHART / "direct"}
TASKS = binding.selection.TASKS


def register():
    dest = OUT / "registered.json"
    files = [HERE / "run.py", HERE / "PROTOCOL.md", binding.HERE / "run.py", binding.HERE / "hoist.cjs",
             binding.ROLLUP, binding.selection.DATA / f"{CHART}.json", Path(core.__file__), Path(browser.__file__),
             ROOT / "src/gui_dna/provider.py", ROOT / "studies/interface_blind/core.py"]
    for base in ROOTS.values():
        for n in TASKS:
            src = base / str(n)
            files.append(src / "result.json")
            raw = src / "call/response.json"
            if raw.exists():
                files.append(raw)
    source = {str(f.relative_to(ROOT)): sha(f) for f in files}
    if not dest.exists():
        core.save(dest, {"utc": now(), "sources": source, "contract": browser.verify_contract(CHART)})
    saved = read(dest)
    assert saved["sources"] == source and saved["contract"] == browser.verify_contract(CHART)
    return saved


def direct_files(parsed):
    if not isinstance(parsed, dict) or not parsed:
        raise ValueError("Expected file map")
    if set(parsed) == {"files"} and isinstance(parsed["files"], dict):
        status, contents = "wrapped", parsed["files"]
    else:
        status, contents = "bare_file_map", parsed
    if not contents:
        raise ValueError("Empty file map")
    return status, core.files_map([{"path": k, "content": v} for k, v in contents.items()])


def prepare(group, n, starter):
    previous = ROOTS[group]/str(n)
    src = read(previous / "result.json")
    raw = previous / "call/response.json"
    dest = OUT / "candidates" / group / str(n)
    status = {"task": n, "original_status": src["status"], "original_reason": src.get("reason"), "pages": {}}
    if not raw.exists():
        return status | {"delivery": "missing"}
    status["response_sha256"] = sha(raw)
    assert status["response_sha256"] == src["response_sha256"]
    content = read(raw)["choices"][0]["message"].get("content")
    if not content:
        return status | {"delivery": "empty_text"}
    try:
        delivery, additions = direct_files(parse_json(content))
        files = validate_files(starter | additions)
    except (KeyError, TypeError, ValueError) as exc:
        return status | {"delivery": "invalid", "error": str(exc)[:300]}
    status["delivery"] = delivery
    original = core.emit(CHART, files, dest / "wrapped")
    if src["status"] == "valid":
        assert original == src["files"]
    status["pages"]["wrapped"] = original
    mounted = binding.mounted_package({"files": additions}, starter)
    mounted_files = core.emit(CHART, validate_files(starter | mounted["files"]), dest / "mounted")
    status["public_observations"] = binding.observe(dest / "mounted", mounted_files)
    repair, edits = binding.correct(mounted, status["public_observations"])
    status["public_error_edits"] = edits
    status["pages"]["repaired"] = core.emit(CHART, validate_files(starter | repair["files"]), dest / "repaired")
    status["mount_changed"] = original != mounted_files
    return status


def freeze():
    registered = register()
    seal = OUT / "sealed.json"
    if seal.exists():
        previous = read(seal)
        assert previous["registered_sha256"] == sha(OUT / "registered.json")
        return previous
    public = read(binding.selection.DATA / f"{CHART}.json")
    # Use the identical original observation method with a distinct cache root.
    binding.OUT = OUT
    groups = {}
    for group in ROOTS:
        def one(n):
            return prepare(group, n, public["starter"])
        with ThreadPoolExecutor(max_workers=2) as worker:
            groups[group] = list(worker.map(one, TASKS))
    result = {"utc": now(), "registered_sha256": sha(OUT / "registered.json"),
              "contract": registered["contract"], "groups": groups}
    core.save(seal, result)
    return result


def score(seal):
    browser.OUT = OUT
    work = {}
    for name, rows in seal["groups"].items():
        for row in rows:
            n = row["task"]
            for arm, files in row["pages"].items():
                work[(n, digest(files))] = (n, OUT / "candidates" / name / str(n) / arm, files)
    def one(job):
        n, page, files = job
        key = digest(files)
        path = Path(f"browser/scores/{CHART}/task-{n}/{key}/score.json")
        expected = dict(project=CHART, task=n, files_digest=key, contract_digest=digest(seal["contract"]))
        for original in (binding.selection.MATRIX, binding.selection.EXTENSION):
            if (original / path).exists():
                browser.verify_page(page, files, CHART)
                raw = browser.verify_receipt(original, original / path, expected)
                break
        else:
            original = OUT
            raw = browser.run_one(OUT, CHART, n, page, files, seal["contract"])
        return f"{n}/{key}", {k: raw[k] for k in ("passed","report_sha256","files_digest")} | {
            "receipt": str((original / path).relative_to(ROOT))}
    with ThreadPoolExecutor(max_workers=2) as worker:
        core.save(OUT/"scores.json", dict(worker.map(one, work.values())))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("freeze", "score"))
    phase = parser.parse_args().phase
    seal = freeze()
    if phase == "score":
        score(seal)
