"""Offline assessment of sealed table libraries against the original current-task contract."""
import argparse
import hashlib
from decimal import Decimal, ROUND_CEILING

from gui_dna.provider import parse_json
from studies.contract_library import run
from studies.ledger_read import calls, totals
from studies.library_refinement_table.adapter import score_pages
from studies.study_io import ROOT, cases_by_file, digest, dump, read, sha, source_files
from studies.table_library_sources.run import verify

RESULT = ROOT / "studies/results/contract-library-table-20261123.json"


def audit_call(folder, expected, validator, by_id, seen, model, limit, seed):
    """Follow only repairs authorized by the generator, including fully missing responses."""
    attempts = []
    for stage in ("first", "repair"):
        part = folder / stage
        if stage == "repair" and not part.exists():
            break
        receipt = read(part / "result.json")
        assert read(part / "messages.json") == expected
        assert digest(expected) == receipt["prompt_sha256"]
        info = {**receipt, "stage": stage}
        path = part / "call/request.json"
        if path.exists():
            req = read(path)
            rid = req["call_id"]
            assert rid not in seen
            seen.add(rid)
            row = by_id[rid]
            assert row["purpose"].endswith("/".join(part.parts[-(4 if folder.parent.name in ("component", "plans") else 3):]))
            body = req["body"]
            assert body["messages"] == expected and body["model"] == row["model"] == model
            assert body["max_tokens"] == limit
            if "seed" in body:
                assert body["seed"] == seed
            info.update(call_id=rid, status=row["status"], model=model, actual_micro_usd=row["actual"],
                        reserved_micro_usd=row["reserved"], request_sha256=sha(path))
        else:
            assert not receipt["received"] and not receipt["valid"]
        answer = part / "call/response.json"
        if answer.exists():
            assert path.exists()
            raw = read(answer)
            info["response_sha256"] = sha(answer)
            cost = raw.get("usage", {}).get("cost")
            if by_id[rid]["actual"] is not None:
                assert cost is not None
                billed = Decimal(str(cost)) * 1_000_000
                assert int(billed.to_integral_value(rounding=ROUND_CEILING)) == by_id[rid]["actual"]
        else:
            assert not receipt["received"]
        if receipt["received"]:
            choice = raw["choices"][0]
            content = choice["message"]["content"] or ""
            info["finish_reason"] = choice.get("finish_reason")
            info["output_tokens"] = raw["usage"].get("completion_tokens")
            info["reasoning_tokens"] = raw["usage"].get("completion_tokens_details", {}).get("reasoning_tokens")
            try:
                value = validator(parse_json(content))
            except (ValueError, TypeError, KeyError):
                assert not receipt["valid"] and not (part / "accepted.json").exists()
            else:
                assert receipt["valid"] and value == read(part / "accepted.json")
                info["accepted_sha256"] = sha(part / "accepted.json")
                attempts.append(info)
                assert stage == "repair" or not (folder / "repair").exists()
                return value, attempts
        else:
            assert not receipt["valid"] and not (part / "accepted.json").exists()
        attempts.append(info)
        if not receipt["received"]:
            assert not (folder / "repair").exists()
            break
        expected = expected + [{"role": "assistant", "content": content}, {"role": "user", "content":
            "Public validation failed: " + receipt["error"] + ". Return a complete corrected JSON object."}]
    return None, attempts


def compiled_files(package, plan):
    return {name: hashlib.sha256(content.encode()).hexdigest()
            for name, content in run.compile_plan(package, plan).items()}


def grade_value(out, key, task):
    folder = out / "evaluation/scores" / key
    score = read(folder / "score.json")
    raw = read(folder / "report.json")
    assert sha(folder / "report.json") == score["report_sha256"]
    assert not [e for e in raw.get("errors", []) if "maximum allowed failures" not in e.get("message", "")]
    cases = cases_by_file(raw)
    assert set(cases) == {task} and cases[task] == score["tests"][task] and cases[task]
    passed = all(c["passed"] for c in cases[task])
    assert passed or any(s in ("failed", "timedOut") for c in cases[task] for s in c["statuses"])
    assert passed == score["all_passed"]
    return {"passed": passed, "page_manifest_sha256": key.split("/")[-1],
            "official_report_sha256": score["report_sha256"]}


