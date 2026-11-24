"""Build the manuscript comparison from matched, current-task observations."""

from collections import defaultdict

from studies.study_io import ROOT, read

MISTRAL = "mistralai/mistral-small-3.2-24b-instruct"
OSS = "openai/gpt-oss-120b"
GPT5 = "openai/gpt-5"
SONNET = "anthropic/claude-sonnet-4.5"
BACKBONES = {
    "google/gemma-3-12b-it": "Gemma 3 12B",
    "qwen/qwen3.5-9b": "Qwen3.5-9B",
    MISTRAL: "Mistral Small 3.2",
    "qwen/qwen3-coder-30b-a3b-instruct": "Qwen3-Coder-30B",
    OSS: "GPT-OSS-120B",
    "deepseek/deepseek-v4-flash": "DeepSeek V4 Flash",
    "deepseek/deepseek-v4-pro-0813": "DeepSeek V4 Pro",
    "google/gemini-2.5-flash": "Gemini 2.5 Flash",
    "openai/gpt-5-mini": "GPT-5 mini",
    GPT5: "GPT-5",
    "anthropic/claude-haiku-4.5": "Claude Haiku 4.5",
    SONNET: "Claude Sonnet 4.5",
}
FORM_RESULTS = "backbone-form-20261124.json"
SUITE_RESULTS = "backbone-suites-20261124.json"
FILES = ["backbone-matrix-20261124.json", "backbone-extension-20261124.json", FORM_RESULTS, SUITE_RESULTS]
WEB_PROJECTS = {"table": "Table editor", "svg-chart": "SVG charts", "form": "Question form"}


def joint_scores(arms, baseline="direct"):
    """Use one common intersection. Keep invalid output as False, unavailable as None."""
    known = {a: {k: v for k, v in rows.items() if v is not None} for a, rows in arms.items()}
    known = {a: rows for a, rows in known.items() if rows}
    if baseline not in known or len(known) < 2:
        return None
    targets = sorted(set.intersection(*(set(rows) for rows in known.values())))
    if not targets:
        return None
    assert all(type(rows[k]) is bool for rows in known.values() for k in targets)
    return {
        "n": len(targets),
        "targets": targets,
        "passed": {a: sum(rows[k] for k in targets) for a, rows in known.items()},
    }


def performance_matrix(data, replay, trials, today, batches=None):
    if batches is None:
        batches = [read(ROOT / "studies/results" / name) for name in FILES]
    matrix = {
        model: {"current": {}, "supplied": {}, "sources": {}, "retrospective": {}} for model in BACKBONES
    }
    observations = defaultdict(lambda: defaultdict(dict))

    def add(model, phase, project, method, task, value):
        arm = observations[model, phase, project][method]
        if task in arm:
            raise ValueError(f"Duplicate observation: {(model, phase, project, method, task)}")
        arm[task] = value

    for batch in batches:
        for model, group in batch["models"].items():
            for row in group["rows"]:
                if row["arm"] == "fixed":
                    continue
                project = row.get("project") or ("todomvc" if row["group"] == "todomvc" else "duo")
                add(model, "current", project, row["arm"], row["task"], row["passed"])

    for project, study in (("table", today["table"]), ("expression-editor", today["editor"])):
        for task, row in study["targets"].items():
            for key, method in (("direct", "direct"), ("reference", "human"), ("ai", GPT5)):
                add(
                    study["model"],
                    "sources",
                    project,
                    method,
                    int(task.removeprefix("task-")),
                    row[key]["first"]["passed"],
                )
    for project, study, ref in (
        ("form", trials["form"], "reference"),
        ("svg-chart", today["chart"], "reference_typed"),
    ):
        for task in study["targets"]:
            for key, method in (("direct", "direct"), (ref, "human"), ("ai", GPT5)):
                add(
                    study["generator"],
                    "sources",
                    project,
                    method,
                    task,
                    study["cells"][key][str(task)]["passed"],
                )
    for row in data["records"]:
        if row["cohort"] in ("interface", "expansion"):
            method = "direct" if row["method"] == "free" else row["builder"]
            add(
                row["model"],
                "retrospective",
                row["project"],
                method,
                int(row["task"].removeprefix("task-")),
                row["current"],
            )
    for (model, phase, project), arms in observations.items():
        scores = joint_scores(arms)
        if scores:
            matrix[model][phase][project] = scores
    for suite in replay["suites"]:
        project = {"webbench": "dom1", "todomvc": "todomvc"}[suite["suite"]]
        for row in suite["models"]:
            model = row["model"]
            if model not in BACKBONES or model not in suite["primary_models"]:
                continue
            free, dna = (row["counts"][m] for m in ("free", "dna"))
            assert free["n"] == dna["n"] and suite["all_match"]
            matrix[model]["supplied"][project] = {
                "n": free["n"],
                "replay_stage": suite["stage"],
                "passed": {"direct": free["final_all"], "human": dna["final_all"]},
            }
    return matrix


