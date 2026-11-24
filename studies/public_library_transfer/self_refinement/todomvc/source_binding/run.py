"""Recover submitted controller source and bind its own Boolean option declarations."""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import subprocess

from studies.public_library_transfer import browser
from studies.public_library_transfer.backbone_suites import run as suite
from studies.public_library_transfer.other_benchmarks import evaluate, generate
from studies.public_library_transfer.self_refinement.todomvc.executable_options.report import verification
from studies.study_io import ROOT, digest, now, read, sha

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/todomvc-source-binding-20261124"
REPORT = HERE / "result.json"
ACORN = ROOT / "artifacts/benchmark-probe/WebApp1k/staging/node_modules/acorn/dist/acorn.js"
TAGS = tuple(sorted(suite.MODELS))
TASKS = tuple(f"todo-{n:02}" for n in range(1, 9))
ARMS = ("direct", "bound", "fixed")


def receipt(tag, task=None):
    directory = suite.OUT / tag
    request = directory / "targets" / task / "direct" if task else directory / "build/todomvc"
    return request / "call/response.json"


def register():
    paths = [HERE / "PROTOCOL.md", HERE / "extract.cjs", Path(__file__), ACORN, suite.RESULT,
             suite.SOURCE / "build-inputs.json", suite.SOURCE / "targets.json",
             Path(evaluate.__file__), evaluate.todo.SHELL, evaluate.todo.HARNESS / "demo-todo-app.spec.ts"]
    paths += [receipt(tag, task) for tag in TAGS for task in (None, *TASKS) if receipt(tag, task).exists()]
    sources = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    file = OUT / "registration.json"
    if file.exists():
        assert read(file)["files"] == sources
    else:
        browser.preserve_json(file, {"utc": now(), "files": sources, "tasks": TASKS, "models": TAGS})


def inspect_reply(path):
    if not path.exists():
        raise FileNotFoundError(path)
    raw = read(path)["choices"][0]["message"].get("content") or ""
    fences = re.findall(r"^\s*```(\w*)[^\S\n]*\n(.*?)^\s*```[^\S\n]*$", raw, re.M | re.S)
    obj = None
    for candidate in [raw, *(body for lang, body in fences if lang.lower() in ("json", ""))]:
        try:
            parsed = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(parsed, dict) and isinstance(parsed.get("source"), str):
            obj = parsed
            break
    if obj is not None:
        src, envelope = obj["source"], "json"
    else:
        blocks = [body for lang, body in fences if lang.lower() in ("js", "javascript", "") and "window.candidate" in body]
        src, envelope = (blocks[0], "fenced") if blocks else (raw, "raw")
    if not src.strip():
        raise ValueError("Empty source")
    result = subprocess.run(["node", str(HERE / "extract.cjs"), str(ACORN)], input=src,
                            capture_output=True, text=True, timeout=15)
    if result.returncode:
        raise ValueError("No parseable controller assignment")
    return obj, json.loads(result.stdout), envelope


def canonical(identifier):
    return re.sub(r"^enabled?", "", re.sub(r"[^a-z0-9]", "", identifier.lower()))


def plan(first, spec, requirement):
    known = {canonical(k): any(line in requirement for line in lines) for k, lines in spec.items()}
    return {key: known.get(canonical(key), value) for key, value in first.items()}


def prepare_library(path):
    obj, ast, envelope = inspect_reply(path)
    if obj is not None and "controls" in obj:
        first = generate.interface("todomvc", obj)["first"]
        def render(values):
            return "(function(){\nconst DNA_CONFIG = Object.freeze(" + json.dumps(values, sort_keys=True) + ");\n" + ast["code"] + "\n})();\n"
        uses = ast["mentions"] > 0
    else:
        literal = ast["binding"]
        if not literal:
            raise ValueError("No unique Boolean DNA_CONFIG declaration")
        first = literal["first"]
        def render(values):
            return literal["before"] + json.dumps(values, sort_keys=True) + literal["after"]
        uses = ast["mentions"] > 1
    info = {"status": "valid", "envelope": envelope, "first": first, "config_identifier_referenced": uses,
            "truncated_tail": ast["truncated_tail"], "extracted_source_sha256": digest(ast["code"])}
    return info, render


def unavailable(exc):
    return {"status": "missing" if isinstance(exc, FileNotFoundError) else "invalid", "reason": str(exc)}


def seal():
    register()
    if (OUT / "seal.json").exists():
        assert read(OUT / "seal.json")["registration_sha256"] == sha(OUT / "registration.json")
        return
    targets, builders = suite.inputs()
    builds, rows = {}, []
    for tag in TAGS:
        build_path = receipt(tag)
        try:
            build, render = prepare_library(build_path)
        except (FileNotFoundError, ValueError, KeyError, TypeError) as exc:
            build, render = unavailable(exc), None
        builds[tag] = build
        for task in TASKS:
            files = {}
            try:
                _, direct, _ = inspect_reply(receipt(tag, task))
                files["direct"] = {"candidate.js": direct["code"]}
                direct_status = {"status": "valid"}
            except (FileNotFoundError, ValueError) as exc:
                direct_status = unavailable(exc)
            choices = {}
            if render:
                choices = {"fixed": build["first"], "bound": plan(build["first"], builders["todomvc"]["spec"],
                                                                  targets[task]["public"]["requirement"])}
                files.update({arm: {"candidate.js": render(p)} for arm, p in choices.items()})
            for arm in ARMS:
                status = direct_status if arm == "direct" else {k: build[k] for k in ("status", "reason") if k in build}
                row = {"tag": tag, "model": suite.MODELS[tag][0], "task": task, "arm": arm, **status}
                if arm in choices:
                    row["plan"] = choices[arm]
                if arm in files:
                    dest = OUT / "sources" / tag / task / (arm + ".json")
                    browser.preserve_json(dest, files[arm])
                    row["files_sha256"] = sha(dest)
                rows.append(row)
    browser.preserve_json(OUT / "seal.json", {"utc": now(), "registration_sha256": sha(OUT / "registration.json"),
                                               "builds": builds, "rows": rows})


