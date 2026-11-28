"""Assemble the additional full-project rows and the small-model TodoMVC configuration study."""

from studies import paper_component_followup as components
from studies import paper_library_capabilities as capabilities
from studies.study_io import ROOT, read, sha

WEB = ROOT / "studies/webbench"
TODO = ROOT / "studies/public_library_transfer/compact_todomvc"
CALC = WEB / "calculator/target_models/result.json"
STARTER = WEB / "calculator/starter_transfer/result.json"
FILES = WEB / "file_explorer/target_models/result.json"
DIRECT = WEB / "file_explorer/target_models/direct_reception/result.json"
IDENTITY = WEB / "file_explorer/interaction_contracts/entry_identity/result.json"
EXAMPLES = WEB / "calculator/example_selection/result.json"
FALLBACK = WEB / "calculator/compiler_fallback/result.json"
KEYPAD = WEB / "calculator/keypad_labels/result.json"
ROUTES = TODO / "route_preservation/result.json"
FACTORIAL = ROUTES.parent / "interaction/result.json"
VIEWS = TODO / "filtered_view/result.json"
SCOPES = TODO / "edit_scope/result.json"
CHOICES = TODO / "edit_choices/result.json"
KEYBOARD = WEB / "table/keyboard_contract/result.json"
NAVIGATION = WEB / "table/navigation_context/result.json"
COORDINATES = WEB / "table/coordinate_navigation/result.json"
RECEPTION = WEB / "table/coordinate_navigation/documented_reception/result.json"
ACCOUNTING = ROOT / "studies/results/target-extension-costs-20261128.json"
SOURCES = (
    CALC,
    STARTER,
    KEYPAD,
    EXAMPLES,
    FALLBACK,
    FILES,
    DIRECT,
    SCOPES,
    CHOICES,
    VIEWS,
    ROUTES,
    FACTORIAL,
    KEYBOARD,
    NAVIGATION,
    COORDINATES,
    RECEPTION,
    ACCOUNTING,
)
WEB_MODELS = {"gemma": components.GEMMA, "oss": "openai/gpt-oss-120b"}


def relative(path):
    return str(path.relative_to(ROOT))


def example_outcomes(rows):
    fixed = {(r["task"], r["arm"]): r for r in rows if r["arm"].startswith("fixed-")}
    for r in rows:
        if r["arm"] == "selected" and r["status"] == "valid":
            if r["choice"] not in (0, 1):
                raise ValueError("Selected calculator example has no registered index")
            control = fixed[r["task"], f"fixed-{r['choice']}"]
            if (control["passed"], control["report_sha256"]) != (
                r["passed"],
                r["report_sha256"],
            ):
                raise ValueError(
                    "Selected and fixed example must share the official verdict"
                )
    return components.outcomes(rows, "selected")


def compiler_outcomes(rows):
    by_target = {}
    for row in rows:
        arms = by_target.setdefault(row["task"], {})
        if row["arm"] in arms:
            raise ValueError("Duplicate calculator deployment")
        arms[row["arm"]] = row
    for arms in by_target.values():
        if set(arms) != {"native", "final", "fixed-0", "fixed-1"}:
            raise ValueError("Missing calculator deployment control")
        native, final = arms["native"], arms["final"]
        rejected = native["status"] == "invalid"
        if final["triggered"] is not rejected:
            raise ValueError("Only a compiler rejection permits example selection")
        choice = final["choice"]
        if rejected and final["status"] == "valid":
            if type(choice) is not int or choice not in (0, 1):
                raise ValueError("Recovered page requires a registered example")
            expected = arms[f"fixed-{choice}"]
        elif rejected:
            if choice is not None or final["status"] not in ("invalid", "missing"):
                raise ValueError("Unresolved compiler rejection has an invalid outcome")
            continue
        else:
            if choice is not None:
                raise ValueError(
                    "A native success or transport failure cannot select an example"
                )
            expected = native
        fields = ("status", "passed", "files_digest", "report_sha256")
        if any(expected[k] != final[k] for k in fields):
            raise ValueError(
                "Final calculator page or official verdict differs from its source"
            )
    return components.outcomes(rows, "final")


