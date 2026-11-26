"""Join the matched November 26 observations without changing older protocol snapshots."""

from copy import deepcopy

from studies import paper_component_followup as prior
from studies.study_io import ROOT, read

SUITE = ROOT / "studies/public_library_transfer"
TABLE = ROOT / "studies/webbench/table"
EXPLORER = ROOT / "studies/webbench/file_explorer"
ROUTE = prior.SUITE / "route_completion/result.json"
TODO = prior.SUITE / "numbered_plans/result.json"
SLOT_CHOICES = prior.SUITE / "slot_choices/result.json"
SLOT_COMPLETION = SLOT_CHOICES.with_name("completion-result.json")
SLOT_FINAL = SLOT_CHOICES.with_name("last-result.json")
DONORS = SUITE / "duo_donor_library/result.json"
CALLBACKS = SUITE / "duo_react_callbacks/result.json"
PROP_CONTRACT = CALLBACKS.parent / "prop_contract/result.json"
ACTIONS = TABLE / "action_library/result.json"
FEEDBACK = ACTIONS.parent / "event_feedback/result.json"
CONTRACTS = TABLE / "action_contracts/result.json"
BINDING = TABLE / "selection_binding/result.json"
TYPED_BINDING = BINDING.parent / "typed-result.json"
FILES = EXPLORER / "library_sources/result.json"
EXTENSIONS = EXPLORER / "dom_extensions/result.json"
DOCUMENTS = EXPLORER / "document_library/result.json"
FILE_CONTROLS = DOCUMENTS.parent / "controls.json"
SURVEY = ROOT / "studies/webbench/form/survey_workflow/result.json"
LINKS = SURVEY.parent / "module_links/result.json"
SURVEY_TRANSPORT = SURVEY.parent / "transport/result.json"
GEOMETRY = ROOT / "studies/webbench/typed_components/svg_public_geometry/result.json"
DECORATION = GEOMETRY.parent / "decoration/result.json"
SVG_HELPERS = DECORATION.with_name("helpers-result.json")
BACKBONE_ROUTES = ROOT / "studies/webbench/backbone_matrix/route_completion/result.json"
CALCULATOR = ROOT / "studies/webbench/calculator/key_groups/result.json"
CALCULATOR_MODULES = CALCULATOR.parents[1] / "starter_modules/result.json"
CALCULATOR_FOCUSED = CALCULATOR_MODULES.parent / "focused/result.json"
SUMMARY = ROOT / "studies/results/library-capabilities-20261126.json"
SOURCES = (
    ROUTE,
    TODO,
    DONORS,
    CALLBACKS,
    ACTIONS,
    FEEDBACK,
    CONTRACTS,
    BINDING,
    TYPED_BINDING,
    FILES,
    EXTENSIONS,
    DOCUMENTS,
    FILE_CONTROLS,
    prior.SUITE / "contract_repair/result.json",
    prior.SUITE / "syntax_reception/result.json",
    TABLE / "selection_binding/replication/result.json",
    TABLE / "menu_propagation/result.json",
    SURVEY,
    LINKS,
    SURVEY_TRANSPORT,
    GEOMETRY,
    DECORATION,
    SVG_HELPERS,
    BACKBONE_ROUTES,
    PROP_CONTRACT,
    CALCULATOR,
    CALCULATOR_MODULES,
    CALCULATOR_FOCUSED,
    SLOT_CHOICES,
    SLOT_COMPLETION,
    SLOT_FINAL,
)
TAGS = {"gemma": prior.GEMMA, "qwen9": prior.QWEN9, "deepseek-flash": prior.FLASH}


def set_method(group, arm, rows, name, source, marker):
    observed = prior.outcomes(rows, name)
    targets = group["targets"]
    if not all(type(observed.get(t)) is bool for t in targets):
        return False
    group["passed"][arm] = sum(observed[t] for t in targets)
    group.setdefault("markers", {})[arm] = marker
    group["excluded_build_arms"] = [
        k for k in group.get("excluded_build_arms", []) if k != arm
    ]
    group.setdefault("implementation_sources", {})[arm] = str(source.relative_to(ROOT))
    return True


def survey_rows(model, original):
    if model != "mistralai/mistral-small-3.2-24b-instruct":
        return original
    (delivery,) = read(SURVEY_TRANSPORT)["rows"]
    matches = [
        r
        for r in original
        if (r["task"], r["arm"]) == (delivery["task"], delivery["arm"])
    ]
    assert len(matches) == 1 and matches[0]["status"] == "missing"
    return [delivery if row is matches[0] else row for row in original]


