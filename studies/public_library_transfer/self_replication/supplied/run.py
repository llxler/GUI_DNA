"""Redeploy frozen supplied libraries with the exact native Qwen target settings."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from gui_dna.budget import BudgetStop, Ledger
from gui_dna.provider import parse_json
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.public_library_transfer.self_refinement.native import (
    run as native,
    transport,
)
from studies.study_io import ROOT, digest, read, sha
from studies.webbench.backbone_matrix import run as old

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/self-supplied-native-20261124"
RESULT = ROOT / "studies/results/self-supplied-native-20261124.json"
ARMS = ("human", "gpt5-library")
CAP = 0.45


def source(project):
    batch = "extension" if project == "table" else "form"
    return ROOT / f"artifacts/backbone-{batch}-20261124/inputs" / project


def verify():
    for name, h in read(OUT / "registered.json")["files"].items():
        if sha(ROOT / name) != h:
            raise ValueError(f"Registered dependency changed: {name}")


def register():
    if (OUT / "registered.json").exists():
        verify()
        return
    credit = check_credits(2 * CAP)
    if not credit["sufficient"]:
        raise BudgetStop("Insufficient credit")
    files = [
        Path(__file__),
        HERE / "PROTOCOL.md",
        Path(transport.__file__),
        Path(old.__file__),
        Path(browser.__file__),
        ROOT / "studies/interface_blind/compile.cjs",
        ROOT / "studies/webbench_expand/core.py",
        ROOT / "studies/interface_blind/core.py",
    ]
    for project in native.PROJECTS:
        src = source(project)
        assert read(src / "browser.json") == browser.verify_contract(project)
        files.extend([src / "public.json", src / "browser.json"])
        for a in ARMS:
            files.append(src / (a + ".json"))
            files.extend(src / a / (str(t) + ".json") for t in native.TASKS)
    core.save(
        OUT / "registered.json",
        {
            "utc": core.now(),
            "model": transport.MODEL,
            "tasks": native.TASKS,
            "arms": ARMS,
            "cap_per_project": CAP,
            "end": transport.END.isoformat(),
            "balance": credit,
            "files": {str(p.relative_to(ROOT)): sha(p) for p in files},
        },
    )


def generate(project):
    verify()
    dest = OUT / project
    src = source(project)
    ledger = Ledger(dest / "budget.sqlite3", CAP, CAP)
    public = read(src / "public.json")
    compiler = old.table_compile if project == "table" else old.chart_compile

    def one(item):
        a, t = item
        d = dest / a / str(t)
        if (d / "status.json").exists():
            return
        lib = read(src / (a + ".json"))
        try:
            raw = transport.request(
                d / "call",
                ledger,
                read(src / a / (str(t) + ".json")),
                f"{project}/{a}/target/{t}",
                8192,
                seed=native.SEEDS["direct"],
                schema=lib["plan_schema"],
            )
            plan = parse_json(raw)
            added = compiler(lib, plan)
            files = core.emit(
                project, old.validate_files(public["starter"] | added), d / "page"
            )
            row = {"status": "valid", "files": files, "plan": plan}
        except native.MISSING as exc:
            row = {"status": "missing", "reason": str(exc)}
        except native.INVALID as exc:
            row = {"status": "invalid", "reason": str(exc)[:400]}
        core.save(d / "status.json", row)

    jobs = [(a, t) for t in native.TASKS for a in ARMS]
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(one, jobs))
    core.save(
        dest / "seal.json",
        {f"{a}/{t}": sha(dest / a / str(t) / "status.json") for a, t in jobs},
    )


def score(project):
    verify()
    root = OUT / project
    browser.OUT = root
    contract = browser.verify_contract(project)
    seal = read(root / "seal.json")

    def one(item):
        a, t = item
        d = root / a / str(t)
        assert seal[f"{a}/{t}"] == sha(d / "status.json")
        case = read(d / "status.json")
        row = {"arm": a, "task": t, "status": case["status"], "passed": None}
        if case["status"] == "valid":
            rec = browser.run_one(root, project, t, d / "page", case["files"], contract)
            row.update(
                passed=rec["passed"],
                files_digest=digest(case["files"]),
                report_sha256=rec["report_sha256"],
            )
        elif case["status"] == "invalid":
            row.update(passed=False, reason=case["reason"])
        else:
            row["reason"] = case["reason"]
        call = d / "call/response.json"
        row["response_sha256"] = sha(call) if call.exists() else None
        return row

    with ThreadPoolExecutor(max_workers=4) as pool:
        core.save(
            root / "scores.json",
            list(pool.map(one, ((a, t) for t in native.TASKS for a in ARMS))),
        )


def report(check):
    verify()
    comparison = read(ROOT / "studies/results/self-native-20261124.json")
    out = {"registration_sha256": sha(OUT / "registered.json"), "projects": {}}
    for p in native.PROJECTS:
        root = OUT / p
        direct = {
            r["task"]: r["direct"]["passed"]
            for r in comparison["projects"][p]["replicas"]["build-a"]["rows"]
        }
        rows = read(root / "scores.json")
        by_arm = {
            a: {r["task"]: r["passed"] for r in rows if r["arm"] == a} for a in ARMS
        }
        known = [
            i
            for i in native.TASKS
            if all(x[i] is not None for x in (direct, *by_arm.values()))
        ]
        for r in rows:
            if r["status"] == "valid":
                t = r["task"]
                case = read(root / r["arm"] / str(t) / "status.json")
                browser.verify_page(root / r["arm"] / str(t) / "page", case["files"], p)
                key = digest(case["files"])
                rpath = root / "browser/scores" / p / f"task-{t}" / key / "score.json"
                exp = {
                    "project": p,
                    "task": t,
                    "files_digest": key,
                    "contract_digest": digest(read(source(p) / "browser.json")),
                }
                rec = browser.verify_receipt(root, rpath, exp)
                assert (
                    rec["report_sha256"] == r["report_sha256"]
                    and rec["passed"] == r["passed"]
                )
        oldfile = (
            ROOT
            / f"studies/results/backbone-{'extension' if p == 'table' else 'form'}-20261124.json"
        )
        orig = {
            a: {
                r["task"]: r["passed"]
                for r in read(oldfile)["models"][transport.MODEL]["rows"]
                if r["project"] == p and r["arm"] == a
            }
            for a in ARMS
        }
        old_pairs = {}
        for a in ARMS:
            joint = [t for t in native.TASKS if None not in (orig[a][t], by_arm[a][t])]
            old_pairs[a] = {
                "tasks": joint,
                "old_text": sum(orig[a][t] for t in joint),
                "native": sum(by_arm[a][t] for t in joint),
            }
        out["projects"][p] = {
            "tasks": known,
            "passed": {
                a: sum(values[i] for i in known)
                for a, values in {"direct": direct, **by_arm}.items()
            },
            "rows": rows,
            "comparison_to_original": old_pairs,
            "seal_sha256": sha(root / "seal.json"),
            "historical_sha256": sha(oldfile),
            "ledger": ledger_read.totals(root / "budget.sqlite3"),
        }
    if check:
        assert out == read(RESULT)
    else:
        core.save(RESULT, out)
    print({p: v["passed"] for p, v in out["projects"].items()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("register", "generate", "score", "report", "check")
    )
    parser.add_argument("project", nargs="?", choices=native.PROJECTS)
    args = parser.parse_args()
    if args.action == "register":
        register()
    elif args.action in ("check", "report"):
        report(args.action == "check")
    elif args.project:
        globals()[args.action](args.project)
    else:
        parser.error("A project is required")


if __name__ == "__main__":
    main()
