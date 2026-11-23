"""Preregister, screen, and conditionally repair the frozen Duo libraries on single tests only."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import re
import shutil
import subprocess

from experiments.webapp1k_probe import REPO, STAGING, module_name
from studies.public_library_transfer_extra import evaluate as base
from studies.public_library_transfer_extra.generate import (
    ATTEMPTS,
    HERE,
    OUT,
    ROOT,
    STRING,
    dump,
    invoke,
    now,
    obj,
    read,
    request,
    sha,
)

DIR = ROOT / "artifacts/public-library-transfer-extra-duo-admission-20261123"
GROUPS = ("blogging", "taskmanagement")
MATCH = "Match each public single-feature request to the single frozen component that implements it. Use the menu descriptions. Return each identifier exactly once. Do not generate or change code.\n"
REPAIR = "Repair only the designated failing single-feature React modules, using the supplied official single-feature tests and failure feedback. Keep the exact frozen component IDs and default-export contract. Return complete replacement JavaScript module source for each requested ID, preserving independently composed behavior. Observe single-feature labels, role semantics, state changes, request side effects, and both success and error cases. Do not use tools or any other data.\n"
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def folders():
    return [DIR / group / rep for group in GROUPS for rep in ATTEMPTS]


def register():
    if DIR.exists():
        raise FileExistsError(DIR)
    inputs = read(OUT / "build-inputs.json")
    menus = read(OUT / "plans-registered.json")["interfaces"]
    requests = {}
    for path in folders():
        group, rep = path.parts[-2:]
        menu = menus[f"{group}/{rep}"]["menu"]["menu"]
        schema = obj(
            {
                k: {"type": "string", "enum": [e["id"] for e in menu]}
                for k in inputs[group]
            }
        )
        requests[f"{group}/{rep}"] = request(
            path / "matching",
            MATCH,
            dict(public_single=inputs[group], frozen_menu=menu),
            schema,
        )
    dump(
        DIR / "registered.json",
        dict(
            registered=now(),
            source_sha256=sha(Path(__file__)),
            protocol_sha256=sha(HERE / "DUO_ADMISSION.md"),
            original_results_sha256=sha(base.RESULT),
            main_seal_sha256=sha(OUT / "sealed.json"),
            inputs_sha256=sha(OUT / "build-inputs.json"),
            targets_sha256=sha(OUT / "targets.json"),
            requests=requests,
        ),
    )


def match():
    if (DIR / "matching-sealed.json").exists():
        return
    assert sha(Path(__file__)) == read(DIR / "registered.json")["source_sha256"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(invoke, [p / "matching" for p in folders()]))
    maps = {}
    for path in folders():
        group, rep = path.parts[-2:]
        folder = path / "matching"
        status = read(folder / "status.json")
        if status["status"] == "returned":
            assignments = read(folder / "reply.json")
            expected = read(OUT / "build-inputs.json")[group]
            ids = {
                c["id"]
                for c in read(OUT / "build" / group / rep / "reply.json")["components"]
            }
            if (
                set(assignments) == set(expected)
                and set(assignments.values()) == ids
                and len(ids) == len(expected)
            ):
                maps[f"{group}/{rep}"] = dict(
                    status="valid",
                    lookup=assignments,
                    reply_sha256=sha(folder / "reply.json"),
                )
                continue
        maps[f"{group}/{rep}"] = dict(status="invalid")
    dump(
        DIR / "matching-sealed.json",
        dict(sealed=now(), registered_sha256=sha(DIR / "registered.json"), maps=maps),
    )


def single(job):
    folder, group, name, source = job
    folder.mkdir(parents=True, exist_ok=True)
    if (folder / "verdict.json").exists():
        return name, read(folder / "verdict.json")
    stage = folder / "staging"
    stage.mkdir(exist_ok=True)
    shutil.copyfile(STAGING / "package.json", stage / "package.json")
    if not (stage / "node_modules").exists():
        (stage / "node_modules").symlink_to(
            STAGING / "node_modules", target_is_directory=True
        )
    src = stage / "src/react" / group
    src.mkdir(parents=True, exist_ok=True)
    original = REPO / "tests/react" / group / (name + ".test.js")
    test = src / original.name
    text = original.read_text()
    if text != read(OUT / "build-inputs.json")[group][name]:
        raise RuntimeError("Public single test changed")
    test.write_text(text)
    (src / (module_name(text) + ".js")).write_text(source)
    report = folder / "jest.json"
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("OPENROUTER_API_KEY", "OPENAI_API_KEY")
    } | {"CI": "true"}
    cmd = [
        "npm",
        "test",
        "--",
        "--runInBand",
        "--json",
        f"--outputFile={report}",
        "--runTestsByPath",
        str(test),
    ]
    with (folder / "jest.log").open("w") as log:
        subprocess.run(cmd, cwd=stage, env=env, stdout=log, stderr=log, timeout=180)
    data = read(report)["testResults"]
    if len(data) != 1 or Path(data[0]["name"]).resolve() != test:
        raise RuntimeError("Unexpected official file")
    cases = data[0]["assertionResults"]
    if len(cases) != 2 and (cases or not data[0].get("message")):
        raise RuntimeError("Expected two single-feature cases or suite load failure")
    feedback = []
    for case in cases:
        if case["status"] != "passed":
            msg = ANSI.sub("", case["failureMessages"][0]).split("\n    at ")[0]
            feedback.append(dict(public_case=case["title"], error=msg[:850]))
    if not cases:
        feedback.append(
            dict(
                public_case="suite_load",
                error=ANSI.sub("", data[0]["message"]).split("\n    at ")[0][:850],
            )
        )
    verdict = dict(
        passed=len(cases) == 2 and all(c["status"] == "passed" for c in cases),
        feedback=feedback,
        test_sha256=sha(original),
        source_sha256=sha(src / (module_name(text) + ".js")),
        report_sha256=sha(report),
    )
    dump(folder / "verdict.json", verdict)
    return name, verdict


def screen(path, lookup, library, phase, workers):
    group = path.parent.name
    scripts = {e["id"]: e["source"] for e in library["components"]}
    jobs = [
        (path / phase / k, group, k, scripts[component])
        for k, component in lookup.items()
    ]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return dict(pool.map(single, jobs))


def run(workers):
    if (DIR / "libraries-sealed.json").exists():
        return
    match()
    maps = read(DIR / "matching-sealed.json")["maps"]
    inputs = read(OUT / "build-inputs.json")
    seals = {}
    repairs = []
    started = {}
    for path in folders():
        group, rep = path.parts[-2:]
        key = f"{group}/{rep}"
        lookup = maps[key]
        if lookup["status"] != "valid":
            seals[key] = dict(status="mapping_failed")
            continue
        library = read(OUT / "build" / group / rep / "reply.json")
        before = screen(path, lookup["lookup"], library, "single-before", workers)
        failed = [k for k, v in before.items() if not v["passed"]]
        started[key] = (library, before, failed)
        if failed:
            folder = path / "repair"
            if not folder.exists():
                request(
                    folder,
                    REPAIR,
                    dict(
                        public_single=inputs[group],
                        library=library,
                        mapping=lookup["lookup"],
                        single_failure_feedback={
                            k: before[k]["feedback"] for k in failed
                        },
                        allowed_replacement_ids=[lookup["lookup"][k] for k in failed],
                    ),
                    obj({lookup["lookup"][k]: STRING for k in failed}),
                )
            repairs.append(folder)
    if not (DIR / "repairs-registered.json").exists():
        dump(
            DIR / "repairs-registered.json",
            dict(
                registered=now(),
                matching_sha256=sha(DIR / "matching-sealed.json"),
                requests={
                    str(p.relative_to(DIR)): dict(
                        prompt_sha256=sha(p / "prompt.txt"),
                        schema_sha256=sha(p / "schema.json"),
                    )
                    for p in repairs
                },
            ),
        )
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(invoke, repairs))
    for path in folders():
        group, rep = path.parts[-2:]
        key = f"{group}/{rep}"
        if key not in started:
            continue
        lookup = maps[key]["lookup"]
        library, before, failed = started[key]
        row = dict(
            initial_single=before,
            failed_single=failed,
            repair_attempted=bool(failed),
            source_available=False,
        )
        if failed:
            folder = path / "repair"
            status = read(folder / "status.json")
            replacements = (
                read(folder / "reply.json") if status["status"] == "returned" else {}
            )
            if set(replacements) != {lookup[k] for k in failed} or not all(
                isinstance(v, str) and v.strip() for v in replacements.values()
            ):
                seals[key] = row | dict(status="repair_invalid")
                continue
            for component in library["components"]:
                if component["id"] in replacements:
                    component["source"] = replacements[component["id"]]
            after = screen(path, lookup, library, "single-after", workers)
        else:
            after = before
        accepted = all(v["passed"] for v in after.values())
        dump(path / "frozen-library.json", library)
        seals[key] = row | dict(
            status="admitted" if accepted else "single_failed",
            final_single=after,
            source_available=True,
            source_sha256=sha(path / "frozen-library.json"),
        )
    dump(
        DIR / "libraries-sealed.json",
        dict(
            sealed=now(),
            matching_sha256=sha(DIR / "matching-sealed.json"),
            repairs_registration_sha256=sha(DIR / "repairs-registered.json"),
            builds=seals,
        ),
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("phase", choices=["register", "run"])
    p.add_argument("--workers", type=int, default=3)
    args = p.parse_args()
    register() if args.phase == "register" else run(args.workers)
