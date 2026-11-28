"""Trace the new Calculator column to its own pages and preserve the other methods."""

from studies.lookup import MATRIX, find_cell
from studies.study_io import ROOT, read, sha
from studies.webbench.calculator.gpt5_profiles import report


def test_calculator_gpt5_rows_use_official_receipts_for_all_registered_targets():
    matrix = read(ROOT / MATRIX)
    study = read(report.RESULT)
    verification = read(report.VERIFICATION)
    assert verification["source"] == sha(report.RESULT)
    assert len(study["models"]) == 4
    assert set(study["accepted_responses"]) == {
        "scientific",
        "appearance",
        "memory",
        "history",
    }
    assert all(
        src["model"] == "openai/gpt-5" for src in study["accepted_responses"].values()
    )
    for model, rows in study["models"].items():
        info = find_cell(matrix, "web-bench/calculator", model, report.ARM)
        assert ROOT / info["method_record"] == report.RESULT
        assert info["denominator"] == len(info["targets"]) == 20
        assert info["targets"] == list(range(1, 21))
        evidence = verification["models"][model]
        for arm, key in (
            (report.ARM, "score"),
            (report.FIXED, "fixed_configuration_score"),
            ("self-choice", "same_self_configuration_score"),
        ):
            obs = report.observations(rows, arm, info["targets"])
            passing = [t for t, row in obs.items() if row["passed"]]
            assert passing == evidence["passed"][arm] and len(passing) == info[key]
        assert all(
            verification["models"][model]["choices"][str(r["task"])]["profile"]
            == r["profile"]
            for r in rows
            if r["arm"] == report.ARM
        )
        previous = dict(matrix)
        previous[model] = {
            k: v for k, v in matrix[model].items() if k != "calculator_profiles"
        }
        archived = find_cell(previous, "web-bench/calculator", model, report.ARM)
        assert (
            info["earlier_delivery_record"] == archived["method_record"]
            and archived["status"] == "unavailable"
        )
        for unchanged in ("human", "self", "direct"):
            assert find_cell(
                matrix, "web-bench/calculator", model, unchanged
            ) == find_cell(previous, "web-bench/calculator", model, unchanged)


def test_calculator_retains_failed_build_and_accounts_for_the_first_delivery():
    evidence = read(report.VERIFICATION)
    probes = evidence["public_mount_tests"]
    assert all(
        probes[k]["status"] == "completed"
        for k in ("scientific", "history", "appearance", "without_memory")
    )
    assert probes["memory"]["status"] == probes["full"]["status"] == "timeout"
    assert evidence["billing"]["first_delivery"]["calls"] == 4
    assert evidence["total"]["calls"] == sum(
        v["calls"] for v in evidence["billing"].values()
    )
    assert (
        0 < evidence["total"]["settled_usd"] <= evidence["total"]["exposure_usd"] <= 10
    )
