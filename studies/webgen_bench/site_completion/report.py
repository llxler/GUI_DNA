"""Reconstruct integer operation passes from portable, per-operation receipts."""

import argparse
from collections import Counter, defaultdict
from pathlib import Path

from studies import ledger_read
from studies.study_io import ROOT, dump, read, sha
from studies.webbench.table.menu_propagation.event_trace import verify as menu_trace
from .. import report as pilot
from ..component_contracts import report as historical

HERE = Path(__file__).resolve().parent
STATE = HERE / "state_updates"
CANDIDATES = HERE / "candidates.json"
JUDGMENTS = HERE / "judgments.json"
SDK = HERE / "sdk-audit.json"
ACCOUNTING = HERE / "accounting.json"
RESULT = ROOT / "studies/results/webgen-site-completion-20261128.json"
SECOND = HERE / "second-judge.json"
NAVIGATION = HERE / "navigation-audit.json"
TABS = HERE / "tab-layout.json"
TAB_VERDICTS = HERE / "tab-layout-judgments.json"
VERTICAL = HERE / "vertical-primary.json"
VERTICAL_SECOND = HERE / "vertical-secondary.json"
LINEAGE = HERE / "page-lineage.json"
COMPLETION = HERE / "independent-completion.json"
FINAL_VERDICTS = HERE / "completed-verdicts.json"
KEYBOARD = ROOT / "studies/webbench/table/keyboard_navigation"
TABLE_RUNS = (KEYBOARD / "result.json", KEYBOARD / "projection-result.json")
MENU = KEYBOARD.parent / "menu_propagation/author_repair/result.json"
MENU_TRACE = KEYBOARD.parent / "menu_propagation/event_trace/result.json"
RECEIPTS = (
    CANDIDATES,
    JUDGMENTS,
    SDK,
    NAVIGATION,
    TABS,
    TAB_VERDICTS,
    VERTICAL,
    VERTICAL_SECOND,
    LINEAGE,
    SECOND,
    COMPLETION,
    FINAL_VERDICTS,
    ACCOUNTING,
    historical.RESULT,
    STATE / "candidates.json",
    STATE / "judgments.json",
    STATE / "grounded-candidates.json",
    STATE / "grounded-judgments.json",
    STATE / "program-candidates.json",
    STATE / "program-judgments.json",
    *TABLE_RUNS,
    MENU,
    MENU_TRACE,
    menu_trace.EVIDENCE,
)
LEDGERS = {
    "generation": "webgen-site-completion",
    "judge": "webgen-site-completion-judge",
    "optional_generation": "webgen-native-state",
    "optional_judge": "webgen-native-state-judge",
    "grounded_generation": "webgen-grounded-actions",
    "grounded_judge": "webgen-grounded-actions-judge",
    "program_judge": "webgen-state-program-judge",
    "independent_judge": "webgen-independent-flash",
    "tab_judge": "webgen-native-tabs",
    "vertical_primary": "webgen-vertical-primary",
    "vertical_secondary": "webgen-vertical-secondary",
    "rater_completion": "webgen-rater-completion",
    "missing_verdicts": "webgen-missing-verdicts",
}
MEASURE = "fully passed operations"


