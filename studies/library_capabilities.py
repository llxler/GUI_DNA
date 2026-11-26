"""Reconcile November 26 public-build records, paired outcomes and API exposure."""

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone

from studies import ledger_read, paper_library_capabilities as paper
from studies.public_library_transfer import core
from studies.study_io import ROOT, read, sha

ART = ROOT / "artifacts"
STAGES = {
    "Llama delivery": ("todomvc-route", paper.ROUTE),
    "TodoMVC contract repair": (
        "todomvc-contract-repair",
        paper.prior.SUITE / "contract_repair/result.json",
    ),
    "TodoMVC syntax reception": (
        "todo-syntax-reception",
        paper.prior.SUITE / "syntax_reception/result.json",
    ),
    "Duo transferred GPT-5 components": ("duo-donors", paper.DONORS),
    "Duo paired hooks and views": ("duo-react-callbacks", paper.CALLBACKS),
    "Table actions": ("table-action-library", paper.ACTIONS),
    "Table public exceptions": ("table-event-feedback", paper.FEEDBACK),
    "Table isolated actions": ("table-action-contracts", paper.CONTRACTS),
    "Table selection binding": ("table-selection-binding", paper.BINDING),
    "Table typed binding": ("table-typed-binding", paper.TYPED_BINDING),
    "Shared survey configuration": ("survey-workflow", paper.SURVEY),
    "Undelivered survey request": ("survey-transport", paper.SURVEY_TRANSPORT),
    "Table fresh libraries": (
        "table-binding-replication",
        paper.TABLE / "selection_binding/replication/result.json",
    ),
    "File explorer source comparison": ("file-explorer-sources", paper.FILES),
    "File explorer DOM extensions": ("file-explorer-dom", paper.EXTENSIONS),
    "File explorer document entry": ("file-explorer-documents", paper.DOCUMENTS),
    "SVG public geometry": ("svg-public-geometry", paper.GEOMETRY),
    "SVG post-draw modules": ("svg-public-decorations", paper.DECORATION),
    "Commercial backbone availability": ("backbone-routes", paper.BACKBONE_ROUTES),
    "Duo declared props": ("duo-prop-contract", paper.PROP_CONTRACT),
    "Calculator key groups": ("calculator-key-groups", paper.CALCULATOR),
    "Calculator starter functions": (
        "calculator-starter-modules",
        paper.CALCULATOR_MODULES,
    ),
    "Calculator function prompts": (
        "calculator-function-prompts",
        paper.CALCULATOR_FOCUSED,
    ),
    "TodoMVC final delivery": ("todo-slot-final", paper.SLOT_FINAL),
    "TodoMVC missing decisions": ("todo-slot-completion", paper.SLOT_COMPLETION),
    "TodoMVC matched slot choices": ("todo-slot-choices", paper.SLOT_CHOICES),
}
CAUSAL = paper.TABLE / "menu_propagation/result.json"


def budget():
    totals = Counter()
    phase_totals = defaultdict(Counter)
    stages = {}
    timestamps = []
    registrations = []
    for label, (short, result) in STAGES.items():
        root = ART / (short + "-20261126")
        ledger = root / "budget.sqlite3"
        registration = read(root / "registration.json")
        registrations.append((registration["utc"], registration.get("balance", {})))
        costs = ledger_read.totals(ledger)
        assert read(result)["cost"] == costs
        by_model = defaultdict(lambda: defaultdict(Counter))
        for call in ledger_read.calls(ledger):
            phase = call["purpose"].split("/")[0]
            if short == "backbone-routes" and phase == "target":
                phase = "plan"
            assert phase in ("plan", "build")
            value = call["actual"]
            counts = dict(
                requests=1,
                settled_microusd=value or 0,
                unresolved=int(value is None),
                exposure_microusd=call["reserved"] if value is None else value,
            )
            totals.update(counts)
            phase_totals[phase].update(counts)
            timestamps.append(call["created"])
            by_model[call["model"]][phase].update(counts)
        stages[label] = dict(
            result=str(result.relative_to(ROOT)),
            result_sha256=sha(result),
            registration_sha256=sha(root / "registration.json"),
            ledger=costs,
            by_model=by_model,
        )
    assert totals["exposure_microusd"] <= 20_000_000
    return dict(
        stages=stages,
        total=dict(totals),
        by_phase=phase_totals,
        first_stage_balance=min(registrations, key=lambda x: x[0])[1],
        last_request_utc=datetime.fromtimestamp(
            max(timestamps), timezone.utc
        ).isoformat(),
        authorized_usd=20,
        authorized_hours=4,
    )


def counts(rows, arm):
    vals = paper.prior.outcomes(rows, arm)
    return dict(
        passed=sum(v is True for v in vals.values()),
        observed=sum(type(v) is bool for v in vals.values()),
        passing_targets=sorted(k for k, v in vals.items() if v is True),
        scheduled=len(vals),
    )