def full_project(project, source, models, starter_tag=None, starter_source=None):
    from studies.paper_performance import joint_scores

    study = read(source)
    starter_builds = read(starter_source) if starter_source else None
    selections = read(EXAMPLES) if project == "calculator" else None
    groups = {}
    for tag, model in models.items():
        rows = study["models"][model]
        build = study["libraries"][tag]["a"]["status"]
        gpt_admitted = (
            study["public"]["fixed-gpt5-library"]["arithmetic"]
            if project == "calculator"
            else study["public"]["admitted"]
        )
        intentions = {m: components.outcomes(rows, m) for m in ("direct", "human")}
        sources = dict.fromkeys(intentions, relative(source))
        if project == "dom1":
            intentions["direct"] = components.outcomes(
                read(DIRECT)["models"][model], "direct"
            )
            sources["direct"] = relative(DIRECT)
        excluded = []
        if gpt_admitted:
            if selections is None:
                intentions["gpt5-library"] = components.outcomes(rows, "gpt5-library")
                sources["gpt5-library"] = relative(source)
            else:
                assert selections["public"]["arithmetic"]
                assert len(example_outcomes(selections["models"][model])) == 20
                intentions["gpt5-library"] = compiler_outcomes(
                    read(FALLBACK)["models"][model]
                )
                sources["gpt5-library"] = relative(FALLBACK)
        else:
            excluded.append("gpt5-library")
        builds = [dict(status=build, source=relative(source))]
        if starter_builds and tag == starter_tag:
            assert build == "build_failed"
            build = starter_builds["libraries"]["a"]["status"]
            builds.append(dict(status=build, source=relative(starter_source)))
            self_rows = [r for r in starter_builds["rows"] if r["rep"] == "a"]
            self_arm = "planned"
            self_source = starter_source
        else:
            self_rows, self_arm, self_source = rows, "self-a", source
        if build == "valid":
            intentions["self"] = components.outcomes(self_rows, self_arm)
            sources["self"] = relative(self_source)
        elif build == "build_failed":
            excluded.append("self")
        elif build != "missing":
            raise ValueError(f"Unrecognised build status {build}")
        for scores in intentions.values():
            if set(scores) != set(range(1, 21)):
                raise ValueError(f"Incomplete registration in {project} / {model}")
        group = joint_scores(intentions, allow_direct_only=True)
        if group is None:
            raise ValueError(f"No jointly observed baseline in {project} / {model}")
        filters = {arm: {"arm": arm} for arm in sources}
        if "self" in filters:
            filters["self"] = {"arm": self_arm}
            if self_arm == "planned":
                filters["self"]["rep"] = "a"
        if selections is not None and "gpt5-library" in filters:
            filters["gpt5-library"] = {"arm": "final"}
        groups[model] = group | dict(
            implementation_sources=sources,
            record_filters=filters,
            excluded_build_arms=excluded,
            first_builds=builds,
            registered=20,
            source=relative(source),
        )
        if selections is not None:
            groups[model]["protocols"] = {
                "gpt5-library": "native plan; request one of the builder's two examples only after compiler rejection"
            }
    return groups


def existing_file_rows(matrix):
    from studies.paper_performance import joint_scores

    original = read(IDENTITY)
    corrected = read(DIRECT)["models"]
    groups = {}
    for tag, model in (
        ("qwen9", components.QWEN9),
        ("deepseek-flash", components.FLASH),
    ):
        controls = [r for r in original["controls"] if r["tag"] == tag]
        self_rows = [r for r in original["rows"] if r["tag"] == tag and r["rep"] == "a"]
        methods = {
            a: components.outcomes(controls, a)
            for a in ("direct", "human", "gpt5-library")
        }
        methods["self"] = components.outcomes(self_rows, "planned")
        previous = matrix[model]["source_diagnosis"]["dom1"]
        assert joint_scores(methods)["passed"] == previous["passed"]
        methods["direct"] = components.outcomes(corrected[model], "direct")
        comparison = joint_scores(methods)
        assert comparison["targets"] == sorted(map(int, previous["targets"]))
        groups[model] = comparison | dict(
            source=relative(IDENTITY),
            registered=20,
            excluded_build_arms=[],
            implementation_sources=dict.fromkeys(methods, relative(IDENTITY))
            | {"direct": relative(DIRECT)},
            record_filters={
                "direct": {"arm": "direct"},
                "self": {"arm": "planned", "tag": tag, "rep": "a"},
                "human": {"arm": "human", "tag": tag},
                "gpt5-library": {"arm": "gpt5-library", "tag": tag},
            },
        )
    return groups