def totals(rows):
    grouped = {}
    for tag in TAGS:
        model_rows = [r for r in rows if r["tag"] == tag]
        values = {arm: {r["task"]: r["passed"] for r in model_rows if r["arm"] == arm}
                  for arm in (*ARMS, "strict_self", "strict_direct")}
        assert all(set(column) == set(TASKS) for column in values.values())
        joint = [t for t in TASKS if all(values[a][t] is not None for a in values)]
        grouped[tag] = {"targets": joint, "passed": {arm: [t for t in joint if column[t]] for arm, column in values.items()},
                        "bound_only_vs_direct": [t for t in joint if values["bound"][t] and not values["direct"][t]],
                        "direct_only_vs_bound": [t for t in joint if values["direct"][t] and not values["bound"][t]]}
    return grouped


def official(where, target, row):
    raw = where / "playwright.json"
    verdict = read(where / "verdict.json")
    witnessed, n = verification(read(raw), target)
    assert (witnessed, n, sha(raw)) == (verdict["passed"], verdict["official_tests"], verdict["report_sha256"])
    return {**row, "passed": witnessed, "official_tests": n, "report_sha256": sha(raw)}


def score():
    seal()
    record = read(OUT / "seal.json")
    targets, _ = suite.inputs()
    original = read(suite.RESULT)["models"]
    server = evaluate.todo.Server(OUT)
    known, old = {}, []
    for tag in TAGS:
        model = suite.MODELS[tag][0]
        for r in original[model]["rows"]:
            if r["task"] not in TASKS or r["arm"] not in ("direct", "self", "fixed"):
                continue
            if r["arm"] in ("direct", "self"):
                old.append({"tag": tag, "model": model, "task": r["task"], "arm": "strict_" + r["arm"],
                            "passed": r["passed"], "status": r["status"]})
            if r["status"] == "valid":
                file = suite.OUT / tag / "targets" / r["task"] / r["arm"] / "files.json"
                assert sha(file) == r["files_sha256"]
                where = suite.OUT / tag / "scores" / r["task"] / r["arm"]
                assert sha(where / "playwright.json") == r["report_sha256"]
                known[(r["task"], digest(read(file)))] = where

    def one(r):
        if r["status"] != "valid":
            return {**r, "passed": None if r["status"] == "missing" else False}
        task, tag, arm = r["task"], r["tag"], r["arm"]
        srcfile = OUT / "sources" / tag / task / (arm + ".json")
        assert sha(srcfile) == r["files_sha256"]
        files = read(srcfile)
        key = (task, digest(files))
        where = known.get(key, OUT / "scores" / task / key[1])
        if key not in known:
            with browser.lock(where / ".lock"):
                if not (where / "verdict.json").exists():
                    with browser.browser_slot():
                        evaluate.score(("todomvc", targets[task], files, where, server))
        scored = official(where, targets[task], r)
        scored["score_source"] = "same-source historical replay" if key in known else "new browser replay"
        return scored

    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            rows = list(pool.map(one, record["rows"])) + old
    finally:
        server.close()
    result = {"protocol_sha256": sha(HERE / "PROTOCOL.md"), "strict_source_sha256": sha(suite.RESULT),
              "registered_utc": read(OUT / "registration.json")["utc"], "sealed_utc": record["utc"],
              "registration_sha256": sha(OUT / "registration.json"), "seal_sha256": sha(OUT / "seal.json"),
              "new_model_calls": 0, "builds": record["builds"], "rows": rows, "paired": totals(rows)}
    browser.write_json(REPORT, result)
    check()


def check():
    report = read(REPORT)
    assert report["protocol_sha256"] == sha(HERE / "PROTOCOL.md") and report["strict_source_sha256"] == sha(suite.RESULT)
    assert report["paired"] == totals(report["rows"])
    assert all(n == 1 for n in Counter((r["tag"],r["arm"],r["task"]) for r in report["rows"]).values())
    published = read(suite.RESULT)["models"]
    for r in report["rows"]:
        if r["arm"].startswith("strict_"):
            orig = next(x for x in published[r["model"]]["rows"] if x["task"] == r["task"] and "strict_"+x["arm"] == r["arm"])
            assert (orig["passed"], orig["status"]) == (r["passed"], r["status"])
    for tag, pair in report["paired"].items():
        print(tag, len(pair["targets"]), {arm: len(tasks) for arm, tasks in pair["passed"].items()})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("seal", "score", "check"))
    action = parser.parse_args().action
    {"seal": seal, "score": score, "check": check}[action]()
