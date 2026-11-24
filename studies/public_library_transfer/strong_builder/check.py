"""Verify the published result offline; optionally trace it back to local raw receipts."""

import argparse
from collections import Counter
from itertools import product
from pathlib import Path

from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, digest, read, sha


def check(raw=False):
    folder = Path(__file__).resolve().parent
    result = read(folder / "result.json")
    reference = ROOT / "studies/results/backbone-extension-20261124.json"
    assert sha(reference) == result["source_report_sha256"]
    reference_rows = read(reference)["models"][result["deployer"]]["rows"]
    tasks = result["target_files"]
    assert tasks == list(range(1, 21))
    for arm, passed in result["comparison_passed_tasks"].items():
        rows = [
            row
            for row in reference_rows
            if row["project"] == "table" and row["arm"] == arm
        ]
        assert (
            sorted(row["task"] for row in rows if isinstance(row["passed"], bool))
            == tasks
        )
        assert sorted(row["task"] for row in rows if row["passed"]) == passed
    replicas = ("replica-1", "replica-2")
    assert set(result["sources"]) == set(replicas)
    expected = set(product(replicas, ("selected", "fixed"), tasks))
    actual = Counter(
        (row["replica"], row["arm"], row["task"]) for row in result["rows"]
    )
    assert set(actual) == expected and set(actual.values()) == {1}
    for replica in replicas:
        source = result["sources"][replica]
        for arm, counts in source["outcomes"].items():
            rows = [
                row
                for row in result["rows"]
                if row["replica"] == replica and row["arm"] == arm
            ]
            assert counts["passed"] == [r["task"] for r in rows if r["passed"] is True]
            assert counts["missing"] == [r["task"] for r in rows if r["passed"] is None]
            assert counts["invalid"] == [
                r["task"] for r in rows if r["status"] == "invalid"
            ]
            for row in rows:
                assert (row["status"] == "missing") == (row["passed"] is None)
                if row["status"] == "valid":
                    assert len(row["report_sha256"]) == 64
                elif row["status"] != "missing":
                    assert (
                        row["status"] in ("build_failed", "invalid")
                        and row["passed"] is False
                    )
    ledger = result["target_api"]
    assert (
        0 <= ledger["settled_usd"] <= ledger["exposure_usd"] <= ledger["cap_usd"] == 2.5
    )
    capacity_path = folder / "capacity.json"
    if capacity_path.exists():
        capacity = read(capacity_path)
        assert capacity["deployer_seal_sha256"] == result["seal_sha256"]
        for replica, space in capacity["spaces"].items():
            if not space["exhaustive"]:
                assert space.get("size", 5) > 4
                continue
            size = space["size"]
            assert 1 <= size <= 4 and len(space["plans"]) == size
            keys = [(r["config"], r["task"]) for r in space["rows"]]
            assert Counter(keys) == Counter(product(range(size), tasks))
            for index, passed in enumerate(space["by_config"]):
                assert [
                    r["task"]
                    for r in space["rows"]
                    if r["config"] == index and r["passed"]
                ] == passed
            reachable = sorted({n for passed in space["by_config"] for n in passed})
            assert reachable == space["reachable"]
            assert space["pass_count_by_task"] == {
                str(n): sum(n in passed for passed in space["by_config"]) for n in tasks
            }
            for arm in result["sources"][replica]["outcomes"].values():
                assert set(arm["passed"]) <= set(reachable)
    native_path = folder / "native/result.json"
    if native_path.exists():
        native = read(native_path)
        check_native(native, result, raw)
        from .plans import RESULT, USAGE, delivery, reconstruct

        plans = read(RESULT)
        assert plans["text_seal_sha256"] == result["seal_sha256"]
        assert plans["native_seal_sha256"] == native["seal_sha256"]
        for replica, details in plans["sources"].items():
            for label, group in details["arms"].items():
                counts = details["arms"][label]["settings"]
                positions = [n for setting in counts for n in setting["tasks"]]
                assert sorted(positions + group["invalid"] + group["missing"]) == tasks
                if label == "native":
                    assert len(counts) == 1 and counts[0]["plan"] == details["first"]
        if raw:
            assert reconstruct() == plans and delivery() == read(USAGE)
    if raw:
        raw_checks(result)