def todo_rows(matrix):
    from studies.paper_performance import joint_scores

    choices, scoped, routes = read(CHOICES), read(SCOPES), read(ROUTES)
    results = {}
    for model, current in choices["models"].items():
        earlier = matrix[model]["state_examples"]["todomvc"]
        rows = routes["models"][model]["rows"]
        arms = {
            a: components.outcomes(rows, "a" if a == "self" else a)
            for a in ("direct", "human", "gpt5-library", "self")
        }
        for arm in ("direct", "human", "gpt5-library", "fixed-a", "fixed-b"):
            controls = [r for r in current["rows"] if r["arm"] == arm]
            if not arm.startswith("fixed-"):
                assert controls == [r for r in rows if r["arm"] == arm]
            assert controls == [
                r for r in scoped["models"][model]["rows"] if r["arm"] == arm
            ]
        group = joint_scores(arms)
        if group is None:
            raise ValueError(f"No jointly observed TodoMVC tasks for {model}")
        assert set(arms["direct"]) == set(earlier["targets"]) and all(
            set(a) == set(arms["direct"]) for a in arms.values()
        )
        sources = earlier["implementation_sources"] | {"self": relative(ROUTES)}
        results[model] = group | dict(
            implementation_sources=sources,
            record_filters={"self": {"arm": "a"}},
            excluded_build_arms=[],
            source=relative(ROUTES),
            protocols={
                "self": "frozen switch decisions with public view and route checks"
            },
            configuration_source=relative(CHOICES),
            registered=8,
        )
    return results


def attach(matrix):
    audit = read(ACCOUNTING)
    for receipt in (
        *audit["stages"].values(),
        audit["offline_interaction"],
        audit["offline_direct_reception"],
    ):
        if sha(ROOT / receipt["result"]) != receipt["result_sha256"]:
            raise ValueError(
                f"Published extension receipt changed: {receipt['result']}"
            )
        for path, expected in receipt.get("registered_sources", {}).items():
            if sha(ROOT / path) != expected:
                raise ValueError(f"Registered public study source changed: {path}")
    for rows in read(FALLBACK)["models"].values():
        if set(compiler_outcomes(rows)) != set(range(1, 21)):
            raise ValueError("Incomplete scheduled calculator comparison")
    projects = {
        "dom1": full_project("dom1", FILES, WEB_MODELS) | existing_file_rows(matrix),
        "calculator": full_project("calculator", CALC, WEB_MODELS, "gemma", STARTER)
        | full_project(
            "calculator",
            capabilities.CALCULATOR,
            {"qwen9": components.QWEN9, "deepseek-flash": components.FLASH},
            "qwen9",
            capabilities.CALCULATOR_FOCUSED,
        ),
        "todomvc": todo_rows(matrix),
    }
    for project, models in projects.items():
        for model, row in models.items():
            matrix[model].setdefault("target_extensions", {})[project] = row


def offline_receipt(result, directory):
    root = ROOT / "artifacts" / directory
    reg = root / "registration.json"
    registration = read(reg)
    deployment = read(result)
    assert registration["paid_calls"] == deployment["paid_calls"] == 0
    assert (
        sha(reg) == deployment["registration"]
        and sha(root / "seal.json") == deployment["seal"]
    )
    sources = {
        p: h
        for p, h in registration["sources"].items()
        if p.startswith("studies/") and p.endswith((".py", ".md"))
    }
    return dict(
        result=relative(result),
        result_sha256=sha(result),
        registered_at=registration["utc"],
        registration=sha(reg),
        registered_sources=sources,
        paid_calls=0,
    )