def summarize(rows, arms=pilot.ARMS):
    by_arm = {arm: {} for arm in arms}
    for row in rows:
        target = f"{row['site']}/{row['check']}"
        items = by_arm[row["arm"]]
        if target in items:
            raise ValueError(f"Duplicate {row['arm']} record on {target}")
        items[target] = row
        if row["status"] == "judged":
            if row["verdict"] not in ("YES", "PARTIAL", "NO"):
                raise ValueError("Invalid three-level verdict")
        elif row["status"] not in ("start_failed", "missing", "build_failed") or row["verdict"] is not None:
            raise ValueError("Unknown observation status")
    registered = set(by_arm[arms[0]])
    if any(set(items) != registered for items in by_arm.values()):
        raise ValueError("All methods must schedule exactly the same targets")
    known = {
        arm: {key for key, v in items.items() if v["status"] in ("judged", "start_failed")}
        for arm, items in by_arm.items()
    }
    observed = [arm for arm, ids in known.items() if ids]
    joint = set.intersection(*(known[a] for a in observed)) if arms[0] in observed else set()
    runnable = {key for key in joint if all(by_arm[a][key]["status"] == "judged" for a in observed)}
    passes = {a: {key for key in joint if by_arm[a][key]["verdict"] == "YES"} for a in observed}
    groups = {}
    for arm, items in by_arm.items():
        groups[arm] = dict(
            status=dict(sorted(Counter(v["status"] for v in items.values()).items())),
            observed=len(known[arm]),
            start_failed_in_common=0,
        )
        if arm in observed and joint:
            groups[arm].update(
                passes=sorted(passes[arm]),
                passed=len(passes[arm]),
                verdicts=dict(
                    sorted(
                        Counter(items[k]["verdict"] for k in joint if items[k]["status"] == "judged").items()
                    )
                ),
                start_failed_in_common=sum(items[k]["status"] == "start_failed" for k in joint),
            )
    base = passes.get(arms[0], set())
    paired = {
        a: {"direct_only": sorted(base - passed), "method_only": sorted(passed - base)}
        for a, passed in passes.items()
        if a != arms[0]
    }
    return dict(
        registered=len(registered),
        n=len(joint),
        targets=sorted(joint),
        methods=groups,
        paired_vs_first=paired,
        jointly_runnable=dict(
            n=len(runnable),
            targets=sorted(runnable),
            passed={a: len(ids & runnable) for a, ids in passes.items()},
        ),
    )


def by_model(rows, models):
    result = {}
    for tag, model in models.items():
        selected = [r for r in rows if r["model"] == tag]
        sites = sorted({r["site"] for r in selected})
        group = summarize(selected)
        by_site = {}
        methods = {a: set(item["passes"]) for a, item in group["methods"].items() if "passed" in item}
        for site in sites:
            targets = {key for key in group["targets"] if key.split("/", 1)[0] == site}
            by_site[site] = dict(
                n=len(targets), passed={a: len(passes & targets) for a, passes in methods.items()}
            )
        assert sum(row["n"] for row in by_site.values()) == group["n"]
        result[model] = group | dict(sites=sites, by_site=by_site)
    return result


def accounting():
    out = {}
    for name, directory in LEDGERS.items():
        path = ROOT / "artifacts" / (directory + "-20261128") / "budget.sqlite3"
        groups = defaultdict(list)
        for call in ledger_read.calls(path):
            # The shared site plan is charged once for all library-backed arms.
            purpose = call["purpose"]
            phase = (
                "build"
                if purpose.startswith("build/")
                else "direct"
                if "/direct/" in purpose
                else "plan"
                if name.endswith("generation")
                else "judge"
            )
            groups[(call["model"], phase)].append(call)
        out[name] = {
            "totals": ledger_read.totals(path),
            "models": [
                dict(
                    model=model,
                    phase=phase,
                    calls=len(calls),
                    settled_usd=sum(c["actual"] or 0 for c in calls) / 1e6,
                    exposure_usd=sum(c["reserved"] if c["actual"] is None else c["actual"] for c in calls)
                    / 1e6,
                )
                for (model, phase), calls in sorted(groups.items())
            ],
        }
    return out


def replace_human(original, replacements, *, require_model=True):
    def key(row):
        return ((row["model"],) if require_model else ()) + (row["site"], row["check"], row["arm"])

    expected = {key(r) for r in original if r["arm"] == "human"}
    index = {key(r): r for r in replacements}
    if len(index) != len(replacements) or set(index) != expected:
        raise ValueError("A uniform layout correction must cover every scheduled Human operation")
    return [index[key(r)] if r["arm"] == "human" else r for r in original]


