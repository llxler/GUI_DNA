"""Join all four methods by the original Duo target IDs and preserve the separate confirmation cohort."""

from collections import defaultdict
from pathlib import Path
from studies.study_io import ROOT, read, sha

HERE = Path(__file__).resolve().parent
FIRST = HERE / "result.json"
CONTRACT = HERE / "component_contract/result.json"
ROUTES = HERE / "resource_routes/result.json"
PAID = HERE / "author_completion/result.json"
CROSSED = HERE / "author_completion/same-choices.json"
FINAL = HERE / "field_bindings/result.json"
FORMS = HERE / "form_sdk/result.json"
HUMAN = HERE / "form_sdk/declared_config/result.json"
INDEPENDENT = HERE / "unseen_pairs/result.json"
ACCOUNT = HERE / "accounting.json"
AUDIT = HERE / "source-audit.json"
ORIGINAL = ROOT / "studies/results/backbone-suites-20261124.json"
CALLBACK = HERE.parent / "duo_react_callbacks/result.json"
INPUTS = (
    FIRST,
    CONTRACT,
    ROUTES,
    PAID,
    CROSSED,
    FINAL,
    FORMS,
    HUMAN,
    AUDIT,
    INDEPENDENT,
)
ROUTER = HERE / "unseen_pairs/router/result.json"
ENTRIES = HERE / "unseen_pairs/entry_points/result.json"
SOURCES = (*INPUTS, ACCOUNT, ROUTER, ENTRIES, HERE / "verification.json")
STAGES = {
    "author-completion": ("duo-author-completion", PAID),
    "form-bindings": ("duo-form-sdk", FORMS),
    "form-reception": ("duo-form-config", HUMAN),
    "independent-pairs": ("duo-unseen-pairs", INDEPENDENT),
}
FLASH = "deepseek/deepseek-v4-flash"


def observations(rows, arm, targets):
    selected = {r["task"]: r for r in rows if r["arm"] == arm and r["task"] in targets}
    assert set(selected) == set(targets)
    assert len(selected) == sum(r["arm"] == arm and r["task"] in targets for r in rows)
    return selected


def attach(matrix):
    final, form, author = read(FINAL), read(HUMAN), read(PAID)
    crossed = read(CROSSED)
    budget = read(ACCOUNT)
    assert all(sha(ROOT / f) == v for f, v in budget["records"].items())
    assert (
        form["choices_source"] == author["candidate_seal"]
        and crossed["choices"] == author["candidate_seal"]
    )
    assert final["choices"] == author["choices"]
    direct, flash = read(ORIGINAL)["models"], read(CALLBACK)["models"]
    for model, rows in final["models"].items():
        old = matrix[model]["library_capabilities"]["duo"]
        ids = old["targets"]
        baseline = CALLBACK if model == FLASH else ORIGINAL
        controls = flash[model] if model == FLASH else direct[model]["rows"]
        records = {
            "direct": (baseline, controls),
            "human": (HUMAN, form["models"][model]),
            "gpt5-library": (FINAL, rows),
            "self": (FINAL, rows),
        }
        group = dict(
            n=len(ids),
            targets=ids,
            passed={},
            excluded_build_arms=[],
            implementation_sources={},
            record_filters={},
            previous_row="library_capabilities",
            source=str(FINAL.relative_to(ROOT)),
            measure="fully passed four-case feature pairs",
            fixed_passed={},
            same_choice_previous={},
            protocols={
                "human": "Target-authored finite bindings for Final Form 5.0.0 and React Final Form 7.0.0, followed by the shared feature choice.",
                "self": "Same-model single-feature source, checked independently, repaired by its owner and mounted with declared resource and field bindings.",
                "gpt5-library": "Isolated GPT-5 donor views from disjoint pairs, supplemented by genuine GPT-5 single-feature builds under public-only checks. The target model selects features.",
                "direct": "Frozen same-model direct code on precisely the same pairs.",
            },
        )
        for arm, (source, items) in records.items():
            checked = observations(items, arm, ids)
            vals = [r["passed"] for r in checked.values()]
            if all(v is not None for v in vals):
                assert all(type(v) is bool for v in vals)
                group["passed"][arm] = sum(vals)
            elif any(r["status"] == "build_failed" for r in checked.values()):
                group["excluded_build_arms"].append(arm)
            else:
                group.setdefault("unavailable_reasons", {})[arm] = (
                    "Missing model delivery for at least one registered target"
                )
            group["implementation_sources"][arm] = str(source.relative_to(ROOT))
            group["record_filters"][arm] = dict(arm=arm)
            if arm != "direct":
                fixed = observations(items, arm + "-fixed", ids)
                if all(r["passed"] is not None for r in fixed.values()):
                    group["fixed_passed"][arm] = sum(
                        r["passed"] for r in fixed.values()
                    )
        assert group["passed"]["direct"] == old["passed"]["direct"]
        for arm in ("self", "gpt5-library"):
            prior = observations(crossed["models"][model], arm, ids)
            group["same_choice_previous"][arm] = (
                sum(r["passed"] for r in prior.values())
                if all(r["passed"] is not None for r in prior.values())
                else None
            )
        group["configuration_source"] = str(PAID.relative_to(ROOT))
        matrix[model]["duo_feature_bindings"] = group


