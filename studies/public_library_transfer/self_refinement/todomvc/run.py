"""Compare two independently prepared single-script TodoMVC libraries with one direct arm."""

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import subprocess

from gui_dna.budget import BudgetStop, Ledger
from scripts.check_openrouter_credits import check_credits
from studies.ledger_read import calls, totals
from studies.public_library_transfer import browser, core
from studies.public_library_transfer.backbone_suites import run as historical
from studies.public_library_transfer.other_benchmarks import generate as menus
from studies.public_library_transfer.self_refinement.native import transport
from studies.study_io import ROOT, read, sha

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/self-controller-todomvc-20261124"
RESULT = ROOT / "studies/results/self-controller-todomvc-20261124.json"
CAP = 0.65
SEEDS = {"build-a": 20261124, "build-b": 20261125, "direct": 20261124}
TASKS = tuple(f"todo-{n:02}" for n in range(1, 9))
SCHEMA = core.obj(
    {k: v for k, v in menus.TODO_SCHEMA["properties"].items() if k != "source"}
)
DESIGN = (
    "Design the Boolean interface of one reusable TodoMVC state controller. Read only the supplied public "
    "specification and host contract. Choose one to six semantic controls with unique short JavaScript "
    "identifiers, a boolean default and unambiguous descriptions. Give the example as enabled IDs "
    "(all others false). Use a common state and independent features. Do not write code or target switches."
)
IMPLEMENT = (
    "Implement the entire state controller below as one complete classic JavaScript source, without "
    "Markdown or JSON wrapping. Follow the public event, state, localStorage and view contracts "
    "literally. Use a single shared state across features. The host declares const DNA_CONFIG with "
    "explicit Boolean values for your controls before your code. Assign window.candidate with "
    "init, reduce and select. The shell owns the DOM. Do not access outside files or tools."
)
DIRECT = (
    "Write the complete plain browser JavaScript source for this task. Assign window.candidate with init, "
    "reduce and select according to the public shell contract. Return only source, without Markdown or "
    "JSON wrapping. Do not access outside files or tools."
)


def verify():
    registration = read(OUT / "registered.json")
    for path, value in registration["files"].items():
        if sha(ROOT / path) != value:
            raise ValueError(f"Frozen TodoMVC input changed: {path}")
    return registration


def register():
    if (OUT / "registered.json").exists():
        verify()
        return
    balance = check_credits(CAP)
    if not balance["sufficient"]:
        raise BudgetStop("Insufficient balance")
    targets, contexts = historical.inputs()
    public = {task: targets[task] for task in TASKS}
    assert tuple(t for t, r in targets.items() if r["group"] == "todomvc") == TASKS
    core.save(OUT / "public-build.json", contexts["todomvc"])
    core.save(OUT / "targets.json", public)
    paths = [
        HERE / "PROTOCOL.md",
        Path(__file__),
        Path(transport.__file__),
        Path(menus.__file__),
        Path(menus.__file__).with_name("evaluate.py"),
        Path(historical.__file__),
        historical.RESULT,
        ROOT / "studies/todomvc_dna/domain.py",
        ROOT / "studies/todomvc_dna/shell.html",
        ROOT / "studies/todomvc_dna/harness/demo-todo-app.spec.ts",
        ROOT / "studies/todomvc_dna/review_evaluate.py",
        ROOT / "studies/todomvc_dna/evaluate.py",
        historical.SOURCE / "build-inputs.json",
        historical.SOURCE / "targets.json",
        OUT / "public-build.json",
        OUT / "targets.json",
    ]
    core.save(
        OUT / "registered.json",
        {
            "utc": core.now(),
            "model": transport.MODEL,
            "tasks": TASKS,
            "seeds": SEEDS,
            "cap_usd": CAP,
            "balance": balance,
            "deadline": transport.END.isoformat(),
            "files": {str(p.relative_to(ROOT)): sha(p) for p in paths},
        },
    )


def source(raw):
    text = raw.strip()
    match = re.fullmatch(r"```(?:javascript|js)?\s*\n(.*?)\n?```", text, re.I | re.S)
    if match:
        text = match.group(1).strip()
    if not text:
        raise ValueError("Empty JavaScript")
    test = subprocess.run(
        ["node", "--check", "-"], input=text, text=True, capture_output=True, timeout=10
    )
    if test.returncode != 0:
        raise ValueError("JavaScript syntax check: " + test.stderr[:700])
    return text


