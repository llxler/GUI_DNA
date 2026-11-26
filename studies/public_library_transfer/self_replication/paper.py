"""Join the paired follow-ups by task and replicate for the last panel of Table 1."""

from studies.study_io import ROOT, dump, read, sha

RESULTS = ROOT / "studies/results"
STRONG = ROOT / "studies/public_library_transfer/strong_builder"
LINKED = RESULTS / "self-coherent-linker-20261124.json"
NATIVE = RESULTS / "self-native-20261124.json"
SUPPLIED = RESULTS / "self-supplied-native-20261124.json"
TODOMVC = RESULTS / "self-todomvc-executable-options-20261124.json"
CODER = RESULTS / "self-dependency-resume-20261124.json"
PUBLISHED = RESULTS / "paper-library-followups-20261124.json"
SOURCES = (
    LINKED,
    NATIVE,
    SUPPLIED,
    TODOMVC,
    CODER,
    STRONG / "result.json",
    STRONG / "native/result.json",
)


def appendix_sources():
    return (
        PUBLISHED,
        STRONG / "capacity.json",
        STRONG / "plans.json",
        STRONG / "delivery.json",
        *(
            RESULTS / (name + "-20261124.json")
            for name in (
                "self-failure-diagnosis",
                "self-capacity",
                "self-coherent",
                "self-refinement",
                "self-line-contract",
                "self-line-contract-form",
                "self-normalized-table",
                "self-controller-todomvc",
                "self-controller-todomvc-repair",
                "self-controller-todomvc-host-binding",
                "self-executable-options",
                "self-fixed-delivery",
                "self-construction-accounting",
                "self-dependency-table",
            )
        ),
    )


def matched_row(
    project, builder, decoding, arms, targets=range(1, 21), *, generator="Qwen3.5-9B"
):
    targets = list(targets)
    assert all(set(values) == set(targets) for values in arms.values())
    joint = [i for i in targets if all(arms[k][i] is not None for k in arms)]
    return {
        "project": project,
        "target_generator": generator,
        "builder": builder,
        "decoding": decoding,
        "targets": joint,
        "passed": {k: sum(values[i] for i in joint) for k, values in arms.items()},
    }


