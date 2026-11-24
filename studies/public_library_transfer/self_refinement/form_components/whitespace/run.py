"""Replay escaped outer JSON whitespace on both form protocols, without a model call."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import re

from gui_dna.provider import parse_json
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, digest, now, read, sha
from .. import report as original
from .. import run as source

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/form-json-whitespace-20261124"
SUMMARY = HERE / "result.json"
ARMS = ("self", "fixed", "direct_first", "direct")


def outer_whitespace(text):
    """Preserve every quoted byte, including JS escapes and escaped quotes."""
    quoted = False
    escaped = False
    pos = 0
    result = []
    replacements = 0
    whitespace = {"n": "\n", "r": "\r", "t": "\t"}
    while pos < len(text):
        char = text[pos]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char == "\\" and text[pos + 1 : pos + 2] in whitespace:
            pos += 1
            char = whitespace[text[pos]]
            replacements += 1
        result.append(char)
        pos += 1
    return "".join(result), replacements


def checked_raw(folder):
    path = folder / "call/response.json"
    h = sha(path)
    assert h == read(path.with_name("settled.json"))["response_sha256"]
    choice = read(path)["choices"][0]
    text = choice["message"]["content"]
    try:
        parse_json(text)
        count = 0
    except ValueError:
        text, count = outer_whitespace(text)
    return text, {
        "response_sha256": h,
        "finish_reason": choice["finish_reason"],
        "changed_escapes": count,
    }


def register():
    source.register()
    spec = {
        "upstream_seal_sha256": sha(source.OUT / "seal.json"),
        "protocol_sha256": sha(HERE / "PROTOCOL.md"),
        "implementation_sha256": sha(HERE / "run.py"),
        "targets": list(original.TASKS),
        "api_calls": 0,
    }
    path = OUT / "registration.json"
    if not path.exists():
        core.save(path, {"utc": now(), "spec": spec})
    assert read(path)["spec"] == spec
    return path


def probe_names(public, task):
    requirements = source.details(public, task)
    return [
        name
        for name in source.TYPES
        if any(
            re.search(r"\b(?:class|Class)\s+" + name + r"\b", line, re.I)
            for line in requirements
        )
    ]


def extract_direct(stored, public):
    task = stored["task"]
    attempts = []
    selected = None
    stop = False
    for idx, old in enumerate(stored["attempts"]):
        folder = source.OUT / "direct" / str(task) / str(idx)
        raw, item = checked_raw(folder)
        item["eligible"] = not stop
        try:
            rendered = source.direct_files(raw, public)
            if old.get("files"):
                assert not item["changed_escapes"]
                files = old["files"]
                page = folder / "page"
                browser.verify_page(page, files, "form")
                obs = read(folder / "probe.json")
            else:
                page = OUT / "direct" / str(task) / str(idx) / "page"
                files = core.emit("form", rendered, page)
                obs = source.observe(rendered, probe_names(public, task), True)
                core.save(page.parent / "probe.json", obs)
            item.update(
                files=files,
                page=str(page.relative_to(ROOT)),
                passes_public=not bool(source.problem(obs)),
            )
            if item["eligible"]:
                selected = idx
                stop = item["passes_public"]
        except (TypeError, KeyError, ValueError) as e:
            item["error"] = str(e)[:300]
        attempts.append(item)
    return {"task": task, "attempts": attempts, "selected": selected}


def extract_plan(rep, arm, task, old, public):
    folder = source.OUT / rep / arm / str(task)
    raw, item = checked_raw(folder)
    try:
        plan = parse_json(raw)
        rendered = source.compile_plan(
            {
                "files": public["starter"] | source.module_files(rep),
                "compiler": source.COMPILER.read_text(),
            },
            plan,
        )
        if old["status"] == "valid":
            files = old["files"]
            assert plan == old["plan"] and not item["changed_escapes"]
            page = folder / "page"
            browser.verify_page(page, files, "form")
        else:
            page = OUT / rep / arm / str(task) / "page"
            files = core.emit("form", rendered, page)
        item.update(files=files, page=str(page.relative_to(ROOT)))
    except (KeyError, ValueError, TypeError) as e:
        item["error"] = str(e)[:300]
    return item


def seal():
    registration = register()
    sealed = OUT / "seal.json"
    if sealed.exists():
        assert read(sealed)["registration_sha256"] == sha(registration)
        return
    upstream = read(source.OUT / "seal.json")
    public = read(source.PUB)
    direct = [extract_direct(s, public) for s in upstream["direct"]]
    groups = {}
    for rep in original.REPS:
        selected = [
            extract_plan(rep, "selected", task, p, public)
            for task, p in zip(original.TASKS, upstream["plans"][rep], strict=True)
        ]
        fixed = extract_plan(rep, "fixed", 20, upstream["fixed"][rep], public)
        groups[rep] = {"self": selected, "fixed": fixed}
    core.save(
        sealed,
        {
            "utc": now(),
            "registration_sha256": sha(registration),
            "direct": direct,
            "groups": groups,
        },
    )


def changed(record):
    return record and record.get("page", "").startswith(
        str(OUT.relative_to(ROOT)) + "/"
    )


def new_scores(sealed):
    contract = browser.verify_contract("form")
    records = [
        (d["task"], a) for d in sealed["direct"] for a in d["attempts"] if changed(a)
    ]
    for group in sealed["groups"].values():
        records.extend(
            (t, g)
            for t, g in zip(original.TASKS, group["self"], strict=True)
            if changed(g)
        )
        if changed(group["fixed"]):
            records.extend((t, group["fixed"]) for t in original.TASKS)
    jobs = {(task, digest(item["files"])): item for task, item in records}
    browser.OUT = OUT

    def evaluate(pair):
        (task, _), item = pair
        return browser.run_one(
            OUT, "form", task, ROOT / item["page"], item["files"], contract
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        return dict(zip(jobs, pool.map(evaluate, jobs.items())))


def cell(task, item, original_row, new):
    if not item or "files" not in item:
        return {"status": "invalid", "passed": False}
    key = digest(item["files"])
    raw = new.get((task, key))
    if not raw:
        raw = next(
            (
                original_row[k]
                for k in ARMS
                if original_row[k].get("files_digest") == key
            ),
            None,
        )
    if not raw:
        # An original first draft can now become selected; the raw score has the same content address.
        fixed = source.OUT / "browser/scores/form" / f"task-{task}" / key / "score.json"
        raw = read(fixed)
        assert sha(source.OUT / raw["report"]) == raw["report_sha256"]
    assert raw["files_digest"] == key
    return {
        "status": "valid",
        "files_digest": key,
        "passed": raw["passed"],
        "report_sha256": raw["report_sha256"],
    }


def assemble():
    seal()
    sealed = read(OUT / "seal.json")
    scores = new_scores(sealed)
    base = read(original.RESULT)
    groups = {}
    for rep, frozen in sealed["groups"].items():
        rows = []
        for task, old, direct, plan in zip(
            original.TASKS,
            base["projects"]["form"]["replicas"][rep]["rows"],
            sealed["direct"],
            frozen["self"],
            strict=True,
        ):
            sel = direct["selected"]
            chosen = direct["attempts"][sel] if sel is not None else None
            row = {"task": task}
            for arm, rec in zip(
                ARMS,
                [plan, frozen["fixed"], direct["attempts"][0], chosen],
                strict=True,
            ):
                row[arm] = cell(task, rec, old, scores)
            rows.append(row)
        groups[rep] = {"rows": rows, "paired": original.comp(rows)}
    evidence = [
        {
            "task": d["task"],
            "selected": d["selected"],
            "attempts": [
                {k: v for k, v in a.items() if k not in {"page", "files"}}
                for a in d["attempts"]
            ],
        }
        for d in sealed["direct"]
    ]
    return {
        "registered_utc": read(OUT / "registration.json")["utc"],
        "sealed_utc": sealed["utc"],
        "registration_sha256": sha(OUT / "registration.json"),
        "seal_sha256": sha(OUT / "seal.json"),
        "protocol_sha256": sha(HERE / "PROTOCOL.md"),
        "implementation_sha256": sha(HERE / "run.py"),
        "source_result_sha256": sha(original.RESULT),
        "model": source.MODEL,
        "extra_api_calls": 0,
        "plan_responses_checked": sum(
            len(g["self"]) + 1 for g in sealed["groups"].values()
        ),
        "direct_responses_checked": sum(len(d["attempts"]) for d in evidence),
        "new_page_tasks": len(scores),
        "direct_deliveries": evidence,
        "projects": {"form": {"replicas": groups}},
    }


def check(result):
    assert result["source_result_sha256"] == sha(original.RESULT)
    assert result["implementation_sha256"] == sha(HERE / "run.py") and result[
        "protocol_sha256"
    ] == sha(HERE / "PROTOCOL.md")
    assert result["extra_api_calls"] == 0 and result["plan_responses_checked"] == 42
    base = read(original.RESULT)
    assert result["direct_responses_checked"] == sum(
        len(d["attempts"]) for d in base["projects"]["form"]["direct_deliveries"]
    )
    for rep, g in result["projects"]["form"]["replicas"].items():
        assert g["paired"] == original.comp(g["rows"]) and [
            r["task"] for r in g["rows"]
        ] == list(original.TASKS)
        print(
            rep,
            {
                k: (c["self"], c["other"], len(c["tasks"]))
                for k, c in g["paired"].items()
            },
        )
    print("new pages by task", result["new_page_tasks"])


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "phase",
        choices=["register", "seal", "score-new", "report", "check", "check-local"],
    )
    phase = p.parse_args().phase
    if phase == "register":
        register()
    elif phase == "seal":
        seal()
    elif phase == "score-new":
        seal()
        new_scores(read(OUT / "seal.json"))
    else:
        result = read(SUMMARY) if phase == "check" else assemble()
        check(result)
        if phase == "report":
            core.save(SUMMARY, result)
        if phase == "check-local":
            assert result == read(SUMMARY)