def independent_agreement(primaries, ratings, second):
    lookup = {(r["site"], r["check"], r["arm"]): r for r in primaries if r["model"] == "deepseek-flash"}
    secondary = []
    assert len(second["subset"]) == 9 and len(ratings) == 18
    for v in ratings:
        assert v["check"] == second["subset"][v["site"]]
        primary_row = lookup[v["site"], v["check"], v["arm"]]
        if v["status"] == "judged" and primary_row["status"] == "judged":
            secondary.append(
                dict(
                    site=v["site"],
                    check=v["check"],
                    arm=v["arm"],
                    primary=primary_row["verdict"],
                    second=v["verdict"],
                )
            )
    paired_sites = [
        s for s in second["subset"] if {v["arm"] for v in secondary if v["site"] == s} == {"human", "direct"}
    ]
    return dict(
        model=second["model"],
        qualified=second["calibration"]["qualified"],
        rows=secondary,
        registered=18,
        n=len(secondary),
        exact=sum(r["primary"] == r["second"] for r in secondary),
        binary=sum((r["primary"] == "YES") == (r["second"] == "YES") for r in secondary),
        paired_sites=sorted(paired_sites),
        paired_passes={
            judge: {
                a: sum(r[judge] == "YES" for r in secondary if r["site"] in paired_sites and r["arm"] == a)
                for a in ("direct", "human")
            }
            for judge in ("primary", "second")
        },
    )


