"""Register and run the chronological file-edit Self experiment."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import httpx

from gui_dna.budget import BudgetStop, Ledger
from scripts.check_openrouter_credits import check_credits
from studies.public_library_transfer import browser, core
from studies.public_library_transfer.self_refinement import method, report, run as shared
from studies.study_io import ROOT, read, sha
from studies.webbench.backbone_matrix import run as transport

from . import edit

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/incremental-self-table-20261124"
OUTPUT = ROOT / "studies/results/incremental-self-table-20261124.json"
BASELINE = ROOT / "studies/results/backbone-matrix-20261124.json"
MODEL = "openai/gpt-oss-120b"
TAG = "oss"
CAP = 2
MODELS = {TAG: (MODEL, CAP, 0.25, 1)}
END = datetime(2026, 11, 24, 5, 18, tzinfo=timezone.utc)
TASKS = range(1, 21)
BATCH_ENDS = (4, 8, 12, 16, 20)
save = core.save


def register():
    if (OUT / "registered.json").exists():
        return shared.verify()
    balance = check_credits(CAP)
    if not balance["sufficient"]:
        raise BudgetStop("Insufficient credit")
    res = httpx.get("https://openrouter.ai/api/v1/models", timeout=30)
    res.raise_for_status()
    route = next(r for r in res.json()["data"] if r["id"] == MODEL)
    save(OUT / "public.json", core.public_input("table"))
    save(OUT / "browser.json", browser.verify_contract("table"))
    files = [HERE / "PROTOCOL.md", Path(__file__), Path(edit.__file__), Path(shared.__file__),
             Path(transport.__file__), Path(method.__file__), Path(core.__file__), Path(browser.__file__),
             ROOT / "src/gui_dna/budget.py", BASELINE, OUT / "public.json", OUT / "browser.json"]
    save(OUT / "registered.json", {"utc": core.now(), "end": END.isoformat(), "project": "table",
         "models": MODELS, "parameters": {MODEL: route["supported_parameters"]}, "budget_usd": CAP,
         "balance": balance, "tasks": list(TASKS), "batch_ends": BATCH_ENDS,
         "files": {str(p.relative_to(ROOT)): sha(p) for p in files}})


def request(ledger, folder, system, obj, limit):
    return transport.request(TAG, ledger, folder, core.messages(system, obj),
        "build/table/" + str(folder.relative_to(OUT / TAG / "build")), limit)


def design(ledger, folder, data):
    context = {"public_project": data}
    for suffix in ("design", "design-repair"):
        answer = request(ledger, folder / suffix, edit.DESIGN, context, 3500)
        try:
            return edit.controls(answer)
        except shared.INVALID as exc:
            if suffix == "design-repair":
                raise
            context = {"public_project": data, "previous_answer": answer, "format_error": str(exc)}


def revision(ledger, folder, data, spec, files, end):
    stage = folder / f"through-{end}"
    context = {"project": data["project"], "init": data["init"], "assets": data["assets"],
        "earlier_requirements": data["requirements"][:end-4], "new_requirements": data["requirements"][end-4:end],
        "frozen_controls": spec["controls"], "first_example": method.first(spec), "current_files": files}
    first_loadable = None
    history = []
    for name in ("edit", "repair"):
        folder_name = f"through-{end}-{name}"
        try:
            answer = request(ledger, stage / name, edit.EDIT, context, 14000)
            candidate, probe = edit.changed(answer, files)
            check = method.examine(data, {**spec, "smoke": probe}, candidate, folder / (folder_name + "-page"))
            save(folder / (folder_name + "-public-check.json"), check)
            history.append({"attempt": name, "edited_files": edit.updates(files, candidate),
                            "load_errors": check["load_errors"], "probe": probe, "result": check["probe"]})
            if not check["load_errors"]:
                latest = (candidate, folder_name, check)
                if name == "repair" or check["probe"]["passed"]:
                    return latest, history
                first_loadable = latest
            issue = {"load_errors": check["load_errors"], "public_interaction_check": check["probe"]}
        except shared.INVALID as exc:
            history.append({"attempt": name, "format_error": str(exc)})
            issue = {"format_error": str(exc)}
        except shared.MISSING as exc:
            history.append({"attempt": name, "missing": str(exc)})
            if first_loadable:
                return first_loadable, history
            raise
        if name == "edit":
            context = {**context, "previous_edit_response": answer, "public_feedback": issue,
                       "retry": "Return all edits relative to current_files, including the public check."}
    if first_loadable:
        return first_loadable, history
    raise ValueError(f"No loadable incremental revision at batch {end}: {history[-1]}")


def build(ledger, data):
    folder = OUT / TAG / "build"
    status = folder / "status.json"
    if status.exists():
        return read(status)
    history = []
    try:
        spec = design(ledger, folder, data)
        save(folder / "interface.json", spec)
        files = data["starter"]
        for end in BATCH_ENDS:
            (files, selected, check), attempts = revision(ledger, folder, data, spec, files, end)
            stage_file = folder / f"through-{end}/files.json"
            save(stage_file, files)
            history.append({"through": end, "selected": selected, "source_sha256": sha(stage_file), "attempts": attempts})
            print("Accepted incremental edit through", end, selected, flush=True)
        save(folder / "package.json", {"spec": spec, "sources": files})
        state = {"status": "valid", "selected": selected, "package_sha256": sha(folder / "package.json"),
                 "probe": check["probe"], "first_files": check["files"], "controls": spec["controls"]}
    except shared.MISSING as exc:
        state = {"status": "missing", "reason": str(exc)}
    except shared.INVALID as exc:
        state = {"status": "invalid", "reason": str(exc)}
    state["revisions"] = history
    save(status, state)
    return state


def generate():
    shared.verify()
    base = OUT / TAG
    ledger = Ledger(base / "budget.sqlite3", CAP, CAP)
    data = read(OUT / "public.json")
    built = build(ledger, data)
    pkg = read(base / "build/package.json") if built["status"] == "valid" else None

    def target(n):
        folder = base / "plans" / str(n)
        if (folder / "status.json").exists():
            return read(folder / "status.json")
        row = {"task": n, "status": built["status"]}
        if pkg is None:
            row["reason"] = "library " + built["status"]
        else:
            spec = pkg["spec"]
            user = {"public_project": core.prefix(data, n), "controls": spec["controls"], "output_example": method.first(spec)}
            try:
                raw = transport.request(TAG, ledger, folder, core.messages(edit.PLAN, user), f"plan/table/{n}", 1600)
                plan = method.plan(raw, spec)
                hashes = method.emit(data, pkg["sources"], plan, folder / "page")
                row.update(status="valid", plan=plan, files=hashes)
            except shared.MISSING as exc:
                row.update(status="missing", reason=str(exc))
            except shared.INVALID as exc:
                row.update(status="invalid", reason=str(exc))
        save(folder / "status.json", row)
        return row

    with ThreadPoolExecutor(max_workers=5) as pool:
        rows = list(pool.map(target, TASKS))
    save(base / "seal.json", {"model": MODEL, "registered_sha256": sha(OUT / "registered.json"),
         "build_sha256": sha(base / "build/status.json"),
         "plans": {str(r["task"]): sha(base / "plans" / str(r["task"]) / "status.json") for r in rows}})


def publish(check):
    shared.verify()
    reg = read(OUT / "registered.json")
    result = {"study": "Chronological file edits for a Self-built table library",
        "project": "table", "model": MODEL, "registered_utc": reg["utc"], "end_utc": reg["end"],
        "registration_sha256": sha(OUT / "registered.json"), "files_at_registration": reg["files"],
        "budget_usd": CAP, "tasks": reg["tasks"], "batch_ends": reg["batch_ends"],
        "upstream_commit": browser.UPSTREAM_COMMIT,
        **report.model_report(OUT, TAG, MODEL, "table", read(BASELINE))}
    if check:
        assert read(OUTPUT) == result
    else:
        save(OUTPUT, result)
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
            generate()
    elif args.action == "score":
        shared.score(TAG)
    else:
        publish(args.action == "check")


if __name__ == "__main__":
    main()
