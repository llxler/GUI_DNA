"""Verify sealed pages, model identities, configuration replies and original browser reports."""

import argparse
import hashlib

from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, read, sha
from . import report, run
from .event_routing import run as routed
from .command_delivery import run as commands
from .core_recovery import run as recovered
from .keyboard_transitions import run as transitions


def replies(folder, model):
    for path in sorted(folder.rglob("settled.json")):
        raw = path.with_name("response.json")
        assert sha(raw) == read(path)["response_sha256"]
        body = read(path.with_name("request.json"))["body"]
        answer = read(raw)
        assert body["model"] == answer["model"] == model
        yield dict(
            response=str(raw.relative_to(ROOT)),
            sha256=sha(raw),
            returned_model=answer["model"],
            requested_model=model,
            text=answer["choices"][0]["message"].get("content") or "",
        )


def verify_stage(local, result_path, parent=None):
    data = read(result_path)
    reg = read(local / "registration.json")
    seal = read(local / "seal.json")
    assert (
        sha(local / "registration.json") == data["registration"] == seal["registration"]
    )
    assert sha(local / "seal.json") == data["seal"] and data[
        "cost"
    ] == ledger_read.totals(local / "budget.sqlite3")
    assert data["cost"]["exposure_usd"] <= reg["cap"]
    assert all(sha(ROOT / p) == h for p, h in reg["sources"].items())
    if local == transitions.OUT:
        assert (
            seal["parent_seals"]
            == reg["parent_seals"]
            == {p.name: sha(p / "seal.json") for p in transitions.STAGES}
        )
    elif parent:
        assert seal["parent_seal"] == sha(parent / "seal.json")
    summary = report.summarize(data)
    indexed = {(r["tag"], r["task"], r["arm"]): r for r in seal["rows"]}
    assert len(indexed) == len(seal["rows"])
    compared = set()
    for tag, model in data["generators"].items():
        local_lib = read(local / "libraries" / tag / "library.json")
        allowed = {p["count"] for p in local_lib["profiles"]}
        if local == transitions.OUT:
            parent = transitions.parent(tag)
        if parent:
            assert local_lib["parent_library"] == sha(
                parent / "libraries" / tag / "library.json"
            )
        original_choices = local
        if parent and not local_lib["changed"] and local_lib["status"] == "valid":
            parent_lib = read(parent / "libraries" / tag / "library.json")
            assert (
                parent_lib["parts"] == local_lib["parts"]
                and parent_lib["profiles"] == local_lib["profiles"]
            )
            ancestors = (*transitions.STAGES, transitions.OUT)
            for previous in reversed(ancestors[: ancestors.index(local)]):
                old_path = previous / "libraries" / tag / "library.json"
                if old_path.exists() and read(old_path).get("changed", True):
                    original_choices = previous
                    break
            else:
                raise AssertionError(f"No original configuration for {tag}")
        # Record the hash of every module used for deployment. A composed renderer
        # also has a manifest of the same author's item definitions and callbacks.
        modules = {
            f"common/{k}.js": hashlib.sha256(v.encode()).hexdigest()
            for k, v in local_lib["parts"].items()
        }
        origins = []
        authored = set()
        for rec in replies(local / "libraries" / tag, model):
            origins.append({k: v for k, v in rec.items() if k != "text"})
            code = run.API.calc.base.uncode(rec["text"]).strip()
            authored.add(hashlib.sha256(code.encode()).hexdigest())
        if parent is None and local_lib["status"] == "valid":
            assert set(modules.values()) <= authored
        if local == transitions.OUT:
            old = read(parent / "libraries" / tag / "library.json")["parts"]
            aligned = {k: old.get(k, transitions.NOOP) for k in local_lib["parts"]}
            previous_modules = {
                f"common/{k}.js": hashlib.sha256(v.encode()).hexdigest()
                for k, v in aligned.items()
            }
            accepted = {}
            public = {
                "before": sorted(run.passed(local_lib["history"][0]["public"])),
                "after": local_lib["profiles"][-1]["checks"],
                "groups": {},
            }
            for name in transitions.GROUPS:
                folder = local / "libraries" / tag / "functions" / name
                attempts = []
                for evidence in sorted(folder.glob("*/unit.json")):
                    checks = read(evidence)
                    response = list(replies(evidence.parent / "call", model))[-1]
                    body = routed.function_body(response["text"], "s")
                    assert transitions.unit(name, body) == checks
                    failures = [case for case in checks if not case["pass"]]
                    attempts.append(
                        dict(
                            tested=len(checks),
                            passed=len(checks) - len(failures),
                            failed_examples=failures,
                            response_sha256=response["sha256"],
                        )
                    )
                    if not failures and name in local_lib["retained"]:
                        accepted[name] = body
                public["groups"][name] = {
                    "deployed": name in accepted,
                    "attempts": attempts,
                }
            summary[model]["public_keyboard_checks"] = public
            if local_lib["changed"]:
                assert accepted and local_lib["parts"] == transitions.candidate(
                    old, accepted
                )
            else:
                assert not accepted and local_lib["parts"] == old
        plan_sources = {}
        for row in data["models"][model]:
            n, arm = row["task"], row["arm"]
            candidate = indexed[tag, n, arm]
            assert (
                row["count"] == candidate["count"]
                and row["status"] == candidate["status"]
            )
            compared.add((tag, n, arm))
            if row["status"] != "valid":
                continue
            fp = row["files_digest"]
            assert fp == browser.digest(candidate["files"])
            browser.verify_page(ROOT / candidate["page"], candidate["files"], "table")
            if arm in ("self", "fixed-self"):
                assert all(
                    candidate["files"].get(path) == digest
                    for path, digest in modules.items()
                )
            if arm == "old-same-choice":
                new = indexed[tag, n, "self"]
                assert candidate["count"] == new["count"]
                assert candidate["files"]["index.js"] == new["files"]["index.js"]
                assert all(
                    candidate["files"][p] == h for p, h in previous_modules.items()
                )
            if arm == "fixed-self":
                assert row["count"] == len(modules)
            if arm == "self":
                folder = original_choices / "plans" / tag / str(n)
                choice = read(folder / "choice.json")
                actual = []
                for rec in replies(folder, model):
                    text = run.API.calc.base.uncode(rec["text"]).strip()
                    if text.isdecimal() and int(text) in allowed:
                        actual.append((int(text), rec["sha256"]))
                assert actual[0][0] == choice["count"] == row["count"]
                plan_sources[str(n)] = dict(
                    count=choice["count"], response_sha256=actual[0][1]
                )
            receipt = local / f"browser/scores/table/task-{n}" / fp / "score.json"
            real = browser.verify_receipt(
                local,
                receipt,
                dict(
                    project="table",
                    task=n,
                    files_digest=fp,
                    contract_digest=browser.digest(reg["contract"]),
                ),
            )
            assert (real["report_sha256"], real["passed"]) == (
                row["report_sha256"],
                row["passed"],
            )
            if local == transitions.OUT and arm == "self" and not real["passed"]:
                cases = browser.cases_by_file(read(local / real["report"]))[f"task-{n}"]
                failing = [
                    c["title"]
                    for c in cases
                    if {"failed", "timedOut"}.intersection(c["statuses"])
                ]
                assert failing
                summary[model].setdefault("official_failures", {})[str(n)] = {
                    "cases": failing,
                    "report_sha256": real["report_sha256"],
                }
        summary[model].update(
            modules=modules if local_lib["status"] == "valid" else {},
            choices=plan_sources,
            build_responses=origins,
        )
    assert compared == set(indexed)
    return summary


def verify():
    paths = report.STAGES
    stages = {
        "first": verify_stage(run.OUT, report.FIRST),
        "routed": verify_stage(routed.OUT, report.ROUTED, run.OUT),
        "commands": verify_stage(commands.OUT, report.COMMANDS, routed.OUT),
        "core": verify_stage(recovered.OUT, report.RECOVERED, commands.OUT),
        "transitions": verify_stage(transitions.OUT, report.TRANSITIONS),
    }
    budgets = {name: read(path)["cost"] for name, path in paths.items()}
    totals = {
        k: round(sum(b[k] for b in budgets.values()), 6)
        for k in ("calls", "settled_usd", "exposure_usd", "unsettled_calls")
    }
    assert totals["exposure_usd"] <= 10
    return dict(
        receipts={k: sha(v) for k, v in paths.items()},
        stages=stages,
        costs=budgets,
        total=totals,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    data = verify()
    if parser.parse_args().write:
        core.save(report.VERIFICATION, data)
    assert data == read(report.VERIFICATION)
    print(data["total"])