def accounting():
    from collections import defaultdict
    from studies import ledger_read

    earlier_path = ROOT / "studies/results/webgen-site-completion-20261128.json"
    earlier = read(earlier_path)["campaign"]
    stages = {}
    settled, exposure, calls, unknown = 0, 0, 0, 0
    for name, receipt in (
        ("calculator-target-models", CALC),
        ("calculator-starter-transfer", STARTER),
        ("calculator-keypad-labels", KEYPAD),
        ("calculator-example-selection", EXAMPLES),
        ("calculator-compiler-fallback", FALLBACK),
        ("file-explorer-target-models", FILES),
        ("todo-edit-scope", SCOPES),
        ("todo-edit-choices", CHOICES),
        ("todo-filtered-view", VIEWS),
        ("todo-route-preservation", ROUTES),
        ("table-keyboard-contract", KEYBOARD),
        ("table-navigation-context", NAVIGATION),
        ("table-coordinate-navigation", COORDINATES),
        ("table-coordinate-reception", RECEPTION),
    ):
        root = ROOT / "artifacts" / (name + "-20261128")
        db = root / "budget.sqlite3"
        reg = root / "registration.json"
        stats = ledger_read.totals(db)
        deployment = read(receipt)
        registration = read(reg)
        assert deployment["cost"] == stats and deployment["registration"] == sha(reg)
        assert deployment["seal"] == sha(root / "seal.json")
        if name == "table-coordinate-reception":
            assert registration["paid_calls"] == stats["calls"] == 0
        else:
            assert registration["cap"] == stats["cap_usd"]
        registered = {
            p: h
            for p, h in registration["sources"].items()
            if p.startswith("studies/") and p.endswith((".py", ".md"))
        }
        for p, h in registered.items():
            assert sha(ROOT / p) == h
        counts = defaultdict(
            lambda: dict(
                calls=0, settled_micro_usd=0, exposure_micro_usd=0, unsettled=0
            )
        )
        for r in ledger_read.calls(db):
            model = r["model"]
            phase = r["purpose"].split("/")[0]
            group = counts[model, phase]
            group["calls"] += 1
            group["settled_micro_usd"] += r["actual"] or 0
            group["exposure_micro_usd"] += (
                r["reserved"] if r["actual"] is None else r["actual"]
            )
            group["unsettled"] += int(r["actual"] is None)
        s, e = (
            sum(v[k] for v in counts.values())
            for k in ("settled_micro_usd", "exposure_micro_usd")
        )
        assert s == round(stats["settled_usd"] * 1e6) and e == round(
            stats["exposure_usd"] * 1e6
        )
        settled += s
        exposure += e
        calls += stats["calls"]
        unknown += stats["unsettled_calls"]
        stages[name] = dict(
            result=relative(receipt),
            result_sha256=sha(receipt),
            registration=deployment["registration"],
            registered_at=registration["utc"],
            registered_sources=registered,
            totals=stats,
            by_model_phase=[
                dict(model=m, phase=p, **v) for (m, p), v in sorted(counts.items())
            ],
        )
    campaign = dict(
        settled_usd=(round(earlier["settled_usd"] * 1e6) + settled) / 1e6,
        exposure_usd=(round(earlier["exposure_usd"] * 1e6) + exposure) / 1e6,
        calls=earlier["calls"] + calls,
        unsettled_calls=earlier["unsettled_calls"] + unknown,
    )
    assert campaign["exposure_usd"] <= 20
    return dict(
        previous_source=relative(earlier_path),
        previous=earlier,
        offline_direct_reception=offline_receipt(
            DIRECT, "file-explorer-direct-reception-20261128"
        ),
        offline_interaction=offline_receipt(
            FACTORIAL, "todo-route-view-interaction-20261128"
        ),
        stages=stages,
        added=dict(
            settled_usd=settled / 1e6,
            exposure_usd=exposure / 1e6,
            calls=calls,
            unsettled_calls=unknown,
        ),
        campaign=campaign,
    )


if __name__ == "__main__":
    from argparse import ArgumentParser
    from studies.study_io import dump

    parser = ArgumentParser(
        description="Reconcile the primary and follow-up study ledgers."
    )
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    record = accounting()
    if args.write and not ACCOUNTING.exists():
        dump(ACCOUNTING, record)
    assert read(ACCOUNTING) == record
    print(record["added"], record["campaign"])