def reconstruct():
    source = read(CANDIDATES)
    run = read(JUDGMENTS)
    assert run["candidates"] == sha(CANDIDATES) and run["calibration"]["qualified"]
    models = {t: m for t, m in source["models"].items() if t in source["rows"]}
    for r in run["rows"]:
        page = source["rows"][r["model"]][r["site"]][r["arm"]]
        if r["status"] == "judged":
            assert page["status"] == "valid" and r.get("source")
        if page["status"] != "valid":
            assert r["status"] == ("start_failed" if page["status"] == "invalid" else page["status"])
    vertical, vertical_second = read(VERTICAL), read(VERTICAL_SECOND)
    assert all(
        batch["candidates"] == sha(TABS) and batch["original_candidates"] == sha(CANDIDATES)
        for batch in (vertical, vertical_second)
    )
    assert vertical["judge"] == run["route"]["model"] and vertical_second["judge"] == read(SECOND)["model"]
    lineage = read(LINEAGE)
    assert lineage["candidates"] == sha(CANDIDATES)
    original_primary = by_model(run["rows"], models)
    corrected_rows = replace_human(run["rows"], vertical["rows"])
    followup = read(FINAL_VERDICTS)
    assert (
        followup["baseline"] == sha(JUDGMENTS)
        and followup["vertical"] == sha(VERTICAL)
        and followup["judge"] == vertical["judge"]
    )

    def case_id(row):
        return row["model"], row["site"], row["check"], row["arm"]

    additions = {case_id(r): r for r in followup["rows"]}
    assert len(additions) == len(followup["rows"]) and set(additions) == {
        case_id(r) for r in corrected_rows if r["status"] == "missing"
    }
    layout_candidates = read(TABS)["candidates"]
    for (tag, site, index, arm), r in additions.items():
        expected = (
            layout_candidates[tag][site]["vertical"] if arm == "human" else source["rows"][tag][site][arm]
        )
        assert r["candidate"] == expected["sha256"]
    corrected_rows = [additions.get(case_id(r), r) for r in corrected_rows]
    primary = by_model(corrected_rows, models)
    for tag, model in models.items():
        primary[model]["replayed"] = {
            arm: sorted(
                f"{s}/{i}"
                for (t, s, i, a), r in additions.items()
                if t == tag and a == arm and r["status"] == "judged"
            )
            for arm in pilot.ARMS
        }
    layout_changes = {}
    for tag, model in models.items():
        old = [r | {"arm": "horizontal"} for r in run["rows"] if r["model"] == tag and r["arm"] == "human"]
        updated = [
            r | {"arm": "vertical"} for r in corrected_rows if r["model"] == tag and r["arm"] == "human"
        ]
        layout_changes[model] = summarize(old + updated, ("horizontal", "vertical"))

    _, prior_rows = historical.website_groups()
    prior = by_model(prior_rows, models)
    official_sites = set(next(iter(source["rows"].values())))
    assert len(official_sites) == 9 and all(set(pages) == official_sites for pages in source["rows"].values())
    assert all(set(g["sites"]).isdisjoint(official_sites) for g in prior.values())
    assert all(len(g["sites"]) == 9 for g in prior.values())
    extras = {}
    for method, c, j in [
        ("optional", STATE / "candidates.json", STATE / "judgments.json"),
        ("grounded", STATE / "grounded-candidates.json", STATE / "grounded-judgments.json"),
        ("program_replay", STATE / "program-candidates.json", STATE / "program-judgments.json"),
    ]:
        cand, record = read(c), read(j)
        assert record["candidates"] == sha(c) and record["judge"] == run["route"]["model"]
        sites = sorted({r["site"] for r in record["rows"]})
        assert sites == ["000068", "000084", "000099"]
        base = [
            r | {"arm": "original"}
            for r in run["rows"]
            if r["model"] == "deepseek-flash" and r["site"] in sites and r["arm"] == "human"
        ]
        summary = summarize(base + record["rows"], ("original", "active", "inert"))
        extras[method] = summary | dict(
            sites=sites,
            identical_twins=[
                site
                for site in sites
                if cand["rows"][site]["active"].get("sha256")
                and cand["rows"][site]["active"]["sha256"] == cand["rows"][site]["inert"].get("sha256")
            ],
        )
        if method == "grounded":
            extras[method]["browser_replay"] = cand["behavior"]
        elif method == "program_replay":
            extras[method]["browser_replay"] = cand["observations"]
    tab_data, tab_judgments = read(TABS), read(TAB_VERDICTS)
    assert tab_data["original"] == sha(CANDIDATES) and tab_judgments["candidates"] == sha(TABS)
    assert tab_judgments["judge"] == run["route"]["model"]
    tab_totals = Counter()
    for tag, websites in tab_data["labels"].items():
        if tag == "archived-flash":
            continue
        assert set(websites) == official_sites
        for site, views in websites.items():
            if "status" in views:
                continue
            assert all(t["found"] for sequence in views.values() for t in sequence)
            a, b = views["horizontal"], views["vertical"]
            assert [(t["name"], t["index"]) for t in a] == [(t["name"], t["index"]) for t in b]
            tab_totals["pages"] += 1
            tab_totals["tabs"] += len(a)
            horizontal = sum(t["labelled"] for t in a)
            vertical = sum(t["labelled"] for t in b)
            tab_totals["horizontal"] += horizontal
            tab_totals["vertical"] += vertical
            tab_totals[
                "improved" if vertical > horizontal else "declined" if vertical < horizontal else "tied"
            ] += 1
    tab_summary = dict(counts=dict(tab_totals), ranking=tab_judgments["rows"])
    second = read(SECOND)
    assert second["candidates"] == sha(CANDIDATES)
    initial_ratings = replace_human(second["rows"], vertical_second["rows"], require_model=False)
    recovered = read(COMPLETION)
    assert recovered["direct_judgments"] == sha(SECOND) and recovered["human_judgments"] == sha(
        VERTICAL_SECOND
    )
    assert recovered["subset"] == second["subset"] and recovered["model"] == second["model"]

    def rating_key(row):
        return row["site"], row["check"], row["arm"]

    replacements = {rating_key(r): r for r in recovered["rows"]}
    assert len(replacements) == len(recovered["rows"]) and set(replacements) == {
        rating_key(r) for r in initial_ratings if r["status"] != "judged"
    }
    final_ratings = [replacements.get(rating_key(r), r) for r in initial_ratings]
    agreement = independent_agreement(corrected_rows, final_ratings, second)
    original_agreement = independent_agreement(run["rows"], second["rows"], second)
    costs = read(ACCOUNTING)
    for name, f in [
        ("generation", CANDIDATES),
        ("judge", JUDGMENTS),
        ("optional_generation", STATE / "candidates.json"),
        ("optional_judge", STATE / "judgments.json"),
        ("grounded_generation", STATE / "grounded-candidates.json"),
        ("grounded_judge", STATE / "grounded-judgments.json"),
        ("program_judge", STATE / "program-judgments.json"),
        ("independent_judge", SECOND),
        ("tab_judge", TAB_VERDICTS),
        ("vertical_primary", VERTICAL),
        ("vertical_secondary", VERTICAL_SECOND),
        ("rater_completion", COMPLETION),
        ("missing_verdicts", FINAL_VERDICTS),
    ]:
        assert costs[name]["totals"] == read(f)["cost"]
    costs_usd = {
        key: sum(round(r["totals"][key] * 1e6) for r in costs.values()) / 1e6
        for key in ("settled_usd", "exposure_usd")
    }
    totals = [v["totals"] for v in costs.values()]
    for f in TABLE_RUNS:
        table = read(f)
        direct = read(KEYBOARD.parent / "action_sequences/selection_mode/result.json")
        assert [r for r in table["rows"] if r["arm"] == "direct"] == [
            r for r in direct["rows"] if r["arm"] == "direct"
        ]
        assert all(table["calibrated"].values())
        for arm in ("direct", "self-a", "self-b", "fixed-a", "fixed-b"):
            records = [r for r in table["rows"] if r["arm"] == arm]
            assert sorted(r["task"] for r in records) == list(range(1, 21))
            assert all(type(r["passed"]) is bool for r in records)
        totals.append(table["cost"])
    menu_trace.portable()
    totals.extend(read(path)["cost"] for path in (MENU, MENU_TRACE))
    campaign = {
        key: sum(round(r[key] * 1e6) for r in totals) / 1e6 for key in ("settled_usd", "exposure_usd")
    }
    campaign.update(
        calls=sum(r["calls"] for r in totals), unsettled_calls=sum(r["unsettled_calls"] for r in totals)
    )
    assert campaign["exposure_usd"] <= 20
    return dict(
        measure=MEASURE,
        criterion="YES",
        judge=run["route"]["model"],
        primary=primary,
        original_layout=original_primary,
        human_layout_comparison=layout_changes,
        previous_nine=prior,
        updates=extras,
        navigation=tab_summary,
        independent=agreement,
        original_independent=original_agreement,
        spend=costs_usd,
        campaign=campaign,
        costs=costs,
        sources={str(f.relative_to(ROOT)): sha(f) for f in RECEIPTS},
    )