def attach(matrix):
    from studies.paper_performance import current_group, joint_scores

    def existing(model, project):
        entry = matrix[model]
        if project == "table" and "table_protocol_followup" in entry:
            return entry["table_protocol_followup"]
        return (
            entry.get("extended_targets", {}).get(project)
            or entry.get("component_followup", {}).get(project)
            or current_group(entry, project)
        )

    def publish(model, project, group):
        matrix[model].setdefault("library_capabilities", {})[project] = group

    # Chronological first libraries with complete target measurements, including ties or declines.
    for source in (ACTIONS, FEEDBACK, CONTRACTS, BINDING, TYPED_BINDING):
        for study in read(source)["cases"]:
            if (
                study["rep"] != "a"
                or study["status"] != "valid"
                or study["tag"] not in TAGS
            ):
                continue
            tag = study["tag"]
            model = TAGS[tag]
            group = deepcopy(existing(model, "table"))
            rows = study["deployments"][tag]
            if set_method(group, "self", rows, "planned", source, "events"):
                group.setdefault("build_attempts", {})["self"] = "valid"
                publish(model, "table", group)
    geometry = read(SVG_HELPERS)
    survey = read(SURVEY)
    linked = read(LINKS)
    survey_tags = {
        prior.GEMMA: "gemma",
        "mistralai/mistral-small-3.2-24b-instruct": "mistral",
        "openai/gpt-oss-120b": "oss",
    }
    chart_tags = {
        prior.QWEN9: "qwen9",
        **{m: t for m, t in survey_tags.items() if t != "gemma"},
    }
    for model, tag in chart_tags.items():
        assert geometry["libraries"][tag]["status"] == "valid"
        group = deepcopy(existing(model, "svg-chart"))
        rows = [r for r in geometry["rows"] if r["tag"] == tag]
        if set_method(group, "self", rows, "planned", SVG_HELPERS, "events"):
            publish(model, "svg-chart", group)
    for model, rows in survey["models"].items():
        rows = survey_rows(model, rows)
        tag = survey_tags[model]
        previous = existing(model, "form")
        arms = {k: prior.outcomes(rows, k) for k in ("direct", "human", "gpt5-library")}
        final = [r for r in linked["rows"] if r["tag"] == tag and r["rep"] == "a"]
        arms["self"] = prior.outcomes(final, "self")
        if all(
            all(type(v.get(n)) is bool for n in previous["targets"])
            for v in arms.values()
        ):
            group = joint_scores(arms)
            assert set(previous["targets"]) <= set(group["targets"])
            group["markers"] = dict.fromkeys(arms, "survey")
            group["implementation_sources"] = {
                k: str((LINKS if k == "self" else SURVEY).relative_to(ROOT))
                for k in arms
            }
            if tag == "mistral":
                group["direct_transport_receipt"] = str(
                    SURVEY_TRANSPORT.relative_to(ROOT)
                )
            publish(model, "form", group)
    for model, data in read(TODO)["models"].items():
        assert data["libraries"]["a"] == "valid"
        if model == read(ROUTE)["model"]:
            arms = {
                k: prior.outcomes(data["rows"], k)
                for k in ("direct", "human", "gpt5-library")
            }
            arms["self"] = prior.outcomes(data["rows"], "a")
            group = joint_scores(arms)
            assert group["n"] == 8
            group["implementation_sources"] = {
                k: str(TODO.relative_to(ROOT)) for k in arms
            }
            group["markers"] = {"self": "events"}
            revised = read(SLOT_FINAL)["models"][model]["rows"]
            choices = {
                k: prior.outcomes(revised, "a" if k == "self" else k) for k in arms
            }
            if all(
                all(type(v.get(t)) is bool for t in group["targets"])
                for v in choices.values()
            ):
                group = joint_scores(choices)
                group["implementation_sources"] = {
                    k: str((TODO if k == "direct" else SLOT_FINAL).relative_to(ROOT))
                    for k in arms
                }
                group["markers"] = {k: "menu" for k in arms if k != "direct"}
        else:
            group = deepcopy(existing(model, "todomvc"))
            assert set_method(group, "self", data["rows"], "a", TODO, "events")
        group.setdefault("build_attempts", {})["self"] = "valid"
        publish(model, "todomvc", group)
    donors = read(DONORS)
    assert all(v["status"] == "valid" for v in donors["libraries"].values())
    for model, rows in donors["models"].items():
        group = deepcopy(existing(model, "duo"))
        tag = next((t for t, m in TAGS.items() if m == model), None)
        callback_source = PROP_CONTRACT if tag == "qwen9" else CALLBACKS
        callback = read(callback_source)
        builds = callback["libraries"].get(tag, {}).get("a", {})
        if builds and all(lib["status"] == "valid" for lib in builds.values()):
            new = callback["models"][model]
            arms = {
                "direct": prior.outcomes(new, "direct"),
                "self": prior.outcomes(new, "a"),
                "gpt5-library": prior.outcomes(rows, "planned"),
            }
            # Only replace with the prespecified entire two-domain comparison.
            if all(
                len(v) == 10 and all(type(x) is bool for x in v.values())
                for v in arms.values()
            ):
                group = joint_scores(arms)
                group["markers"] = {"self": "events", "direct": "events"}
                group["implementation_sources"] = {
                    k: str(callback_source.relative_to(ROOT))
                    for k in ("direct", "self")
                }
        assert set_method(group, "gpt5-library", rows, "planned", DONORS, "donor")
        publish(model, "duo", group)
    base = read(FILES)
    docs = read(DOCUMENTS)
    controls = read(FILE_CONTROLS)["rows"]
    for tag in ("qwen9", "deepseek-flash"):
        model = TAGS[tag]
        rows = [r for r in controls if r["tag"] == tag]
        arms = {k: prior.outcomes(rows, k) for k in ("direct", "human", "gpt5-library")}
        own = docs["libraries"][tag]["a"]
        if own["status"] == "valid":
            attempts = [r for r in docs["rows"] if r["tag"] == tag and r["rep"] == "a"]
            arms["self"] = prior.outcomes(attempts, "planned")
        else:
            previous = base["public"][tag]["a"]
            if previous["status"] == "valid":
                arms["self"] = prior.outcomes(base["models"][model], "self-a")
        group = joint_scores(arms, allow_direct_only=True)
        assert group and group["targets"] == list(range(1, 21))
        group["excluded_build_arms"] = []
        if base["frozen_public"]["gpt5-library"]["admitted"] is False:
            group["excluded_build_arms"].append("gpt5-library")
        if "self" not in group["passed"] and own["status"] == "build_failed":
            group["excluded_build_arms"].append("self")
        group["build_attempts"] = {"self": own["status"]}
        group["implementation_sources"] = {
            k: str(FILE_CONTROLS.relative_to(ROOT))
            for k in ("direct", "human", "gpt5-library")
        }
        if "self" in group["passed"]:
            group["implementation_sources"]["self"] = str(DOCUMENTS.relative_to(ROOT))
        publish(model, "dom1", group)
    calculator = read(CALCULATOR)
    additions = read(CALCULATOR_FOCUSED)
    for tag in ("qwen9", "deepseek-flash"):
        model = TAGS[tag]
        rows = calculator["models"][model]
        build = calculator["libraries"][tag]["a"]["status"]
        names = {"direct": "direct", "human": "human"}
        if calculator["public"]["fixed-gpt5-library"]["arithmetic"]:
            names["gpt5-library"] = "gpt5-library"
        if build == "valid":
            names["self"] = "self-a"
        outcomes = {
            method: prior.outcomes(rows, name) for method, name in names.items()
        }
        if tag == "qwen9" and additions["libraries"]["a"]["status"] == "valid":
            build = "valid"
            names["self"] = "planned"
            outcomes["self"] = prior.outcomes(
                [r for r in additions["rows"] if r["rep"] == "a"], "planned"
            )
        group = joint_scores(outcomes)
        assert group and group["targets"] == list(range(1, 21))
        group["excluded_build_arms"] = [
            k
            for k in ("self", "gpt5-library")
            if k not in names and (k != "self" or build == "build_failed")
        ]
        group["build_attempts"] = {"self": build}
        group["implementation_sources"] = dict.fromkeys(
            names, str(CALCULATOR.relative_to(ROOT))
        )
        if tag == "qwen9" and names.get("self") == "planned":
            group["implementation_sources"]["self"] = str(
                CALCULATOR_FOCUSED.relative_to(ROOT)
            )
        publish(model, "calculator", group)
    return matrix
