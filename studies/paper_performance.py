"""Build the manuscript comparison from matched, current-task observations."""

from collections import defaultdict

from studies.study_io import ROOT, read
from studies.webgen_bench import report as functional
from studies.public_library_transfer.source_diagnosis import report as sources
from studies.webgen_bench.component_contracts import report as validation
from studies.public_library_transfer.self_refinement.suite_recovery import paper as recovery
from studies.webbench.form.flash_self_build import paper as flash_form
from studies import paper_component_followup as components, paper_library_capabilities as capabilities
from studies.webbench.table.event_modules import paper as table_protocols

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
FEATURE_SUITES = {"todomvc": "TodoMVC", "duo": "WebApp1K-Duo"}
METHODS = {"direct": "Direct", "human": "Human", "gpt5-library": "GPT-5", "self": "Self"}


def joint_scores(arms, baseline="direct", *, allow_direct_only=False):
    """Use one common intersection. Keep invalid output as False, unavailable as None."""
    known = {a: {k: v for k, v in rows.items() if v is not None} for a, rows in arms.items()}
    known = {a: rows for a, rows in known.items() if rows}
    if baseline not in known or (len(known) < 2 and not allow_direct_only):
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
    published = batches is None
    if published:
        batches = [read(ROOT / "studies/results" / name) for name in FILES]
    matrix = {
        model: {"current": {}, "supplied": {}, "sources": {}, "retrospective": {}} for model in BACKBONES
    }
    observations = defaultdict(lambda: defaultdict(dict))
    failed_builds = defaultdict(lambda: defaultdict(set))

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
                if row.get("status") == "build_failed":
                    failed_builds[model, project][row["arm"]].add(row["task"])

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
    editor = today["editor"]
    if editor.get("provenance", {}).get("ai", {}).get("preparation_status") == "returned_artifacts_failed_public_validation":
        source = matrix[editor["model"]]["sources"].get("expression-editor")
        if source:
            source["excluded_build_arms"] = [GPT5]
    for (model, project), failed in failed_builds.items():
        arms = observations[model, "current", project]
        eligible = {
            arm: {task: passed for task, passed in tasks.items() if task not in failed.get(arm, ())}
            for arm, tasks in arms.items()
        }
        scores = joint_scores(eligible, allow_direct_only=True)
        if scores:
            scores["excluded_build_arms"] = sorted(arm for arm in failed if arm not in scores["passed"])
            scores["failed_build_targets"] = {arm: sorted(tasks) for arm, tasks in failed.items()}
            matrix[model].setdefault("paper_current", {})[project] = scores
    if published:
        original = observations[flash_form.MODEL, "current", "form"]
        matrix[flash_form.MODEL]["panel_a_self"] = {"form": flash_form.panel_a_self(original)}
        recovery.attach(matrix)
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
    if published:
        components.attach(matrix)
        components.extend(matrix)
        table_protocols.attach(matrix)
        capabilities.attach(matrix)
        pilot = read(functional.RESULT)
        for tag, model_name in pilot['registered_models'].items():
            group = pilot['stages'][pilot['primary_stage']]['models'][tag]
            matrix[model_name]['webgen_functional'] = {
                'targets': group['targets'], 'n': group['n'], 'registered': group['registered'],
                'passed': {a: v['points'] for a, v in group['methods'].items() if 'points' in v},
                'excluded_build_arms': [a for a,v in group['methods'].items() if v['status']=={'build_failed':43}],
                'measure': 'functional points', 'judge': pilot['stages'][pilot['primary_stage']]['route']['model'],
            }
        confirm = pilot['table']['interaction_repairs']
        primary = confirm['libraries']['a']
        if primary['status'] == 'valid' and primary['matched'] == list(range(1, 21)):
            group = matrix[components.QWEN9]['library_capabilities']['table']
            assert group['targets'] == primary['matched']
            counts = {arm:len(confirm['arms'][source]['passes']) for arm,source in [('direct','direct'),('self','self-a')]}
            matrix[components.QWEN9]['table_state_transitions'] = {
                **group, 'passed':group['passed'] | counts, 'preparation':'incremental interaction repair',
                'rep':'a', 'complete':True, 'build_status':'valid', 'observed':primary['matched'],
                'markers':group['markers'] | {'self':'typed'},
                'implementation_sources':group['implementation_sources'] | {'self':str((functional.TABLE_STAGES['interaction_repairs']/'result.json').relative_to(ROOT))},
                'fixed_passes':confirm['arms']['fixed-a']['passes'],
            }
        sources.attach(matrix)
        validation.attach(matrix)
    return matrix


