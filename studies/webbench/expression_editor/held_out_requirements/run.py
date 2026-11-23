"""Matched half-brief preparation, followed by deployment on ten unseen requirements."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from gui_dna.budget import BudgetStop, Ledger
from gui_dna.provider import ProviderError, parse_json
from scripts.check_openrouter_credits import check_credits
from studies.expression_editor_sources import browser, core
from studies.expression_editor_sources.run import END, with_error
from studies.interface_blind.core import write_files
from studies.ledger_read import totals
from studies.streaming_provider_v2 import StreamingOpenRouter
from studies.study_io import ROOT, digest, dump, now, read, sha, source_files
from studies.table_library_sources.run import file_hashes, verify
from studies.webbench_expand.core import config

HERE = Path(__file__).resolve().parent
OLD = core.OUT
OUT = ROOT / "artifacts/expression-editor-unseen-20261123"
ARMS = ("ai", "direct")
EARLY = core.TASKS[:10]
LATE = core.TASKS[10:]


def folder_files(path):
    return [f for f in path.rglob("*") if f.is_file()]


def locked(marker):
    value = read(OUT / marker)
    verify(value["inputs_sha256"])
    return value


def public_preparation():
    source = core.requirements()[:10]
    if [r["id"] for r in source] != list(EARLY) or set(core.starter()) != {"index.html", "index.js"}:
        raise ValueError("Unexpected public prefix or starter")
    user = core.common_inputs(source)
    prompts = {}
    for arm in ARMS:
        # Keep the main study's generic role. Only the public ten-row user turn is transmitted.
        system = read(OLD / "prep-prompts" / f"{arm}.json")[0]
        if system["role"] != "system":
            raise ValueError("Invalid frozen system template")
        prompts[arm] = [system, {"role":"user", "content":user}]
    return source, prompts


def freeze(cap):
    if not 0 < cap <= 10:
        raise ValueError("Supply this stage's authorized share of the daily cap")
    verify(read(OLD / "freeze.json")["inputs_sha256"])
    registration = read(OUT / "registration.json")
    if (registration["protocol_sha256"] != sha(HERE / "PROTOCOL.md")
        or registration["main_freeze_sha256"] != sha(OLD / "freeze.json")):
        raise ValueError("Initial registration differs")
    if (OUT / "freeze.json").exists():
        if locked("freeze.json")["budget_usd"] != cap:
            raise ValueError("Stage limit already locked")
        return
    controls = read(OLD / "controls-complete.json")["rows"]
    distinguishable = [t for t in core.TASKS if controls["upstream_final/" + t]["passed"]
                       and not controls["blank/" + t]["passed"] and not controls["starter/" + t]["passed"]]
    if len(distinguishable) < 10:
        raise ValueError("Matched calibration gate failed")
    credit = check_credits(cap)
    if not credit["sufficient"]:
        raise BudgetStop("Insufficient available balance")
    public, prompts = public_preparation()
    dump(OUT / "public/first-ten.json", public)
    for arm, messages in prompts.items():
        dump(OUT / "prep-prompts" / f"{arm}.json", messages)
    paths = [HERE / f for f in ("PROTOCOL.md", "run.py", "report.py")]
    paths += [OUT / "registration.json", OLD / "freeze.json", OLD / "controls-complete.json",
              OUT / "public/first-ten.json", *folder_files(OUT / "prep-prompts")]
    shared = read(OLD / "freeze.json")["inputs_sha256"]
    dump(OUT / "freeze.json", {"utc":now(), "budget_usd":cap, "credit_check":credit,
        "models":{"preparation":core.BUILDER, "deployment":core.MODEL}, "deadline_utc":END.isoformat(),
        "calibrated_targets":distinguishable, "prepare":EARLY, "deployment":LATE,
        "inputs_sha256":shared | file_hashes(paths)})


def api_client():
    cap = locked("freeze.json")["budget_usd"]
    ledger = OUT / "budget.sqlite3"
    remaining = cap - (totals(ledger)["exposure_usd"] if ledger.exists() else 0)
    credit = check_credits(max(remaining, 0))
    if not credit["sufficient"]:
        raise BudgetStop("Insufficient pre-call balance for remaining stage exposure")
    cfg = config(True)
    cfg.update(models=[core.BUILDER, core.MODEL], provider_order={}, budget_usd=cap, stop_new_requests_usd=cap)
    cfg["model_price_caps"][core.MODEL] = {"prompt":.2, "completion":.8}
    api = StreamingOpenRouter(cfg, Ledger(ledger, cap, cap))
    api.RATE_LIMIT_TRIES = 1
    return api


def attempt(api, folder, model, messages, purpose, limit, accept):
    marker = folder / "record.json"
    if marker.exists():
        row = read(marker)
        if row["prompt_sha256"] != digest(messages):
            raise ValueError("Cannot replay different messages")
        return row
    row = {"prompt_sha256":digest(messages), "received":False, "valid":False}
    try:
        if datetime.now(timezone.utc) >= END and not (folder / "call/request.json").exists():
            raise BudgetStop("No new calls after deadline")
        raw = api.call(model, messages, folder / "call", purpose, max_tokens=limit, seed=20261123)
        row["received"] = True
        row.update(accept(parse_json(raw), folder))
        row["valid"] = True
    except (BudgetStop, ProviderError, ValueError, TypeError, KeyError) as error:
        row["error"] = str(error)[:1100]
    dump(marker, row)
    return row


def repaired_prompt(first_folder):
    req = read(first_folder / "call/request.json")["body"]["messages"]
    response = read(first_folder / "call/response.json")["choices"][0]["message"]["content"]
    return with_error(req, response, read(first_folder / "record.json")["error"])


def prepare():
    locked("freeze.json")
    early, prompts = public_preparation()
    if (OUT / "preparation-complete.json").exists():
        locked("preparation-complete.json")
        return
    if early != read(OUT / "public/first-ten.json"):
        raise ValueError("Preparation-prefix mismatch")
    api = api_client()
    def one(arm):
        folder = OUT / "preparation" / arm
        def save(obj, dest):
            obj = core.validate_preparation(arm, obj, dest / "validation")
            dump(folder / "artifact.json", obj)
            return {"artifact_sha256":sha(folder / "artifact.json")}
        messages = read(OUT / "prep-prompts" / f"{arm}.json")
        if messages != prompts[arm]:
            raise ValueError("Preparation prompt differs from allowlisted inputs")
        rows = {}
        for stage in ("first", "repair"):
            if stage == "repair":
                if rows["first"]["valid"] or not rows["first"]["received"]:
                    break
                messages = repaired_prompt(folder / "first")
            rows[stage] = attempt(api, folder / stage, core.BUILDER, messages,
                                  "prepare-" + arm + "-" + stage, 16000, save)
        return arm, rows
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = dict(pool.map(one, ARMS))
    dump(OUT / "preparation-complete.json", {"utc":now(), "arms":rows,
         "inputs_sha256":file_hashes([OUT / "freeze.json", *folder_files(OUT / "preparation")])})


def freeze_targets():
    prep = locked("preparation-complete.json")
    if (OUT / "planning-freeze.json").exists():
        return locked("planning-freeze.json")
    available = []
    paths = [OUT / "preparation-complete.json"]
    for arm, records in prep["arms"].items():
        if not any(row["valid"] for row in records.values()):
            continue
        artifact = read(OUT / "preparation" / arm / "artifact.json")
        available.append(arm)
        for task in LATE:
            path = OUT / "inputs" / arm / f"{task}.json"
            dump(path, core.target_prompt(arm, task, artifact))
            paths.append(path)
        if arm == "ai":
            fixed = OUT / "fixed-example"
            write_files(fixed, core.render(arm, artifact, artifact["examples"][1]["plan"]))
            paths.extend(folder_files(fixed))
    dump(OUT / "planning-freeze.json", {"utc":now(), "available":available, "inputs_sha256":file_hashes(paths)})
    return locked("planning-freeze.json")


def generate():
    prep = freeze_targets()
    if (OUT / "generation-complete.json").exists():
        locked("generation-complete.json")
        return
    api = api_client()
    packages = {arm:read(OUT / "preparation" / arm / "artifact.json") for arm in prep["available"]}
    jobs = [(arm, t) for t in LATE for arm in ARMS if arm in packages]
    def one(job):
        arm, task, stage = job
        folder = OUT / "candidates" / arm / task
        def save(obj, dest):
            page = dest / "page"
            write_files(page, core.render(arm, packages[arm], obj))
            return {"files_sha256":source_files(page)}
        messages = (read(OUT / "inputs" / arm / f"{task}.json") if stage == "first"
                    else repaired_prompt(folder / "first"))
        row = attempt(api, folder / stage, core.MODEL, messages, arm + "-" + stage, 8192, save)
        return arm, task, stage, row
    with ThreadPoolExecutor(max_workers=4) as pool:
        first = list(pool.map(one, [(arm, t, "first") for arm, t in jobs]))
        repairs = list(pool.map(one, [(a,t,"repair") for a,t,_,row in first if row["received"] and not row["valid"]]))
    dump(OUT / "generation-complete.json", {"utc":now(), "rows":[*first, *repairs],
        "inputs_sha256":file_hashes([OUT / "planning-freeze.json", *folder_files(OUT / "candidates")])})


def score():
    locked("freeze.json")
    prep = locked("planning-freeze.json")
    gen = locked("generation-complete.json")
    if (OUT / "scores-complete.json").exists():
        return locked("scores-complete.json")
    harness = OUT / "harness"
    if not harness.exists():
        harness.symlink_to(OLD / "harness", target_is_directory=True)
    browser.OUT = OUT
    def one(job):
        key, task, folder, control = job
        return key, browser.score(key, task, folder, control)
    jobs = []
    for arm, task, stage, row in gen["rows"]:
        if row["valid"]:
            key = f"{arm}/{task}/{stage}"
            page = OUT / "candidates" / key / "page"
            if source_files(page) != row["files_sha256"]:
                raise ValueError(f"Frozen candidate changed: {key}")
            jobs.append((key, task, page, False))
    if "ai" in prep["available"]:
        jobs.extend((f"fixed/{t}", t, OUT / "fixed-example", True) for t in LATE)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = dict(pool.map(one, jobs))
    reports = [path for name in ("scores", "calibration") for path in (OUT / name).rglob("report.json")]
    dump(OUT / "scores-complete.json", {"utc":now(), "rows":results,
         "inputs_sha256":file_hashes([OUT / "generation-complete.json", *reports])})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze","prepare","generate","score"))
    parser.add_argument("--budget-usd", type=float)
    args = parser.parse_args()
    if args.action == "freeze":
        if args.budget_usd is None:
            parser.error("freeze requires the authorized stage limit")
        freeze(args.budget_usd)
    else:
        {"prepare":prepare, "generate":generate, "score":score}[args.action]()
