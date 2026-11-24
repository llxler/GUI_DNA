"""Build and evaluate paired native-schema Self and Direct Qwen workflows."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from gui_dna.budget import BudgetStop, Ledger
from scripts.check_openrouter_credits import check_credits
from studies.public_library_transfer import browser, core
from studies.public_library_transfer.self_refinement import method
from studies.public_library_transfer.self_refinement.line_contract import run as lines
from studies.public_library_transfer.self_refinement.native import transport
from studies.study_io import ROOT, digest, read, sha

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/self-native-20261124"
PROJECTS = ("table", "form")
GROUPS = ("direct", "build-a", "build-b")
SEEDS = {"direct": 20261124, "build-a": 20261124, "build-b": 20261125}
CAP = 1.20
TASKS = tuple(range(1, 21))
INVALID = (ValueError, KeyError, IndexError, TypeError, AttributeError)
MISSING = (transport.Unavailable, BudgetStop)
FILE_SCHEMA = core.obj({"files": core.array(core.FILE)})
SWITCH = core.obj(
    {"on": core.S, "off": core.S, "first": {"type": "string", "enum": ["on", "off"]}}
)
SMOKE = core.obj(
    {
        "selector": core.S,
        "event": {
            "type": "string",
            "enum": [
                "click",
                "dblclick",
                "contextmenu",
                "input",
                "change",
                "mouseover",
            ],
        },
        "visible": core.S,
    }
)
DESIGN_SCHEMA = core.obj(
    {"architecture": core.S, "choices": core.array(SWITCH), "smoke": SMOKE}
)
DESIGN = """Design a reusable, complete browser application from this public starter and public requirements.
In architecture, state the exact exports and signatures for each specified source path, the DOM and event
ownership, data structures, updates, selectors and dependencies. Implement stable requirements for all plans.
Choose up to four actual user-facing choices where two supported behaviors differ. Describe each alternative
and nominate the first example. Controls will have stable keys choice1, choice2, etc., assigned in order.
Never use task numbers, prefix indices or a map of targets to pages. All first-example and planned values
are strings on/off. Provide one small real interaction in the original page and a visible DOM result.
Use the API schema. No tools, external resources, benchmark tests or reference implementation."""
SOURCE = (
    method.AUTHOR
    + """ The shared architecture defines the signatures. Integrate with native browser