def ask(folder, ledger, group, step, content, limit, schema=None):
    if (OUT / "route-closed.json").exists():
        raise transport.Unavailable("Closed Qwen route")
    try:
        return transport.request(
            folder,
            ledger,
            content,
            f"{group}/{step}",
            limit,
            seed=SEEDS[group],
            schema=schema,
        )
    except transport.Unavailable as err:
        if str(err) in ("HTTP 401", "HTTP 402", "HTTP 403", "HTTP 404"):
            browser.preserve_json(OUT / "route-closed.json", {"reason": str(err)})
        raise


def build(group, ledger, public):
    folder = OUT / group / "build"
    if (folder / "status.json").exists():
        return read(folder / "status.json")
    try:
        prompt = core.messages(DESIGN, {"public": public, "output_schema": SCHEMA})
        design = core.parse(
            ask(folder / "design", ledger, group, "build/design", prompt, 4096, SCHEMA)
        )
        menus.interface("todomvc", {**design, "source": "/* design only */"})
        prompt = core.messages(IMPLEMENT, {"public": public, "interface": design})
        first = ask(folder / "source", ledger, group, "build/source", prompt, 12000)
        try:
            code = source(first)
        except ValueError as error:
            if not str(error).startswith("JavaScript syntax check:"):
                raise
            repair = prompt + [
                {"role": "assistant", "content": first},
                {
                    "role": "user",
                    "content": f"Public {error}. Return the complete corrected raw JavaScript.",
                },
            ]
            code = source(
                ask(folder / "repair", ledger, group, "build/repair", repair, 12000)
            )
        package = {**design, "source": code}
        menu = menus.interface("todomvc", package)
        core.save(folder / "package.json", package)
        status = {
            "status": "valid",
            "menu": menu,
            "package_sha256": sha(folder / "package.json"),
        }
    except (transport.Unavailable, BudgetStop) as error:
        status = {"status": "missing", "reason": str(error)}
    except (ValueError, KeyError, TypeError, AttributeError, IndexError) as error:
        status = {"status": "invalid", "reason": str(error)[:600]}
    core.save(folder / "status.json", status)
    return status


def candidate(job, ledger, targets, builds):
    group, arm, task = job
    folder = OUT / group / arm / task
    if (folder / "candidate.json").exists():
        return read(folder / "candidate.json")
    row = {"group": group, "arm": arm, "task": task}
    try:
        current = targets[task]["public"]
        if arm == "direct":
            code = source(
                ask(
                    folder / "call",
                    ledger,
                    group,
                    task,
                    core.messages(DIRECT, current),
                    8192,
                )
            )
        elif builds[group]["status"] != "valid":
            row.update(
                status=builds[group]["status"],
                reason="build: " + builds[group]["reason"],
            )
            core.save(folder / "candidate.json", row)
            return row
        else:
            menu = builds[group]["menu"]
            path = OUT / group / "build/package.json"
            assert sha(path) == builds[group]["package_sha256"]
            if arm == "fixed":
                plan = menu["first"]
            else:
                prompt = core.messages(
                    menus.PLAN, {"current": current, "library": menu}
                )
                plan = core.parse(
                    ask(
                        folder / "call",
                        ledger,
                        group,
                        task,
                        prompt,
                        8192,
                        menu["schema"],
                    )
                )
            if set(plan) != set(menu["schema"]["properties"]) or not all(
                type(v) is bool for v in plan.values()
            ):
                raise ValueError("Invalid TodoMVC configuration")
            row["plan"] = plan
            code = (
                "(function(){\nconst DNA_CONFIG = Object.freeze("
                + json.dumps(plan, sort_keys=True)
                + ");\n"
                + read(path)["source"]
                + "\n})();\n"
            )
        core.save(folder / "files.json", {"candidate.js": code})
        row.update(status="valid", files_sha256=sha(folder / "files.json"))
    except (transport.Unavailable, BudgetStop) as error:
        row.update(status="missing", reason=str(error))
    except (ValueError, KeyError, TypeError, IndexError, AttributeError) as error:
        row.update(status="invalid", reason=str(error)[:600])
    if (folder / "call/response.json").exists():
        row["response_sha256"] = sha(folder / "call/response.json")
    core.save(folder / "candidate.json", row)
    return row


def generate():
    verify()
    with browser.lock(OUT / "generation.lock"):
        if (OUT / "seal.json").exists():
            return
        ledger = Ledger(OUT / "budget.sqlite3", CAP, CAP)
        public = read(OUT / "public-build.json")
        targets = read(OUT / "targets.json")
        replicas = ("build-a", "build-b")
        with ThreadPoolExecutor(max_workers=2) as pool:
            builds = dict(
                zip(
                    replicas,
                    pool.map(lambda group: build(group, ledger, public), replicas),
                )
            )
        jobs = [
            (group, arm, task)
            for task in TASKS
            for group, arm in [
                ("direct", "direct"),
                ("build-a", "self"),
                ("build-a", "fixed"),
                ("build-b", "self"),
                ("build-b", "fixed"),
            ]
        ]
        with ThreadPoolExecutor(max_workers=4) as pool:
            rows = list(
                pool.map(lambda job: candidate(job, ledger, targets, builds), jobs)
            )
        core.save(
            OUT / "seal.json",
            {
                "utc": core.now(),
                "registered_sha256": sha(OUT / "registered.json"),
                "rows": rows,
                "builds": builds,
            },
        )


