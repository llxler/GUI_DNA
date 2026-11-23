"""Frozen projection and paired deployment replication on the official SVG-chart targets."""
import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from gui_dna.budget import BudgetStop, Ledger
from gui_dna.provider import ProviderError, parse_json
from studies.form_library_sources.run import MODEL
from studies.ledger_read import totals
from studies.streaming_provider_v2 import StreamingOpenRouter
from studies.study_io import ROOT, dump, now, read, sha

from .adapter import BUILD, HERE, ORIGINAL, OUT, TASKS, lock, materialize_plan, old_package, planner_messages, score_run
from .interface import planning_interface

CAP = .08
DEADLINE = datetime(2026, 11, 23, 6, 9, tzinfo=timezone.utc)
ARMS = {"compact_first": ("compact", 20261123), "full_replication": ("full", 20261124),
        "compact_replication": ("compact", 20261124)}


def ordered_jobs():
    jobs = [("compact_first", n) for n in TASKS]
    for n in TASKS:
        pair = ("full_replication", "compact_replication")
        jobs.extend((arm, n) for arm in (pair if n % 2 else reversed(pair)))
    return jobs


def freeze():
    path = OUT / "freeze.json"
    if path.exists():
        for name, value in read(path)["sha256"].items():
            assert sha(ROOT / name) == value, name
        return
    original = read(ORIGINAL / "freeze.json")
    for name, value in original["sha256"].items():
        assert sha(ROOT / name) == value, name
    credits = read(OUT / "opening-credits.json")
    assert credits["required_usd"] == CAP and credits["sufficient"]
    pkg = old_package()
    compact = planning_interface(pkg)
    out_package = OUT / "projection.json"
    dump(out_package, compact)
    paths = [*HERE.glob("*.py"), HERE / "PROTOCOL.md", out_package, OUT / "opening-credits.json",
             ORIGINAL / "freeze.json", ORIGINAL / "results.json", ORIGINAL / "generation-complete.json",
             BUILD / "ai-package.json", ROOT / "studies/ledger_read.py"]
    for task in TASKS:
        for variant, value in (("full", pkg), ("compact", compact)):
            dest = OUT / "prompts" / variant / f"task-{task}.json"
            prompt = planner_messages(task, value)
            if variant == "full":
                assert prompt == read(ORIGINAL / "prompts/ai" / f"task-{task}.json")
            dump(dest, prompt)
            paths.append(dest)
    cfg = original["config"] | {"budget_usd": CAP, "stop_new_requests_usd": CAP}
    dump(path, {"utc": now(), "config": cfg, "deadline": DEADLINE.isoformat(), "arms": ARMS,
                "jobs": ordered_jobs(), "sha256": {str(p.relative_to(ROOT)): sha(p) for p in paths}})


def generation():
    freeze()
    complete = OUT / "generation-complete.json"
    if complete.exists():
        return
    client = StreamingOpenRouter(read(OUT / "freeze.json")["config"], Ledger(OUT / "budget.sqlite3", CAP, CAP))
    client.RATE_LIMIT_TRIES = 1
    pkg = old_package()
    def prepare(arm, task):
        variant, seed = ARMS[arm]
        prompt = read(OUT / "prompts" / variant / f"task-{task}.json")
        dest = OUT / "runs" / arm / f"task-{task}"
        reserve = (Decimal(sum(len(m["content"].encode()) + 256 for m in prompt) + 1024) * Decimal(".2")
                   + Decimal(8192) * Decimal(".8")) / 1_000_000
        return prompt, dest, seed, reserve

    def run(arm, task, prompt, dest, seed, reason=None):
        record = dest / "record.json"
        if record.exists():
            return read(record)
        row = {"arm": arm, "task": task, "response": False}
        try:
            if reason or datetime.now(timezone.utc) >= DEADLINE:
                raise BudgetStop(reason or "Deadline")
            raw = client.call(MODEL, prompt, dest / "call", f"{arm}:task-{task}", max_tokens=8192, seed=seed)
            row["response"] = True
            plan = parse_json(raw)
            dump(dest / "plan.json", plan)
            row["files"] = materialize_plan(pkg, plan, dest / "page")
            row["page"] = str((dest / "page").relative_to(ROOT))
        except (ValueError, TypeError, KeyError, BudgetStop, ProviderError) as exc:
            row["error"] = str(exc)[:700]
        dump(record, row)
        print(arm, task, "response", row["response"], "page", bool(row.get("files")), flush=True)
        return row

    pending = {}
    # Local estimates cover the brief period between pool.submit() and ledger.reserve().
    # Use the union of durable and in-flight obligations, conserving the hard cap.
    jobs = list(ordered_jobs())
    with ThreadPoolExecutor(max_workers=3) as pool:
        while jobs or pending:
            while jobs and len(pending) < 3:
                arm, task = jobs[0]
                prompt, dest, seed, reserve = prepare(arm, task)
                if (dest / "record.json").exists():
                    jobs.pop(0)
                    continue
                tracked = totals(OUT / "budget.sqlite3")
                unreserved = sum(amount for f, (folder, amount) in pending.items()
                                 if not (folder / "call/request.json").exists())
                exceeds = Decimal(str(tracked["exposure_usd"])) + unreserved + reserve > Decimal(str(CAP))
                if exceeds and pending:
                    break
                jobs.pop(0)
                reason = "Hard-cap reservation unavailable" if exceeds else None
                args = (arm, task, prompt, dest, seed)
                if reason or datetime.now(timezone.utc) >= DEADLINE:
                    run(*args, reason=reason)
                else:
                    pending[pool.submit(run, *args)] = (dest, reserve)
            if pending:
                finished, _ = wait(pending, return_when=FIRST_COMPLETED)
                for job in finished:
                    job.result()
                    del pending[job]
    rows = [read(OUT / "runs" / arm / f"task-{task}/record.json") for arm, task in ordered_jobs()]
    dump(complete, {"utc": now(), "rows": rows, "ledger": totals(OUT / "budget.sqlite3")})


def evaluate():
    freeze()
    complete = read(OUT / "generation-complete.json")
    assert len(complete["rows"]) == 60
    for arm in ARMS:
        rows = [r for r in complete["rows"] if r["arm"] == arm]
        score_run(OUT / "evaluations" / arm, rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("freeze", "generate", "evaluate"))
    stage = parser.parse_args().stage
    if stage in ("generate", "freeze"):
        with lock(OUT):
            (generation if stage == "generate" else freeze)()
    else:
        evaluate()