def cell(group, method):
    counts = group.get("passed", {})
    if method not in counts:
        return r"\textcolor[gray]{0.55}{--}"
    value = f"{counts[method]}/{group['n']}"
    if min(counts.values()) < counts[method] == max(counts.values()):
        return r"\textbf{" + value + "}"
    return value


def values(group, methods):
    return [cell(group, method) for method in methods]


def table_head(title, groups):
    size = 1 + sum(len(columns) for _, columns in groups)
    lines = [
        r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}l*{" + str(size - 1) + r"}{c}@{}}",
        r"\toprule" if title.startswith("A.") else r"\addlinespace[1pt]",
        r"\rowcolor[gray]{0.94}\multicolumn{" + str(size) + r"}{l}{\textbf{" + title + r"}} \\",
    ]
    lines.append(
        " & "
        + " & ".join(r"\multicolumn{" + str(len(cols)) + r"}{c}{" + label + "}" for label, cols in groups)
        + r" \\"
    )
    start = 2
    rules = []
    for _, cols in groups:
        rules.append(r"\cmidrule(lr){" + f"{start}-{start + len(cols) - 1}" + "}")
        start += len(cols)
    return lines + ["".join(rules)]


def order_build_rows(rows):
    projects = ("Table editor", "Question form", "TodoMVC", "Duo", "SVG charts")
    models = tuple(BACKBONES.values())
    return sorted(rows, key=lambda r: (projects.index(r["project"]), models.index(r["target_generator"])))


