"""Audit the published trials and optionally verify local pages, requests and receipts."""

import argparse
from collections import defaultdict

from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.public_library_transfer.self_refinement.native import run, transport
from studies.study_io import ROOT, digest, read, sha

RESULT = ROOT / "studies/results/self-native-20261124.json"
ARMS = ("old_direct", "old_self", "direct", "self", "fixed")


def comparison(rows):
    common = [
        row for row in rows if all(row[arm]["passed"] is not None for arm in ARMS)
    ]
    return {
        "common": [row["task"] for row in common],
        "passed": {arm: sum(row[arm]["passed"] for row in common) for arm in ARMS},
        "all_observed": {
            arm: [row["task"] for row in rows if row[arm]["passed"] is not None]
            for arm in ARMS
        },
        "self_only_vs_fixed": [
            row["task"]
            for row in common
            if row["self"]["passed"] and not row["fixed"]["passed"]
        ],
        "fixed_only_vs_self": [
            row["task"]
            for row in common
            if row["fixed"]["passed"] and not row["self"]["passed"]
        ],
    }


def request_evidence(root, schema_steps):
    calls = {r["id"]: r for r in ledger_read.calls(root / "budget.sqlite3")}
    evidence = []
    spends = defaultdict(lambda: [0, 0, 0])
    for path in sorted(root.rglob("request.json")):
        req = read(path)
        call = calls.pop(req["call_id"])
        body = req["body"]
        assert call["model"] == body["model"] == transport.MODEL and body[
            "reasoning"
        ] == {"enabled": False}
        assert (
            body["provider"]["require_parameters"]
            and call["purpose"].split("/")[0] == root.name
        )
        _, group, step, *_ = call["purpose"].split("/")
        assert group in run.GROUPS
        if step in schema_steps:
            assert body["response_format"]["json_schema"]["strict"]
        p = path.parent / "response.json"
        settled = path.parent / "settled.json"
        r = {
            "purpose": call["purpose"],
            "request_sha256": sha(path),
            "response_sha256": sha(p) if p.is_file() else None,
            "ledger_status": call["status"],
        }
        if settled.exists():
            ack, resp = read(settled), read(p)
            assert ack["ticket"] == req["call_id"] and ack["response_sha256"] == sha(p)
            assert resp["model"] == transport.MODEL
            usage = resp["usage"]
            r.update(
                provider=resp.get("provider"),
                completion_tokens=usage["completion_tokens"],
                prompt_tokens=usage["prompt_tokens"],
                reasoning_tokens=(usage.get("completion_tokens_details") or {}).get(
                    "reasoning_tokens"
                ),
                visible_characters=len(
                    resp["choices"][0]["message"].get("content") or ""
                ),
                finish_reason=resp["choices"][0]["finish_reason"],
                receipt_sha256=sha(settled),
            )
        phase = group + ("/target" if step == "target" else "/construction")
        account = spends[phase]
        account[0] += 1
        account[1] += call["actual"] or 0
        account[2] += call["reserved"] if call["actual"] is None else call["actual"]
        evidence.append(r)
    assert not calls
    return {
        "ledger": ledger_read.totals(root / "budget.sqlite3"),
        "by_phase": {
            k: dict(calls=v[0], settled_usd=v[1] / 1e6, exposure_usd=v[2] / 1e6)
            for k, v in spends.items()
        },
        "requests": evidence,
    }


