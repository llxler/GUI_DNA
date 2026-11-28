"""Recompute the published cells from raw model replies and official browser reports."""

import re
from unittest.mock import patch

from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, read, sha
from . import report, run
from .mount_recovery import run as recovery


def verify():
    data = read(report.RESULT)
    local = recovery.OUT
    assert all(sha(ROOT / f) == h for f, h in data["registered_sources"].items())
    reg = read(local / "registration.json")
    assert sha(local / "registration.json") == data["registration"]
    assert sha(local / "seal.json") == data["seal"]
    library = read(local / "libraries/gpt5/library.json")
    with patch.object(run, "OUT", local):
        assert data["accepted_responses"] == run.accepted_responses(library["parts"])
    old = read(run.profiles.HERE / "result.json")
    result = {}
    for tag in run.modules.TARGETS:
        model = reg["models"][tag]
        rows = data["models"][model]
        choices = report.observations(rows, report.ARM, data["targets"])
        checked = {}
        for task, r in choices.items():
            if library["status"] == "valid":
                dest = local / "plans" / tag / str(task)
                assert read(dest / "choice.json").get("number") == r["profile"]
                replies = []
                for receipt in sorted(dest.glob("call/*/transmission-*/settled.json")):
                    raw = receipt.with_name("response.json")
                    assert sha(raw) == read(receipt)["response_sha256"]
                    body = read(raw)
                    assert (
                        body["model"]
                        == read(receipt.with_name("request.json"))["body"]["model"]
                        == model
                    )
                    answer = run.modules.calc.base.uncode(
                        body["choices"][0]["message"].get("content") or ""
                    )
                    if re.fullmatch(r"[0-9]", answer):
                        replies.append((int(answer), sha(raw)))
                if r["status"] == "valid":
                    assert replies[0][0] == r["profile"]
                checked[task] = dict(
                    profile=r["profile"],
                    response_sha256=replies[0][1] if replies else None,
                )
        previous = {
            r["task"]: r["levels"] for r in old["models"][model] if r["arm"] == "self"
        }
        assert (
            previous
            == {r["task"]: r["levels"] for r in rows if r["arm"] == "self-choice"}
            or library["status"] != "valid"
        )
        passed = {}
        for arm in (report.ARM, report.FIXED, "self-choice"):
            for task, r in report.observations(rows, arm, data["targets"]).items():
                if r["status"] != "valid":
                    continue
                expected = dict(
                    project="calculator",
                    task=task,
                    files_digest=r["files_digest"],
                    contract_digest=browser.digest(reg["contract"]),
                )
                receipt = (
                    local
                    / "browser/scores/calculator"
                    / f"task-{task}"
                    / r["files_digest"]
                    / "score.json"
                )
                verified = browser.verify_receipt(local, receipt, expected)
                assert (verified["passed"], verified["report_sha256"]) == (
                    r["passed"],
                    r["report_sha256"],
                )
            passed[arm] = [r["task"] for r in rows if r["arm"] == arm and r["passed"]]
        planned, fixed = set(passed[report.ARM]), set(passed[report.FIXED])
        result[model] = dict(
            choices=checked,
            passed=passed,
            only_planned=sorted(planned - fixed),
            only_fixed=sorted(fixed - planned),
        )
    cost = ledger_read.totals(local / "budget.sqlite3")
    assert cost == data["cost"] and cost["exposure_usd"] <= reg["budget"]
    original = ledger_read.totals(recovery.ORIGINAL / "budget.sqlite3")
    assert original == reg["prior_cost"]
    phases = {"first_delivery": original, "mount_and_deploy": cost}
    total = {
        k: round(sum(v[k] for v in phases.values()), 6)
        for k in ("calls", "unsettled_calls", "settled_usd", "exposure_usd")
    }
    assert total["exposure_usd"] <= 10
    return dict(
        source=sha(report.RESULT),
        models=result,
        public_mount_tests=recovery.diagnose(),
        billing=phases,
        total=total,
    )


if __name__ == "__main__":
    core.save(report.VERIFICATION, verify())
