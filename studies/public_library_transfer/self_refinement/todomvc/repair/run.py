"""Repair public compilation of a frozen TodoMVC library and replay exactly its original plans."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess

from playwright.sync_api import sync_playwright

from gui_dna.budget import BudgetStop, Ledger
from scripts.check_openrouter_credits import check_credits
from studies.ledger_read import totals
from studies.public_library_transfer import browser, core
from studies.public_library_transfer.other_benchmarks import evaluate
from studies.public_library_transfer.self_refinement.native import transport
from studies.study_io import ROOT, read, sha
from .. import run as original

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/self-controller-todomvc-repair-20261124"
RESULT = ROOT / "studies/results/self-controller-todomvc-repair-20261124.json"
CAP = 0.12
REPLICAS = ("build-a", "build-b")
REPAIR = (
    "The supplied implementation failed public host integration. Keep all supplied control names and meanings, "
    "and return one complete replacement plain JavaScript implementation. The host wraps your script in an "
    "IIFE and declares const DNA_CONFIG in that same scope, before your code. Consume it without any "
    "declaration or fallback global. Honor the supplied window.candidate contract including returned state "
    "and view fields. Only use the public information below; do not use tools or external files."
)


def compose(source, plan):
    return (
        "(function(){\nconst DNA_CONFIG = Object.freeze("
        + json.dumps(plan, sort_keys=True)
        + ");\n"
        + source
        + "\n})();\n"
    )


def verify():
    record = read(OUT / "registered.json")
    for path, fingerprint in record["files"].items():
        assert sha(ROOT / path) == fingerprint, path
    return record


def register():
    if (OUT / "registered.json").exists():
        verify()
        return
    prior = totals(original.OUT / "budget.sqlite3")
    balance = check_credits(CAP)
    if (
        not balance["sufficient"]
        or prior["unsettled_calls"]
        or prior["exposure_usd"] + CAP > original.CAP
    ):
        raise BudgetStop("Prior exposure, repair budget or balance unavailable")
    files = [
        Path(__file__),
        HERE / "PROTOCOL.md",
        Path(original.__file__),
        Path(transport.__file__),
        original.OUT / "seal.json",
        original.RESULT,
        original.OUT / "public-build.json",
        original.OUT / "targets.json",
        Path(evaluate.__file__),
    ]
    for replica in REPLICAS:
        files += [
            original.OUT / replica / "build" / name
            for name in ("package.json", "status.json")
        ]
    core.save(
        OUT / "registered.json",
        {
            "utc": core.now(),
            "files": {str(p.relative_to(ROOT)): sha(p) for p in files},
            "deadline": transport.END.isoformat(),
            "model": transport.MODEL,
            "budget_usd": CAP,
            "previous_spend_usd": prior["exposure_usd"],
            "total_todomvc_cap_usd": original.CAP,
            "balance": balance,
        },
    )


def public_check(source, first, folder, server):
    code = compose(source, first)
    checked = subprocess.run(
        ["node", "--check", "-"], input=code, text=True, capture_output=True, timeout=10
    )
    if checked.returncode:
        return {"syntax_error": checked.stderr[:800]}
    app = evaluate.todo.write_app(code, folder / "app")
    try:
        with browser.browser_slot(), sync_playwright() as pw:
            chromium = pw.chromium.launch(env=evaluate.todo.browser_env())
            page = chromium.new_page()
            errors = []
            page.on("pageerror", lambda err: errors.append(str(err)[:500]))
            page.goto(server.url(app), timeout=10000)
            state = page.evaluate("""() => {
              const c = window.candidate;
              if (!c || !['init','reduce','select'].every(k => typeof c[k] === 'function')) return 'missing controller';
              const start = c.init();
              if (!start || !Array.isArray(start.todos)) return 'init must return state with a todos array';
              const out=c.reduce(start,{type:'add',title:'check the public interface'});
              const view=c.select(out);
              if (!view || !Array.isArray(view.visible) || !view.visible.some(t=>t.title==='check the public interface'))
                return 'expected newly added item in select(updated state).visible';
              return '';
            }""")
            chromium.close()
        return {"public_errors": errors + ([state] if state else [])}
    except Exception as error:
        return {"public_errors": [f"{type(error).__name__}: {error}"[:600]]}


def build(replica, ledger, server):
    folder = OUT / replica
    marker = folder / "status.json"
    if marker.exists():
        return read(marker)
    old = read(original.OUT / replica / "build/package.json")
    state = read(original.OUT / replica / "build/status.json")
    first = state["menu"]["first"]
    pre = public_check(old["source"], first, folder / "before", server)
    core.save(folder / "before.json", pre)
    try:
        if pre.get("syntax_error") or pre.get("public_errors"):
            context = {
                "public": read(original.OUT / "public-build.json"),
                "controls": old["controls"],
                "first": first,
                "source": old["source"],
                "public_failure": pre,
            }
            answer = transport.request(
                folder / "call",
                ledger,
                core.messages(REPAIR, context),
                f"{replica}/public-repair",
                12000,
                seed=original.SEEDS[replica],
            )
            source = original.source(answer)
        else:
            source = old["source"]
        after = public_check(source, first, folder / "after", server)
        core.save(folder / "after.json", after)
        if after.get("syntax_error"):
            raise ValueError(after["syntax_error"])
        core.save(folder / "package.json", {**old, "source": source})
        info = {
            "status": "valid",
            "package_sha256": sha(folder / "package.json"),
            "public_after": after,
        }
    except (BudgetStop, transport.Unavailable) as error:
        info = {"status": "missing", "reason": str(error)}
    except (ValueError, TypeError, KeyError, IndexError) as error:
        info = {"status": "invalid", "reason": str(error)[:850]}
    core.save(marker, {**info, "public_before": pre})
    return read(marker)


def generate():
    verify()
    with browser.lock(OUT / "generate.lock"):
        if (OUT / "seal.json").exists():
            return
        ledger = Ledger(OUT / "budget.sqlite3", CAP, CAP)
        server = evaluate.todo.Server(OUT)
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                states = dict(
                    zip(
                        REPLICAS, pool.map(lambda g: build(g, ledger, server), REPLICAS)
                    )
                )
        finally:
            server.close()
        rows = []
        for old in read(original.OUT / "seal.json")["rows"]:
            replica = old["group"]
            if replica not in REPLICAS:
                continue
            state = states[replica]
            row = {k: old[k] for k in ("task", "group", "arm")}
            row.update(
                status=state["status"] if old["status"] == "valid" else old["status"]
            )
            if row["status"] == "valid":
                pkg = read(OUT / replica / "package.json")
                row["plan"] = old["plan"]
                path = OUT / replica / row["arm"] / row["task"] / "files.json"
                core.save(path, {"candidate.js": compose(pkg["source"], old["plan"])})
                row["files_sha256"] = sha(path)
            rows.append(row)
        core.save(
            OUT / "seal.json",
            {
                "utc": core.now(),
                "registration_sha256": sha(OUT / "registered.json"),
                "rows": rows,
                "builds": states,
            },
        )


def score():
    reg = verify()
    seal = read(OUT / "seal.json")
    assert seal["registration_sha256"] == sha(OUT / "registered.json")
    targets = read(original.OUT / "targets.json")
    previous = read(original.RESULT)
    server = evaluate.todo.Server(OUT)

    def one(row):
        result = {**row, "passed": None if row["status"] == "missing" else False}
        if row["status"] == "valid":
            source = OUT / row["group"] / row["arm"] / row["task"] / "files.json"
            assert sha(source) == row["files_sha256"]
            where = OUT / "scores" / row["task"] / row["files_sha256"]
            with browser.lock(where / ".lock"), browser.browser_slot():
                score = evaluate.score(
                    ("todomvc", targets[row["task"]], read(source), where, server)
                )
            assert score["report_sha256"] == sha(where / "playwright.json")
            result.update(
                {k: score[k] for k in ("passed", "official_tests", "report_sha256")}
            )
        return result

    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            rows = list(pool.map(one, seal["rows"]))
    finally:
        server.close()
    summary = {
        g: {
            a: {
                "passed": [
                    r["task"]
                    for r in rows
                    if r["group"] == g and r["arm"] == a and r["passed"] is True
                ],
                "missing": [
                    r["task"]
                    for r in rows
                    if r["group"] == g and r["arm"] == a and r["passed"] is None
                ],
            }
            for a in ("self", "fixed")
        }
        for g in REPLICAS
    }
    core.save(
        RESULT,
        {
            "model": transport.MODEL,
            "registered_utc": reg["utc"],
            "tasks": original.TASKS,
            "registration_sha256": sha(OUT / "registered.json"),
            "seal_sha256": sha(OUT / "seal.json"),
            "original_sha256": sha(original.RESULT),
            "original": previous["summary"],
            "builds": seal["builds"],
            "summary": summary,
            "rows": rows,
            "budget": totals(OUT / "budget.sqlite3"),
        },
    )
    check()


def check():
    data = read(RESULT)
    previous = read(original.RESULT)
    assert (
        data["original_sha256"] == sha(original.RESULT)
        and data["original"] == previous["summary"]
    )
    orig = {
        (r["group"], r["arm"], r["task"]): r
        for r in previous["rows"]
        if r["arm"] != "direct"
    }
    assert len(data["rows"]) == len(orig) == 32
    assert set((r["group"], r["arm"], r["task"]) for r in data["rows"]) == set(orig)
    for r in data["rows"]:
        if r["status"] == "valid":
            assert r["plan"] == orig[r["group"], r["arm"], r["task"]]["plan"]
    for g in REPLICAS:
        for arm, s in data["summary"][g].items():
            rows = [r for r in data["rows"] if r["group"] == g and r["arm"] == arm]
            assert s["passed"] == [r["task"] for r in rows if r["passed"] is True]
            assert s["missing"] == [r["task"] for r in rows if r["passed"] is None]
    print(data["summary"], data["budget"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "generate", "score", "check"))
    args = parser.parse_args()
    {"register": register, "generate": generate, "score": score, "check": check}[
        args.action
    ]()
