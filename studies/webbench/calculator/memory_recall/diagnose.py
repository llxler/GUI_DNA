"""Explain discrepancies on frozen pages that passed all five public memory checks."""

import re
from pathlib import Path

from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, read, sha
from studies.webbench.calculator.key_programs import run as keys

HERE = Path(__file__).resolve().parent


def failures(report):
    results = []

    def visit(suite):
        for spec in suite.get("specs", []):
            for test in spec["tests"]:
                if not test["results"]:
                    continue
                result = test["results"][-1]
                if result["status"] in ("passed", "skipped"):
                    continue
                message = re.sub(
                    r"\x1b\[[0-9;]*m", "", result.get("error", {}).get("message", "")
                )
                lines = {
                    s.split(": ", 1)[0].lower(): s.split(": ", 1)[1]
                    for s in message.splitlines()
                    if s.startswith(("Expected: ", "Received: "))
                }
                results.append(
                    {"case": spec["title"], "status": result["status"], **lines}
                )
        for child in suite.get("suites", []):
            visit(child)

    for suite in report["suites"]:
        visit(suite)
    return results


def inspect():
    cert = ROOT / "artifacts/calculator-memory-recall-20261128/registration.json"
    calibration = read(cert)
    source = keys.HERE / "result.json"
    primary = read(source)
    seal = read(keys.OUT / "seal.json")
    models = read(keys.OUT / "registration.json")["models"]
    output = {}
    for tag, checks in calibration["initial_checks"].items():
        if not all(v["ok"] for v in checks.values()):
            continue
        entries = []
        for task in (15, 16, 18, 19):
            row = next(
                r
                for r in seal["rows"]
                if r["tag"] == tag and r["task"] == task and r["arm"] == "fixed-self"
            )
            score = next(
                r
                for r in primary["models"][models[tag]]
                if r["task"] == task and r["arm"] == "fixed-self"
            )
            fingerprint = browser.digest(row["files"])
            path = (
                keys.OUT
                / f"browser/scores/calculator/task-{task}"
                / fingerprint
                / "score.json"
            )
            receipt = browser.verify_receipt(
                keys.OUT,
                path,
                dict(
                    project="calculator",
                    task=task,
                    files_digest=fingerprint,
                    contract_digest=browser.digest(calibration["contract"]),
                ),
            )
            report = keys.OUT / receipt["report"]
            assert sha(report) == score["report_sha256"]
            errors = failures(read(report))
            assert bool(errors) == (score["passed"] is False)
            entries.append(
                dict(
                    task=task,
                    passed=score["passed"],
                    report_sha256=sha(report),
                    failures=errors,
                )
            )
        output[models[tag]] = entries
    return dict(
        source=str(source.relative_to(ROOT)),
        source_sha256=sha(source),
        frozen_public_check_registration=sha(cert),
        models=output,
    )


if __name__ == "__main__":
    result = inspect()
    core.save(HERE / "browser-errors.json", result)
    print(
        "Verified official memory-task receipts for",
        len(result["models"]),
        "frozen full pages.",
    )
