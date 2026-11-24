"""Check the published results, missingness, disjoint ledgers and paper cells offline."""

from argparse import ArgumentParser
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal

from studies.paper_performance import (
    FILES,
    FORM_RESULTS,
    SUITE_RESULTS,
    WEB_PROJECTS,
    joint_scores,
    performance_matrix,
)
from studies.study_io import ROOT, digest, dump, read, sha
from studies.ledger_read import calls
from gui_dna.budget import micros
from . import allocations

RESULTS = ROOT / "studies/results"
OVERVIEW = RESULTS / "backbone-overview-20261124.json"


def audit(check_table=True):
    daily = Counter()
    projects = defaultdict(dict)
    web_enrollments = set()
    for filename in FILES:
        source = read(RESULTS / filename)
        for model, group in source["models"].items():
            ledger = group["ledger"]
            assert ledger["settled_usd"] <= ledger["exposure_usd"] <= ledger["cap_usd"]
            for name in ("settled_usd", "exposure_usd", "unsettled_calls", "calls"):
                daily[name] += Decimal(str(ledger[name]))
            for key in ("settled", "exposure"):
                expected = int(Decimal(str(ledger[key + "_usd"])) * 1_000_000)
                assert sum(v[key + "_microusd"] for v in group["cost_by_project_method"].values()) == expected
            if filename not in (SUITE_RESULTS, FORM_RESULTS):
                assert model not in web_enrollments
                web_enrollments.add(model)
            groups = defaultdict(lambda: defaultdict(dict))
            outcomes = defaultdict(lambda: defaultdict(Counter))
            for r in group["rows"]:
                project = r.get("project") or ("todomvc" if r["group"] == "todomvc" else "duo")
                records = groups[project][r["arm"]]
                assert r["task"] not in records
                if r["status"] == "missing":
                    assert r["passed"] is None
                elif r["status"] in ("invalid", "build_failed"):
                    assert r["passed"] is False
                else:
                    assert (
                        r["status"] == "valid" and type(r["passed"]) is bool and len(r["report_sha256"]) == 64
                    )
                records[r["task"]] = r["passed"]
                label = (
                    "passed" if r["passed"] else ("test_failed" if r["status"] == "valid" else r["status"])
                )
                outcomes[project][r["arm"]][label] += 1
            for project, arms in groups.items():
                expected = {"todomvc": 8, "duo": 10}.get(project, 20)
                assert len(arms["direct"]) == expected and all(
                    set(a) == set(arms["direct"]) for a in arms.values()
                )
                if expected == 20:
                    assert set(arms["direct"]) == set(range(1, 21))
                assert project not in projects[model]
                fixed = arms.pop("fixed")
                scores = joint_scores(arms)
                fixed_pair = joint_scores({"fixed": fixed, "self": arms["self"]}, baseline="fixed")
                if fixed_pair is not None:
                    target_ids = fixed_pair["targets"]
                    fixed_pair["only_self"] = [t for t in target_ids if arms["self"][t] and not fixed[t]]
                    fixed_pair["only_fixed"] = [t for t in target_ids if fixed[t] and not arms["self"][t]]
                    assert fixed_pair["passed"]["self"] - fixed_pair["passed"]["fixed"] == (
                        len(fixed_pair["only_self"]) - len(fixed_pair["only_fixed"])
                    )
                projects[model][project] = {
                    "comparison": scores,
                    "fixed_pair": fixed_pair,
                    "all_scheduled_outcomes": outcomes[project],
                }
    assert len(web_enrollments) == 12 and daily["exposure_usd"] <= 20
    if check_table:
        matrix = read(RESULTS / "paper-performance-matrix.json")
        assert set(matrix) == web_enrollments
        archive = {
            key: read(RESULTS / (name + "-20261123.json"))
            for key, name in (
                ("table", "table-library-sources"),
                ("editor", "expression-editor-sources"),
                ("chart", "svg-chart-interfaces"),
            )
        }
        assert matrix == performance_matrix(
            read(RESULTS / "end_to_end.json"),
            read(RESULTS / "primary-replay.json"),
            read(RESULTS / "library-sources-20261121.json"),
            archive,
        )
        for m, model in projects.items():
            for project, r in model.items():
                assert matrix[m]["current"].get(project) == r["comparison"]
    suite_path = RESULTS / SUITE_RESULTS
    suite_data = read(suite_path)
    recovery = read(RESULTS / "backbone-suite-replays-20261124.json")
    assert recovery["suite_results_sha256"] == sha(suite_path)
    for decision in recovery["rows"]:
        (row,) = (
            r
            for r in suite_data["models"][decision["model"]]["rows"]
            if (r["task"], r["arm"]) == (decision["task"], decision["arm"])
        )
        assert all(row[k] == decision[k] for k in ("passed", "files_sha256", "report_sha256"))
        votes = decision["case_statuses"]
        assert set(votes) == set(decision["official_titles"]) and len(votes) == 4
        if decision["passed"]:
            assert all(set(states) == {"passed"} for states in votes.values())
        else:
            assert any(set(states) == {"failed"} for states in votes.values())
    schedule = read(allocations.RESULT)
    reports = {name: read(RESULTS / f"backbone-{name}-20261124.json") for name in allocations.ORDER}
    allocations.validate(schedule["stages"], reports)
    return projects, daily


