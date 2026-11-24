"""Generate and audit the local manuscript's end-to-end result tables.

Does not regenerate old appendix inputs or alter historical result files.
"""
from __future__ import annotations

import argparse
from decimal import Decimal, ROUND_HALF_UP
import json
import re

from studies.public_library_transfer.self_replication import paper as self_followups
from studies.public_library_transfer.self_refinement import domain_panel, prospective_panel, suite_comparisons
from studies.end_to_end import ROOT, OUTPUT, reconstruct, sha

PAPER = ROOT / "DNA_latex"
SOURCE_TRIALS = ROOT / "studies/results/library-sources-20261121.json"
FORM_REPAIR = ROOT / "studies/results/form-public-repair-20261121.json"
NOVEMBER_RESULTS = {key: ROOT / "studies/results" / (name + "-20261123.json") for key, name in {
    "chart": "svg-chart-interfaces", "table": "table-library-sources", "editor": "expression-editor-sources",
    "flex_conflict": "flex-requirement-conflict", "chart_conflict": "svg-chart-requirement-conflict",
    "fixture": "svg-chart-fixture", "react_calibration": "react-blog-calibration", "coverage": "webbench-coverage", "reuse_costs": "reuse-costs",
    "editor_empty": "expression-editor-empty-plan", "unseen": "expression-editor-unseen",
    "window": "expression-editor-window", "admission": "expression-editor-unseen-notes-admission",
    "enumeration": "table-controller-enumeration", "selection": "table-controller-selection", "interface_examples": "expression-editor-interface-examples",
    "chart_recovery": "svg-chart-library-refinement", "table_shell": "library-refinement-table",
    "contract_preparation": "contract-library-table", "rebuilt": "compatible-library-rebuild",
    "fresh_plans": "compatible-table-local-plans", "chart_backends": "compatible-chart-rebuild",
    "chart_backend_fences": "compatible-chart-rebuild-fences", "local_chart": "svg-chart-compact-local",
    "chart_local_comparison": "svg-chart-local-prompt-comparison", "chart_local_fences": "svg-chart-local-fences",
    "public_controllers": "public-controller-table", "refinement_costs": "library-refinement-accounting",
    "constrained_table": "schema-constrained-table",
    "transfer_overview": "public-library-transfer-overview", "transfer_delivery": "public-library-transfer-delivery",
    "transfer_remote": "public-library-transfer-remote", "transfer_milestones": "public-library-transfer-remote-milestones",
    "transfer_archive_deployers": "public-library-transfer-historical-models",
    "transfer_original_duo": "public-library-transfer-duo-original-sources",
    "transfer_table_space": "public-library-transfer-table-space",
    "transfer_extra": "public-library-transfer-extra", "transfer_holdout": "public-library-transfer-holdout",
    "transfer_open": "public-library-transfer-open", "transfer_boolean": "public-library-transfer-boolean",
    "transfer_prompt": "public-library-transfer-prompt", "transfer_public_checks": "public-library-transfer-duo-public-admission",
    "drag": "draw-pointer-transition", "drag_length": "draw-pointer-length"}.items()}
COHORTS = {"interface": "dom1 / form", "expansion": "calculator / table / bom", "draw": "draw (milestones)"}
MODELS = {"openai/gpt-5": "GPT-5", "anthropic/claude-sonnet-4.5": "Claude Sonnet 4.5",
          "openai/gpt-oss-120b": "GPT-OSS-120B", "mistralai/mistral-small-3.2-24b-instruct": "Mistral Small"}