def cell(group, method):
    counts = group.get("passed", {})
    if method in group.get("excluded_build_arms", ()):
        return ""
    if method not in counts:
        return r"\textcolor[gray]{0.55}{--}"
    value = f"{counts[method]:g}/{group['n']}"
    marker = r"$^{\ddagger}$" if method == "self" and group.get("rep") == "a" else ""
    stage = group.get("markers", {}).get(method)
    if stage:
        marker = {"menu": r"$^{*}$", "visible": r"$^{*}$", "rebuild": r"$^{\ddagger}$",
                  "flash-visible": r"$^{\dagger}$", "flash-schema": r"$^{\dagger *}$", "profiles": r"$^{*}$", "handlers": r"\textsuperscript{\S}", "typed": r"\textsuperscript{\S}", "events": r"\textsuperscript{\S}", "blind": "", "donor": r"$^{t}$", "survey": r"$^{s}$", "source-plans": r"$^{p}$", "self-sequences": r"$^{u}$", "visible-choices": r"$^{v}$", "core-profile": r"$^{vc}$", "quoted-exclusions": r"$^{e}$"}[stage]
    if min(counts.values()) < counts[method] == max(counts.values()):
        return r"\textbf{" + value + "}" + marker
    return value + marker


def values(group, methods):
    return [cell(group, method) for method in methods]


def _current_record(model, project):
    field = "paper_current" if project in model.get("paper_current", {}) else "current"
    original = model[field].get(project, {})
    trial = model.get("self_recovery", {}).get(project)
    if trial and (trial["first"]["complete"] or "self" not in original.get("passed", {})):
        return ("self_recovery", project, "first"), trial["first"]
    return (field, project), original


def current_group(model, project):
    return _current_record(model, project)[1]


def table_record(model, project):
    """Return the matrix key path and the record used to render this generator's row."""
    if project == "webgen-bench":
        return ("webgen_functional",), model.get("webgen_functional", {})
    if project == "webgen-heldout":
        return ("webgen_holdout",), model.get("webgen_holdout", {})
    ordered = (
        ("state_examples", project),
        ("source_diagnosis", project),
        ("table_state_transitions",) if project == "table" else (),
        ("library_capabilities", project),
        ("form_visible_targets",) if project == "form" else (),
        ("table_protocol_followup",) if project == "table" else (),
        ("extended_targets", project),
        ("component_followup", project),
    )
    for path in ordered:
        if not path or path[0] not in model:
            continue
        record = model[path[0]]
        if len(path) == 1:
            return path, record
        if project in record:
            return path, record[project]

    path, group = _current_record(model, project)
    rebuild = model.get("panel_a_self", {}).get(project)
    if rebuild is None:
        return path, group
    original = model["current"][project]
    assert rebuild["targets"] == original["targets"] and group["n"] == len(rebuild["targets"])
    return ("panel_a_self", project), {
        **rebuild, "n": group["n"], "passed": original["passed"] | rebuild["passed"]
    }


def project_cells(model, project):
    path, group = table_record(model, project)
    cells = values(group, METHODS)
    if path[0] == "panel_a_self":
        cells[-1] += r"$^{\dagger}$"
    return cells


def table_models(matrix, project):
    """Generator IDs in the order displayed for a current Table 1 project."""
    if project in WEB_PROJECTS:
        return [m for m in BACKBONES if any(current_group(matrix[m], p) for p in WEB_PROJECTS)]
    if project in ("dom1", "calculator"):
        return (components.QWEN9, components.FLASH) if "dom1" in matrix[components.FLASH].get("library_capabilities", {}) else ()
    if project == "todomvc":
        return components.TODO_ROSTER
    if project == "duo":
        return [m for m in BACKBONES if current_group(matrix[m], project)]
    if project in ("webgen-bench", "webgen-heldout"):
        return [m for m, entry in matrix.items() if table_record(entry, project)[1]]
    raise KeyError(project)


