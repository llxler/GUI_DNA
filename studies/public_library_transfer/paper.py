"""Small source-checked manuscript tables for the new public-library trials."""

from .core import PROJECTS


def fraction(n, d):
    return f"{n}/{d}" if d else "---"


def match(row):
    d = row["paired"]
    return f"{row['plan_passed']}/{d}, {row['comparator_passed']}/{d}" if d else "---"


def tables(today, table):
    overview = today["transfer_overview"]
    rows = []
    sensitivity = {p["project"]: p for p in today["transfer_delivery"]["projects"]}
    for project in overview["local_groups"]:
        name = project["project"]
        accepted = [r for r in project["builds"] if r["tag"].startswith("codex")]
        assert len(accepted) == 2 and all(
            r["plan_vs_direct"]["paired"] == 20 and r["plan_vs_fixed"]["paired"] == 20
            for r in accepted
        )
        assert all(
            r["plan_vs_direct"]["comparator_passed"] == project["direct_passed"]
            for r in accepted
        )
        alternate = sensitivity[name]["after"]
        assert (
            sensitivity[name]["before"]["passed"] == project["direct_passed"]
            and alternate["known"] == 20
        )
        row = [
            name,
            fraction(project["direct_valid"], 20),
            fraction(project["direct_passed"], 20),
            fraction(alternate["passed"], 20),
        ]
        for r in accepted:
            v = r["plan_vs_fixed"]
            row += [
                fraction(v["plan_passed"], 20),
                fraction(v["comparator_passed"], 20),
            ]
        rows.append(row)
    main = table(
        "tab:transfer-ten",
        "Ten previously studied Web-Bench projects, twenty current files each. "
        "Qwen2.5-0.5B writes code once per target or selects legal values for each independently prepared GPT-6.2 Astra library. "
        "Direct valid counts executable submissions. Lenient parsing reuses the same free-code text. "
        "Fixed deploys each library's first example. Each direct column is shared across builds within a row.",
        [
            "Project",
            "Direct valid",
            "Direct pass",
            "Lenient pass",
            "Plan A",
            "Fixed A",
            "Plan B",
            "Fixed B",
        ],
        rows,
        wide=True,
    )
    rows = []
    for label, study in [
        ("Original deployment models", today["transfer_remote"]),
        ("Additional milestones", today["transfer_milestones"]),
    ]:
        pairs = study["pairs"]
        rows.append([r"\emph{" + label + "}", "", "", "", "", ""])
        for p in PROJECTS:
            for model, short in [
                ("mistralai/mistral-small-3.2-24b-instruct", "Mistral"),
                ("openai/gpt-oss-120b", "GPT-OSS"),
            ]:
                selected = [
                    r
                    for r in pairs
                    if r["project"] == p
                    and r["builder"] == "gpt-6.2-astra"
                    and r["planner"] == model
                ]
                if not selected:
                    continue
                lookup = {(r["rep"], r["comparator"]): r["all_tasks"] for r in selected}
                rows.append(
                    [
                        p,
                        short,
                        *(
                            match(lookup[rep, arm])
                            for rep in (1, 2)
                            for arm in ("direct", "fixed")
                        ),
                    ]
                )
    remote = table(
        "tab:transfer-remote",
        "Fresh Mistral Small and GPT-OSS-120B deployments. Each cell gives plan passes versus comparator passes on the stated number of jointly observed targets. "
        "Direct outputs are genuinely shared within each project and model. Fixed reuses the corresponding first example. The draw, canvas and flex rows use milestones 4, 8, 12, 16 and 20. "
        "The remaining projects schedule all twenty targets. GPT-5 and Claude library acquisition returned no package for this protocol.",
        [
            "Project",
            "Planner",
            "A vs. direct",
            "A vs. fixed",
            "B vs. direct",
            "B vs. fixed",
        ],
        rows,
        wide=True,
    )
    extra = today["transfer_extra"]["totals"]
    rows = []
    for k, label in [
        ("todomvc", "TodoMVC"),
        ("blogging", "Duo, blogging"),
        ("taskmanagement", "Duo, task management"),
    ]:
        group = extra[k]
        rows.append(
            [
                label,
                *(
                    fraction(group["passed"][arm], group["targets"])
                    for arm in ("direct", "dna-a", "first-a", "dna-b", "first-b")
                ),
            ]
        )
    other = table(
        "tab:transfer-other",
        "GPT-6.2 Astra builds and deploys on two further public suites. "
        "TodoMVC uses eight feature subsets. Each Duo domain has five distinct two-feature targets, graded by four Jest cases per target. "
        "The two Duo libraries are prepared separately for each domain. All methods share the row targets.",
        ["Suite / domain", "Direct", "Plan A", "Fixed A", "Plan B", "Fixed B"],
        rows,
        wide=True,
    )
    recovered_pages = []
    for project in today["transfer_boolean"]["projects"]:
        for group in project["groups"]:
            builder = group["builder"]
            admission = group["public_admission"]["status"]
            if admission == "valid":
                recovered_pages.append(
                    [
                        project["project"],
                        "GPT-OSS" if builder == "openai/gpt-oss-120b" else "Mistral",
                        match(group["plan_vs_direct"]),
                        match(group["plan_vs_fixed"]),
                    ]
                )
    normalized = table(
        "tab:transfer-boolean",
        "Fresh Qwen configurations on the packages admitted by the format-only analysis. "
        "Cells report plan and comparator passes on identical targets. From-scratch Qwen code reuses the original responses. "
        "Table and svg-chart use all targets; the other projects use the five prespecified milestones.",
        ["Project", "Builder", "Plan, direct", "Plan, fixed"],
        recovered_pages,
        wide=True,
    )
    prompts = []
    for r in today["transfer_prompt"]["groups"]:
        prompts.append(
            [
                r["project"],
                str(r["rep"]),
                fraction(r["plan_passed"], r["paired"]),
                fraction(r["comparator_passed"], r["paired"]),
                str(r["plan_only"]),
                str(r["comparator_only"]),
            ]
        )
    prompt = table(
        "tab:transfer-prompts",
        "Fixed-example coverage under behavior-focused versus generic guidance. "
        "The model, public inputs, assembler and output schema are shared. Each cell describes an independent library evaluated on the same twenty targets. "
        "We chose the two projects because each original GPT-5 library had passed three targets.",
        ["Project", "Build", "Focused", "Generic", "Only focused", "Only generic"],
        prompts,
        wide=True,
    )
    heldout = []
    for tag in ("codex-1", "codex-2"):
        pairs = {
            r["baseline"]: r
            for r in today["transfer_holdout"]["pairs"]
            if r["tag"] == tag
        }
        heldout.append([tag[-1], match(pairs["direct"]), match(pairs["fixed"])])
    unseen = table(
        "tab:transfer-holdout",
        "Two independent GPT-6.2 Astra libraries see expression-editor requirements 1--10. "
        "Mistral receives the public target prefix and is evaluated on current files 11--20. Cells show plan and comparator passes on the jointly observed targets.",
        ["Build", "Plan, direct", "Plan, fixed"],
        heldout,
    )
    remote_extra = today["transfer_archive_deployers"]
    names = {
        "oss": "GPT-OSS",
        "mistral": "Mistral",
        "qwen30b": "Qwen3 Coder 30B",
        "deepseek": "DeepSeek V4 Pro",
        "qwen": "Qwen3 Coder",
    }
    model_rows = []
    for suite, label in (("todomvc", "TodoMVC"), ("webapp1k-duo", "Duo")):
        for tag, panels in remote_extra["panels"].items():
            if suite not in panels:
                continue
            data = panels[suite]
            arms = data["arms"]
            n = data["scheduled_task_samples"]
            assert all(arms[k]["scored"] == n for k in ("direct", "dna-a", "dna-b"))
            model_rows.append(
                [
                    label,
                    names[tag],
                    fraction(arms["direct"]["status"].get("valid", 0), n),
                    *(
                        fraction(arms[k]["passed"], n)
                        for k in ("direct", "dna-a", "dna-b")
                    ),
                ]
            )
    archive_deployers = table(
        "tab:transfer-extra-deployers",
        "Remote deployment of the two independent Astra libraries. "
        "TodoMVC samples eight requirements twice per model. Duo samples ten two-feature targets once. "
        "Direct valid counts executable deliveries. DeepSeek reached its output cap on every direct Duo call and supplied no visible code.",
        ["Suite", "Deployer", "Direct valid", "Direct pass", "Plan A", "Plan B"],
        model_rows,
        wide=True,
    )
    original_rows = []
    original_duo = today["transfer_original_duo"]
    for name, panels in original_duo["panels"].items():
        data = panels["webapp1k-duo"]
        cells = []
        for control in ("direct", "first"):
            pair = data["paired"][control]
            cells.append(
                match(
                    {
                        "paired": pair["n"],
                        "plan_passed": pair["dna"],
                        "comparator_passed": pair["control"],
                    }
                )
            )
        original_rows.append([name.replace("_", r"\_"), *cells])
    originals = table(
        "tab:transfer-original-duo",
        "Fresh preparation and deployment with Duo's historical API model identities. "
        "The source and deployment names label each row. The direct candidate for each deployer and target is shared across sources. "
        "The first example is fixed at preparation. Experimental settings differ from the archived study.",
        ["Preparation and deployment", "Plan, direct", "Plan, fixed"],
        original_rows,
        wide=True,
    )
    return [
        main,
        remote,
        other,
        normalized,
        prompt,
        unseen,
        archive_deployers,
        originals,
    ]
