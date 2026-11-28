"""Publish the matched calculator and table rebuilds without changing their archived protocols."""

from tempfile import NamedTemporaryFile
from pathlib import Path

from studies import paper_component_followup as components
from studies import paper_target_extensions as previous
from studies.study_io import ROOT, dump, read, sha

CALC = ROOT / "studies/webbench/calculator/behavior_modules/result.json"
DELIVERY = CALC.parent / "gpt5_delivery/result.json"
ADDITIVE = CALC.parent / "incremental/result.json"
TABLE = ROOT / "studies/webbench/table/author_modules/result.json"
TABLE_SELF = ROOT / "studies/webbench/table/model_modules/result.json"
KEYS = ROOT / "studies/webbench/calculator/key_programs/result.json"
INDIVIDUAL = KEYS.parent / "individual_keys/result.json"
DESIGN = TABLE_SELF.parent / "structured_design/result.json"
TRACE = TABLE_SELF.parent / "public_trace/result.json"
MEMORY = CALC.parent.parent / "memory_recall/result.json"
ARRAYS = TRACE.parent / "array_reception/result.json"
HOOKS = TABLE.parent.parent / "event_hooks/result.json"
DOM = HOOKS.parent / "dom_contract/result.json"
SELECT = HOOKS.parent / "handler_selection/result.json"
ACCOUNT = ROOT / "studies/results/library-rebuild-costs-20261128.json"
STAGES = {
    "calculator-behavior-modules": CALC,
    "calculator-behavior-gpt5-delivery": DELIVERY,
    "calculator-additive-modules": ADDITIVE,
    "table-author-modules": TABLE,
    "table-model-modules": TABLE_SELF,
    "table-structured-design": DESIGN,
    "table-self-public-trace": TRACE,
    "table-self-edit-arrays": ARRAYS,
    "table-event-hooks": HOOKS,
    "table-dom-contract": DOM,
    "table-handler-selection": SELECT,
    "calculator-key-programs": KEYS,
    "calculator-individual-keys": INDIVIDUAL,
    "calculator-memory-recall": MEMORY,
}
LINKS = (INDIVIDUAL.with_name("lineage.json"), TRACE.with_name("lineage.json"))
SOURCES = (
    *STAGES.values(),
    *LINKS,
    MEMORY.with_name("browser-errors.json"),
    ACCOUNT,
)


def relative(path):
    return str(path.relative_to(ROOT))


def accounting():
    from studies import ledger_read

    old = read(previous.ACCOUNTING)["campaign"]
    totals = dict(calls=0, unsettled_calls=0, settled_micro_usd=0, exposure_micro_usd=0)
    stages = {}
    for name, path in STAGES.items():
        folder = ROOT / "artifacts" / (name + "-20261128")
        data, reg = read(path), read(folder / "registration.json")
        assert data["registration"] == sha(folder / "registration.json")
        assert data["seal"] == sha(folder / "seal.json")
        ledger = ledger_read.totals(folder / "budget.sqlite3")
        assert ledger == data["cost"] and ledger["cap_usd"] == reg["cap"]
        phases = {}
        for call in ledger_read.calls(folder / "budget.sqlite3"):
            phase = call["purpose"].split("/")[0]
            usd = call["actual"]
            group = phases.setdefault(call["model"], {}).setdefault(
                phase, dict(calls=0, settled_micro_usd=0, exposure_micro_usd=0)
            )
            group["calls"] += 1
            group["settled_micro_usd"] += usd or 0
            group["exposure_micro_usd"] += call["reserved"] if usd is None else usd
        totals["calls"] += ledger["calls"]
        totals["unsettled_calls"] += ledger["unsettled_calls"]
        for kind in ("settled", "exposure"):
            n = sum(
                v[kind + "_micro_usd"]
                for groups in phases.values()
                for v in groups.values()
            )
            assert n == round(ledger[kind + "_usd"] * 1e6)
            totals[kind + "_micro_usd"] += n
        public = {p: h for p, h in reg["sources"].items() if p.startswith("studies/")}
        assert all(sha(ROOT / p) == h for p, h in public.items())
        stages[name] = dict(
            result=relative(path),
            sha256=sha(path),
            registration=data["registration"],
            registered_at=reg["utc"],
            public_sources=public,
            totals=ledger,
            model_phases=phases,
        )
    added = dict(
        calls=totals["calls"],
        unsettled_calls=totals["unsettled_calls"],
        settled_usd=totals["settled_micro_usd"] / 1e6,
        exposure_usd=totals["exposure_micro_usd"] / 1e6,
    )
    campaign = {k: round(old[k] + added[k], 6) for k in added}
    assert campaign["exposure_usd"] <= 20
    return dict(
        previous_source=relative(previous.ACCOUNTING),
        previous=old,
        stages=stages,
        added=added,
        campaign=campaign,
    )


