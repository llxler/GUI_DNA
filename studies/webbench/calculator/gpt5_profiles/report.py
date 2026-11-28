"""Publish the four Calculator GPT-5 cells from the sealed profile experiment."""

from pathlib import Path

from studies.study_io import ROOT, read, sha

HERE = Path(__file__).resolve().parent
RESULT = HERE / "mount_recovery/result.json"
VERIFICATION = HERE / "verification.json"
ARM = "gpt5-library"
FIXED = "fixed-gpt5-library"


def observations(rows, arm, targets):
    selected = [r for r in rows if r["arm"] == arm]
    if sorted(r["task"] for r in selected) != sorted(targets):
        raise ValueError(f"Incomplete or duplicate Calculator targets for {arm}")
    for r in selected:
        if r["status"] == "valid":
            assert (
                type(r["passed"]) is bool and r["report_sha256"] and r["files_digest"]
            )
        elif r["status"] == "invalid":
            assert r["passed"] is False
        else:
            assert r["status"] in ("build_failed", "missing") and r["passed"] is None
    return {r["task"]: r for r in selected}


def attach(matrix):
    study = read(RESULT)
    verification = read(VERIFICATION)
    assert verification["source"] == sha(RESULT)
    assert all(
        sha(ROOT / f) == h
        for f, h in study["registered_sources"].items()
        if f.startswith("studies/")
    )
    assert set(study["targets"]) == set(range(1, 21))
    if study["library"]["status"] == "valid":
        assert {r["model"] for r in study["accepted_responses"].values()} == {
            "openai/gpt-5"
        }
    for model, rows in study["models"].items():
        old = matrix[model]["module_rebuilds"]["calculator"]
        assert old["targets"] == study["targets"] and old["n"] == len(study["targets"])
        primary = observations(rows, ARM, old["targets"])
        fixed = observations(rows, FIXED, old["targets"])
        cross = observations(rows, "self-choice", old["targets"])
        source = str(RESULT.relative_to(ROOT))
        row = dict(
            n=old["n"],
            targets=old["targets"],
            passed=dict(old["passed"]),
            excluded_build_arms=list(old["excluded_build_arms"]),
            inherited_methods=["direct", "human", "self"],
            source=source,
            implementation_sources={ARM: source},
            record_filters={ARM: dict(arm=ARM)},
            earlier_delivery_record=old["implementation_sources"][ARM],
            historical_gpt5_source=old["historical_gpt5_source"],
            protocols={
                ARM: "GPT-5 writes four optional Calculator modules on the public starter. The target model selects from ten observed pages per task."
            },
        )
        if study["library"]["status"] == "build_failed":
            row["excluded_build_arms"].append(ARM)
        elif all(r["passed"] is not None for r in primary.values()):
            assert study["library"]["status"] == "valid"
            row["passed"][ARM] = sum(r["passed"] for r in primary.values())
        else:
            row["unavailable_reasons"] = {
                ARM: "A registered build or deployment did not deliver."
            }
        if all(r["passed"] is not None for r in fixed.values()):
            assert all(r["profile"] == 0 for r in fixed.values())
            row["fixed_score"] = sum(r["passed"] for r in fixed.values())
        if all(r["passed"] is not None for r in cross.values()):
            row["self_choice_score"] = sum(r["passed"] for r in cross.values())
        if ARM in row["passed"]:
            expected = verification["models"][model]["passed"][ARM]
            assert expected == sorted(t for t, r in primary.items() if r["passed"])
        row["verification_record"] = str(VERIFICATION.relative_to(ROOT))
        matrix[model]["calculator_profiles"] = row