def paired(legacy, fresh):
    cells = {"both_pass": [], "legacy_only": [], "new_only": [], "both_fail": []}
    names = {(True, True): "both_pass", (True, False): "legacy_only",
             (False, True): "new_only", (False, False): "both_fail"}
    missing = []
    for task in legacy:
        old, new = legacy[task], fresh[task]["passed"]
        if old is None or new is None:
            missing.append(task)
        else:
            cells[names[old, new]].append(task)
    return {"observed_pairs": sum(map(len, cells.values())), "cell_counts": {k: len(v) for k, v in cells.items()},
            "cell_targets": cells, "unpaired": missing}


def summarize_targets(rows):
    observed = [v for v in rows.values() if v["passed"] is not None]
    return {"planned": len(rows), "preparation_blocked": sum(v["status"] == "preparation_failed" for v in rows.values()),
            "no_plan_response": sum(v["status"] == "missing_response" for v in rows.values()),
            "invalid_response": sum(v["status"] == "invalid_response" for v in rows.values()),
            "executable": sum(v["status"] == "executable" for v in rows.values()),
            "observed": len(observed), "passed": sum(v["passed"] for v in observed) if observed else None}


def evaluate(write=False, workers=4):
    out = run.OUT
    freeze = read(out / "freeze.json")
    generation = read(out / "generation-complete.json")
    verify(freeze["inputs"])
    verify(generation["inputs"])
    public = read(out / "public.json")
    assert public["starter"] == run.starter() and public["requirements"] == run.requirements("table")
    assert [r["id"] for r in public["requirements"]] == ["init", *run.TASKS]
    archived = read(run.BASE)
    assert set(archived["targets"]) == set(run.TASKS)
    historical = {arm: {t: archived["targets"][t][arm]["first"]["passed"] for t in run.TASKS}
                  for arm in ("direct", "reference", "ai")}
    assert all(isinstance(x, bool) for arm in historical.values() for x in arm.values())
    assert sum(historical["ai"].values()) == 3
    ledger_file = out / "budget.sqlite3"
    by_id = {r["id"]: r for r in calls(ledger_file)}
    ledger = totals(ledger_file)
    assert ledger["exposure_usd"] <= ledger["cap_usd"] == freeze["cap"]
    seen = set()
    jobs, repeats, expected_rows = {}, {}, []

    def register(page, task, files):
        assert source_files(page) == files
        key = task + "/" + digest(files)
        jobs.setdefault(key, (key, task, page))
        return key

    for rep in (1, 2):
        folder = out / f"rep-{rep}"
        build = read(folder / "build.json")
        assert build == generation["builds"][str(rep)]
        seed = freeze["seeds"][rep - 1]
        design, design_calls = audit_call(folder / "design", run.msg(run.DESIGN, public), run.design_ok,
                                         by_id, seen, run.BUILDER, 1500, seed)
        preparation = {"design": design_calls, "components": {}}
        components = {}
        expected_failure = "design"
        if design:
            for name in ["core", *(f["id"] for f in design["features"])]:
                payload = {"public": public, "design": design, "component": name}
                if name != "core":
                    payload["installed_core"] = components["core"]["js"]
                part, receipts = audit_call(folder / "component" / name, run.msg(run.IMPLEMENT, payload),
                                            run.component_ok, by_id, seen, run.MODEL, 4096, seed)
                preparation["components"][name] = receipts
                if part is None:
                    expected_failure = name
                    break
                components[name] = part
            else:
                expected_failure = "public load" if build["problems"] else None
                package = read(folder / "package.json")
                assert package == run.assemble(public, design, components)
                assert sha(folder / "package.json") == build["package_sha256"]
        assert build["failed_at"] == expected_failure and build["valid"] == (expected_failure is None)
        targets, controls = {}, {}
        for i, task in enumerate(run.TASKS, 1):
            if not build["valid"]:
                targets[task] = {"status": "preparation_failed", "passed": None}
                continue
            prefix = public["requirements"][:i + 1]
            payload = {"starter": public["starter"], "requirements": prefix, "interface": package["plan_documentation"],
                       "examples": package["examples"], "plan_schema": package["plan_schema"]}
            dest = folder / "plans" / task
            assert not (dest / "repair").exists()

            def plan_value(plan):
                return {"plan": plan, "files": compiled_files(package, plan)}

            accepted, receipts = audit_call(dest, run.msg(run.PLAN, payload), plan_value, by_id, seen, run.MODEL, 8192, seed)
            r = receipts[0]
            files = accepted["files"] if accepted else None
            expected_rows.append({"rep": rep, "task": task, "response": r["received"], "valid": accepted is not None,
                                  "files": files})
            if accepted:
                targets[task] = {"status": "executable", "score_key": register(dest / "page", task, files),
                                 "plan": accepted["plan"]}
            else:
                status = "invalid_response" if r["received"] else "missing_response"
                targets[task] = {"status": status, "passed": False if r["received"] else None}
            targets[task]["attempt"] = r
        if build["valid"]:
            for label, example in zip(("empty", "full"), package["examples"], strict=True):
                page = folder / "fixed" / label
                files = compiled_files(package, example)
                controls[label] = {task: {"score_key": register(page, task, files)} for task in run.TASKS}
        repeats[str(rep)] = {"seed_requested": seed, "build": build, "preparation_receipts": preparation,
                             "targets": targets, "fixed_page_controls": controls}
    assert seen == set(by_id)
    assert sorted(expected_rows, key=lambda r: (r["rep"], r["task"])) == sorted(
        generation["rows"], key=lambda r: (r["rep"], r["task"]))
    if jobs and write:
        score_pages(out / "evaluation", list(jobs.values()), workers)
    scored = {k: grade_value(out, k, task) for k, task, _ in jobs.values()}
    for repeat in repeats.values():
        for group in (repeat["targets"], *repeat["fixed_page_controls"].values()):
            for t, row in group.items():
                if "score_key" in row:
                    row.update(scored[row.pop("score_key")])
        repeat["target_summary"] = summarize_targets(repeat["targets"])
        repeat["fixed_summaries"] = {k: {"passed": sum(v["passed"] for v in rows.values()), "observed": len(rows)}
                                     for k, rows in repeat["fixed_page_controls"].items()}
        repeat["paired_vs_legacy_ai"] = paired(historical["ai"], repeat["targets"])
    confirmed = all(r["target_summary"]["observed"] == len(run.TASKS) and r["target_summary"]["passed"] > 3
                    for r in repeats.values())
    summary = {"study": "contract-library-table-20261123", "project": "table",
               "confirmation_rule": "Each of the two independently prepared libraries must produce a first response "
                                    "at all 20 matched targets and pass more than 3 current official task files.",
               "confirmed": confirmed, "historical_first_response": {
                    arm: {"observed": len(rows), "passed": sum(rows.values()), "targets": rows}
                    for arm, rows in historical.items()},
               "repeats": repeats, "ledger": ledger,
               "verification": {"generation_closed_utc": generation["utc"], "preparation_frozen_utc": freeze["utc"],
                                "freeze_sha256": sha(out / "freeze.json"),
                                "generation_manifest_sha256": sha(out / "generation-complete.json"),
                                "historical_summary_sha256": sha(run.BASE), "upstream_revision": archived["upstream_revision"],
                                "unique_task_and_page_bundles_scored": len(scored), "ledger_ids_matched": len(seen),
                                "evaluation_runtime_if_scored": archived["evaluation_runtime"]}}
    if write and not RESULT.exists():
        dump(RESULT, summary)
    else:
        assert read(RESULT) == summary, "Mismatch with published result"
    print("confirmed", confirmed, "unique official reports", len(scored), "ledger", ledger)
    for key, value in repeats.items():
        print("rep", key, value["target_summary"])
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("score", "check"))
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    evaluate(write=args.mode == "score", workers=args.workers)