def recorded(
    row,
    arm,
    items,
    source_arm,
    receipt,
    build_status,
    protocol,
    inherit_if_incomplete=False,
):
    targets = {int(n) for n in row["targets"]}
    values = components.outcomes(items, source_arm)
    assert set(values) == set(range(1, 21)) and len(targets) == row["n"]
    available = all(values[n] is not None for n in targets)
    if inherit_if_incomplete and build_status == "valid" and not available:
        row.setdefault("partial_followups", {})[arm] = relative(receipt)
        return
    row["inherited_methods"].remove(arm)
    row.setdefault("implementation_sources", {})[arm] = relative(receipt)
    row.setdefault("record_filters", {})[arm] = {"arm": source_arm}
    row.setdefault("protocols", {})[arm] = protocol
    row["passed"].pop(arm, None)
    failures = row.setdefault("excluded_build_arms", [])
    if arm in failures:
        failures.remove(arm)
    if build_status == "build_failed":
        assert all(v is None for v in values.values())
        failures.append(arm)
    elif build_status == "missing" or not available:
        row.setdefault("unavailable_reasons", {})[arm] = (
            "Undelivered library or incomplete registered deployment"
        )
    else:
        assert build_status == "valid"
        row["passed"][arm] = sum(values[n] is True for n in targets)