def check_native(native, primary, raw):
    folder = Path(__file__).resolve().parent
    assert native["previous_result_sha256"] == sha(folder / "result.json")
    tasks = primary["target_files"]
    assert (native["deployer"], native["builder"]) == (
        primary["deployer"],
        primary["builder_requested"],
    )
    for replica, summary in native["sources"].items():
        rows = [r for r in native["rows"] if r["replica"] == replica]
        assert sorted(r["task"] for r in rows) == tasks
        assert summary["passed"] == [r["task"] for r in rows if r["passed"] is True]
        assert summary["missing"] == [r["task"] for r in rows if r["passed"] is None]
        assert summary["invalid"] == [
            r["task"] for r in rows if r["status"] == "invalid"
        ]
        assert summary["baseline"] == primary["sources"][replica]["outcomes"]
        assert (
            summary["package_sha256"] == primary["sources"][replica]["package_sha256"]
        )
        assert summary["budget"]["exposure_usd"] <= summary["budget"]["cap_usd"] == 0.50
        assert summary["routing"] == dict(
            Counter(r["provider"] for r in rows if "provider" in r)
        )
    if not raw:
        return
    from .native import run as trial
    from studies.ledger_read import totals
    from studies.public_library_transfer.deployments.historical.run import (
        request_format,
    )

    assert trial.verify()["model"] == native["deployer"]
    assert sha(trial.OUT / "seal.json") == native["seal_sha256"]
    assert sha(trial.OUT / "registered.json") == native["registration_sha256"]
    data = read(trial.primary.OUT / "inputs/table/public.json")
    protocol = read(trial.primary.OUT / "inputs/table/browser.json")
    candidates = {
        (r["replica"], r["task"]): r
        for r in read(trial.OUT / "seal.json")["candidates"]
    }
    for row in native["rows"]:
        replica, n = row["replica"], row["task"]
        assert (
            totals(trial.OUT / replica / "budget.sqlite3")
            == native["sources"][replica]["budget"]
        )
        candidate = candidates[replica, n]
        assert row["status"] == candidate["status"]
        library = read(ROOT / primary["sources"][replica]["folder"] / "package.json")
        request_dir = trial.OUT / replica / f"task-{n}" / "call"
        if (request_dir / "request.json").exists():
            body = read(request_dir / "request.json")["body"]
            assert body["response_format"] == request_format(
                "answer", library["plan_schema"]
            )
            assert (
                body["reasoning"] == {"enabled": False}
                and body["provider"]["require_parameters"]
            )
            assert (
                body["seed"] == 20261124
                and body["temperature"] == 0
                and body["max_tokens"] == 8192
            )
            assert body["messages"] == core.plan_messages(data, n, library)
        if "response_sha256" in row:
            assert row["response_sha256"] == sha(request_dir / "response.json")
            assert (
                read(request_dir / "settled.json")["response_sha256"]
                == row["response_sha256"]
            )
        if candidate["status"] == "valid":
            files = candidate["files"]
            assert browser.tree(ROOT / candidate["page"]) == files
            receipt_path = (
                trial.primary.OUT
                / "browser/scores/table"
                / f"task-{n}"
                / digest(files)
                / "score.json"
            )
            expect = {
                "project": "table",
                "task": n,
                "files_digest": digest(files),
                "contract_digest": digest(protocol),
            }
            rec = browser.verify_receipt(trial.primary.OUT, receipt_path, expect)
            assert (rec["passed"], rec["report_sha256"]) == (
                row["passed"],
                row["report_sha256"],
            )


def raw_checks(result):
    from . import run
    from studies.ledger_read import totals

    run.configure()
    manifest = run.registered()
    assert sha(run.OUT / "registered.json") == result["registration_sha256"]
    assert sha(run.OUT / "seal.json") == result["seal_sha256"]
    assert totals(run.LEDGER) == result["target_api"]
    data = read(run.OUT / "inputs/table/public.json")
    primary = (
        ROOT
        / "artifacts/backbone-extension-20261124/qwen9/table/direct/1/call/request.json"
    )
    settings = {k: v for k, v in read(primary)["body"].items() if k != "messages"}
    sealed = {
        (r["replica"], r["arm"], r["task"]): r
        for r in read(run.OUT / "seal.json")["rows"]
    }
    for row in result["rows"]:
        replica, arm, n = row["replica"], row["arm"], row["task"]
        candidate = sealed[replica, arm, n]
        assert row["status"] == candidate["status"]
        source = result["sources"][replica]
        if source["status"] != "valid":
            continue
        library = ROOT / source["folder"] / "package.json"
        assert sha(library) == source["package_sha256"]
        package = read(library)
        if arm == "fixed":
            assert candidate["plan"] == package["examples"][0]["plan"]
        else:
            private = run.OUT / replica / arm / str(n) / "call"
            if (private / "request.json").exists():
                request = read(private / "request.json")["body"]
                assert request["messages"] == core.plan_messages(data, n, package)
                assert {k: v for k, v in request.items() if k != "messages"} == settings
            if "response_sha256" in row:
                assert sha(private / "response.json") == row["response_sha256"]
        if row["status"] == "valid":
            page = ROOT / candidate["page"]
            files = candidate["files"]
            assert browser.tree(page) == files
            scores = (
                run.OUT
                / "browser/scores/table"
                / f"task-{n}"
                / digest(files)
                / "score.json"
            )
            protocol = read(run.OUT / "inputs/table/browser.json")
            expected = {
                "project": "table",
                "task": n,
                "files_digest": digest(files),
                "contract_digest": digest(protocol),
            }
            receipt = browser.verify_receipt(run.OUT, scores, expected)
            assert (receipt["passed"], receipt["report_sha256"]) == (
                row["passed"],
                row["report_sha256"],
            )
    assert manifest["deployer"] == result["deployer"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Verify local request, budget and browser receipts too",
    )
    check(parser.parse_args().raw)
    print(
        "Verified registered library results and the available capacity and native-decoding follow-ups."
    )
