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


def render(data):
    headers = ["Study", "Direct: current", "GUI-DNA: current", "Direct: history", "GUI-DNA: history"]
    rows = [[COHORTS[c], *outcomes(value["results"])] for c, value in data["cohorts"].items()]
    main = table("tab:endtoend", "End-to-end comparison on public Web-Bench projects. Direct code receives no library; GUI-DNA includes AI library construction followed by plan generation. Cells give final passes / candidates (percent). Both builders' plan outputs are retained; the shared no-library candidate is counted once. Studies use distinct protocols and are not pooled. Construction has additional requirement access and compute (Section~\\ref{sec:setup}).", headers, rows, wide=True)
    appendix = [r"\section{Detailed End-to-End Results}", r"\label{app:details}",
                "All tables below derive from the same retained final candidates as Table~\\ref{tab:endtoend}. Shared baseline observations are displayed for each builder for interpretation, but are never counted as additional independent trials. No best-library selection is performed."]
    rows = [[p, *outcomes(result)] for value in data["cohorts"].values() for p, result in value["by_project"].items()]
    appendix.append(table("tab:endtoend-project", "Per-project results. The draw study has five milestones rather than all twenty prefixes. Direct code and GUI-DNA retain their actual denominators.", ["Project", *headers[1:]], rows))
    for key, name in (("by_builder", "Builder"), ("by_generator", "Generator")):
        rows = [[COHORTS[c], MODELS[model], *outcomes(result)] for c, value in data["cohorts"].items() for model, result in value[key].items()]
        appendix.append(table("tab:endtoend-" + name.lower(), name + " breakdown. Baseline observations recur across builder rows only as shared comparators. No independent-pairs significance claim is made.", ["Study", name, *headers[1:]], rows, spec="llrrrr"))
    appendix += [r"\clearpage", r"\section{Construction and Generation Accounting}", r"\label{app:cost}",
                 r"Construction is an explicit cost of GUI-DNA. Table~\ref{tab:construction} includes the original building stages, including recorded unsuccessful attempts. Settled cost and conservative exposure differ when transport calls have unresolved reservations. These are retained historical measurements, not costs of the reporting revision. Local compute and unlogged human preparation time are excluded."]
    rows = [[COHORTS[c], f"{v['settled_usd']:.6f}", f"{v['exposure_usd']:.6f}"] for c, v in data["costs"]["construction"].items()]
    appendix.append(table("tab:construction", "Library construction in USD. Exposure preserves unknown transport reservations. Construction charges must be included when amortizing GUI-DNA over a declared set of target requests.", ["Study", "Settled", "Exposure"], rows))
    rows = []
    for model, value in data["costs"]["draw_per_generator_scenarios"].items():
        rows.append([MODELS[model], f"{value['free_receipts_usd']:.6f}", f"{value['pipeline_receipts_usd']:.6f}",
                     f"{value['free_per_target_receipts_usd']:.6f}", f"{value['pipeline_per_target_receipts_usd']:.6f}"])
    appendix.append(table("tab:draw-endtoend-cost", "Draw provider receipts in USD, including repairs. Each generator scenario charges both library builds once across ten GUI-DNA targets (two libraries, five milestones); direct code has five targets. These are separate accounting scenarios: the original study built the libraries once, so do not add their construction charges across rows. Per-target values describe this observed reuse scope, not an equal-budget experiment.", ["Generator", "Direct / 5", "Build + plans / 10", "Direct / target", "Pipeline / target"], rows))
    appendix.append(r"The original draw study's complete ledger remains \$3.285408 (provider receipts \$3.28538045), including conditions outside this paper's comparison. Micro-dollar rounding occurs per request. The reporting revision incurs no model calls and does not rewrite historical bills. In the three-project study, accepted generation-response receipts are \$0.10038547 for direct code and \$0.20490933 for plans; these exclude construction and unresolved transport reservations and are not complete pipeline costs.")
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
    labels = re.findall(r"\\label\{(tab:[^}]+)\}", content)
    expected_labels = re.findall(r"\\label\{(tab:[^}]+)\}", "\n".join(generated.values()))
    assert set(labels) == set(expected_labels) and len(labels) == len(set(labels)), "Unregistered table"
    # Adverse endpoint and protocol disclosures must survive editorial changes.
    for phrase in ("26/240", "15/120", "2/20", "2/10", "79/216", "39/108",
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
