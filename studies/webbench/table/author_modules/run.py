"""Compose non-overlapping GPT-5 revisions and pair all source variants on fresh plans."""

from concurrent.futures import ThreadPoolExecutor
from itertools import product
from pathlib import Path
from unittest.mock import patch
import re
import shutil

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read, paper_target_extensions as earlier
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from studies.webbench.calculator.behavior_modules import run as calc
from studies.webbench.calculator.behavior_modules.gpt5_delivery import run as recovery
from studies.webbench.table.menu_propagation.event_trace import run as trace

author = trace.author
protocol = author.protocol
HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/table-author-modules-20261128"
ORIGINAL = ROOT / "artifacts/webbench-expand-build/libraries"
REVIEW = ROOT / "artifacts/library-repair-20261113/libraries"
TAGS = ("gemma", "qwen9", "mistral", "qwen", "oss", "deepseek-flash", "deepseek-pro")
CAP = 1.50
ARMS = ("original", "review", "trace", "combined")


def pkg(project, revised):
    return (
        REVIEW / project / "openai__gpt-5/review"
        if revised
        else ORIGINAL / project / "openai__gpt-5"
    )


def inputs():
    sources = [
        Path(__file__),
        HERE / "PROTOCOL.md",
        Path(author.__file__),
        Path(protocol.__file__),
        trace.RESULT,
        *(trace.OUT / t / "builder.json" for t in "ab"),
        earlier.ACCOUNTING,
        calc.OUT / "registration.json",
        recovery.OUT / "registration.json",
        earlier.FALLBACK,
    ]
    for proj in ("table", "calculator"):
        for revision in (True, False):
            p = pkg(proj, revision)
            sources.extend(
                [p / n for n in ("package.json", "record.json", "messages.json")]
            )
            sources.extend(p.glob("call*/**/response.json"))
    return sources


def historical(project, revised):
    folder = pkg(project, revised)
    paths = sorted(folder.glob("call*/**/response.json"))
    replies = [read(p) for p in paths]
    assert replies and all(
        "gpt-5" in r["model"] and r["usage"]["cost"] is not None for r in replies
    )
    if revised:
        record = read(folder / "record.json")
        assert (
            record["deployed"] == "revision"
            and record["condition"] == "review"
            and record["valid_responses"] == 1
        )
    return dict(
        package=sha(folder / "package.json"),
        responses=[sha(p) for p in paths],
        usd=sum(r["usage"]["cost"] for r in replies),
    )


def register():
    path = OUT / "registration.json"
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in inputs()}
    if not path.exists():
        prior = read(earlier.ACCOUNTING)["campaign"]["exposure_usd"]
        upper = prior + calc.CAP + recovery.CAP + CAP
        assert upper <= 20
        balance = check_credits(CAP)
        assert balance["sufficient"]
        history = {
            p: {k: historical(p, k == "review") for k in ("original", "review")}
            for p in ("table", "calculator")
        }
        assert (
            history["calculator"]["original"]["package"]
            == history["calculator"]["review"]["package"]
        )
        core.save(
            path,
            dict(
                utc=now(),
                cap=CAP,
                upper=upper,
                deadline=calc.END.isoformat(),
                balance=balance,
                sources=hashes,
                models={
                    t: calc.calc.action.settings("table", t, "plan")["model"]
                    for t in TAGS
                },
                history=history,
                contract=browser.verify_contract("table"),
            ),
        )
    assert read(path)["sources"] == hashes
    return read(path)


def with_edit(library, edit):
    files = library["files"]
    assert (
        edit["status"] == "delivered" and files["index.js"].count(edit["before"]) == 1
    )
    return library | {
        "files": files
        | {"index.js": files["index.js"].replace(edit["before"], edit["after"], 1)}
    }


def materialize(arm, library, profiles, pub, attempt):
    return [
        protocol.compact.compile_page(
            "table",
            "gpt5-library",
            library,
            profile,
            pub,
            OUT / "libs" / attempt / arm / str(i),
        )
        for i, profile in enumerate(profiles)
    ]


def choose(job, ledger, profiles, pub, package):
    tag, n = job
    folder = OUT / "plans" / tag / str(n)
    dest = folder / "record.json"
    if dest.exists():
        return read(dest)
    prompt = core.messages(
        "Pick one profile of the existing interactive table library. Return only its number from 0 to 3. Other controls use their documented defaults.",
        dict(
            public=core.prefix(pub, n),
            documentation=package["plan_documentation"],
            profiles=list(enumerate(profiles)),
        ),
    )
    result = dict(status="invalid")
    try:
        for turn in range(2):
            raw = calc.calc.base.request(
                ledger, ("table", tag, "a"), folder / str(turn), prompt, "plan", 1150
            )
            text = calc.calc.base.uncode(raw).strip()
            if re.fullmatch("[0-3]", text):
                result = dict(status="valid", profile=int(text))
                break
            prompt.extend(
                [
                    dict(role="assistant", content=raw),
                    dict(role="user", content="Only a digit, 0 through 3."),
                ]
            )
    except calc.calc.action.typed.MISSING as err:
        result = dict(status="missing", reason=str(err))
    core.save(dest, result)
    return result