def project_report(project, *, stage=run.OUT, schema_steps=("design", "target", "repair")):
    root = stage / project
    source = "extension" if project == "table" else "form"
    archived = ROOT / f"studies/results/backbone-{source}-20261124.json"
    oldroot = ROOT / f"artifacts/backbone-{source}-20261124/inputs" / project
    contract = read(root / "browser.json")
    assert read(oldroot / "public.json") == read(root / "public.json")
    assert (
        read(oldroot / "browser.json") == contract == browser.verify_contract(project)
    )
    original = {
        (r["arm"], r["task"]): {
            k: r[k]
            for k in ("status", "passed", "response_sha256", "report_sha256")
            if k in r
        }
        for r in read(archived)["models"][transport.MODEL]["rows"]
        if r["project"] == project
    }
    indexed = {}
    for r in read(root / "scores.json"):
        group, arm, t = r["group"], r["arm"], r["task"]
        f = root / group
        if arm == "fixed":
            status = read(f / "build/status.json")
            page = f / status.get("fixed_page", "")
        else:
            f = f / "targets" / str(t)
            status = read(f / "status.json")
            page = f / "page"
        assert r["status"] == status["status"]
        if r["status"] == "valid":
            files = status["files"]
            browser.verify_page(page, files, project)
            key = digest(files)
            receipt = (
                root / "browser/scores" / project / f"task-{t}" / key / "score.json"
            )
            expected = dict(
                project=project,
                task=t,
                files_digest=key,
                contract_digest=digest(contract),
            )
            verified = browser.verify_receipt(root, receipt, expected)
            assert (
                r["files_digest"] == key
                and r["report_sha256"] == verified["report_sha256"]
                and r["passed"] == verified["passed"]
            )
        else:
            assert (r["status"], r["passed"]) in (("invalid", False), ("missing", None))
        indexed[group, arm, t] = {
            k: v for k, v in r.items() if k not in ("group", "arm", "task")
        }
    assert len(indexed) == 100
    for g in run.GROUPS:
        for name, h in read(root / g / "seal.json").items():
            assert sha(root / name) == h
    out = {}
    for replica in ("build-a", "build-b"):
        b = root / replica / "build"
        state = read(b / "status.json")
        package = b / "package.json"
        if state["status"] == "valid":
            assert sha(package) == state["package_sha256"]
        rows = [
            {
                "task": i,
                "old_direct": original["direct", i],
                "old_self": original["self", i],
                "direct": indexed["direct", "direct", i],
                "self": indexed[replica, "self", i],
                "fixed": indexed[replica, "fixed", i],
            }
            for i in run.TASKS
        ]
        out[replica] = {
            "seal_sha256": sha(root / replica / "seal.json"),
            "status": state["status"],
            "reason": state.get("reason"),
            "package_sha256": state.get("package_sha256"),
            "controls": read(b / "manifest.json")["controls"]
            if (b / "manifest.json").exists()
            else None,
            "public_checks": {
                p.stem: {
                    k: v for k, v in read(p).items() if k in ("load_errors", "probe")
                }
                for p in sorted(b.glob("*-check.json"))
            },
            "comparison": comparison(rows),
            "rows": rows,
        }
    return {
        "historical_sha256": sha(archived),
        "input_sha256": sha(root / "public.json"),
        "browser_sha256": digest(contract),
        "direct_seal_sha256": sha(root / "direct/seal.json"),
        "replicas": out,
        **request_evidence(root, schema_steps),
    }


def public_check(data):
    assert set(data["projects"]) == set(run.PROJECTS)
    for project, block in data["projects"].items():
        assert block["ledger"]["exposure_usd"] <= data["project_budget_usd"]
        assert len(block["requests"]) == block["ledger"]["calls"]
        for result in block["replicas"].values():
            assert [r["task"] for r in result["rows"]] == list(run.TASKS)
            assert comparison(result["rows"]) == result["comparison"]
        a, b = (block["replicas"][k] for k in ("build-a", "build-b"))
        assert [r["direct"] for r in a["rows"]] == [r["direct"] for r in b["rows"]]
        print(
            project,
            [
                (r["comparison"]["passed"], len(r["comparison"]["common"]))
                for r in (a, b)
            ],
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "check-local"))
    args = parser.parse_args()
    if args.action == "check":
        public_check(read(RESULT))
        return
    run.verify()
    data = {
        "model": transport.MODEL,
        "registered_utc": read(run.OUT / "registered.json")["utc"],
        "registration_sha256": sha(run.OUT / "registered.json"),
        "protocol_sha256": sha(run.HERE / "PROTOCOL.md"),
        "project_budget_usd": run.CAP,
        "end_utc": transport.END.isoformat(),
        "projects": {p: project_report(p) for p in run.PROJECTS},
    }
    public_check(data)
    if args.action == "write":
        core.save(RESULT, data)
    else:
        assert data == read(RESULT)


if __name__ == "__main__":
    main()