module imports; implement any publicly named classes in their named source paths. Stable behavior must work with
either allowed value. Read actual modules for integration when supplied. Preserve the publicly requested markup."""
)
FIX = """Repair the public browser load or public interaction failure. Read the actual generated modules;
return complete replacements for affected local files using the schema. Preserve the behavior/role of every
unrelated file. Use the listed source paths only. No official tests or external resources are available."""


def register():
    if (OUT / "registered.json").exists():
        verify()
        return
    balance = check_credits(CAP * len(PROJECTS))
    if not balance["sufficient"]:
        raise BudgetStop("Insufficient balance")
    native_required = {"reasoning", "response_format", "temperature", "seed"}
    import httpx

    catalog = httpx.get("https://openrouter.ai/api/v1/models", timeout=30)
    catalog.raise_for_status()
    route = next(r for r in catalog.json()["data"] if r["id"] == transport.MODEL)
    if not native_required <= set(route["supported_parameters"]):
        raise ValueError("Model does not advertise the registered parameters")
    paths = [
        HERE / "PROTOCOL.md",
        Path(__file__),
        Path(transport.__file__),
        Path(lines.__file__),
        Path(method.__file__),
        Path(browser.__file__),
        Path(core.__file__),
    ]
    for project in PROJECTS:
        data = core.public_input(project)
        for name, value in (
            ("public", data),
            ("paths", lines.layout(data)),
            ("browser", browser.verify_contract(project)),
        ):
            p = OUT / project / (name + ".json")
            core.save(p, value)
            paths.append(p)
    core.save(
        OUT / "registered.json",
        {
            "utc": core.now(),
            "projects": PROJECTS,
            "model": transport.MODEL,
            "targets": TASKS,
            "seeds": SEEDS,
            "deadline": transport.END.isoformat(),
            "cap_per_project": CAP,
            "route_parameters": route["supported_parameters"],
            "balance": balance,
            "files": {str(p.relative_to(ROOT)): sha(p) for p in paths},
        },
    )


def verify():
    record = read(OUT / "registered.json")
    for path, fingerprint in record["files"].items():
        if sha(ROOT / path) != fingerprint:
            raise ValueError(f"Changed registered input: {path}")


def build(root, group, ask, data):
    folder = root / group / "build"
    status = folder / "status.json"
    if status.is_file():
        return read(status)
    paths = read(root / "paths.json")
    try:
        response = ask(
            folder / "design",
            DESIGN,
            {"starter_and_requirements": data, "source_paths": paths},
            "design",
            5800,
            DESIGN_SCHEMA,
        )
        design = core.parse(response)
        if not isinstance(design["choices"], list) or len(design["choices"]) > 4:
            raise ValueError("Invalid number of semantic switches")
        controls = []
        for idx, item in enumerate(design["choices"], 1):
            if not all(
                isinstance(item[k], str) and item[k].strip() for k in ("on", "off")
            ) or item["first"] not in ("on", "off"):
                raise ValueError("Invalid semantic choice")
            controls.append(
                {
                    "id": f"choice{idx}",
                    "values": ["on", "off"],
                    "example": item["first"],
                    "description": "on: " + item["on"] + " / off: " + item["off"],
                }
            )
        spec = {
            "controls": controls,
            "entry": paths["entry"],
            "files": list(paths["public_paths"]),
            "smoke": design["smoke"],
            "architecture": design["architecture"],
        }
        core.save(folder / "manifest.json", spec)

        def implement(name):
            body = {"project": data, "manifest": spec, "requested_file": name}
            return name, method.source(
                ask(folder / "source" / name, SOURCE, body, "source/" + name, 8192)
            )

        with ThreadPoolExecutor(max_workers=4) as pool:
            files = dict(
                pool.map(implement, [p for p in spec["files"] if p != spec["entry"]])
            )
        entry = spec["entry"]
        integration = {
            "project": data,
            "manifest": spec,
            "requested_file": entry,
            "complete_other_files": files,
        }
        files[entry] = method.source(
            ask(folder / "entry", SOURCE, integration, "entry", 12000)
        )
        public = method.examine(data, spec, files, folder / "initial")
        core.save(folder / "initial-check.json", public)
        selected = "initial"
        if public["load_errors"] or not public["probe"]["passed"]:
            repair = {
                "project": data,
                "manifest": spec,
                "sources": files,
                "public_feedback": {
                    "load_errors": public["load_errors"],
                    "model_probe": public["probe"],
                },
            }
            try:
                patch = core.parse(
                    ask(folder / "repair", FIX, repair, "repair", 12000, FILE_SCHEMA)
                )
                replacements = core.files_map(patch["files"])
                if not replacements or set(replacements) - set(files):
                    raise ValueError("Unknown replacement path")
                revised = files | replacements
                check = method.examine(data, spec, revised, folder / "repaired")
                core.save(folder / "repaired-check.json", check)
                if not check["load_errors"]:
                    selected, files, public = "repaired", revised, check
            except MISSING + INVALID:
                if public["load_errors"]:
                    raise
        if public["load_errors"]:
            raise ValueError(
                "Final public load failed: " + str(public["load_errors"])[:400]
            )
        core.save(folder / "package.json", {"spec": spec, "sources": files})
        row = {
            "status": "valid",
            "package_sha256": sha(folder / "package.json"),
            "fixed_page": f"build/{selected}",
            "files": public["files"],
            "probe": public["probe"],
        }
    except MISSING as exc:
        row = {"status": "missing", "reason": str(exc)}
    except INVALID as exc:
        row = {"status": "invalid", "reason": str(exc)}
    core.save(status, row)
    return row


def generate(project, group):
    verify()
    root = OUT / project
    data = read(root / "public.json")
    ledger = Ledger(root / "budget.sqlite3", CAP, CAP)

    def ask(folder, prompt, content, step, limit, schema=None):
        return transport.request(
            folder,
            ledger,
            core.messages(prompt, content),
            f"{project}/{group}/{step}",
            limit,
            seed=SEEDS[group],
            schema=schema,
        )

    built = None if group == "direct" else build(root, group, ask, data)
    package = (
        read(root / group / "build/package.json")
        if built and built["status"] == "valid"
        else None
    )

    def target(task):
        dest = root / group / "targets" / str(task)
        st = dest / "status.json"
        if st.exists():
            return read(st)
        if built and not package:
            row = {"status": built["status"], "reason": "build: " + built["reason"]}
        else:
            try:
                if group == "direct":
                    raw = transport.request(
                        dest / "call",
                        ledger,
                        core.direct_messages(data, task),
                        f"{project}/direct/target/{task}",
                        8192,
                        seed=SEEDS[group],
                        schema=FILE_SCHEMA,
                    )
                    files = core.materialize_direct(
                        project, data, core.parse(raw), dest / "page"
                    )
                    row = {"status": "valid", "files": files}
                else:
                    spec = package["spec"]
                    schema = core.obj(
                        {
                            c["id"]: {"type": "string", "enum": c["values"]}
                            for c in spec["controls"]
                        }
                    )
                    params = {
                        "public_project": core.prefix(data, task),
                        "controls": spec["controls"],
                        "first_example": method.first(spec),
                    }
                    raw = ask(
                        dest / "call",
                        method.PLAN,
                        params,
                        f"target/{task}",
                        8192,
                        schema,
                    )
                    plan = method.plan(raw, spec)
                    files = method.emit(data, package["sources"], plan, dest / "page")
                    row = {"status": "valid", "files": files, "plan": plan}
            except MISSING as exc:
                row = {"status": "missing", "reason": str(exc)}
            except INVALID as exc:
                row = {"status": "invalid", "reason": str(exc)}
        core.save(st, row)
        return row

    first = target(TASKS[0])
    closed = first.get("status") == "missing" and first.get("reason") in {
        "HTTP 401",
        "HTTP 402",
        "HTTP 403",
        "HTTP 404",
    }
    if closed:
        for task in TASKS[1:]:
            core.save(
                root / group / "targets" / str(task) / "status.json",
                {
                    "status": "missing",
                    "reason": "permanent route failure on the first target",
                },
            )
    else:
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(target, TASKS[1:]))
    files = [root / group / "targets" / str(t) / "status.json" for t in TASKS]
    if built:
        files.append(root / group / "build/status.json")
    core.save(
        root / group / "seal.json", {str(p.relative_to(root)): sha(p) for p in files}
    )


def score(project):
    verify()
    root = OUT / project
    browser.OUT = root
    contract = read(root / "browser.json")
    assert browser.verify_contract(project) == contract
    for group in GROUPS:
        for name, h in read(root / group / "seal.json").items():
            assert sha(root / name) == h

    def evaluate(item):
        group, arm, task = item
        path = root / group
        if arm == "fixed":
            record = read(path / "build/status.json")
            page = path / record.get("fixed_page", "")
        else:
            path = path / "targets" / str(task)
            record = read(path / "status.json")
            page = path / "page"
        row = {"group": group, "arm": arm, "task": task, "status": record["status"]}
        if row["status"] == "valid":
            files = record["files"]
            result = browser.run_one(root, project, task, page, files, contract)
            row.update(
                passed=result["passed"],
                report_sha256=result["report_sha256"],
                files_digest=digest(files),
            )
        else:
            row.update(
                passed=False if row["status"] == "invalid" else None,
                reason=record["reason"],
            )
        return row

    jobs = [
        (g, a, t)
        for g in GROUPS
        for a in (("direct",) if g == "direct" else ("self", "fixed"))
        for t in TASKS
    ]
    with ThreadPoolExecutor(max_workers=4) as pool:
        core.save(root / "scores.json", list(pool.map(evaluate, jobs)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "verify", "generate", "score"))
    parser.add_argument("project", choices=PROJECTS, nargs="?")
    parser.add_argument("group", choices=GROUPS, nargs="?")
    args = parser.parse_args()
    if args.action in ("register", "verify"):
        globals()[args.action]()
    elif args.project and args.action == "score":
        score(args.project)
    elif args.project and args.group:
        generate(args.project, args.group)
    else:
        parser.error("Missing project or generation group")


if __name__ == "__main__":
    main()
