"""Recompute Self cells from the registered current-task observations, without a browser."""

from pathlib import Path

from studies.paper_component_followup import outcomes
from studies.study_io import ROOT, read, sha

HERE = Path(__file__).resolve().parent
FIRST = HERE / "result.json"
ROUTED = HERE / "event_routing/result.json"
COMMANDS = HERE / "command_delivery/result.json"
RECOVERED = HERE / "core_recovery/result.json"
TRANSITIONS = HERE / "keyboard_transitions/result.json"
STAGES = {
    "first": FIRST,
    "routed": ROUTED,
    "commands": COMMANDS,
    "core": RECOVERED,
    "transitions": TRANSITIONS,
}
VERIFICATION = HERE / "verification.json"
FIELD = "table_shared_selection"


def summarize(study):
    targets = study["targets"]
    assert targets == list(range(1, 21))
    models = {}
    for tag, model in study["generators"].items():
        lib = study["libraries"][tag]
        rows = study["models"][model]
        arm_scores = {}
        for arm in sorted({row["arm"] for row in rows}):
            scores = outcomes(rows, arm)
            assert sorted(scores) == targets
            arm_scores[arm] = (
                None if None in scores.values() else [n for n in targets if scores[n]]
            )
        assert arm_scores["binding-only"] == []
        if lib["status"] == "valid":
            assert arm_scores["fixed-self"] is not None
        else:
            assert arm_scores["self"] is None and arm_scores["fixed-self"] is None
        models[model] = dict(status=lib["status"], passed=arm_scores)
    return models


def attach(matrix):
    studies = {name: read(path) for name, path in STAGES.items()}
    verification = read(VERIFICATION)
    assert verification["receipts"] == {k: sha(p) for k, p in STAGES.items()}
    assert all(
        sha(ROOT / p) == h
        for study in studies.values()
        for p, h in study["sources"].items()
        if p.startswith("studies/")
    )
    initial = summarize(studies["first"])
    commands = summarize(studies["commands"])
    recovery = summarize(studies["core"])
    assert set(recovery) == {
        model for model, obs in commands.items() if obs["status"] == "build_failed"
    }
    targets = studies["commands"]["targets"]
    final_stage = "transitions"
    final = summarize(studies[final_stage])
    assert set(final) == set(commands | recovery) and all(
        x["status"] == "valid" for x in (commands | recovery).values()
    )
    for model, result in final.items():
        source = str(STAGES[final_stage].relative_to(ROOT))
        previous = matrix[model]["module_rebuilds"]["table"]
        assert previous["targets"] == targets and previous["n"] == len(targets)
        prior_scores = previous["passed"]
        row = dict(
            n=len(targets),
            targets=targets,
            passed={k: v for k, v in prior_scores.items() if k != "self"},
            inherited_methods=["direct", "human", "gpt5-library"],
            excluded_build_arms=[
                k for k in previous["excluded_build_arms"] if k != "self"
            ],
            source=source,
            implementation_sources={"self": source},
            record_filters={"self": {"arm": "self"}},
            protocols={
                "self": "The target model writes the table modules against one shared selection interface. Public checks gate same-author menu and keyboard repairs. The model specifies keyboard state transitions and the host applies the returned changes. The model selects a module profile per target."
            },
            verification_record=str(VERIFICATION.relative_to(ROOT)),
            first_stage_record=str(FIRST.relative_to(ROOT)),
        )
        for arm, passed in result["passed"].items():
            assert passed == verification["stages"][final_stage][model]["passed"][arm]
        if result["status"] == "build_failed":
            row["excluded_build_arms"].append("self")
        elif result["passed"]["self"] is not None:
            row["passed"]["self"] = len(result["passed"]["self"])
        else:
            row["unavailable_reasons"] = {
                "self": "Missing registered build or target response."
            }
        if result["passed"]["fixed-self"] is not None:
            row["fixed_score"] = len(result["passed"]["fixed-self"])
        if result["passed"]["old-same-choice"] is not None:
            row["previous_same_configuration_score"] = len(
                result["passed"]["old-same-choice"]
            )
        if initial[model]["passed"]["self"] is not None:
            row["first_stage_score"] = len(initial[model]["passed"]["self"])
        matrix[model][FIELD] = row


if __name__ == "__main__":
    for path in STAGES.values():
        print(path.relative_to(ROOT))
        for model, result in summarize(read(path)).items():
            print(
                model,
                result["status"],
                {
                    k: len(v) if v is not None else None
                    for k, v in result["passed"].items()
                },
            )