def audit_local_receipts():
    """Match every provider authorization to exactly one ledger line and a model ID."""
    from .run import END
    from studies.public_library_transfer import browser

    calibration = read(RESULTS / "public-library-transfer-calibration-20261123.json")
    web_projects = tuple(WEB_PROJECTS)
    controls = browser.calibration_evidence(ROOT / calibration["artifacts"], web_projects)
    for row in controls:
        assert row in calibration["projects"] and row["tested_tasks"] == list(range(1, 21))
        assert not row["reference_failed"] and row["blank_passed"] == (
            [1] if row["project"] == "svg-chart" else []
        )

    assert allocations.reconstruct() == read(allocations.RESULT)
    folders = [filename.removesuffix(".json") for filename in FILES]
    stamps = Counter()
    for folder, filename in zip(folders, FILES, strict=True):
        root = ROOT / "artifacts" / folder
        registered = read(root / "registered.json")
        opened = datetime.fromisoformat(registered["utc"]).timestamp()
        public = read(RESULTS / filename)
        for tag, (model, *_) in registered["models"].items():
            base = root / tag
            rows = {r["id"]: r for r in calls(base / "budget.sqlite3")}
            seen = set()
            for file in base.rglob("request.json"):
                req = read(file)
                ticket = req["call_id"]
                assert ticket in rows and ticket not in seen
                seen.add(ticket)
                entry = rows[ticket]
                assert req["body"]["model"] == entry["model"] == model
                assert opened <= entry["created"] < END.timestamp()
                if entry["actual"] is not None:
                    paid = read(file.parent / "response.json")
                    assert micros(paid["usage"]["cost"]) == entry["actual"]
                    assert read(file.parent / "settled.json")["response_sha256"] == sha(
                        file.parent / "response.json"
                    )
                    assert paid["model"] == model, (folder, tag, paid["model"], model)
                    stamps[(model, paid["model"])] += 1
                else:
                    assert entry["status"] in ("uncertain", "reserved")
            assert seen == rows.keys(), (folder, tag, len(seen), len(rows))
            published = public["models"][model]
            assert published["seal_sha256"] == sha(base / "seal.json")
            assert published["rows"] == read(base / "scores.json")["rows"]
            for row in published["rows"]:
                if row["status"] != "valid":
                    continue
                task = row["task"]
                if "project" in row:
                    project = row["project"]
                    contract = read(root / "inputs" / project / "browser.json")
                    output = root / "browser/scores" / project / f"task-{task}" / row["files_digest"]
                    verdict = browser.verify_receipt(
                        root,
                        output / "score.json",
                        dict(
                            project=project,
                            task=task,
                            contract_digest=digest(contract),
                            files_digest=row["files_digest"],
                        ),
                    )
                else:
                    output = base / "scores" / task / row["arm"]
                    raw = output / ("playwright.json" if row["group"] == "todomvc" else "jest.json")
                    assert sha(raw) == row["report_sha256"]
                    verdict = read(output / "verdict.json")
                assert verdict["passed"] is row["passed"] and verdict["report_sha256"] == row["report_sha256"]
    print("Settled requests and model identities:", dict(stamps))


def overview(projects, money):
    """Summarize counts at their registered unit, retaining each builder and generator."""
    fresh = {}
    for filename in FILES:
        source = read(RESULTS / filename)
        for model, group in source["models"].items():
            stage = fresh.setdefault(model, {})
            scope = {SUITE_RESULTS: "suites", FORM_RESULTS: "question_form"}.get(filename, "table_and_charts")
            build_cost = sum(
                v["settled_microusd"]
                for k, v in group["cost_by_project_method"].items()
                if k.startswith("build/")
            )
            stage[scope] = {
                "source_file": filename,
                "source_registration": source.get("registration_sha256") or source["registered_sha256"],
                "settled_build_microusd": build_cost,
                "ledger": group["ledger"],
                "build_outcomes": {k: v["status"] for k, v in group["builds"].items()},
                "route_closed": group.get("model_stop"),
            }
    by_project = {}
    for model, records in projects.items():
        fresh[model]["projects"] = records
        for project, group in records.items():
            comparison = group["comparison"]
            if comparison is None:
                continue
            methods = by_project.setdefault(project, {})
            passed = comparison["passed"]
            for method in sorted(passed.keys() - {"direct"}):
                counts = methods.setdefault(method, {"higher": 0, "tied": 0, "lower": 0})
                delta = passed[method] - passed["direct"]
                counts["higher" if delta > 0 else "lower" if delta < 0 else "tied"] += 1
    return {
        "date": "2026-11-24",
        "unit": "one current task file per position",
        "daily_cap_usd": 20,
        "calls": int(money["calls"]),
        "unsettled_calls": int(money["unsettled_calls"]),
        "settled_usd": float(money["settled_usd"]),
        "exposure_usd": float(money["exposure_usd"]),
        "sources_sha256": {
            n: sha(RESULTS / n)
            for n in FILES + ["backbone-suite-replays-20261124.json", allocations.RESULT.name]
        },
        "model_count_comparisons_to_direct_by_project": by_project,
        "models": fresh,
    }


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--sources-only", action="store_true")
    parser.add_argument(
        "--receipts", action="store_true", help="also audit the private request and billing records"
    )
    parser.add_argument(
        "--write-overview", action="store_true", help="publish per-model fixed controls and costs"
    )
    args = parser.parse_args()
    rows, money = audit(not args.sources_only)
    summary = overview(rows, money)
    if args.write_overview:
        dump(OVERVIEW, summary)
    else:
        assert read(OVERVIEW) == summary, "Stale multi-model overview"
    for model, projects in rows.items():
        print(
            model,
            {
                p: (s["comparison"]["passed"], s["comparison"]["n"]) if s["comparison"] else None
                for p, s in projects.items()
            },
        )
    print({k: str(x) for k, x in money.items()})
    if args.receipts:
        audit_local_receipts()
