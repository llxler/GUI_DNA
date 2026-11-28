"""Re-run only unjudged positions in the displayed four-way comparison."""

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import time
from unittest.mock import patch

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from . import sdk_navigation as navigation, rater_completion, report

main = navigation.main
OUT = ROOT / "artifacts/webgen-missing-verdicts-20261128"
RESULT = report.HERE / "completed-verdicts.json"
# The table runners perform only local Playwright scoring after they seal both builder replies.
TABLE_SEALS = tuple(
    ROOT / "artifacts" / (name + "-20261128") / "seal.json"
    for name in ("table-menu-author-repair", "table-menu-event-trace")
)


def run():
    import duckdb

    prerequisites = (
        report.JUDGMENTS,
        report.VERTICAL,
        rater_completion.RESULT,
        *report.TABLE_RUNS,
        *TABLE_SEALS,
        report.STATE / "program-judgments.json",
    )
    while not all(p.exists() for p in prerequisites):
        if datetime.now(timezone.utc) >= main.gen.END:
            raise TimeoutError("Awaiting original receipts at deadline")
        time.sleep(15)
    if RESULT.exists():
        return
    base = read(report.JUDGMENTS)
    sdk = read(report.VERTICAL)
    rows = report.replace_human(base["rows"], sdk["rows"])
    jobs = [(v["model"], v["site"], v["check"], v["arm"]) for v in rows if v["status"] == "missing"]
    jobs.sort(key=lambda j: hashlib.sha256("/".join(map(str, j)).encode()).digest())
    cal = base["calibration"]
    assert cal["qualified"] and cal["model"] == sdk["judge"] == main.api.ALTERNATE
    reg = OUT / "registration.json"
    sources = [
        Path(__file__),
        report.HERE / "MISSING_VERDICTS.md",
        report.CANDIDATES,
        report.TABS,
        report.VERTICAL,
        report.JUDGMENTS,
        rater_completion.RESULT,
        *TABLE_SEALS,
        Path(main.evaluator.__file__),
        Path(main.api.__file__),
        main.gen.gen.SRC,
    ]
    sums = {str(p.relative_to(ROOT)): sha(p) for p in sources}
    if not reg.exists():
        known = [n for n in report.LEDGERS.values() if n != "webgen-missing-verdicts"] + [
            "table-keyboard-navigation",
            "table-membership-projection",
            "table-menu-author-repair",
            "table-menu-event-trace",
        ]
        previous = (
            sum(
                round(
                    ledger_read.totals(ROOT / "artifacts" / (n + "-20261128") / "budget.sqlite3")[
                        "exposure_usd"
                    ]
                    * 1e6
                )
                for n in known
            )
            / 1e6
        )
        cap = min(4.50, round(20 - previous, 6))
        assert cap > 0
        balance = check_credits(cap)
        assert balance["sufficient"] and datetime.now(timezone.utc) < main.gen.END
        core.save(
            reg,
            dict(
                utc=now(),
                deadline=main.gen.END.isoformat(),
                sources=sums,
                model=cal["model"],
                scheduled=[list(j) for j in jobs],
                previous_exposure=previous,
                cap=cap,
                balance=balance,
            ),
        )
    assert read(reg)["sources"] == sums and read(reg)["scheduled"] == [list(j) for j in jobs]
    ledger = Ledger(OUT / "budget.sqlite3", read(reg)["cap"], read(reg)["cap"])
    primary = read(report.CANDIDATES)["rows"]
    layouts = read(report.TABS)["candidates"]
    raw = duckdb.sql(
        "select id,ui_instruct from read_parquet(?) where id in (select unnest(?))",
        params=[str(main.gen.gen.SRC), list(primary["deepseek-flash"])],
    ).fetchall()
    tests = {
        (s, i): {k: c[k] for k in ("task", "expected_result")} for s, ops in raw for i, c in enumerate(ops)
    }
    send = main.api.send
    previous_start = 0.0

    def paced(*args, **kwargs):
        nonlocal previous_start
        remaining = 2.0 - (time.monotonic() - previous_start)
        if remaining > 0:
            time.sleep(remaining)
        previous_start = time.monotonic()
        return send(*args, **kwargs)

    repaired = []
    with (
        patch.multiple(main.api, OUT=OUT, END=main.gen.END, send=paced),
        patch.dict(main.api.PRICES, {cal["model"]: (0.15, 0.6)}),
    ):
        for tag, site, i, arm in jobs:
            candidate = layouts[tag][site]["vertical"] if arm == "human" else primary[tag][site][arm]
            f = ROOT / candidate["file"]
            assert sha(f) == candidate["sha256"]
            dest = OUT / "checks" / tag / site / str(i) / arm
            v = main.evaluator.browser_job(
                lambda engine: main.evaluator.journey(
                    ledger, cal["model"], f.read_text(), arm == "human", tests[site, i], dest, engine
                )
            )
            repaired.append(
                dict(
                    model=tag,
                    site=site,
                    check=i,
                    arm=arm,
                    status=v["status"],
                    verdict=v["verdict"],
                    reason=v.get("reason"),
                    source=sha(dest / "judgment.json"),
                    candidate=candidate["sha256"],
                )
            )
    core.save(
        RESULT,
        dict(
            registration=sha(reg),
            baseline=sha(report.JUDGMENTS),
            vertical=sha(report.VERTICAL),
            judge=cal["model"],
            rows=repaired,
            cost=ledger_read.totals(OUT / "budget.sqlite3"),
        ),
    )


if __name__ == "__main__":
    with browser.lock(OUT / "run.lock"):
        run()
