"""Register all four fixed initial bundles, materialize public files and deploy."""

import argparse
from pathlib import Path
from unittest.mock import patch

from gui_dna.budget import BudgetStop
from scripts.check_openrouter_credits import check_credits
from studies.public_library_transfer import browser, core
from studies.public_library_transfer.self_refinement import method
from studies.public_library_transfer.self_refinement.coherent import run as source
from studies.public_library_transfer.self_refinement.native import run as native, transport
from studies.study_io import ROOT, read, sha

from . import modules

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/coherent-linker-20261124"
CAP = 0.4
GROUPS = ("build-a", "build-b")


def verify():
    record = read(OUT / "registered.json")
    for name, fingerprint in record["files"].items():
        if sha(ROOT / name) != fingerprint:
            raise ValueError(f"Registered source changed: {name}")


def register():
    if (OUT / "registered.json").exists():
        return verify()
    balance = check_credits(CAP * len(native.PROJECTS))
    if not balance["sufficient"]:
        raise BudgetStop("Insufficient credit")
    refs = [HERE / "PROTOCOL.md", Path(__file__), Path(modules.__file__), Path(native.__file__),
            Path(method.__file__), Path(transport.__file__), Path(core.__file__), Path(browser.__file__),
            source.OUT / "registered.json", ROOT / "src/gui_dna/budget.py",
            ROOT / "studies/results/self-native-20261124.json", ROOT / "studies/results/self-coherent-20261124.json"]
    for project in native.PROJECTS:
        for label in ("public.json", "browser.json", "paths.json"):
            orig = source.OUT / project / label
            dest = OUT / project / label
            core.save(dest, read(orig))
            refs.extend([orig, dest])
        for group in GROUPS:
            old = source.OUT / project / group / "build"
            spec = read(old / "manifest.json")
            dest = OUT / project / group / "build/manifest.json"
            core.save(dest, spec)
            refs.extend([old / "manifest.json", dest])
            for name in [source.SHARED] + [p for p in spec["files"] if p.endswith(".css")]:
                path = old / "initial" / name
                label = "program" if name == source.SHARED else "style"
                response = old / label / "response.json"
                assert method.source(read(response)["choices"][0]["message"]["content"]) == path.read_text()
                assert sha(response) == read(old / label / "settled.json")["response_sha256"]
                refs.extend([path, response, old / label / "settled.json"])
    core.save(OUT / "registered.json", {"utc": core.now(), "model": transport.MODEL,
        "end": transport.END.isoformat(), "projects": native.PROJECTS, "groups": GROUPS, "tasks": native.TASKS,
        "seeds": native.SEEDS, "cap_per_project": CAP, "balance": balance,
        "files": {str(p.relative_to(ROOT)): sha(p) for p in refs}})


def build(root, group, _ask, data):
    dest = root / group / "build"
    old = source.OUT / root.name / group / "build/initial"
    if (dest / "status.json").exists():
        return read(dest / "status.json")
    spec = read(dest / "manifest.json")
    program = (old / source.SHARED).read_text()
    styles = {p: (old / p).read_text() for p in spec["files"] if p.endswith(".css")}
    try:
        files, provenance = modules.compile_sources(program, styles, spec)
        core.save(dest / "link.json", provenance)
        tested = method.examine(data, spec, files, dest / "linked")
        core.save(dest / "public-check.json", tested)
        if tested["load_errors"]:
            raise ValueError("Public entry did not load: " + str(tested["load_errors"])[:500])
        core.save(dest / "package.json", {"spec": spec, "sources": files})
        state = {"status": "valid", "package_sha256": sha(dest / "package.json"), "fixed_page": "build/linked",
                 "files": tested["files"], "probe": tested["probe"]}
    except native.INVALID as exc:
        state = {"status": "invalid", "reason": str(exc)}
    core.save(dest / "status.json", state)
    print(root.name, group, state["status"], state.get("reason", ""), flush=True)
    return state


def attach_direct(project):
    original = source.ORIGINAL / project / "direct"
    for name, fingerprint in read(original / "seal.json").items():
        assert sha(source.ORIGINAL / project / name) == fingerprint
    target = OUT / project / "direct"
    if not target.exists():
        target.symlink_to(original, target_is_directory=True)
    assert target.resolve() == original.resolve()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "generate", "score"))
    parser.add_argument("project", choices=native.PROJECTS, nargs="?")
    parser.add_argument("group", choices=GROUPS, nargs="?")
    args = parser.parse_args()
    if args.action == "register":
        return register()
    if not args.project:
        parser.error("Choose a project")
    browser.OUT = OUT / args.project
    with patch.multiple(native, OUT=OUT, CAP=CAP, verify=verify, build=build):
        if args.action == "generate" and args.group:
            return native.generate(args.project, args.group)
        if args.action == "score":
            for p in native.PROJECTS:
                for g in GROUPS:
                    if not (OUT / p / g / "seal.json").is_file():
                        raise ValueError("Both projects must be sealed before official scoring")
            attach_direct(args.project)
            return native.score(args.project)
    parser.error("A replicate is required to generate")


if __name__ == "__main__":
    main()