def red_cell_history():
    """Track the originally marked targets separately from the current, sometimes expanded row."""
    from studies.paper_performance import joint_scores

    source = ROOT / "studies/results/component-followup-20261125.json"
    linked = read(paper.LINKS)
    survey = read(paper.SURVEY)
    history = []
    for old in read(source)["red_cells"]:
        targets = old["targets"]
        prior = old["stages"][old["stage"]]["selected"]
        assert prior["observed"] == len(targets)
        current = old["paper"]
        current_on_original = prior["passed_targets"]
        evidence = source
        if (
            old["project"] == "form"
            and old["arm"] == "self"
            and old["tag"] in ("gemma", "mistral")
        ):
            rows = paper.survey_rows(old["model"], survey["models"][old["model"]])
            controls = {
                k: paper.prior.outcomes(rows, k)
                for k in ("direct", "human", "gpt5-library")
            }
            records = [
                r for r in linked["rows"] if r["tag"] == old["tag"] and r["rep"] == "a"
            ]
            own = paper.prior.outcomes(records, "self")
            paired = joint_scores({**controls, "self": own})
            assert set(targets) <= set(paired["targets"])
            current = dict(targets=paired["targets"], passed=paired["passed"]["self"])
            current_on_original = [t for t in targets if own[t]]
            evidence = paper.LINKS
        history.append(
            dict(
                project=old["project"],
                model=old["model"],
                method=old["arm"],
                original_targets=targets,
                original_passes=old["original"],
                november25_on_original=prior["passed"],
                current_on_original=len(current_on_original),
                current_passing_original_targets=current_on_original,
                displayed=current,
                source=str(evidence.relative_to(ROOT)),
            )
        )
    return dict(
        previous_snapshot=str(source.relative_to(ROOT)),
        previous_sha256=sha(source),
        rows=history,
    )


