"""Apply one real tool-authored file write at a time, then evaluate frozen pages."""

import argparse
import subprocess
from pathlib import Path

import httpx

from gui_dna.budget import BudgetStop, Ledger
from scripts.check_openrouter_credits import check_credits
from studies.public_library_transfer import browser, core
from studies.public_library_transfer.self_refinement import method, report, run as shared
from studies.public_library_transfer.self_refinement.incremental import run as previous
from studies.study_io import ROOT, read, sha
from studies.webbench.backbone_matrix import run as transport

from . import provider

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/native-incremental-self-table-20261124"
OUTPUT = ROOT / "studies/results/native-incremental-self-table-20261124.json"
MODEL, TAG, END = previous.MODEL, previous.TAG, previous.END
CAP = 1.99
MODELS = {TAG: (MODEL, CAP, 0.25, 1)}
BASE = OUT / TAG
BUILD = BASE / "build"
SAVE = core.save
STR = {"type": "string"}
EVENTS = ["click", "dblclick", "contextmenu", "input", "change", "mouseover"]
PLAN_TOOL = {"name": "plan_revision", "description": "Select local files, precise edit responsibilities and a smoke check.",
             "parameters": core.obj({"files": core.array(core.obj({"path": STR, "edit": STR})),
                 "smoke": core.obj({"selector": STR, "event": {"type": "string", "enum": EVENTS}, "visible": STR})})}
DESIGN = """Implement the new public interactive GUI requirements on top of the supplied working repository. Plan only the files needing changes in chronological implementation order. Each file needs a concrete editing contract including relevant shared state, callers, imports/exports and interaction details. Respect public filename and selector requirements, event ownership and dependencies. Prefer keeping earlier functioning interactions. Use globalThis.APP_CONFIG only for genuine alternatives; implement stable requirements in all configurations. Do not select task IDs, pages or code via configurations. Original HTML stays mounted. Only local ES modules and CSS may be edited. Define a modest public smoke check for the fixed example. Choose an existing interactive event target and a CSS selector shown after dispatching the event. Return the native plan_revision call."""
AUTHOR = """Write the complete contents of the one requested local file. Use the native file tool. Preserve working behaviors, exact public selectors, module boundaries, browser events and shared application state. Implement the specified interaction end to end and keep the imports and exported names consistent across files. The supplied project files are the exact current workspace. Load this file via existing entrypoints or the other requested files. globalThis.APP_CONFIG has string values for genuine switchable behaviors; stable requirements remain available. Write production browser code only. Do not include code fences, placeholder code, tests, task IDs or per-task dispatch."""


def register():
    if (OUT / "registered.json").exists():
        return shared.verify()
    old = read(previous.OUTPUT)
    if old["ledger"]["unsettled_calls"] or CAP + old["ledger"]["exposure_usd"] > 2:
        raise BudgetStop("Combined allocation would exceed two dollars")
    balance = check_credits(CAP)
    if not balance["sufficient"]:
        raise BudgetStop("Insufficient credit")
    res = httpx.get("https://openrouter.ai/api/v1/models", timeout=30)
    res.raise_for_status()
    supported = next(r["supported_parameters"] for r in res.json()["data"] if r["id"] == MODEL)
    if not {"tools", "tool_choice"} <= set(supported):
        raise ValueError("Route does not support native tools")
    SAVE(OUT / "public.json", core.public_input("table"))
    SAVE(OUT / "browser.json", browser.verify_contract("table"))
    old_interface = previous.OUT / TAG / "build/interface.json"
    SAVE(OUT / "interface.json", read(old_interface))
    paths = [HERE / "PROTOCOL.md", Path(__file__), Path(provider.__file__), Path(shared.__file__), Path(previous.__file__),
             Path(method.__file__), Path(core.__file__), Path(transport.__file__), Path(browser.__file__),
             ROOT / "src/gui_dna/budget.py", previous.BASELINE, previous.OUTPUT, old_interface,
             OUT / "public.json", OUT / "browser.json", OUT / "interface.json"]
    SAVE(OUT / "registered.json", {"utc": core.now(), "end": END.isoformat(), "project": "table", "models": MODELS,
         "parameters": {MODEL: supported}, "budget_usd": CAP, "previous_exposure_usd": old["ledger"]["exposure_usd"],
         "balance": balance, "tasks": list(previous.TASKS), "batch_ends": previous.BATCH_ENDS,
         "files": {str(p.relative_to(ROOT)): sha(p) for p in paths}})


def revision_plan(args, limit):
    files, smoke = args["files"], args["smoke"]
    if not isinstance(files, list) or not 1 <= len(files) <= limit:
        raise ValueError(f"Expected 1 through {limit} named source edits")
    paths = core.files_map([{"path": v["path"], "content": v["edit"]} for v in files])
    if not all(p.endswith((".js", ".mjs", ".css")) and desc.strip() for p, desc in paths.items()):
        raise ValueError("Expected local JS/CSS files and nonempty editing instructions")
    if smoke["event"] not in EVENTS or not all(isinstance(smoke[k], str) and 0 < len(smoke[k]) <= 512 for k in ("selector", "visible")):
        raise ValueError("Invalid public smoke check")
    return args


def source(args, path):
    name, content = args["path"], args["content"]
    if name != path or not isinstance(content, str) or not content.strip() or content.lstrip().startswith("```"):
        raise ValueError("Expected named file and complete, unfenced, nonempty contents")
    core.files_map([{"path": name, "content": content}])
    if name.endswith((".js", ".mjs")):
        rc = subprocess.run(["node", "--input-type=module", "--check", "-"], input=content, text=True, capture_output=True, timeout=15)
        if rc.returncode:
            raise ValueError(rc.stderr[:800])
    return content


