"""Generate and audit the local manuscript's end-to-end result tables.

Does not regenerate old appendix inputs or alter historical result files.
"""
from __future__ import annotations

import argparse
from decimal import Decimal, ROUND_HALF_UP
import json
import re

from studies.end_to_end import ROOT, OUTPUT, reconstruct, sha

PAPER = ROOT / "DNA_latex"
COHORTS = {"interface": "dom1 / form", "expansion": "calculator / table / bom", "draw": "draw (milestones)"}
MODELS = {"openai/gpt-5": "GPT-5", "anthropic/claude-sonnet-4.5": "Claude Sonnet 4.5",
          "openai/gpt-oss-120b": "GPT-OSS-120B", "mistralai/mistral-small-3.2-24b-instruct": "Mistral Small"}


def percentage(value):
    return str(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def cell(value):
    return f"{value['passed']}/{value['total']} ({percentage(value['rate_percent'])}\\%)"


def outcomes(result):
    return [cell(result[endpoint][method]) for endpoint in ("current", "history") for method in ("free", "plan")]


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


def render(data):
    columns = ["Direct", "GUI-DNA (GPT-5)", "GUI-DNA (Sonnet)"]
    rows = [[COHORTS[c], endpoint.title(), *builder_cells(value["by_builder"], endpoint)]
            for c, value in data["cohorts"].items() for endpoint in ("current", "history")]
    main = table("tab:endtoend", "Web-Bench results separated by library builder. The two GUI-DNA columns identify GPT-5-built and Claude-Sonnet-4.5-built libraries, not target generators. Each row uses identical target keys and denominators. Direct is one shared no-library baseline, shown once; it is not an additional sample for each library. Cells are final passes / candidates (percent). Target generators are pooled within each explicitly named study; their separate results appear in Appendix~\\ref{app:details}. Construction adds information and compute (Section~\\ref{sec:setup}).", ["Study", "Endpoint", *columns], rows, wide=True)
    appendix = [r"\section{Detailed End-to-End Results}", r"\label{app:details}",
                "Library builders remain separate in every comparison. The shared direct baseline appears once per row. Generator and project breakdowns retain the same target keys for all three columns; no best-library selection or independent replication of shared baselines is performed."]
    rows = [[p, endpoint.title(), *builder_cells(groups, endpoint)] for value in data["cohorts"].values()
            for p, groups in value["by_project_builder"].items() for endpoint in ("current", "history")]
    appendix.append(table("tab:endtoend-project", "Per-project results, with library builders in separate columns. Target generators are pooled only within each project. Draw uses five milestones; the other studies use all twenty prefixes.", ["Project", "Endpoint", *columns], rows))
    names = {"interface":"dom1/form", "expansion":"Three-project", "draw":"draw"}
    rows = [[names[c], MODELS[model], endpoint.title(), *builder_cells(groups, endpoint)]
            for c, value in data["cohorts"].items() for model, groups in value["by_generator_builder"].items()
            for endpoint in ("current", "history")]
    appendix.append(table("tab:endtoend-generator", "Separate target-generator and library-builder results. Three-project denotes calculator/table/bom; projects remain pooled within that row, and individual project results appear above. The header's model names identify library builders; the Generator column identifies the model producing target code or plans.", ["Study", "Generator", "Endpoint", *columns], rows, spec="lllrrr"))
    appendix += [r"\clearpage", r"\section{Construction and Generation Accounting}", r"\label{app:cost}",
                 r"Table~\ref{tab:construction} separates library builders' recorded construction charges, including unsuccessful attempts. Each row covers that builder's libraries for the named study. Exposure includes unresolved transport reservations. Local compute and unlogged human preparation time are excluded."]
    rows = [[COHORTS[c], MODELS[b], f"{values[b]['settled_usd']:.6f}", f"{values[b]['exposure_usd']:.6f}"]
            for c, values in data["costs"]["construction_by_builder"].items() for b in BUILDERS]
    appendix.append(table("tab:construction", "Library construction in USD, separated by builder. No two builders' bills are pooled into a method comparison.", ["Study", "Builder", "Settled", "Exposure"], rows, spec="llrr"))
    rows = []
    for value in data["costs"]["draw_by_generator_builder"].values():
        rows.append([MODELS[value['generator']], MODELS[value['builder']], f"{value['direct_usd']:.6f}",
                     f"{value['pipeline_usd']:.6f}", f"{value['direct_per_target_usd']:.6f}", f"{value['pipeline_per_target_usd']:.6f}"])
    appendix.append(table("tab:draw-endtoend-cost", "Draw provider receipts in USD. Every comparison covers five direct targets and five GUI-DNA targets. Pipeline cost charges the indicated builder once plus that generator's five plan chains and repairs. Baseline receipts are shared across builder comparisons, and the same library is shared across generator scenarios; do not add these scenarios into an overall study bill. This is observed accounting, not an equal-budget experiment.", ["Generator", "Builder", "Direct / 5", "Build + plans / 5", "Direct / target", "Pipeline / target"], rows, spec="llrrrr"))
    appendix.append(r"The original draw study's complete ledger remains \$3.285408 (provider receipts \$3.28538045), including conditions outside the current comparison. This is a historical billing total, not a pooled method comparison. Micro-dollar rounding occurs per request. The present revision incurs no model calls and does not rewrite historical bills.")
    return {"end_to_end_table.tex": main, "end_to_end_details.tex": "\n\n".join(appendix) + "\n"}


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
    for pooled in ("86/160", "93/240", "36/160", "26/240", "14/20", "79/216", "Build + plans / 10"):
        assert pooled not in content, f"Pooled builder comparison still active: {pooled}"
    labels = re.findall(r"\\label\{(tab:[^}]+)\}", content)
    expected_labels = re.findall(r"\\label\{(tab:[^}]+)\}", "\n".join(generated.values()))
    assert set(labels) == set(expected_labels) and len(labels) == len(set(labels)), "Unregistered table"
    # Adverse endpoint and protocol disclosures must survive editorial changes.
    for phrase in ("8/120", "18/120", "15/120", "0/10", "2/10", "43/108", "36/108", "39/108",
                   "all twenty public requirements", "not a matched total-budget", "retrospective"):
        assert phrase in content, f"Missing primary result/boundary: {phrase}"
    result = {"all_passed": True, "tables": expected_labels,
              "all_active_tables_generated_and_verified": True,
              "primary_view_sha256": sha(OUTPUT), "source_sha256": data["source_sha256"],
              "manuscript_sources_sha256": {p.relative_to(ROOT).as_posix(): sha(p) for p in active},
              "scope": "Reconstructs primary candidates, checks complete generated table text and active manuscript scope; not independent human review or verification of every prose claim."}
    (ROOT / "studies/results/paper_end_to_end_audit.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    data = reconstruct()
    assert json.loads(OUTPUT.read_text()) == data
    generated = render(data)
    if args.write:
        for name, text in generated.items():
            (PAPER / name).write_text(text)
    report = audit(data, generated)
    print(json.dumps({"all_passed": report["all_passed"], "tables": len(report["tables"])}))


if __name__ == "__main__":
    main()