def attach(matrix):
    doc = read(RESULT)
    for model, group in doc["primary"].items():
        matrix[model]["webgen_completion"] = dict(
            measure=MEASURE,
            judge=doc["judge"],
            sites=group["sites"],
            targets=group["targets"],
            n=group["n"],
            registered=group["registered"],
            passed={a: v["passed"] for a, v in group["methods"].items() if "passed" in v},
            jointly_runnable=group["jointly_runnable"],
            start_failures={a: v["start_failed_in_common"] for a, v in group["methods"].items()},
            excluded_build_arms=[
                a for a, v in group["methods"].items() if v["status"] == {"build_failed": group["registered"]}
            ],
            source=str(RESULT.relative_to(ROOT)),
            candidate_sources={
                a: str((TABS if a == "human" else CANDIDATES).relative_to(ROOT)) for a in pilot.ARMS
            },
            protocols={"human": str((HERE / "SDK_NAVIGATION.md").relative_to(ROOT))},
            supplemental_records={
                a: [str(FINAL_VERDICTS.relative_to(ROOT))]
                for a, targets in group["replayed"].items()
                if targets
            },
            replayed_targets=group["replayed"],
            implementation_sources={
                a: str((VERTICAL if a == "human" else JUDGMENTS).relative_to(ROOT)) for a in pilot.ARMS
            },
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--ledgers", action="store_true")
    args = parser.parse_args()
    if args.write or args.ledgers:
        table_files = [
            ("table-keyboard-navigation", TABLE_RUNS[0]),
            ("table-membership-projection", TABLE_RUNS[1]),
            ("table-menu-author-repair", MENU),
            ("table-menu-event-trace", MENU_TRACE),
        ]
        for name, record in table_files:
            db = ROOT / "artifacts" / (name + "-20261128") / "budget.sqlite3"
            assert ledger_read.totals(db) == read(record)["cost"]
        costs = accounting()
        if args.write and not ACCOUNTING.exists():
            dump(ACCOUNTING, costs)
        assert costs == read(ACCOUNTING)
    report = reconstruct()
    if args.write and not RESULT.exists():
        dump(RESULT, report)
    assert report == read(RESULT)
    print("Verified full passes, paired targets, both SDK controls and per-method costs.")