def checked_call(ledger, folder, system, context, tool, validate, tokens):
    errors = []
    for attempt in (1, 2):
        dest = folder / f"attempt-{attempt}"
        try:
            msg = core.messages(system, {**context, "previous_public_errors": errors})
            obj = provider.tool_call(BASE, ledger, dest, MODEL, END, msg, tool,
                    "build/table/" + str(dest.relative_to(BUILD)), tokens)
            return validate(obj), errors
        except shared.INVALID as exc:
            errors.append(str(exc)[:800])
    return None, errors


def revision(ledger, batch, end, data, spec, files, feedback, max_files):
    base = BUILD / batch
    context = {"public_project": core.prefix(data, end), "new_requirements": data["requirements"][end-4:end],
               "current_files": files, "frozen_interface": spec["controls"], "fixed_example": method.first(spec),
               "previous_public_feedback": feedback, "maximum_changed_files": max_files}
    proposal, errors = checked_call(ledger, base / "plan", DESIGN, context, PLAN_TOOL,
                                   lambda obj: revision_plan(obj, max_files), 4500)
    evidence = {"through": end, "batch": batch, "selection_errors": errors, "writes": []}
    if not proposal:
        return files, evidence, None
    evidence["proposal"] = proposal
    updated = dict(files)
    for i, change in enumerate(proposal["files"], 1):
        name = change["path"]
        tool = {"name": "write_file", "description": "Replace the one named file in the working project with complete source.",
                "parameters": core.obj({"path": {"type": "string", "enum": [name]}, "content": STR})}
        obj = {**context, "current_files": updated, "planned_edits": proposal["files"], "requested_edit": change}
        content, errors = checked_call(ledger, base / f"file-{i}", AUTHOR, obj, tool,
                                       lambda args: source(args, name), 8500)
        receipt = {"path": name, "public_errors": errors, "accepted": content is not None}
        if content is not None:
            updated[name] = content
            checkpoint = base / f"file-{i}/accepted.json"
            SAVE(checkpoint, {"path": name, "content": content})
            receipt["checkpoint_sha256"] = sha(checkpoint)
        evidence["writes"].append(receipt)
    result = method.examine(data, {**spec, "smoke": proposal["smoke"]}, updated, BUILD / (batch + "-page"))
    SAVE(BUILD / (batch + "-public-check.json"), result)
    SAVE(base / "files.json", updated)
    evidence.update(source_sha256=sha(base / "files.json"), load_errors=result["load_errors"], probe=result["probe"])
    print(batch, "accepted writes", sum(r["accepted"] for r in evidence["writes"]),
          "load errors", len(result["load_errors"]), "probe", (result["probe"] or {}).get("passed"), flush=True)
    return updated, evidence, result


def build(ledger):
    status = BUILD / "status.json"
    if status.exists():
        return read(status)
    data, spec = read(OUT / "public.json"), read(OUT / "interface.json")
    files, history = dict(data["starter"]), []
    try:
        for end in previous.BATCH_ENDS:
            selected = f"through-{end}"
            files, feedback, result = revision(ledger, selected, end, data, spec, files, history[-1:], 8)
            history.append(feedback)
        if not result or result["load_errors"] or not result["probe"]["passed"]:
            prior_files, prior_selected, prior_result = files, selected, result
            selected = "integration-repair"
            files, feedback, result = revision(ledger, selected, 20, data, spec, files, history[-1:], 3)
            history.append(feedback)
            if (not result or result["load_errors"]) and prior_result and not prior_result["load_errors"]:
                files, selected, result = prior_files, prior_selected, prior_result
        if files == data["starter"] or not result or result["load_errors"]:
            raise ValueError("Final workspace has no accepted implementation or did not load")
        SAVE(BUILD / "package.json", {"spec": spec, "sources": files})
        state = {"status": "valid", "selected": selected, "first_files": result["files"],
                 "package_sha256": sha(BUILD / "package.json"), "controls": spec["controls"]}
    except shared.MISSING as exc:
        state = {"status": "missing", "reason": str(exc)}
    except shared.INVALID as exc:
        state = {"status": "invalid", "reason": str(exc)}
    state["revisions"] = history
    SAVE(status, state)
    return state


def publish(check):
    shared.verify()
    reg = read(OUT / "registered.json")
    result = {"study": "Native per-file tool writes for a Self-built table library",
        "project": "table", "model": MODEL, "registered_utc": reg["utc"], "end_utc": reg["end"],
        "registration_sha256": sha(OUT / "registered.json"), "files_at_registration": reg["files"],
        "budget_usd": CAP, "previous_editor_exposure_usd": reg["previous_exposure_usd"], "tasks": reg["tasks"],
        "batch_ends": reg["batch_ends"], "upstream_commit": browser.UPSTREAM_COMMIT,
        **report.model_report(OUT, TAG, MODEL, "table", read(previous.BASELINE))}
    if check:
        assert result == read(OUTPUT)
    else:
        SAVE(OUTPUT, result)
    print(result["summary"], result["cost_by_phase"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "generate", "score", "publish", "check"))
    args = parser.parse_args()
    shared.configure(OUT, "table", MODELS, END)
    if args.action == "register":
        register()
    elif args.action == "generate":
        with browser.lock(OUT / ".generate.lock"):
            shared.verify()
            build(Ledger(BASE / "budget.sqlite3", CAP, CAP))
            # The shared deployment runner reads the already frozen build status and package.
            shared.generate(TAG)
    elif args.action == "score":
        shared.score(TAG)
    else:
        publish(args.action == "check")


if __name__ == "__main__":
    main()