def comparison_panel(title, projects, matrix, models=None):
    methods = list(METHODS.values())
    column_count = 1 + len(projects) * len(methods)
    headings = []
    rules = []
    for index, label in enumerate(projects.values()):
        first = 2 + index * len(methods)
        last = first + len(methods) - 1
        headings.append(rf"\multicolumn{{{len(methods)}}}{{c}}{{{label}}}")
        rules.append(rf"\cmidrule(lr){{{first}-{last}}}")
    lines = [
        r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}p{1.18in}*{" + str(column_count - 1) + r"}{c}@{}}",
        r"\toprule",
        r"\rowcolor[gray]{0.94}\multicolumn{" + str(column_count) + r"}{l}{\textbf{" + title + r"}} \\",
        " & " + " & ".join(headings) + r" \\",
        "".join(rules),
        " & ".join(["Target generator", *(methods * len(projects))]) + r" \\",
        r"\midrule",
    ]
    if models is None:
        models = (table_models(matrix, "table") if projects == WEB_PROJECTS else
                  [m for m in BACKBONES if any(current_group(matrix[m], p) for p in projects)])
    for model in models:
        cells = [value for project in projects for value in project_cells(matrix[model], project)]
        lines.append(" & ".join([BACKBONES[model], *cells]) + r" \\")
    return [*lines, r"\bottomrule\end{tabular*}\par"]


def order_build_rows(rows):
    projects = ("Table editor", "Question form", "TodoMVC", "Duo", "SVG charts")
    models = tuple(BACKBONES.values())
    return sorted(rows, key=lambda r: (projects.index(r["project"]), models.index(r["target_generator"])))


def feature_panel(matrix):
    labels = BACKBONES | components.LABELS
    duo = table_models(matrix, "duo")
    lines = [
        r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}lcccc@{\hspace{1.1em}}lcccc@{}}",
        r"\toprule\rowcolor[gray]{0.94}\multicolumn{10}{l}{\textbf{B. Feature subsets and pairs}} \\",
        r"\multicolumn{5}{c}{TodoMVC} & \multicolumn{5}{c}{WebApp1K-Duo} \\",
        r"\cmidrule(lr){1-5}\cmidrule(lr){6-10}",
        " & ".join(["Target generator", *METHODS.values()] * 2) + r" \\",
        r"\midrule",
    ]
    for left, right in zip(table_models(matrix, "todomvc"), duo, strict=True):
        fields = [labels[left], *project_cells(matrix[left], "todomvc"),
                  labels[right], *project_cells(matrix[right], "duo")]
        lines.append(" & ".join(fields) + r" \\")
    return [*lines, r"\bottomrule\end{tabular*}\par"]


def additional_web_projects(matrix):
    lines = [
        r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}lcccccccc@{}}",
        r"& \multicolumn{4}{c}{File explorer} & \multicolumn{4}{c}{Calculator} \\",
        r"\cmidrule(lr){2-5}\cmidrule(lr){6-9}",
        " & ".join(["Target generator", *METHODS.values(), *METHODS.values()]) + r" \\",
        r"\midrule",
    ]
    for model in table_models(matrix, "dom1"):
        fields = [BACKBONES[model]]
        for project in ("dom1", "calculator"):
            fields.extend(project_cells(matrix[model], project))
        lines.append(" & ".join(fields) + r" \\")
    return [*lines, r"\bottomrule\end{tabular*}\par"]


def planned_panel():
    study = read(components.PLANNED)
    assert study["state"] == "planned" and study["measurements"] == [] and study["arms"] == list(METHODS)
    names = [BACKBONES[m] for m in study["models"]]
    return [
        r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}lcccc@{}}",
        r"\toprule\rowcolor[gray]{0.94}\multicolumn{5}{l}{\textbf{C. WebGen-Bench} (planned functional evaluation)} \\",
        " & ".join(["Registered generators", *METHODS.values()]) + r" \\",
        r"\midrule",
        " & ".join([", ".join(names), *values({}, METHODS)]) + r" \\",
        r"\bottomrule\end{tabular*}\par",
    ]