def build():
    report = dict(
        budget=budget(),
        annotated_cells=red_cell_history(),
        api_free={
            str(f.relative_to(ROOT)): sha(f)
            for f in (
                paper.TODO,
                CAUSAL,
                paper.FILE_CONTROLS,
                paper.LINKS,
                paper.SVG_HELPERS,
            )
        },
    )
    trials = {}
    for f in (
        paper.ACTIONS,
        paper.FEEDBACK,
        paper.CONTRACTS,
        paper.BINDING,
        paper.TYPED_BINDING,
        paper.TABLE / "selection_binding/replication/result.json",
    ):
        result = read(f)
        trials[str(f.relative_to(ROOT))] = [
            dict(
                builder=c["tag"],
                rep=c["rep"],
                status=c["status"],
                options=c.get("options"),
                models={
                    m: {a: counts(rows, a) for a in sorted({r["arm"] for r in rows})}
                    for m, rows in c["deployments"].items()
                },
            )
            for c in result["cases"]
        ]
    report["table_preparations"] = trials
    routes = read(paper.BACKBONE_ROUTES)["models"]
    report["commercial_route_outcomes"] = {
        tag: value["first"] for tag, value in routes.items()
    }
    props = read(paper.PROP_CONTRACT)
    report["duo_prop_contract"] = dict(
        libraries=props["libraries"],
        models={
            m: {a: counts(rows, a) for a in sorted({r["arm"] for r in rows})}
            for m, rows in props["models"].items()
        },
    )
    for label, source in (
        ("svg_public_geometry", paper.GEOMETRY),
        ("svg_post_draw", paper.DECORATION),
        ("svg_named_helpers", paper.SVG_HELPERS),
    ):
        geo = read(source)
        report[label] = {}
        for tag, library in geo["libraries"].items():
            rows = [r for r in geo["rows"] if r["tag"] == tag]
            report[label][tag] = dict(
                initial_public_checks=len(library["initial"]["passed"]),
                final_public_checks=len(library["final"]["passed"]),
                retained_modules=(
                    [a["module"] for a in library["attempts"] if a["retained"]]
                    + [
                        a["name"]
                        for a in library.get("helper_attempts", [])
                        if a["retained"]
                    ]
                ),
                measurements={arm: counts(rows, arm) for arm in ("planned", "fixed")},
            )
    causal = read(CAUSAL)
    checks = causal["public"]
    planned = {}
    for tag in sorted(
        {r["tag"] for r in causal["rows"] if r["arm"] == "corrected-plan"}
    ):
        rows = [
            r
            for r in causal["rows"]
            if r["arm"] == "corrected-plan" and r["tag"] == tag
        ]
        paired = [
            r for r in rows if type(r["before"]) is bool and type(r["passed"]) is bool
        ]
        planned[tag] = dict(
            targets=[r["task"] for r in paired],
            before=sum(r["before"] for r in paired),
            after=sum(r["passed"] for r in paired),
            gained=[r["task"] for r in paired if r["passed"] and not r["before"]],
            lost=[r["task"] for r in paired if r["before"] and not r["passed"]],
        )
    report["researcher_event_correction"] = dict(
        public=checks,
        planned=planned,
        fixed={
            i: {
                a: counts([r for r in causal["rows"] if r["tag"] == i], a)
                for a in ("original-fixed", "corrected-fixed")
            }
            for i in checks
        },
    )
    todo = read(paper.TODO)
    report["todomvc_slot_choices"] = {
        m: {
            arm: counts(data["rows"], arm)
            for arm in sorted({r["arm"] for r in data["rows"]})
        }
        for m, data in read(paper.SLOT_FINAL)["models"].items()
    }
    small = read(paper.prior.SMALL)["models"]
    report["todomvc"] = {}
    for m, run in todo["models"].items():
        result = {}
        for arm in ("direct", "human", "gpt5-library", "a", "b", "fixed-a", "fixed-b"):
            rows = (
                run["rows"]
                if any(r["arm"] == arm for r in run["rows"])
                else small[m]["rows"]
            )
            result[arm] = counts(rows, arm)
        report["todomvc"][m] = result
    donors = read(paper.DONORS)
    report["duo_donors"] = dict(
        choices=donors["choices"],
        source_revision=donors["source_revision"],
        domains={
            g: {
                "public_passes": sum(c["passed"] for c in v["singles"].values()),
                "available_sources": len(v["singles"]),
                "required": len(donors["choices"][g]),
            }
            for g, v in donors["libraries"].items()
        },
        models={
            m: {a: counts(rs, a) for a in ("planned", "fixed", "names")}
            for m, rs in donors["models"].items()
        },
    )
    callbacks = read(paper.CALLBACKS)
    report["duo_callbacks"] = dict(
        libraries=callbacks["libraries"],
        models={
            m: {
                a: counts(rs, a)
                for a in (
                    "direct",
                    "a",
                    "b",
                    "fixed-a",
                    "fixed-b",
                    "names-a",
                    "names-b",
                )
            }
            for m, rs in callbacks["models"].items()
        },
    )
    survey = read(paper.SURVEY)
    linked = read(paper.LINKS)
    report["survey"] = {
        m: {
            a: counts(paper.survey_rows(m, rs), a)
            for a in sorted({r["arm"] for r in rs})
        }
        for m, rs in survey["models"].items()
    }
    report["survey_transport"] = read(paper.SURVEY_TRANSPORT)["rows"]
    report["survey_source_links"] = {
        t: {
            rep: dict(
                edits=info["edits"],
                public_before=info["initial"]["checks"],
                public_after=info["after"]["checks"],
                measurements={
                    a: counts(
                        [
                            r
                            for r in linked["rows"]
                            if r["tag"] == t and r["rep"] == rep
                        ],
                        a,
                    )
                    for a in ("self", "fixed")
                },
            )
            for rep, info in reps.items()
        }
        for t, reps in linked["libraries"].items()
    }
    initial, docs = read(paper.FILES), read(paper.DOCUMENTS)
    controls = read(paper.FILE_CONTROLS)["rows"]
    report["file_explorer"] = {}
    for tag in ("qwen9", "deepseek-flash"):
        m = paper.TAGS[tag]
        paired = {
            a: counts([r for r in controls if r["tag"] == tag], a)
            for a in ("direct", "human", "gpt5-library")
        }
        fixed = {
            a: counts(initial["models"][m], a)
            for a in (
                "fixed-gpt5-library",
                "astra-a",
                "astra-b",
                "fixed-astra-a",
                "fixed-astra-b",
            )
        }
        own = {}
        for r in ("a", "b"):
            cases = [c for c in docs["rows"] if c["tag"] == tag and c["rep"] == r]
            own[r] = dict(
                status=docs["libraries"][tag][r]["status"],
                modules=docs["libraries"][tag][r]["options"],
                measurements={
                    a: counts(cases, a) for a in ("planned", "core", "fixed")
                },
            )
        report["file_explorer"][m] = dict(
            controls=paired, other_frozen_pages=fixed, own=own
        )
    report["file_explorer"]["source_costs"] = initial["source_costs"]
    report["file_explorer"]["empty"] = counts(
        [r for r in docs["rows"] if r["tag"] == "starter"], "host"
    )
    calc = read(paper.CALCULATOR)
    report["calculator"] = dict(
        source_costs=calc["source_costs"],
        public_first_examples=calc["public"],
        builds={
            t: {r: v["status"] for r, v in reps.items()}
            for t, reps in calc["libraries"].items()
        },
        models={
            m: {arm: counts(rows, arm) for arm in sorted({r["arm"] for r in rows})}
            for m, rows in calc["models"].items()
        },
    )
    for label, source in (
        ("qwen_starter_functions", paper.CALCULATOR_MODULES),
        ("qwen_focused_functions", paper.CALCULATOR_FOCUSED),
    ):
        extensions = read(source)
        report["calculator"][label] = {
            rep: dict(
                library=lib,
                measurements={
                    arm: counts([r for r in extensions["rows"] if r["rep"] == rep], arm)
                    for arm in ("planned", "fixed", "starter")
                },
            )
            for rep, lib in extensions["libraries"].items()
        }
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    report = build()
    if args.write:
        core.save(paper.SUMMARY, report)
    assert read(paper.SUMMARY) == report
    print(report["budget"]["total"])