def accounting():
    from studies import ledger_read
    from studies.public_library_transfer import core

    totals = dict(calls=0, settled_micro_usd=0, exposure_micro_usd=0, unsettled_calls=0)
    stages = {}
    for name, (folder, receipt) in STAGES.items():
        path = ROOT / "artifacts" / (folder + "-20261128")
        records = ledger_read.calls(path / "budget.sqlite3")
        ledger = ledger_read.totals(path / "budget.sqlite3")
        assert ledger == read(receipt)["cost"]
        groups = defaultdict(lambda: defaultdict(lambda: {k: 0 for k in totals}))
        for r in records:
            stage = r["purpose"].split("/")[0]
            entry = groups[r["model"]][stage]
            values = dict(
                calls=1,
                settled_micro_usd=r["actual"] or 0,
                exposure_micro_usd=r["reserved"]
                if r["actual"] is None
                else r["actual"],
                unsettled_calls=int(r["actual"] is None),
            )
            for k, v in values.items():
                totals[k] += v
                entry[k] += v
        reg = read(path / "registration.json")
        assert read(receipt)["registration"] == sha(path / "registration.json")
        public = {k: v for k, v in reg["sources"].items() if k.startswith("studies/")}
        assert all(sha(ROOT / k) == v for k, v in public.items())
        stages[name] = dict(
            cost=ledger,
            by_model_and_phase=groups,
            registration=sha(path / "registration.json"),
            sources=public,
        )
    for k in ("settled", "exposure"):
        totals[k + "_usd"] = totals.pop(k + "_micro_usd") / 1e6
    assert (
        totals["exposure_usd"]
        <= sum(v["cost"]["cap_usd"] for v in stages.values())
        <= 10
    )
    # These earlier preparations supplied the archive. Their ledgers also include other models/studies.
    legacy = {}
    for name in (
        "duo-independent-components-20261124",
        "duo-compact-components-20261124",
        "suite-self-recovery-20261125",
        "duo-delivery-confirmation-20261125",
        "duo-react-callbacks-20261126",
        "duo-prop-contract-20261126",
        "duo-donors-20261126",
        "backbone-suites-20261124",
    ):
        folder = ROOT / "artifacts" / name
        if (folder / "budget.sqlite3").is_file():
            legacy[name] = ledger_read.totals(folder / "budget.sqlite3")
    result = dict(
        stages=stages,
        new=totals,
        records={str(f.relative_to(ROOT)): sha(f) for f in INPUTS},
        previous_study_ledgers=legacy,
        external_gpt5_original_cost="Not disclosed by the release authors",
        historical_ledger_scope="Entire earlier studies; these amounts are not new costs and are not marginal costs for the selected files.",
    )
    core.save(ACCOUNT, result)
    return result


if __name__ == "__main__":
    print(accounting()["new"])