def functional_panel(matrix):
    models = table_models(matrix, "webgen-bench")
    if not models:
        return planned_panel()
    projects = {"webgen-bench": "Six development sites"}
    if any("webgen_holdout" in matrix[m] for m in models):
        projects["webgen-heldout"] = "Three held-out sites"
    return comparison_panel("C. WebGen-Bench (alternate vision judge)", projects, matrix, models)


def render_matrix(matrix, followups=(), domain_rows=()):
    updated = all(m in matrix for m in components.LABELS)
    lines = [
        r"\begin{table*}[p]" if followups or domain_rows else r"\begin{table*}[!t]",
        r"\centering",
        (r"\caption{A and B report current-task passes. C reports functional points (full 1, partial 0.5). Denominators count matched targets. Blank cells mark failed builds and dashes mark unavailable results. Bold marks each row maximum within a task group.}" if any('webgen_functional' in entry for entry in matrix.values()) else
         r"\caption{Current-task passes / matched targets. Blank = failed build. Dash = unevaluated or unavailable. Bold = protocol maximum.}"),
        r"\label{tab:endtoend}",
        r"\fontsize{9}{10.5}\selectfont\setlength{\tabcolsep}{2pt}",
        r"\setlength{\aboverulesep}{0.8pt}\setlength{\belowrulesep}{1.25pt}",
    ]
    lines += comparison_panel("A. Web-Bench projects", WEB_PROJECTS, matrix)
    if "dom1" in matrix[components.FLASH].get("library_capabilities", {}):
        lines += additional_web_projects(matrix)
    lines.append(r"\vspace{3pt}")
    lines += feature_panel(matrix) if updated else comparison_panel("B. Feature subsets and pairs", FEATURE_SUITES, matrix)
    if updated:
        lines += [r"\vspace{3pt}", *functional_panel(matrix)]
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
            counts = {"passed": row["passed"], "n": len(row["targets"]),
                      "excluded_build_arms": row.get("excluded_build_arms", ())} if row["targets"] else {}
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
        r"Direct writes code without a library. Human uses prepared components. GPT-5 uses a frozen GPT-5 library. "
        r"Self uses the target model to build and configure its own library. "
        + r"Each Duo domain contributes five pairs. "
        + (r"$^t$ GPT-5 components from other public feature pairs. $^s$ Matched Direct and a shared questionnaire plan across libraries. " if "library_capabilities" in matrix[components.FLASH] else "")
        + (r"$^p$ Revised configuration of a frozen library. $^u$ Public workflow checks and same-model repair. $^v$ Extra reasoning disabled. $^c$ Profiles satisfy shared public requirements. $^e$ Disabling a feature requires a quote from the brief. " if "source_diagnosis" in matrix[components.QWEN9] else "")
        + (r"D uses protocol-specific Direct. Variants reuse libraries. "
           r"Fixed replays an example, pair, defaults, or all renderers. Relaxed files, DOM tokens and SVG C/D share 20 recovered direct replies. Flash file checks include six retransmissions. " if followups else "")
        + (r"In E, fixed A/B retain/swap button order or enable/disable optional events. " if domain_rows else "")
        + (r"$\dagger$ Flash form uses matched decoding and the first file-checked Self library. " if matrix[flash_form.MODEL].get("form_visible_targets") else
           r"$\dagger$ Flash form uses the first file-checked build. " if matrix[flash_form.MODEL].get("panel_a_self") else "")
        + (r"$\ddagger$ First rebuild in the 25-cell follow-up. " if matrix[flash_form.MODEL].get("panel_a_self") else "")
        + (r"$*$ Revised selection on the same library. \S\ First library with a project-specific interface. "
           r"TodoMVC adds three 3--4B models; the three earlier Direct ceiling rows are reported in the text. "
           if updated else "")
        + r"\end{minipage}",
        r"\end{table*}",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print(render_matrix(read(ROOT / "studies/results/paper-performance-matrix.json")), end="")