def percentage(value):
    return str(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def cell(value):
    return f"{value['passed']}/{value['total']} ({percentage(value['rate_percent'])}\\%)"


def table(label, caption, headers, rows, spec=None, wide=False):
    kind = "table*" if wide else "table"
    spec = spec or "l" + "r" * (len(headers) - 1)
    placement = "[t]" if wide else "[htbp]"
    lines = [r"\begin{" + kind + "}" + placement, r"\centering\small", r"\setlength{\tabcolsep}{4pt}",
             r"\caption{" + caption + "}", r"\label{" + label + "}",
             r"\begin{tabular}{@{}" + spec + "@{}}", r"\toprule",
             " & ".join(headers) + r" \\", r"\midrule"]
    lines.extend(" & ".join(row) + r" \\" for row in rows)
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{" + kind + "}"]
    return "\n".join(lines) + "\n"


BUILDERS = ("openai/gpt-5", "anthropic/claude-sonnet-4.5")


def builder_cells(groups, endpoint):
    baseline = groups[BUILDERS[0]][endpoint]["free"]
    assert all(groups[b][endpoint]["free"] == baseline for b in BUILDERS)
    assert all(groups[b][endpoint]["plan"]["total"] == baseline["total"] for b in BUILDERS)
    return [cell(baseline), *(cell(groups[b][endpoint]["plan"]) for b in BUILDERS)]


def matched_table(studies):
    rows = []
    for study in studies:
        limit = f"{study['config']['max_tokens']:,}"
        for rep in (1, 2):
            direct, plan = [study['groups'][f'{arm}-{rep}'] for arm in ('free', 'plan')]
            pairs = study["paired"][str(rep)]
            total = sum(pairs.values())
            rows.append([study["project"], MODELS[study["model"]], limit, str(rep),
                         f"{pairs['direct_only'] + pairs['both_pass']}/{total}",
                         f"{pairs['plan_only'] + pairs['both_pass']}/{total}",
                         f"{direct['cost']['settled_usd']:.3f}", f"{plan['cost']['settled_usd']:.3f}"])
    return table("tab:matched-workflows",
        "Matched workflow experiments on two Web-Bench projects. Each row gives both workflows the full public requirements, the same model, one preparation and five targets. Denominators count jointly observed target positions. A failed build contributes five workflow failures. USD charges include preparation and repairs. The GPT-5 canvas follow-up raised both response limits after initial construction failures. Each repetition uses fresh preparations.",
        ["Project", "Model", "Output cap", "Repeat", "Direct", "GUI-DNA", "Direct USD", "GUI-DNA USD"], rows, wide=True)


def behavior_table(data):
    rows = []
    for label, stage in [("capacity_followup","canvas-capacity-20261118"), ("model_replication","canvas-sonnet-20261118")]:
        for rep in (1,2):
            shots = data["canvas_controls"][label][str(rep)]
            speed = data["canvas_speed"]["libraries"][f"{stage}/plan-{rep}"]
            assert speed["available"] and shots["variants_unobservable"] == 0
            n = shots["variants_tested"]
            assert n == len(speed["rows"]) and all(None not in r["values"] for r in speed["rows"].values())
            changes = []
            for name, delta in speed["witnesses"].items():
                assert all(round(x,2)==round(delta[0],2) for x in delta)
                field = name.removeprefix("field/").replace("_", r"\_")
                changes.append(r"\texttt{" + field + "} $" + f"{delta[0]:+.2f}" + "$")
            rows.append([MODELS[data["canvas_pilots"][label]["model"]],str(rep),str(n),
                         str(shots["variants_with_shooting"]),", ".join(changes)])
    return table("tab:canvas-behavior",
        "Public behavior probes on the four 32,000-token canvas libraries. Configurations comprise two examples and every one-field substitution from the second into the first. Shooting counts configurations in which the firing key increased the bullet count relative to a neutral key. The last column lists every field that changed the acceleration response by at least two pixels in all three seeds. Values are changes from the first example in the extra distance traveled over 96 ms with the acceleration key held. Each row describes one library.",
        ["Builder","Repeat","Configs tested","Shoot","Field and change (px)"],rows,wide=True)


def _render_with_matrix(data):
    columns = ["Direct", "GUI-DNA (GPT-5)", "GUI-DNA (Sonnet)"]
    rows = [[COHORTS[c], *builder_cells(value["by_builder"], endpoint)]
            for c, value in data["cohorts"].items() for endpoint in ("current",)]
    replay = json.loads((ROOT / "studies/results/primary-replay.json").read_text())
    trials = json.loads(SOURCE_TRIALS.read_text())
    paired_rows = []
    for project, study in trials.items():
        arms = ("direct", "reference", "ai")
        paired = [str(n) for n in study["targets"]
                  if all(study["cells"][arm][str(n)]["passed"] is not None for arm in arms)]
        scores = []
        for arm in arms:
            passed = sum(study["cells"][arm][n]["passed"] for n in paired)
            scores.append(cell({"passed": passed, "total": len(paired), "rate_percent": 100 * passed / len(paired)})
                          if paired else "---")
        paired_rows.append([project + " (paired)", *scores, "---"])
    today = {k: json.loads(v.read_text()) for k, v in NOVEMBER_RESULTS.items()}
    arms = ("direct", "reference", "ai")

    def workflow_row(label, observations):
        available = [a for a in arms if any(r[a] is not None for r in observations.values())]
        keys = ([k for k in observations if all(observations[k][a] is not None for a in available)]
                if len(available) >= 2 else [])
        return [label, *(f"{sum(observations[k][a] for k in keys)}/{len(keys)}"
                         if keys and a in available else "---" for a in arms)]

    def staged(study, stage):
        return {k: {a: row[a][stage]["passed"] for a in arms} for k, row in study["targets"].items()}

    chart = today["chart"]
    chart_cells = {n: {a: chart["cells"]["reference_typed" if a == "reference" else a][str(n)]["passed"]
                       for a in arms} for n in chart["targets"]}
    from studies.paper_performance import performance_matrix, render_matrix
    matrix = performance_matrix(data, replay, trials, today)
    main = render_matrix(matrix, [*self_followups.rows(), *prospective_panel.rows(),
                                  *prospective_panel.confirmation_evidence()['rows']],
                         suite_comparisons.evidence()["models"], domain_panel.rows())
    appendix = [r"\section{Detailed End-to-End Results}", r"\label{app:details}",
                "Library builders remain separate in every comparison. The shared direct baseline appears once per row. Each row uses only its own generator and target protocol."]
    appendix.append(table("tab:previous-workflows", "Earlier three-workflow pilots and retrospective AI-only studies. Entries are current files passed / jointly observed targets (percent). The direct comparator for the original SVG milestones had to return a complete file map. Builders share one direct comparator in each retrospective row.",
                          ["Study", "No library", "Human + DNA", "GPT-5 + DNA", "Sonnet + DNA"],
                          paired_rows + [[study, direct, "---", gpt, sonnet] for study, direct, gpt, sonnet in rows], wide=True))
    sensitivity_rows = [workflow_row("Table editor, one repair", staged(today["table"], "after_public_repair")),
                        workflow_row("Editor, one repair", staged(today["editor"], "after_public_repair")),
                        workflow_row("Charts, asset test excluded", {n: chart_cells[n] for n in chart["blank_discriminating"]["tasks"]})]
    appendix.append(table("tab:new-source-sensitivity", "Each row uses its own common observed targets. Repairs use only public validation feedback. The chart row removes the predeclared file passed by the blank control after calibration and before generation.",
                          ["Protocol", "Direct", "Human", "GPT-5"], sensitivity_rows))
    rows = [[p, *builder_cells(groups, endpoint)] for value in data["cohorts"].values()
            for p, groups in value["by_project_builder"].items() for endpoint in ("current",)]
    appendix.append(table("tab:endtoend-project", "Per-project results, with library builders in separate columns. Target generators are pooled only within each project. Draw uses five milestones; the other studies use all twenty prefixes.", ["Project", *columns], rows))
    names = {"interface":"dom1/form", "expansion":"Three-project", "draw":"draw"}
    generators = sorted({model for cohort in data["cohorts"].values() for model in cohort["by_generator_builder"]})
    rows = []
    for cohort, value in data["cohorts"].items():
        for model in generators:
            groups = value["by_generator_builder"].get(model)
            scores = builder_cells(groups, "current") if groups else ["---"] * 3
            rows.append([names[cohort], MODELS[model], *scores])
    appendix.append(table("tab:endtoend-generator", "Separate target-generator and library-builder results. Three-project denotes calculator/table/bom; projects remain pooled within that row, and individual project results appear above. The header's model names identify library builders; the Generator column identifies the model producing target code or plans.", ["Study", "Generator", *columns], rows, spec="llrrr"))
    # Keep absent generators visible across the two supplied-library protocols.
    model_scores = {}
    for suite in replay["suites"]:
        for record in suite["models"]:
            model = record["model"]
            scores = model_scores.setdefault(model, {})
            if suite["suite"] == "webbench" and model == "google/gemma-3-12b-it":
                continue
            counts = record["counts"]
            scores[suite["suite"]] = [f"{counts[m]['final_all']}/{counts[m]['n']}" for m in ("free", "dna")]
    rows = [[model.split("/")[-1], *scores.get("todomvc", ["---"] * 2),
             *scores.get("webbench", ["---"] * 2)] for model, scores in sorted(model_scores.items())]
    appendix.append(table("tab:supplied-models", "Supplied libraries by target generator. Each pair shows no library and human-library assembly. Dashes mark absent or excluded observations; the seven-model dom1 analysis excludes Gemma uniformly.",
                          ["Generator", "Todo direct", "Todo DNA", "dom1 direct", "dom1 DNA"], rows))
    rows = []
    for project, study in trials.items():
        for arm, name in (("reference", "Human + DNA"), ("ai", "GPT-5 + DNA"), ("direct", "No library")):
            entries = list(study["cells"][arm].values())
            rows.append([project, name, str(len(entries)), str(sum(e["passed"] is None for e in entries)),
                         str(sum(e["status"] == "invalid_output" for e in entries)),
                         str(sum(e["passed"] is True for e in entries))])
    appendix.append(table("tab:three-arm-coverage", "All scheduled positions in the single-response Mistral comparisons. Invalid counts format and compile failures. Missing responses have unknown outcomes. The main table uses matched observations; passes here count every observed position.",
                          ["Project", "Workflow", "Planned", "Missing", "Invalid", "Passed"], rows))
    enum = today["enumeration"]
    assert enum["uniform"]["settled_positions"] == 64 * 20
    fraction_rows = []
    for offset in range(1, 6):
        cells = []
        for start in (0, 5, 10, 15):
            target = start + offset
            values = enum["targets"][f"task-{target}"]
            assert values["observed"] == values["possible"] == 64
            cells.extend([str(target), f"{values['passing']}/64"])
        fraction_rows.append(cells)
    appendix.append(r"The table-editor interface has six independent enable/disable choices. For a current file $k$ and controller subset $m$, let $A_k(m)$ denote its binary official score. The exact expected number of files passed by uniform choices is $\sum_{k=1}^{20}\sum_{m=1}^{64} A_k(m)/64$. Each setting has equal weight. Every cell uses one observed browser outcome, including hash-matched retained reports. The expectation is exact for this finite observed matrix. By linearity it also applies to one uniformly sampled configuration reused for all twenty files; the probability of passing every file can differ between these two sampling schemes.")
    appendix.append(table("tab:table-random", "Exact probability that a uniform controller configuration passes each table-editor file. All 64 executable controller subsets were evaluated. A probability refers to configurations on one official current file. There were no new model requests.",
                          ["Task", "Pass", "Task", "Pass", "Task", "Pass", "Task", "Pass"], fraction_rows, spec="rrrrrrrr"))
    select = today["selection"]["summary"]
    appendix.append(f"Matching checksums of the twenty first-response pages to the enumerated configurations recovers the exact model choices. "
                    f"The planner enabled {select['chosen_bindings']} controller bindings in total "
                    f"({select['mean_chosen']:.2f} per target). The smallest single configuration passing every file enabled "
                    f"{select['smallest_perfect_fixed_cardinality']} per target. On {select['chosen_globally_minimal_on_current_file']} of twenty "
                    "current files, the planner selected a minimum-cardinality passing configuration. "
                    "All pages shipped the same implementation modules. These counts describe enabled bindings, without measuring runtime.")
    drag, relative = today["drag"], today["drag_length"]
    assert relative["primary_sha256"] == sha(NOVEMBER_RESULTS["drag"])
    assert drag["settings"] == relative["settings"] == {"minimum length": 162}
    abbreviations = {"release position": "E", "release displacement": "E", "minimum length": "L",
                     "long control unavailable": "---"}
    drag_rows = []
    for model, generator_label in (("openai__gpt-5", "GPT-5"), ("openai__gpt-oss-120b", "GPT-OSS")):
        for builder, workflow_name in (("direct", "No library"), ("openai__gpt-5", "GPT-5 library"),
                                       ("anthropic__claude-sonnet-4.5", "Claude library")):
            group_key = model + "/" + builder
            observations = [arm["pairs"][group_key][k] for arm in (drag, relative) for k in ("task_8", "task_12")]
            drag_rows.append([generator_label, workflow_name, *(abbreviations[v] for v in observations)])
    appendix.append(table("tab:drag-endpoints", "Drawing editor, identical three-unit mouse drag with a nine-unit brush. Columns 3--4 use the registered absolute-coordinate control. Columns 5--6 are a post-hoc analysis allowing a translation of both endpoints. E denotes a line ending at the three-unit release displacement, L a line extended to nine units. The expected pair is E at milestone 8 and L at 12. A dash marks a failed eighteen-unit control or unavailable public widget. Each measurement uses two fresh contexts.",
                          ["Generator", "Workflow", "Absolute 8", "Absolute 12", "Relative 8", "Relative 12"],
                          drag_rows, spec="llcccc"))
    repair = json.loads(FORM_REPAIR.read_text())
    repair_rows = []
    for arm, name in (("reference", "Human + DNA"), ("ai", "GPT-5 + DNA"), ("direct", "No library")):
        positions = [r for r in repair["rows"] if r["arm"] == arm]
        retried = [r for r in positions if not r["reused"]]
        repair_rows.append([name, str(len(retried)), str(sum(r["after"] is None for r in retried)),
                            str(sum(r["after"] is True for r in retried)),
                            str(sum(r["after"] is True for r in positions)) + "/" +
                            str(sum(r["after"] is not None for r in positions))])
    appendix.append(table("tab:public-form-repair", "Post-hoc form diagnostic. A public parse or compile error triggers one repair. Executable first pages retain their original score. Missing counts interrupted repairs; the final column uses each arm's observable positions.",
                          ["Workflow", "Repairs", "Missing", "Recovered", "Final"], repair_rows))
    appendix += [r"\clearpage", r"\subsection{Independent Library Rebuilds}", r"\input{library_rebuild_notes}"]
    rebuilt, fresh = today["rebuilt"], today["fresh_plans"]
    arms = [("original", "Original GPT-5"), ("plain-1", "Codex ordinary 1"), ("plain-2", "Codex ordinary 2"),
            ("contract-1", "Codex state contract 1"), ("contract-2", "Codex state contract 2")]
    replay = rebuilt["cohorts"]
    replacement_rows = []
    for arm, label in arms:
        cells = [replay["primary_20261123"]["summary"][arm], replay["independent_archive"]["summary"][arm],
                 fresh["totals"].get(arm, {}), rebuilt["fixed_documentation_example_1"]["summary"][arm]]
        replacement_rows.append([label, *(f"{c['passed']}/{c['observed']}" if c.get('observed') else "---" for c in cells)])
    appendix.append(table("tab:backend-rebuild", "Compatible table libraries evaluated on the same twenty targets in each column. "
                          "The two Mistral columns replay independent archived first responses made with the original GPT-5 library. "
                          "The Qwen2.5-0.5B column uses fresh source-blind plans. All five backends expose the same public interface, so each target uses one shared response per column. "
                          "The last column deploys the first documentation example everywhere. Each Codex row is an independent first build.",
                          ["Table backend", "Mistral (Nov. 23)", "Mistral (earlier)", "Fresh Qwen", "Fixed example"], replacement_rows))
    new_interfaces = today["constrained_table"]["arms"]
    public_builds = today["public_controllers"]["repeats"]
    public_rows = []
    for arm, label in (("original", "Original GPT-5"), ("rep-1", "Public Codex 1"), ("rep-2", "Public Codex 2")):
        group = new_interfaces[arm]
        admitted = fresh["strictly_valid"] if arm == "original" else sum(
            row["status"] == "valid" for row in public_builds[arm]["targets"].values())
        assert group["received"] == group["valid"] == 20
        public_rows.append([label, f"{admitted}/20", *(f"{group['passed'][k]}/20" for k in ("free_strict", "strict", "fixed"))])
    appendix.append(table("tab:public-controller-decoding", "Table libraries evaluated with Qwen on identical current targets. "
                          "The two new builders each designed a fresh interface from public requirements and starter files. "
                          "Free plans are first text responses. Constrained plans use the same input messages and weights, "
                          "with legal field values selected during decoding. The fixed control deploys the first example on every target.",
                          ["Table backend", "Free plans valid", "Free plans passed", "Constrained passed", "Fixed passed"], public_rows))
    appendix += [r"\section{Construction and Generation Accounting}", r"\label{app:cost}",
                 r"Table~\ref{tab:construction} separates library builders' recorded construction charges, including unsuccessful attempts. Each row covers that builder's libraries for the named study. Exposure includes unresolved transport reservations. Local compute and unlogged human preparation time are excluded."]
    bills = []
    names = {"direct": "Direct", "reference": "Reference", "ai": "GPT-5 library"}
    labels = {"svg-chart": "SVG charts", "table": "Table editor", "expression-editor": "Expression editor"}
    for project, record in today["reuse_costs"]["projects"].items():
        for arm, group in record["workflows"].items():
            end = group["ordered"][-1]
            observed = group["observed_current_files"]
            bills.append([labels[project], names[arm],
                          f"{group['passed_current_files']}/{observed}" if observed else "---",
                          f"{group['preparation_settled_microusd'] / 1e6:.6f}",
                          f"{end['cumulative_settled_microusd'] / 1e6:.6f}",
                          f"{end['cumulative_exposure_microusd'] / 1e6:.6f}"])
    appendix.append(table("tab:twenty-costs",
                          "Provider charges in USD across each twenty-target schedule. Preparation is charged once. "
                          "Total includes allowed public repairs. Exposure adds unresolved reservations. "
                          "Upstream human labor and local compute are unpriced. A dash means no observable final target endpoints. "
                          "This table covers the original two-attempt editor preparation and the enumerated reference guide for charts.",
                          ["Project", "Workflow", "Passed/obs.", "Prepare", "Total", "Exposure"], bills))
    rows = [[COHORTS[c], MODELS[b], f"{values[b]['settled_usd']:.6f}", f"{values[b]['exposure_usd']:.6f}"]
            for c, values in data["costs"]["construction_by_builder"].items() for b in BUILDERS]
    appendix.append(table("tab:construction", "Library construction in USD, separated by builder. No two builders' bills are pooled into a method comparison.", ["Study", "Builder", "Settled", "Exposure"], rows, spec="llrr"))
    rows = []
    for value in data["costs"]["draw_by_generator_builder"].values():
        rows.append([MODELS[value['generator']], MODELS[value['builder']], f"{value['direct_usd']:.6f}",
                     f"{value['pipeline_usd']:.6f}", f"{value['direct_per_target_usd']:.6f}", f"{value['pipeline_per_target_usd']:.6f}"])
    appendix.append(table("tab:draw-endtoend-cost", "Draw provider receipts in USD. Every comparison covers five direct targets and five GUI-DNA targets. Pipeline cost charges the indicated builder once plus that generator's five plan chains and repairs. Baseline receipts are shared across builder comparisons, and the same library is shared across generator scenarios; do not add these scenarios into an overall study bill. This is observed accounting, not an equal-budget experiment.", ["Generator", "Builder", "Direct / 5", "Build + plans / 5", "Direct / target", "Pipeline / target"], rows, spec="llrrrr"))
    appendix.append(r"The original draw study's complete ledger remains \$3.285408 (provider receipts \$3.28538045), including conditions outside the current comparison. This is a historical billing total, not a pooled method comparison. Micro-dollar rounding occurs per request. These are the original draw charges.")
    from studies.public_library_transfer.paper import tables as transfer_tables
    appendix.extend(transfer_tables(today, table))
    return {"canvas_behavior_table.tex":behavior_table(data), "end_to_end_table.tex": main,
            "end_to_end_details.tex": "\n\n".join(appendix) + "\n"}, matrix


def render(data):
    """Return generated LaTeX files for callers rendering the local paper."""
    return _render_with_matrix(data)[0]


def active_sources():
    seen = {}

    def visit(path):
        if path in seen:
            return
        content = path.read_text()
        seen[path] = content
        for name in re.findall(r"\\input\{([^}]+)\}", content):
            visit(PAPER / (name + ".tex"))
    visit(PAPER / "main.tex")
    return seen


def audit(data, generated):
    for name, expected in generated.items():
        assert (PAPER / name).read_text() == expected, f"Stale generated table: {name}"
    active = active_sources()
    content = "\n".join(v for p, v in active.items() if p.name != "preamble.tex")
    for forbidden in (r"\freelib", "same-library code", "Free+Lib", "free_lib", "90/240", "67/160"):
        assert forbidden not in content, f"Archived comparator still active: {forbidden}"
    for pooled in ("86/160", "93/240", "36/160", "26/240", "79/216", "Build + plans / 10"):
        assert pooled not in content, f"Pooled builder comparison still active: {pooled}"
    labels = re.findall(r"\\label\{(tab:[^}]+)\}", content)
    expected_labels = re.findall(r"\\label\{(tab:[^}]+)\}", "\n".join(generated.values()))
    assert set(labels) == set(expected_labels) and len(labels) == len(set(labels)), "Unregistered table"
    # Current-task scope and protocol disclosures must survive editorial changes.
    for phrase in ("43/108", "36/108", "39/108",
                   "all twenty public requirements", "not a matched total-budget", "retrospective"):
        assert phrase in content, f"Missing primary result/boundary: {phrase}"
    assert not re.search(r"complete.history|full.history|history replay", content, re.I)
    assert not re.search(r"ABSTRACT_MATCHED|SONNET_RESULTS|CANVAS_RESULTS", content)
    body = (PAPER / "main.tex").read_text().split(r"\appendix")[0]
    main_tables = re.findall(r"\\input\{([^}]+)\}", body)
    assert [name for name in main_tables if name + ".tex" in generated] == ["end_to_end_table"]
    assert "tab:matched-workflows" not in labels
    assert "current official task file" in content
    result = {"all_passed": True, "tables": expected_labels,
              "all_active_tables_generated_and_verified": True,
              "primary_view_sha256": sha(OUTPUT), "source_sha256": {**data["source_sha256"], str(SOURCE_TRIALS.relative_to(ROOT)): sha(SOURCE_TRIALS),
                                    str(FORM_REPAIR.relative_to(ROOT)): sha(FORM_REPAIR),
                                    **{f"studies/results/{f}": sha(ROOT / "studies/results" / f)
                                       for f in ("primary-replay.json", "paper-performance-matrix.json",
                                                 "backbone-matrix-20261124.json", "backbone-extension-20261124.json",
                                                 "backbone-form-20261124.json", "backbone-suites-20261124.json", "backbone-overview-20261124.json",
                                                 "backbone-suite-replays-20261124.json", "domain-construction-accounting-20261124.json",
                                                 "domain-construction-accounting-final-20261124.json")},
                                    **{str(p.relative_to(ROOT)): sha(p) for p in NOVEMBER_RESULTS.values()},
                                    **{str(p.relative_to(ROOT)): sha(p) for p in self_followups.SOURCES},
                                    **{str(p.relative_to(ROOT)): sha(p) for p in (*suite_comparisons.SOURCES, suite_comparisons.OUTPUT)},
                                    **{str(p.relative_to(ROOT)): sha(p) for p in (*domain_panel.SOURCES, *domain_panel.DIAGNOSTICS,
                                                                                *prospective_panel.SOURCES, prospective_panel.OUTPUT,
                                                                                prospective_panel.CONFIRMATION, prospective_panel.CONFIRMATION_OUTPUT)},
                                    **{str(p.relative_to(ROOT)): sha(p) for p in self_followups.appendix_sources()}},
              "manuscript_sources_sha256": {p.relative_to(ROOT).as_posix(): sha(p) for p in active},
              "scope": "Reconstructs primary candidates, checks complete generated table text and active manuscript scope; not independent human review or verification of every prose claim."}
    (ROOT / "studies/results/paper_end_to_end_audit.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    self_followups.verify_or_publish(args.write)
    suite_comparisons.verify_or_publish(args.write)
    prospective_panel.verify_or_publish(args.write)
    prospective_panel.verify_confirmation(args.write)
    data = reconstruct()
    assert json.loads(OUTPUT.read_text()) == data
    generated, matrix = _render_with_matrix(data)
    matrix_path = ROOT / "studies/results/paper-performance-matrix.json"
    if args.write:
        matrix_path.write_text(json.dumps(matrix, indent=2) + "\n")
        for name, text in generated.items():
            (PAPER / name).write_text(text)
    assert json.loads(matrix_path.read_text()) == matrix, "Stale published performance matrix"
    report = audit(data, generated)
    print(json.dumps({"all_passed": report["all_passed"], "tables": len(report["tables"])}))


if __name__ == "__main__":
    main()
