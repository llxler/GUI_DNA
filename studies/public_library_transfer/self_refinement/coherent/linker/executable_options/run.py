"""Freeze verified compile-time options before collecting the two deployment arms."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from gui_dna.budget import BudgetStop, Ledger
from scripts.check_openrouter_credits import check_credits
from studies.public_library_transfer import browser, core
from studies.public_library_transfer.self_refinement import method
from studies.public_library_transfer.self_refinement.coherent.linker import run as linker
from studies.public_library_transfer.self_refinement.native import run as native, transport
from studies.study_io import ROOT, read, sha

from . import options

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/executable-self-options-20261124"
PROJECT = "table"
BASE = OUT / PROJECT
CAP = 0.65
GROUPS = linker.GROUPS
SAVE = core.save


def verify():
    for name, fingerprint in read(OUT / "registered.json")["files"].items():
        assert sha(ROOT / name) == fingerprint, name


def register():
    if (OUT / "registered.json").exists():
        return verify()
    balance = check_credits(CAP)
    if not balance["sufficient"]:
        raise BudgetStop("Insufficient credit")
    prereg = OUT / "design-registration.json"
    assert read(prereg)["protocol_sha256"] == sha(HERE / "PROTOCOL.md")
    paths = [prereg, HERE / "PROTOCOL.md", Path(__file__), Path(options.__file__), HERE / "probe.cjs", Path(method.__file__),
             Path(native.__file__), Path(transport.__file__), Path(core.__file__), Path(browser.__file__), linker.OUT / "registered.json"]
    for name in ("public.json", "browser.json"):
        src = linker.OUT / PROJECT / name
        dest = BASE / name
        SAVE(dest, read(src))
        paths.extend((src, dest))
    for group in GROUPS:
        parent = linker.OUT / PROJECT / group / "build"
        assert read(parent / "status.json")["package_sha256"] == sha(parent / "package.json")
        assert read(prereg)["initial_sources"][str((parent / "package.json").relative_to(ROOT))] == sha(parent / "package.json")
        paths.extend((parent / "package.json", parent / "status.json", parent / "manifest.json"))
    SAVE(OUT / "registered.json", {"utc": core.now(), "end": transport.END.isoformat(), "model": transport.MODEL,
         "project": PROJECT, "groups": GROUPS, "tasks": native.TASKS, "budget_usd": CAP, "balance": balance,
         "files": {str(p.relative_to(ROOT)): sha(p) for p in paths}})


def build(root, group, ledger, data, pkg):
    folder = root / group / "build"
    if (folder / "status.json").exists():
        return read(folder / "status.json")
    fixed = folder / "original"
    files = options.emit(data, pkg, [], [], fixed)
    old = read(linker.OUT / PROJECT / group / "build/status.json")
    assert old["files"] == files and not browser.public_load(PROJECT, fixed)
    accepted, log = [], []
    feedback = []
    quota = 3
    missing = None
    for step in ("design", "repair"):
        context = {"public_project": data, "frozen_sources": pkg["sources"], "maximum_options": quota,
                   "already_accepted_ids": [o["id"] for o in accepted], "previous_public_feedback": feedback}
        try:
            raw = transport.request(folder / step, ledger, core.messages(options.DESIGN, context),
                f"table/{group}/{step}", 5100, seed=native.SEEDS[group], schema=options.SCHEMA)
            proposed = core.parse(raw)["options"]
            if not isinstance(proposed, list) or not 1 <= len(proposed) <= quota:
                raise ValueError(f"Expected one through {quota} options")
        except native.MISSING as exc:
            missing = str(exc)
            break
        except native.INVALID as exc:
            feedback = [{"error": str(exc)}]
            log.append({"round": step, "error": str(exc)})
            continue
        feedback = []
        for i, candidate in enumerate(proposed, 1):
            dest = folder / f"{step}-option-{i}"
            row = {"round": step, "candidate": candidate}
            try:
                option = options.verify_option(candidate, accepted, data, pkg, dest, fixed)
                accepted.append(option)
                row["accepted"] = True
            except native.INVALID as exc:
                row.update(accepted=False, reason=str(exc)[:900])
                feedback.append({"rejected_candidate": candidate, "reason": row["reason"]})
            if (dest / "witness.json").exists():
                row["observations"] = read(dest / "witness.json")
            log.append(row)
        quota = min(3-len(accepted), len(feedback))
        if not quota:
            break
    spec = {"controls": [{"id": o["id"], "example": "original", "values": ["original", "alternative"],
             "description": f"original: {o['original_behavior']} / alternative: {o['alternative_behavior']}"} for o in accepted]}
    SAVE(folder / "manifest.json", spec)
    SAVE(folder / "package.json", {"source_sha256": old["package_sha256"], "controls": spec["controls"], "options": accepted})
    status = {"status": "valid", "fixed_page": "build/original", "files": files,
              "package_sha256": sha(folder / "package.json"), "proposal_log": log, "transport_interruption": missing,
              "selection_status": "valid" if accepted else "missing" if missing else "invalid"}
    SAVE(folder / "status.json", status)
    print(group, "confirmed", len(accepted), "of", len(log), flush=True)
    return status


def generate(group):
    verify()
    browser.OUT = BASE
    ledger = Ledger(BASE / "budget.sqlite3", CAP, CAP)
    data = read(BASE / "public.json")
    pkg = read(linker.OUT / PROJECT / group / "build/package.json")
    built = build(BASE, group, ledger, data, pkg)
    chosen = read(BASE / group / "build/package.json")
    controls = chosen["controls"]
    schema = core.obj({c["id"]: {"type": "string", "enum": c["values"]} for c in controls})

    def target(n):
        folder = BASE / group / "targets" / str(n)
        if (folder / "status.json").exists():
            return read(folder / "status.json")
        if built["selection_status"] != "valid":
            row = {"status": built["selection_status"], "reason": built["transport_interruption"] or "No confirmed executable option"}
        else:
            try:
                user = {"public_project": core.prefix(data, n), "options": controls, "example": {c["id"]: "original" for c in controls}}
                raw = transport.request(folder / "call", ledger, core.messages(options.PLAN, user), f"table/{group}/target/{n}",
                                        1024, seed=native.SEEDS[group], schema=schema)
                choice = core.parse(raw)
                if not isinstance(choice, dict) or set(choice) != set(schema["properties"]) or any(
                        v not in ("original", "alternative") for v in choice.values()):
                    raise ValueError("Configuration outside frozen finite interface")
                alternatives = [k for k, v in choice.items() if v == "alternative"]
                files = options.emit(data, pkg, chosen["options"], alternatives, folder / "page")
                row = {"status": "valid", "plan": choice, "files": files}
            except native.MISSING as exc:
                row = {"status": "missing", "reason": str(exc)}
            except native.INVALID as exc:
                row = {"status": "invalid", "reason": str(exc)}
        SAVE(folder / "status.json", row)
        return row

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(target, native.TASKS))
    refs = [BASE / group / "build/status.json", *(BASE / group / "targets" / str(n) / "status.json" for n in native.TASKS)]
    SAVE(BASE / group / "seal.json", {str(f.relative_to(BASE)): sha(f) for f in refs})


def score():
    verify()
    source = linker.source.ORIGINAL / PROJECT
    target = BASE / "direct"
    for path, expected in read(source / "direct/seal.json").items():
        assert sha(source / path) == expected
    if not target.exists():
        target.symlink_to(source / "direct", target_is_directory=True)
    assert target.resolve() == (source / "direct").resolve()
    with patch.multiple(native, OUT=OUT, CAP=CAP, verify=verify):
        native.score(PROJECT)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("action", choices=("register", "generate", "score"))
    cli.add_argument("group", nargs="?", choices=GROUPS)
    args = cli.parse_args()
    if args.action == "register":
        register()
    elif args.action == "score":
        score()
    elif args.group:
        generate(args.group)
    else:
        cli.error("A library replicate is required")


if __name__ == "__main__":
    main()