def attach(matrix):
    from studies.paper_performance import METHODS, table_record

    audit = read(ACCOUNT)
    for data in audit["stages"].values():
        assert sha(ROOT / data["result"]) == data["sha256"]
        assert all(sha(ROOT / p) == h for p, h in data["public_sources"].items())
    calc, delivery, additive, table, self_table = map(
        read, (CALC, DELIVERY, ADDITIVE, TABLE, TABLE_SELF)
    )
    keys, structured, individual = read(KEYS), read(DESIGN), read(INDIVIDUAL)
    trace, memory, arrays, hooks, dom, selected = map(
        read, (TRACE, MEMORY, ARRAYS, HOOKS, DOM, SELECT)
    )
    assert all(v["parent_seal"] == dom["seal"] for v in selected["libraries"].values())
    assert all(
        lib["parent_seal"] == trace["seal"] for lib in arrays["libraries"].values()
    )
    for link, source, parent, study in (
        (LINKS[0], INDIVIDUAL, keys, individual),
        (LINKS[1], TRACE, structured, trace),
    ):
        assert read(link) == {
            "parent_seal": parent["seal"],
            "result_sha256": sha(source),
            "seal": study["seal"],
        }
    assert keys["additive_seal"] == additive["seal"]
    assert set(structured["models"]) <= set(self_table["models"])
    assert delivery["main_seal"] == calc["seal"] == additive["parent_seal"]
    assert (
        table["history"]["calculator"]["original"]["package"]
        == table["history"]["calculator"]["review"]["package"]
    )
    assert table["calculator_equivalence"] == sha(previous.FALLBACK)

    def copy_row(model, project):
        path, old = table_record(matrix[model], project)
        return dict(
            n=old["n"],
            passed=dict(old["passed"]),
            excluded_build_arms=list(old.get("excluded_build_arms", [])),
            inherited_from=list(path),
            inherited_methods=list(METHODS),
            targets=sorted(int(n) for n in old["targets"]),
            source=relative(CALC if project == "calculator" else TABLE),
        )

    for tag, model in calc["builders"].items():
        if model not in calc["models"]:
            continue
        row = copy_row(model, "calculator")
        parent = calc["libraries"][tag]
        rows, source = calc["models"][model], CALC
        attempts = [
            {
                "status": item["status"],
                "source": relative(CALC),
                "attempt": item["trial"],
            }
            for item in parent["attempts"]
        ]
        message = "Model-authored calculator modules installed on the public starter."
        if model in additive["models"]:
            successor = additive["libraries"][tag]
            attempts.extend(
                {
                    "status": a["status"],
                    "source": relative(ADDITIVE),
                    "attempt": a["attempt"],
                }
                for a in successor["trials"]
            )
            rows, source = additive["models"][model], ADDITIVE
            message += (
                " Public checks select between the parent and additive rebuild; selected: "
                + successor["selected"]
                + "."
            )
            for arm in ("self", "fixed-self"):
                plans = {r["task"]: r["levels"] for r in rows if r["arm"] == arm}
                assert plans == {
                    r["task"]: r["levels"]
                    for r in calc["models"][model]
                    if r["arm"] == arm
                }
        catalog = keys["models"][model]
        initial_plans = {r["task"]: r["levels"] for r in rows if r["arm"] == "self"}
        assert initial_plans == {
            r["task"]: r["levels"] for r in catalog if r["arm"] == "new-code-old-choice"
        }
        current_plans = {r["task"]: r["levels"] for r in catalog if r["arm"] == "self"}
        assert current_plans == {
            r["task"]: r["levels"] for r in catalog if r["arm"] == "old-code-new-choice"
        }
        message += " Choose among observed UI profiles; keep model-authored key transitions only if public checks improve."
        rows, source = catalog, KEYS
        row["first_builds"] = attempts
        row["component_rebuilds"] = {}

        def note_rebuilds(stage, lib):
            for group, trials in lib["history"].items():
                row["component_rebuilds"].setdefault(group, []).extend(
                    {
                        "source": relative(stage),
                        "attempt": item["attempt"],
                        "adopted": item["accepted"],
                    }
                    for item in trials
                )

        note_rebuilds(KEYS, keys["libraries"][tag])
        if model in individual["models"]:
            revisited = individual["models"][model]
            replay = [r for r in revisited if r["arm"] == "old-code-same-choice"]
            earlier_runs = {r["task"]: r for r in catalog if r["arm"] == "self"}
            assert len(replay) == len(earlier_runs) == 20
            for r in replay:
                previous_run = earlier_runs[r["task"]]
                assert all(
                    r[k] == previous_run[k] for k in ("levels", "status", "passed")
                )
            assert current_plans == {
                r["task"]: r["levels"] for r in revisited if r["arm"] == "self"
            }
            note_rebuilds(INDIVIDUAL, individual["libraries"][tag])
            rows, source = revisited, INDIVIDUAL
            message += " Replay the same target choices after accepting the author's extension-key lists or requesting one transition at a time."
        if model in memory["models"]:
            assert memory["libraries"][tag]["parent_seal"] == read(source)["seal"]
            refreshed = memory["models"][model]
            prior_self = {r["task"]: r for r in rows if r["arm"] == "self"}
            for r in refreshed:
                if r["arm"] == "old-code-same-choice":
                    assert all(
                        r[k] == prior_self[r["task"]][k]
                        for k in ("levels", "status", "passed")
                    )
                if r["arm"] == "self":
                    assert r["levels"] == prior_self[r["task"]]["levels"]
            row["component_rebuilds"].setdefault("memory", []).extend(
                {
                    "source": relative(MEMORY),
                    "attempt": item["attempt"],
                    "adopted": item["accepted"],
                }
                for item in memory["libraries"][tag]["trials"]
            )
            message += " For a missing public memory workflow, rebuild the display and register expressions separately, preserving target choices."
            rows, source = refreshed, MEMORY
        recorded(row, "self", rows, "self", source, parent["status"], message)
        recorded(
            row,
            "gpt5-library",
            delivery["models"][model],
            "gpt5-library",
            DELIVERY,
            delivery["library"]["status"],
            "GPT-5 build with the shared calculator module interface and the same target plans as Self.",
        )
        if delivery["library"]["status"] == "missing":
            row["unavailable_reasons"]["gpt5-library"] = (
                "The provider rejected the GPT-5 calculator build (HTTP 403, model unavailable in region)."
            )
        row["historical_gpt5_source"] = relative(previous.FALLBACK)
        matrix[model].setdefault("module_rebuilds", {})["calculator"] = row
    for model, rows in table["models"].items():
        row = copy_row(model, "table")
        recorded(
            row,
            "gpt5-library",
            rows,
            "combined",
            TABLE,
            "valid" if table["chosen_attempt"] else "build_failed",
            "Non-overlapping GPT-5 self-review files and its own event-trace entry repair with fresh profile choices.",
            inherit_if_incomplete=True,
        )
        if model in self_table["models"]:
            tag = next(
                t for t in self_table["libraries"] if calc_model_name(t) == model
            )
            lib = self_table["libraries"][tag]
            row["first_builds"] = [
                dict(
                    status=a["status"],
                    attempt=a["attempt"],
                    source=relative(TABLE_SELF),
                )
                for a in lib["trials"]
            ]
            successor = TABLE_SELF
            for result, path in (
                (structured, DESIGN),
                (trace, TRACE),
                (arrays, ARRAYS),
                (hooks, HOOKS),
                (dom, DOM),
                (selected, SELECT),
            ):
                if model not in result["models"]:
                    continue
                assert lib["status"] != "valid"
                successor = path
                lib = result["libraries"][tag]
                row["first_builds"].extend(
                    dict(
                        status=a["status"], attempt=a["attempt"], source=relative(path)
                    )
                    for a in lib["trials"]
                )
            description = "Model-designed modules, declared interfaces and a choice of how many ordered modules to install."
            if successor in (HOOKS, DOM, SELECT):
                description += " The researcher dispatches browser events; the original builder writes the menu, commands, dismissal and selection handlers."
            if successor in (DOM, SELECT):
                description += " Reuse original initial handlers; the author's repairs use actual DOM arguments with no application API."
            if successor == SELECT:
                description += " Select the first publicly error-free subset of the author's own event handlers."
            recorded(
                row,
                "self",
                read(successor)["models"][model],
                "self",
                successor,
                lib["status"],
                description,
            )
        matrix[model].setdefault("module_rebuilds", {})["table"] = row


def calc_model_name(tag):
    return {
        "mistral": "mistralai/mistral-small-3.2-24b-instruct",
        "qwen": "qwen/qwen3-coder-30b-a3b-instruct",
        "oss": "openai/gpt-oss-120b",
    }[tag]


if __name__ == "__main__":
    from argparse import ArgumentParser

    parser = ArgumentParser(
        description="Reconcile the new build and target-deployment costs."
    )
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    report = accounting()
    if args.write and (not ACCOUNT.exists() or read(ACCOUNT) != report):
        if ACCOUNT.exists():
            older = read(ACCOUNT)
            assert older["previous"] == report["previous"]
            assert all(report["stages"][k] == v for k, v in older["stages"].items())
        with NamedTemporaryFile(dir=ACCOUNT.parent, delete=False) as temp:
            scratch = Path(temp.name)
        try:
            dump(scratch, report)
            scratch.chmod(0o644)
            scratch.replace(ACCOUNT)
        finally:
            scratch.unlink(missing_ok=True)
    assert read(ACCOUNT) == report
    print(report["added"], report["campaign"])
