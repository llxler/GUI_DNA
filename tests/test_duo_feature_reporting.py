"""Recompute the two Duo cohorts independently of paper table formatting."""

from hashlib import sha256

from studies.lookup import find_cell
from studies.public_library_transfer.duo_verified_features import report
from studies.study_io import ROOT, read, sha


def test_duo_uses_official_shared_targets_and_the_models_actual_choices():
    matrix = read(ROOT / "studies/results/paper-performance-matrix.json")
    author = read(report.PAID)
    fields = read(report.FINAL)
    sdk = read(report.HUMAN)
    assert fields["choices"] == author["choices"]
    assert sdk["choices_source"] == author["candidate_seal"]
    models = [m for m, data in matrix.items() if "duo_feature_bindings" in data]
    assert len(models) == 6
    for model in models:
        before = matrix[model]["library_capabilities"]["duo"]
        targets = before["targets"]
        for arm in ("direct", "human", "gpt5-library", "self"):
            cell = find_cell(matrix, "webapp1k-duo", model, arm)
            assert cell["status"] == "measured" and cell["targets"] == targets
            assert cell["denominator"] == len(targets)
            records = read(ROOT / cell["method_record"])["models"][model]
            if isinstance(records, dict):
                records = records["rows"]
            relevant = [r for r in records if r["task"] in targets and r["arm"] == arm]
            assert sorted(r["task"] for r in relevant) == sorted(targets)
            assert all(type(r["passed"]) is bool for r in relevant)
            assert cell["score"] == sum(r["passed"] for r in relevant)
            if arm == "direct":
                assert cell["score"] == before["passed"]["direct"]
                continue
            assert all(
                r["passed"] == (r["official_cases_passed"] == 4) for r in relevant
            )
            control = [
                r
                for r in records
                if r["task"] in targets and r["arm"] == arm + "-fixed"
            ]
            assert sorted(r["task"] for r in control) == sorted(targets)
            assert (
                sum(r["passed"] for r in control)
                == cell["fixed_configuration_score"]
                == 0
            )


def test_new_combinations_and_all_shared_control_rows_survive_router_regrading():
    first = read(report.INDEPENDENT)
    repair = read(report.ROUTER)
    assert repair["sources"][str(report.INDEPENDENT.relative_to(ROOT))] == sha(
        report.INDEPENDENT
    )
    assert set(repair["calibration"]["cases"].values()) == {"passed"}
    targets = set()
    for domain, sample in first["groups"].items():
        assert len(sample["targets"]) == 5 and not targets.intersection(
            sample["targets"]
        )
        targets.update(sample["targets"])
        members = {x for pair in sample["targets"] for x in pair.split("_")}
        assert members == set(sample["features"]) and members.isdisjoint(
            sample["excluded"]
        )
        source_dir = (ROOT / first["test_files"][sample["targets"][0]]["path"]).parent
        if source_dir.is_dir():
            names = {
                f.name.removesuffix(".test.js") for f in source_dir.glob("*.test.js")
            }
            eligible = [
                n for n in names if set(n.split("_")).isdisjoint(sample["excluded"])
            ]
            assert len(eligible) == sample["eligible"]
            prefix = f"gui-dna-duo-novel-20261128-v1/{domain}/"
            selection = sorted(
                eligible, key=lambda n: sha256((prefix + n).encode()).digest()
            )[:5]
            assert selection == sample["targets"]
    final = read(report.ENTRIES)
    assert {p: sha(ROOT / p) for p in final["sources"]} == final["sources"]
    assert len([t for t, name in final["entries"].items() if t != name]) == 3
    for phase, source in (("initial", first), ("router", repair)):
        for arm in (
            "direct",
            "self",
            "gpt5-library",
            "self-fixed",
            "gpt5-library-fixed",
        ):
            original = report.observations(source["models"][report.FLASH], arm, targets)
            current = report.observations(final["phases"][phase], arm, targets)
            for task, row in current.items():
                assert row["previous_report"] == original[task]["report_sha256"]
                assert row["source_file"] == original[task]["file"]
                assert len(row["official_cases"]) == 4
                assert row["passed"] == (row["official_cases"] == ["passed"] * 4)
                if task == final["entries"][task]:
                    assert row["report_sha256"] == original[task]["report_sha256"]
                else:
                    assert original[task]["official_cases"] == []
                    assert row["report_sha256"] != original[task]["report_sha256"]


def test_duo_provenance_and_budget_match_the_archived_receipts():
    costs = read(report.ACCOUNT)
    assert all(sha(ROOT / k) == v for k, v in costs["records"].items())
    assert costs["new"]["calls"] == sum(
        s["cost"]["calls"] for s in costs["stages"].values()
    )
    assert costs["new"]["unsettled_calls"] == 1
    assert costs["new"]["settled_usd"] <= costs["new"]["exposure_usd"] <= 10
    for stage in costs["stages"].values():
        assert all(sha(ROOT / k) == v for k, v in stage["sources"].items())
    audit = read(report.AUDIT)
    assert audit["human_status"] == "unavailable" and len(audit["releases"]) == 4
    assert len(audit["harness"]["cases"]) == 2
    assert (
        set(audit["harness"]["cases"].values())
        == set(audit["alternate_resource"]["cases"].values())
        == {"passed"}
    )
    sdk = read(report.HUMAN)
    assert len(sdk["calibration"]["cases"]) == 2
    assert {k: v["version"] for k, v in sdk["sdk"]["packages"].items()} == {
        "final-form": "5.0.0",
        "react-final-form": "7.0.0",
    }