def render_matrix(matrix, followups=(), replays=None, domain_rows=()):
    lines = [
        r"\begin{table*}[p]",
        r"\centering",
        r"\caption{Current-task passes / matched targets. Bold marks a row maximum within each protocol. Dashes mark unavailable results.}",
        r"\label{tab:endtoend}",
        r"\fontsize{8.5}{9.5}\selectfont\setlength{\tabcolsep}{2pt}\renewcommand{\arraystretch}{0.97}",
        r"\setlength{\aboverulesep}{0.8pt}\setlength{\belowrulesep}{1.25pt}",
    ]
    fresh = ["Direct", "Human", "GPT-5", "Self"]
    groups = [(label, fresh) for label in WEB_PROJECTS.values()]
    lines += table_head("A. Full-project Web-Bench comparison", groups)
    lines += ["Target generator & " + " & ".join(fresh * len(groups)) + r" \\", r"\midrule"]
    methods = ["direct", "human", "gpt5-library", "self"]
    unavailable = []
    for m, label in BACKBONES.items():
        if all(project not in matrix[m]["current"] for project in WEB_PROJECTS):
            unavailable.append(label)
            continue
        cells = [v for p in WEB_PROJECTS for v in values(matrix[m]["current"].get(p, {}), methods)]
        lines += [" & ".join([label, *cells]) + r" \\"]
    lines += [r"\bottomrule\end{tabular*}\par"]
    if unavailable:
        lines.append(
            r"\begin{minipage}{\textwidth}\footnotesize\raggedright "
            + r"\textit{-- Unavailable in Panel A.} "
            + ", ".join(unavailable)
            + r".\end{minipage}\par"
        )
    lines += [r"\vspace{1pt}"]
    groups = [
        ("TodoMVC", ["Direct", "Human", "Self"]),
        ("WebApp1K-Duo", ["Direct", "Self"]),
        ("TodoMVC (supplied)", ["Direct", "Human"]),
        ("Files (supplied)", ["Edit", "Human"]),
    ]
    if replays:
        groups[0] = ("TodoMVC", ["Direct", "Human", "Self", "Bind"])
        groups.insert(2, ("Duo (replay)", [r"Direct$^*$", "Bind"]))
    lines += table_head("B. Feature subsets, feature pairs and supplied-library studies", groups)
    lines += [
        "Target generator & " + " & ".join(name for _, cols in groups for name in cols) + r" \\",
        r"\midrule",
    ]
    for m, label in BACKBONES.items():
        series = [
            (matrix[m][phase].get(project, {}), arms)
            for phase, project, arms in (
                ("current", "todomvc", ["direct", "human", "self"]),
                ("current", "duo", ["direct", "self"]),
                ("supplied", "todomvc", ["direct", "human"]),
                ("supplied", "dom1", ["direct", "human"]),
            )
        ]
        if replays:
            suite = replays.get(m, {})
            todo, arms = series[0]
            if suite:
                for index, key in ((0, "todomvc"), (1, "duo")):
                    original = series[index][0]
                    recovered = suite[key]
                    assert original["targets"] == recovered["targets"]
                    assert original["passed"]["direct"] == recovered["passed"]["strict_direct"]
                    assert original["passed"]["self"] == recovered["passed"]["strict_self"]
                assert suite["todomvc"]["passed"]["direct"] == todo["passed"]["direct"]
                todo = {**todo, "passed": {**todo["passed"], "bound": suite["todomvc"]["passed"]["bound"]}}
            series[0] = (todo, [*arms, "bound"])
            replay = suite.get("duo", {})
            if replay:
                replay = {**replay, "passed": {k: replay["passed"][k] for k in ("direct", "bound")}}
            series.insert(2, (replay, ["direct", "bound"]))
        if any(group for group, _ in series):
            lines += [
                " & ".join([label, *(s for group, arms in series for s in values(group, arms))]) + r" \\"
            ]
    lines += [r"\bottomrule\end{tabular*}\par\vspace{1pt}"]
    groups = [
        ("Mistral / source comparison", ["Direct", "Human", "GPT-5"]),
        ("Mistral / retrospective", ["Direct", "GPT-5", "Sonnet"]),
        ("GPT-OSS / retrospective", ["Direct", "GPT-5", "Sonnet"]),
    ]
    lines += table_head("C. Earlier comparisons on full Web-Bench project schedules", groups)
    lines += ["Project & " + " & ".join(name for _, cols in groups for name in cols) + r" \\", r"\midrule"]
    for p, label in [
        ("dom1", "File explorer"),
        ("form", "Question form"),
        ("calculator", "Calculator"),
        ("table", "Table editor"),
        ("bom", "Browser object model"),
        ("svg-chart", "SVG charts"),
        ("expression-editor", "Expression editor"),
    ]:
        cells = values(matrix[MISTRAL]["sources"].get(p, {}), ["direct", "human", GPT5])
        for model in (MISTRAL, OSS):
            cells += values(matrix[model]["retrospective"].get(p, {}), ["direct", GPT5, SONNET])
        lines += [" & ".join([label, *cells]) + r" \\"]
    lines += [r"\bottomrule\end{tabular*}\par\vspace{1pt}"]
    if followups:
        lines += [
            r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}lllcccccc@{}}",
            r"\rowcolor[gray]{0.94}\multicolumn{5}{l}{\textbf{D. Paired comparisons with two library builds}} & "
            r"\multicolumn{2}{c}{\textbf{Library 1}} & \multicolumn{2}{c}{\textbf{Library 2}} \\",
            r"\cmidrule(lr){6-7}\cmidrule(lr){8-9}",
            r"Project & Target generator & Builder & Protocol & Direct & Planned & Fixed & Planned & Fixed \\",
            r"\midrule",
        ]
        previous_project = None
        for row in order_build_rows(followups):
            if previous_project and previous_project != row["project"]:
                lines.append(r"\addlinespace[1pt]")
            previous_project = row["project"]
            counts = {"passed": row["passed"], "n": len(row["targets"])} if row["targets"] else {}
            fields = values(counts, ("direct", "self_a", "fixed_a", "self_b", "fixed_b"))
            protocol = row["decoding"]
            if len(row.get("libraries", ("a", "b"))) == 1:
                protocol += " (" + {"a": "1", "b": "2"}[row["libraries"][0]] + ")"
            lines += [" & ".join([row["project"], row["target_generator"], row["builder"], protocol, *fields]) + r" \\"]
        lines += [r"\bottomrule\end{tabular*}\par\vspace{1pt}"]
    if domain_rows:
        lines += [
            r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}lcccccccc@{}}",
            r"\rowcolor[gray]{0.94}\multicolumn{3}{l}{\textbf{E. Domain scaffolds, local Qwen2.5-0.5B}} & "
            r"\multicolumn{3}{c}{\textbf{Library 1}} & \multicolumn{3}{c}{\textbf{Library 2}} \\",
            r"\cmidrule(lr){4-6}\cmidrule(lr){7-9}",
            r"Project & Direct & Rules only & Planned & Fixed A & Fixed B & Planned & Fixed A & Fixed B \\",
            r"\midrule",
        ]
        methods = ("direct", "rules", "A_plan", "A_first", "A_second", "B_plan", "B_first", "B_second")
        for row in domain_rows:
            lines.append(" & ".join([row["project"], *values(row, methods)]) + r" \\")
        lines += [r"\bottomrule\end{tabular*}\par\vspace{1pt}"]
    lines += [
        r"\begin{minipage}{\textwidth}\footnotesize\raggedright "
        r"Human uses supplied components. GPT-5 supplies a frozen library. Self uses the same builder and generator. "
        + (r"Bind links archived code. Direct$^*$ repairs exports. Edit updates the previous page. " if replays else "")
        + (r"D uses each protocol's Direct. Fixed retains an example, pair, defaults, or all renderers. Gemma, SVG and GPT-OSS form variants "
           r"reuse builds. Relaxed files and DOM tokens accept recovered Direct files. " if followups else "")
        + (r"In E, fixed A/B retain/swap button order or enable/disable optional events." if domain_rows else "")
        + r"\end{minipage}",
        r"\end{table*}",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    from studies.public_library_transfer.self_replication.paper import rows
    from studies.public_library_transfer.self_refinement.suite_comparisons import evidence
    from studies.public_library_transfer.self_refinement import domain_panel, prospective_panel
    print(render_matrix(read(ROOT / "studies/results/paper-performance-matrix.json"), [*rows(), *prospective_panel.rows()], evidence()["models"], domain_panel.rows()), end="")
