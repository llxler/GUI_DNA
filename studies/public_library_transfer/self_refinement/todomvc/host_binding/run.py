"""Remove only an initial static redeclaration of the host's own Boolean configuration."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import re
from pathlib import Path

from studies.public_library_transfer import browser, core
from studies.public_library_transfer.other_benchmarks import evaluate
from studies.study_io import ROOT, read, sha
from .. import run as original
from ..repair import run as repair

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/self-controller-todomvc-host-binding-20261124"
RESULT = ROOT / "studies/results/self-controller-todomvc-host-binding-20261124.json"
FIELD = r"([A-Za-z_$][A-Za-z0-9_$]*)\s*:\s*(true|false)"
HEADER = re.compile(r"\A\s*const\s+DNA_CONFIG\s*=\s*\{(?P<body>[^{}]*)\}\s*;")
REPLICAS = ("build-a", "build-b")


def normalized(text, keys):
    match = HEADER.match(text)
    if not match:
        return text, ""
    items = match["body"].strip().removesuffix(",").split(",")
    fields = [re.fullmatch(FIELD, item.strip()) for item in items]
    if not all(fields):
        return text, ""
    names = [field[1] for field in fields]
    if len(names) != len(set(names)) or set(names) != set(keys):
        return text, ""
    return text[match.end() :], text[: match.end()]


def verify():
    reg = read(OUT / "registered.json")
    for path, value in reg["files"].items():
        assert sha(ROOT / path) == value, path
    return reg


def register():
    if (OUT / "registered.json").exists():
        verify()
        return
    files = [
        HERE / "PROTOCOL.md",
        Path(__file__),
        Path(original.__file__),
        Path(repair.__file__),
        Path(evaluate.__file__),
        original.OUT / "seal.json",
        original.OUT / "public-build.json",
        original.OUT / "targets.json",
        original.RESULT,
    ]
    for g in REPLICAS:
        files.extend(
            original.OUT / g / "build" / name
            for name in ("package.json", "status.json")
        )
    core.save(
        OUT / "registered.json",
        {
            "utc": core.now(),
            "new_api_requests": 0,
            "tasks": original.TASKS,
            "files": {str(p.relative_to(ROOT)): sha(p) for p in files},
        },
    )


def fingerprint(text):
    return hashlib.sha256(text.encode()).hexdigest()


def seal():
    verify()
    if (OUT / "seal.json").exists():
        return
    old = read(original.OUT / "seal.json")
    server = evaluate.todo.Server(OUT)
    states = {}
    rows = []
    try:
        for g in REPLICAS:
            package = read(original.OUT / g / "build/package.json")
            menu = old["builds"][g]["menu"]
            control, removed = normalized(
                package["source"], menu["schema"]["properties"]
            )
            assert removed + control == package["source"]
            public = repair.public_check(
                control, menu["first"], OUT / g / "public", server
            )
            status = "invalid" if public.get("syntax_error") else "valid"
            states[g] = {
                "before_sha256": fingerprint(package["source"]),
                "after_sha256": fingerprint(control),
                "removed": removed,
                "removed_sha256": fingerprint(removed),
                "removed_bytes": len(removed.encode()),
                "public_check": public,
                "status": status,
            }
            for r in old["rows"]:
                if r["group"] != g:
                    continue
                candidate = {k: r[k] for k in ("task", "group", "arm", "plan")}
                candidate["status"] = status
                if status == "valid":
                    files = {"candidate.js": repair.compose(control, r["plan"])}
                    path = OUT / g / r["arm"] / r["task"] / "files.json"
                    core.save(path, files)
                    candidate["files_sha256"] = sha(path)
                rows.append(candidate)
    finally:
        server.close()
    core.save(
        OUT / "seal.json",
        {
            "registered_sha256": sha(OUT / "registered.json"),
            "utc": core.now(),
            "builds": states,
            "rows": rows,
        },
    )


def score():
    reg = verify()
    sealed = read(OUT / "seal.json")
    assert sealed["registered_sha256"] == sha(OUT / "registered.json")
    server = evaluate.todo.Server(OUT)
    targets = read(original.OUT / "targets.json")

    def one(row):
        out = {**row, "passed": False}
        if row["status"] == "valid":
            path = OUT / row["group"] / row["arm"] / row["task"] / "files.json"
            assert sha(path) == row["files_sha256"]
            where = OUT / "scores" / row["task"] / row["files_sha256"]
            with browser.lock(where / ".lock"), browser.browser_slot():
                result = evaluate.score(
                    ("todomvc", targets[row["task"]], read(path), where, server)
                )
            assert sha(where / "playwright.json") == result["report_sha256"]
            out.update(
                {k: result[k] for k in ("passed", "official_tests", "report_sha256")}
            )
        return out

    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            rows = list(pool.map(one, sealed["rows"]))
    finally:
        server.close()
    counts = {
        g: {
            arm: [
                r["task"]
                for r in rows
                if r["group"] == g and r["arm"] == arm and r["passed"]
            ]
            for arm in ("self", "fixed")
        }
        for g in REPLICAS
    }
    core.save(
        RESULT,
        {
            "model": original.transport.MODEL,
            "registered_utc": reg["utc"],
            "tasks": original.TASKS,
            "registration_sha256": sha(OUT / "registered.json"),
            "seal_sha256": sha(OUT / "seal.json"),
            "original_sha256": sha(original.RESULT),
            "new_api_calls": 0,
            "new_api_usd": 0,
            "states": sealed["builds"],
            "passed": counts,
            "rows": rows,
        },
    )
    check()


def check():
    result = read(RESULT)
    previous = read(original.RESULT)
    assert result["original_sha256"] == sha(original.RESULT)
    original_rows = {
        (r["group"], r["arm"], r["task"]): r
        for r in previous["rows"]
        if r["arm"] != "direct"
    }
    assert len(result["rows"]) == len(original_rows) == 32
    for row in result["rows"]:
        assert (
            original_rows[row["group"], row["arm"], row["task"]]["plan"] == row["plan"]
        )
    for g, counts in result["passed"].items():
        state = result["states"][g]
        assert fingerprint(state["removed"]) == state["removed_sha256"]
        for arm, tasks in counts.items():
            assert tasks == [
                r["task"]
                for r in result["rows"]
                if r["group"] == g and r["arm"] == arm and r["passed"]
            ]
    print(result["passed"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "seal", "score", "check"))
    args = parser.parse_args()
    {"register": register, "seal": seal, "score": score, "check": check}[args.action]()
