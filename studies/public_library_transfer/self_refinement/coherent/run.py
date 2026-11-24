"""Implement the same model-designed controls in a single shared JavaScript module."""

import argparse
import json
import posixpath
from pathlib import Path

from gui_dna.budget import BudgetStop, Ledger
from scripts.check_openrouter_credits import check_credits
from studies.public_library_transfer import browser, core
from studies.public_library_transfer.self_refinement import method
from studies.public_library_transfer.self_refinement.native import (
    run as native,
    transport,
)
from studies.study_io import ROOT, read, sha

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/self-coherent-20261124"
ORIGINAL = ROOT / "artifacts/self-native-20261124"
CAP = 0.75
SHARED = "gui-dna-implementation.js"
SOURCE = """Write the COMPLETE application as ONE raw browser ES module. Do not import any source files.
Use the actual starter DOM. Use the accumulated public requirements to implement concrete state transitions,
menus, input editing, selection, keyboard/mouse events, required classes and public methods. Keep all mutable
state in this same implementation. Do not leave stubs. Export the named public symbols from this module.
A generic adapter at each specified public .js or .mjs path re-exports those symbols. Export a named object
PUBLIC_DEFAULTS mapping each public path that needs a default export to its actual class or function.
The starter script imports this module on page load. Mount the GUI from this module. A stylesheet will
be written after your code; preserve required DOM/CSS classes. Honor your own original configuration meanings
with globalThis.APP_CONFIG. Implement stable features with any selection. Do not use tasks as selectors or
fetch dependencies. Output raw JavaScript only, with no markdown or planning commentary. No tools."""
CSS = """Write the complete native CSS for the given interactive application. Read the existing markup,
the public visual requirements and the actual JavaScript DOM selectors. Cover every public requirement that
needs styling. Output raw CSS only. Do not make network requests."""
FIX = """The public browser check reported a problem. Repair the single shared JavaScript module. The
entrypoint and other public paths already re-export the module; no imports are necessary. Read the supplied
actual source and original requirements. Preserve all unrelated behavior, public exports and defaults.
Return the complete repaired raw JavaScript only. No tools or external resources."""


def register():
    if (OUT / "registered.json").is_file():
        verify()
        return
    available = check_credits(2 * CAP)
    if not available["sufficient"]:
        raise BudgetStop("Insufficient balance")
    paths = [
        Path(__file__),
        HERE / "PROTOCOL.md",
        Path(native.__file__),
        Path(method.__file__),
        Path(transport.__file__),
        Path(browser.__file__),
        Path(core.__file__),
        ORIGINAL / "registered.json",
    ]
    for p in native.PROJECTS:
        for name in ("public.json", "browser.json", "paths.json"):
            path = ORIGINAL / p / name
            core.save(OUT / p / name, read(path))
            paths.append(OUT / p / name)
        for g in ("build-a", "build-b"):
            path = ORIGINAL / p / g / "build/manifest.json"
            core.save(OUT / p / g / "build/manifest.json", read(path))
            paths.extend([path, OUT / p / g / "build/manifest.json"])
    core.save(
        OUT / "registered.json",
        {
            "utc": core.now(),
            "projects": native.PROJECTS,
            "groups": ["build-a", "build-b"],
            "seeds": native.SEEDS,
            "tasks": native.TASKS,
            "end": transport.END.isoformat(),
            "balance": available,
            "cap_per_project": CAP,
            "source_sha256": {str(p.relative_to(ROOT)): sha(p) for p in paths},
        },
    )


def verify():
    for name, h in read(OUT / "registered.json")["source_sha256"].items():
        if sha(ROOT / name) != h:
            raise ValueError(f"Registered input changed: {name}")


def material(spec, program, style):
    files = {SHARED: program}
    if SHARED in spec["files"]:
        raise ValueError("Conflicting public module name")
    for name in spec["files"]:
        if name.endswith(".css"):
            files[name] = style
            continue
        rel = posixpath.relpath(SHARED, posixpath.dirname(name) or ".")
        if not rel.startswith("."):
            rel = "./" + rel
        source = json.dumps(rel)
        files[name] = (
            f"export * from {source};\nimport * as app from {source};\n"
            f"export default app.PUBLIC_DEFAULTS?.[{json.dumps(name)}] ?? app.default;\n"
        )
    return files


def build(root, group, ask, data):
    loc = root / group / "build"
    if (loc / "status.json").is_file():
        return read(loc / "status.json")
    spec = read(loc / "manifest.json")
    try:
        inputs = {"starter_and_requirements": data, "my_design": spec}
        js = method.source(ask(loc / "program", SOURCE, inputs, "program", 16000))
        css = method.source(
            ask(loc / "style", CSS, {**inputs, "actual_js": js}, "style", 6000)
        )
        files = material(spec, js, css)
        check = method.examine(data, spec, files, loc / "initial")
        core.save(loc / "initial-check.json", check)
        selected = "initial"
        if check["load_errors"] or not check["probe"]["passed"]:
            try:
                response = ask(
                    loc / "repair",
                    FIX,
                    {
                        **inputs,
                        "current_program": js,
                        "css": css,
                        "load_errors": check["load_errors"],
                        "public_probe": check["probe"],
                    },
                    "repair",
                    16000,
                )
                revised = material(spec, method.source(response), css)
                new = method.examine(data, spec, revised, loc / "repaired")
                core.save(loc / "repaired-check.json", new)
                if not new["load_errors"]:
                    selected, files, check = "repaired", revised, new
            except native.INVALID + native.MISSING:
                if check["load_errors"]:
                    raise
        if check["load_errors"]:
            raise ValueError(
                "Final public load failed: " + str(check["load_errors"])[:400]
            )
        core.save(loc / "package.json", {"spec": spec, "sources": files})
        state = {
            "status": "valid",
            "package_sha256": sha(loc / "package.json"),
            "files": check["files"],
            "fixed_page": f"build/{selected}",
            "probe": check["probe"],
        }
    except native.INVALID as exc:
        state = {"status": "invalid", "reason": str(exc)}
    except native.MISSING as exc:
        state = {"status": "missing", "reason": str(exc)}
    core.save(loc / "status.json", state)
    return state


def attach_direct(project):
    source = ORIGINAL / project
    s = read(source / "direct/seal.json")
    for name, fingerprint in s.items():
        assert sha(source / name) == fingerprint
    target = OUT / project / "direct"
    if not target.exists():
        target.symlink_to(source / "direct", target_is_directory=True)
    assert target.resolve() == (source / "direct").resolve()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "verify", "generate", "score"))
    parser.add_argument("project", nargs="?", choices=native.PROJECTS)
    parser.add_argument("group", nargs="?", choices=("build-a", "build-b"))
    args = parser.parse_args()
    if args.action in ("register", "verify"):
        globals()[args.action]()
        return
    if not args.project:
        parser.error("A project is required")
    native.OUT, native.CAP, native.verify, native.build = OUT, CAP, verify, build
    if args.action == "score":
        attach_direct(args.project)
        native.score(args.project)
    elif args.group:
        native.generate(args.project, args.group)
    else:
        parser.error("A build replicate is required")


if __name__ == "__main__":
    main()