def generate(reg):
    seal = OUT / "seal.json"
    if seal.exists():
        return
    old, new = [read(pkg("table", v) / "package.json") for v in (False, True)]
    assert all(old[k] == new[k] for k in old if k != "files")
    changes = [k for k in old["files"] if new["files"].get(k) != old["files"][k]]
    assert set(old["files"]) == set(new["files"]) and set(changes) == {
        "common/table.js",
        "common/key.js",
        "common/mouse.js",
        "common/drag.js",
    }
    profiles = protocol.choices(old, "gpt5-library", "table")
    pub = core.public_input("table")
    checks = {}
    attempt = None
    for rep in "ab":
        edit = read(trace.OUT / rep / "builder.json")
        libs = {
            "original": old,
            "review": new,
            "trace": with_edit(old, edit),
            "combined": with_edit(new, edit),
        }
        pages = {a: materialize(a, v, profiles, pub, rep) for a, v in libs.items()}
        with patch.object(author.diagnosis, "OUT", OUT):
            checks[rep] = {
                k: [author.diagnosis.public(v) for v in vs] for k, vs in pages.items()
            }
        if all(all(c.values()) for c in checks[rep]["combined"]):
            attempt = rep
            break
    ledger = Ledger(OUT / "budget.sqlite3", CAP, CAP)
    jobs = list(product(TAGS, range(1, 21)))

    def settings(project, tag, stage):
        body = calc.calc.action.settings(project, tag, stage)
        if "seed" in body:
            body["seed"] = 2026112871
        return body

    with (
        patch.multiple(calc.calc.base, OUT=OUT, END=calc.END, template=settings),
        ThreadPoolExecutor(max_workers=5) as pool,
    ):
        choices = dict(
            zip(
                jobs,
                pool.map(lambda j: choose(j, ledger, profiles, pub, old), jobs),
                strict=True,
            )
        )
    rows = []
    for (tag, n), selection in choices.items():
        for arm in ARMS:
            for fixed in (False, True):
                i = 0 if fixed else selection.get("profile")
                if arm == "combined" and not attempt:
                    record = dict(status="build_failed")
                elif i is None:
                    record = dict(status=selection["status"])
                else:
                    record = pages[arm][i]
                rows.append(
                    dict(
                        record,
                        project="table",
                        tag=tag,
                        task=n,
                        arm=("fixed-" if fixed else "") + arm,
                        profile=i,
                    )
                )
    core.save(
        seal,
        dict(
            registration=sha(OUT / "registration.json"),
            checks=checks,
            chosen_attempt=attempt,
            changed_files=changes,
            rows=rows,
        ),
    )


def reuse(rows, contract):
    peers = [trace.OUT, author.OUT, protocol.OUT, author.diagnosis.OUT]
    handled = set()
    for r in rows:
        if r["status"] != "valid":
            continue
        key = browser.digest(r["files"])
        relative = (
            Path("browser/scores/table") / f"task-{r['task']}" / key / "score.json"
        )
        dest = OUT / relative
        if relative in handled or dest.exists():
            continue
        handled.add(relative)
        for peer in peers:
            src = peer / relative
            if not src.is_file():
                continue
            expected = dict(
                project="table",
                task=r["task"],
                files_digest=key,
                contract_digest=browser.digest(contract),
            )
            original = browser.verify_receipt(peer, src, expected)
            raw = dest.with_name("reused-report.json")
            raw.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(peer / original["report"], raw)
            core.save(
                dest,
                dict(
                    original,
                    report=str(raw.relative_to(OUT)),
                    source_receipt=str(src.relative_to(ROOT)),
                    source_receipt_sha256=sha(src),
                    source_report=str((peer / original["report"]).relative_to(ROOT)),
                ),
            )
            break


def score(reg):
    d = read(OUT / "seal.json")
    assert d["registration"] == sha(OUT / "registration.json") and reg[
        "contract"
    ] == browser.verify_contract("table")
    reuse(d["rows"], reg["contract"])
    scored = browser.evaluate(d["rows"], OUT, {"table": reg["contract"]}, 4)
    models = {
        m: [
            {k: v[k] for k in ("arm", "task", "status", "profile", "report_sha256")}
            | dict(passed=False if v["status"] == "invalid" else v["passed"])
            for v in scored
            if v["tag"] == t
        ]
        for t, m in reg["models"].items()
    }
    total = ledger_read.totals(OUT / "budget.sqlite3")
    costs = {}
    for c in ledger_read.calls(OUT / "budget.sqlite3"):
        cost = costs.setdefault(
            c["model"], dict(calls=0, settled_micro_usd=0, exposure_micro_usd=0)
        )
        cost["calls"] += 1
        cost["settled_micro_usd"] += c["actual"] or 0
        cost["exposure_micro_usd"] += (
            c["actual"] if c["actual"] is not None else c["reserved"]
        )
    core.save(
        HERE / "result.json",
        dict(
            registration=d["registration"],
            seal=sha(OUT / "seal.json"),
            history=reg["history"],
            changed_files=d["changed_files"],
            chosen_attempt=d["chosen_attempt"],
            checks=d["checks"],
            models=models,
            calculator_equivalence=sha(earlier.FALLBACK),
            cost=total,
            deployment_costs=costs,
        ),
    )


if __name__ == "__main__":
    with browser.lock(OUT / "study.lock"):
        reg = register()
        generate(reg)
        if not (HERE / "result.json").exists():
            score(reg)