def rows(*, admitted_only=False):
    linked = read(LINKED)["projects"]
    native = read(NATIVE)["projects"]
    first = read(STRONG / "result.json")
    constrained = read(STRONG / "native/result.json")
    assert first["deployer"] == constrained["deployer"] == "qwen/qwen3.5-9b"
    result = []
    for project, label in (("table", "Table editor"), ("form", "Question form")):
        trial = linked[project]["replicas"]
        baseline = native[project]["replicas"]["build-a"]["rows"]
        arms = {"direct": {r["task"]: r["direct"]["passed"] for r in baseline}}
        excluded = []
        for g, suffix in (("build-a", "a"), ("build-b", "b")):
            if admitted_only and trial[g]["status"] != "valid":
                excluded.extend((f"self_{suffix}", f"fixed_{suffix}"))
                continue
            rows = trial[g]["rows"]
            assert {r["task"]: r["direct"]["passed"] for r in rows} == arms["direct"]
            for arm in ("self", "fixed"):
                arms[arm + "_" + suffix] = {r["task"]: r[arm]["passed"] for r in rows}
        if len(arms) > 1:
            row = matched_row(label, "Self", "Native", arms)
            if excluded:
                row["excluded_build_arms"] = excluded
            result.append(row)
    coder = read(CODER)
    assert coder["model"] == "qwen/qwen3-coder-30b-a3b-instruct"
    coder_groups = coder["replicas"]
    direct = {r["task"]: r["direct"]["passed"] for r in coder_groups["build-a"]["rows"]}
    arms = {"direct": direct}
    for group, suffix in (("build-a", "a"), ("build-b", "b")):
        batch = coder_groups[group]["rows"]
        assert {r["task"]: r["direct"]["passed"] for r in batch} == direct
        for arm in ("self", "fixed"):
            arms[arm + "_" + suffix] = {r["task"]: r[arm]["passed"] for r in batch}
    result.append(
        matched_row("Table editor", "Self", "Native", arms, generator="Qwen3-Coder-30B")
    )
    targets = native["table"]["replicas"]["build-a"]["rows"]
    for decoding, comparator in (("Text", "old_direct"), ("Native", "direct")):
        arms = {"direct": {r["task"]: r[comparator]["passed"] for r in targets}}
        for g, suffix in (("replica-1", "a"), ("replica-2", "b")):
            a = [r for r in first["rows"] if r["replica"] == g]
            arms["fixed_" + suffix] = {
                r["task"]: r["passed"] for r in a if r["arm"] == "fixed"
            }
            selected = (
                [r for r in a if r["arm"] == "selected"]
                if decoding == "Text"
                else [r for r in constrained["rows"] if r["replica"] == g]
            )
            assert (
                constrained["sources"][g]["package_sha256"]
                == first["sources"][g]["package_sha256"]
            )
            arms["self_" + suffix] = {r["task"]: r["passed"] for r in selected}
        result.append(matched_row("Table editor", "GPT-6 Astra", decoding, arms))
    controller = read(TODOMVC)
    assert controller["model"] == first["deployer"]
    arms = {
        "direct": {
            r["task"]: r["passed"] for r in controller["rows"] if r["group"] == "direct"
        }
    }
    excluded = []
    for group, suffix in (("build-a", "a"), ("build-b", "b")):
        for arm in ("self", "fixed"):
            name = arm + "_" + suffix
            stage = "base_status" if arm == "fixed" else "selection_status"
            if admitted_only and controller["replicas"][group][stage] != "valid":
                excluded.append(name)
                continue
            arms[name] = {
                r["task"]: r["passed"]
                for r in controller["rows"]
                if r["group"] == group and r["arm"] == arm
            }
    if len(arms) > 1:
        row = matched_row(
            "TodoMVC",
            "Self",
            "Native",
            arms,
            targets=[f"todo-{n:02d}" for n in range(1, 9)],
        )
        if excluded:
            row["excluded_build_arms"] = excluded
        result.append(row)
    project_order = {"Table editor": 0, "Question form": 1, "TodoMVC": 2}
    return sorted(result, key=lambda row: project_order[row["project"]])


def evidence():
    supplied = read(SUPPLIED)["projects"]
    native = read(NATIVE)["projects"]
    linked = read(LINKED)["projects"]
    gpt6 = read(STRONG / "native/result.json")["rows"]
    matched = {}
    for project in ("table", "form"):
        arms = {
            a: {
                r["task"]: r["passed"]
                for r in supplied[project]["rows"]
                if r["arm"] == a
            }
            for a in ("human", "gpt5-library")
        }
        arms["direct"] = {
            r["task"]: r["direct"]["passed"]
            for r in native[project]["replicas"]["build-a"]["rows"]
        }
        for group, model in linked[project]["replicas"].items():
            arms["self_" + group] = {
                r["task"]: r["self"]["passed"] for r in model["rows"]
            }
        if project == "table":
            for g in ("replica-1", "replica-2"):
                arms["gpt6_" + g] = {
                    r["task"]: r["passed"] for r in gpt6 if r["replica"] == g
                }
        assert all(set(v) == set(range(1, 21)) for v in arms.values())
        common = [
            i for i in range(1, 21) if all(v[i] is not None for v in arms.values())
        ]
        matched[project] = {
            "target_ids": common,
            "passed": {k: sum(v[i] for i in common) for k, v in arms.items()}
            if common
            else None,
        }
    return {
        "panel": "D",
        "target_generators": ["qwen/qwen3.5-9b", "qwen/qwen3-coder-30b-a3b-instruct"],
        "panel_rows": rows(),
        "separate_source_matched_comparison": matched,
        "sources_sha256": {str(p.relative_to(ROOT)): sha(p) for p in SOURCES},
    }


def verify_or_publish(write):
    current = evidence()
    if write:
        dump(PUBLISHED, current)
    else:
        assert current == read(PUBLISHED)


if __name__ == "__main__":
    verify_or_publish(False)
