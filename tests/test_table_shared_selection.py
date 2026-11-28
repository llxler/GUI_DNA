from studies import lookup
from studies.study_io import ROOT, read, sha
from studies.webbench.table.shared_selection import report


def test_table_self_uses_the_final_registered_workflow_and_inherits_paired_baselines():
    matrix = read(ROOT / lookup.MATRIX)
    earlier = {
        m: {k: v for k, v in entry.items() if k != report.FIELD}
        for m, entry in matrix.items()
    }
    summary = report.summarize(read(report.TRANSITIONS))
    verify = read(report.VERIFICATION)
    assert set(summary) == set(lookup.paper.table_models(matrix, "table"))
    assert verify["receipts"] == {
        name: sha(path) for name, path in report.STAGES.items()
    }
    assert verify["total"]["exposure_usd"] <= 10
    for model, recorded in summary.items():
        for method in ("direct", "human", "gpt5-library"):
            assert lookup.find_cell(
                matrix, "web-bench/table", model, method
            ) == lookup.find_cell(earlier, "web-bench/table", model, method)
        cell = lookup.find_cell(matrix, "web-bench/table", model, "self")
        stage = "transitions"
        assert ROOT / cell["method_record"] == report.STAGES[stage]
        passes = recorded["passed"]
        if passes["self"] is None:
            assert "score" not in cell
        else:
            assert cell["score"] == len(passes["self"]) and cell["denominator"] == 20
            assert cell["previous_same_configuration_score"] == len(
                passes["old-same-choice"]
            )
            assert cell["targets"] == list(range(1, 21))
            assert cell["fixed_configuration_score"] == len(passes["fixed-self"])
        assert passes == verify["stages"][stage][model]["passed"]