def score():
    reg = verify()
    seal = read(OUT / "seal.json")
    assert seal["registered_sha256"] == sha(OUT / "registered.json")
    for key in list(os.environ):
        if key.endswith(("_API_KEY", "_ACCESS_TOKEN", "_AUTH_TOKEN")):
            os.environ.pop(key)
    from studies.public_library_transfer.other_benchmarks import evaluate

    targets = read(OUT / "targets.json")
    server = evaluate.todo.Server(OUT)

    def run(row):
        outcome = {**row, "passed": None if row["status"] == "missing" else False}
        if row["status"] == "valid":
            path = OUT / row["group"] / row["arm"] / row["task"] / "files.json"
            assert sha(path) == row["files_sha256"]
            directory = OUT / "scores" / row["task"] / row["files_sha256"]
            with browser.lock(directory / ".lock"), browser.browser_slot():
                result = evaluate.score(
                    ("todomvc", targets[row["task"]], read(path), directory, server)
                )
            assert sha(directory / "playwright.json") == result["report_sha256"]
            outcome.update(
                {k: result[k] for k in ("passed", "official_tests", "report_sha256")}
            )
        return outcome

    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            rows = list(pool.map(run, seal["rows"]))
    finally:
        server.close()
    orig = [
        r
        for r in read(historical.RESULT)["models"][transport.MODEL]["rows"]
        if r["group"] == "todomvc"
    ]
    summary = {
        group: {
            arm: {
                "passed": [
                    r["task"]
                    for r in rows
                    if r["group"] == group and r["arm"] == arm and r["passed"] is True
                ],
                "missing": [
                    r["task"]
                    for r in rows
                    if r["group"] == group and r["arm"] == arm and r["passed"] is None
                ],
            }
            for arm in (("direct",) if group == "direct" else ("self", "fixed"))
        }
        for group in SEEDS
    }
    costs = defaultdict(
        lambda: {"calls": 0, "settled_microusd": 0, "exposure_microusd": 0}
    )
    for call in calls(OUT / "budget.sqlite3"):
        group, rest = call["purpose"].split("/", 1)
        cost = costs[
            group + "/" + ("build" if rest.startswith("build/") else "targets")
        ]
        cost["calls"] += 1
        cost["settled_microusd"] += call["actual"] or 0
        cost["exposure_microusd"] += (
            call["actual"] if call["actual"] is not None else call["reserved"]
        )
    data = {
        "model": transport.MODEL,
        "tasks": TASKS,
        "registered_utc": reg["utc"],
        "registration_sha256": sha(OUT / "registered.json"),
        "seal_sha256": sha(OUT / "seal.json"),
        "historical_sha256": sha(historical.RESULT),
        "historical_passed": {
            arm: [r["task"] for r in orig if r["arm"] == arm and r["passed"] is True]
            for arm in ("direct", "self", "fixed")
        },
        "summary": summary,
        "builds": seal["builds"],
        "rows": rows,
        "budget": totals(OUT / "budget.sqlite3"),
        "cost_by_stage": dict(costs),
    }
    core.save(RESULT, data)
    check()


def check():
    data = read(RESULT)
    expected = Counter(
        (task, g, a)
        for task in TASKS
        for g, a in [
            ("direct", "direct"),
            ("build-a", "self"),
            ("build-a", "fixed"),
            ("build-b", "self"),
            ("build-b", "fixed"),
        ]
    )
    assert Counter((r["task"], r["group"], r["arm"]) for r in data["rows"]) == expected
    assert sha(historical.RESULT) == data["historical_sha256"]
    assert data["budget"]["exposure_usd"] <= data["budget"]["cap_usd"] == CAP
    for group, arms in data["summary"].items():
        for arm, summary in arms.items():
            selected = [
                r for r in data["rows"] if r["group"] == group and r["arm"] == arm
            ]
            assert [r["task"] for r in selected if r["passed"] is True] == summary[
                "passed"
            ]
            assert [r["task"] for r in selected if r["passed"] is None] == summary[
                "missing"
            ]
    print(data["summary"], data["budget"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "generate", "score", "check"))
    args = parser.parse_args()
    {"register": register, "generate": generate, "score": score, "check": check}[
        args.action
    ]()
