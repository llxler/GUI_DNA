"""Grade sealed first responses offline and preserve each target's paired outcomes."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from studies.public_library_transfer_extra.generate import (
    ATTEMPTS,
    MODEL,
    OUT,
    ROOT,
    dump,
    read,
    sha,
)
from studies.todomvc_dna import evaluate as todo, review_evaluate
from experiments.webapp1k_probe import STAGING

RESULT = ROOT / "studies/results/public-library-transfer-extra-20261123.json"


class MissingCandidate(Exception):
    """Preregistered request produced no valid, deployable candidate."""


def candidate(task, row, arm, menus, seal, *, deployment=None):
    def deployed(name):
        return reply(name, seal) if deployment is None else deployment(name)

    group = row["group"]
    todo_task = group == "todomvc"
    if arm == "direct":
        response = deployed("direct/" + task)
        src = response["source"]
        if not isinstance(src, str) or not src.strip():
            raise MissingCandidate("Empty source")
        return {"candidate.js" if todo_task else row["public"]["module"] + ".js": src}
    method, rep = arm.split("-")
    menu = menus[group + "/" + rep]
    if menu["status"] != "accepted":
        raise MissingCandidate(menu["reason"])
    library = reply(f"build/{group}/{rep}", seal)
    if method == "first":
        plan = menu["menu"]["first"]
    else:
        plan = deployed(f"plan/{rep}/{task}")
    schema = menu["menu"]["schema"]["properties"]
    if set(plan) != set(schema):
        raise MissingCandidate("Unexpected switch keys")
    for k, v in plan.items():
        if schema[k]["type"] == "boolean" and type(v) is not bool:
            raise MissingCandidate("Non-boolean switch")
        if "enum" in schema[k] and v not in schema[k]["enum"]:
            raise MissingCandidate("Unknown component")
    if todo_task:
        return {
            "candidate.js": "(function(){\nconst DNA_CONFIG = Object.freeze("
            + json.dumps(plan, sort_keys=True)
            + ");\n"
            + library["source"]
            + "\n})();\n"
        }
    ids = list(dict.fromkeys(k for k in (plan["first"], plan["second"]) if k != "NONE"))
    modules = {e["id"]: e["source"] for e in library["components"]}
    imports = ["import React from 'react';"]
    files = {}
    for i, k in enumerate(ids):
        files[f"atoms/{k}.js"] = modules[k]
        imports.append(f"import Component{i} from './atoms/{k}';")
    elements = "".join(f"<Component{i} {{...props}} />" for i in range(len(ids)))
    files[row["public"]["module"] + ".js"] = (
        "\n".join(imports)
        + f"\nexport default function App(props) {{ return <>{elements}</>; }}\n"
    )
    return files


def reply(name, seal):
    path = OUT / name
    if sha(path / "status.json") != seal["calls"][name]:
        raise RuntimeError(f"Status hash changed: {name}")
    status = read(path / "status.json")
    if status["status"] != "returned":
        raise MissingCandidate(status["status"])
    if sha(path / "reply.json") != status["reply_sha256"]:
        raise RuntimeError(f"Reply hash changed: {name}")
    return read(path / "reply.json")


def jest(row, files, folder):
    stage = folder / "staging"
    stage.mkdir(exist_ok=True)
    shutil.copyfile(STAGING / "package.json", stage / "package.json")
    if not (stage / "node_modules").exists():
        (stage / "node_modules").symlink_to(
            STAGING / "node_modules", target_is_directory=True
        )
    src = stage / "src/react" / row["group"]
    for rel, code in files.items():
        out = src / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(code)
    public_test = ROOT / row["test"]
    if sha(public_test) != row["test_sha256"]:
        raise RuntimeError("Official Jest test changed")
    testcopy = src / public_test.name
    shutil.copyfile(public_test, testcopy)
    report = folder / "jest.json"
    report.unlink(missing_ok=True)
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("OPENAI_API_KEY", "OPENROUTER_API_KEY")
    }
    env["CI"] = "true"
    cmd = [
        "npm",
        "test",
        "--",
        "--runInBand",
        "--json",
        f"--outputFile={report}",
        "--runTestsByPath",
        str(testcopy),
    ]
    with (folder / "jest.log").open("w") as log:
        subprocess.run(
            cmd, cwd=stage, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=180
        )
    if not report.exists():
        raise RuntimeError("Jest produced no report: " + str(folder / "jest.log"))
    data = read(report)
    ran = data.get("testResults", [])
    if len(ran) != 1 or Path(ran[0]["name"]).resolve() != testcopy:
        raise RuntimeError("Expected one exact official test file")
    statuses = [v["status"] for v in ran[0]["assertionResults"]]
    if len(statuses) != 4 and (
        statuses or ran[0]["status"] != "failed" or not ran[0].get("message")
    ):
        raise RuntimeError(
            "Expected four official assertions or an explicit suite load error"
        )
    return dict(
        passed=ran[0]["status"] == "passed" and statuses == ["passed"] * 4,
        official_tests=4,
        assertion_statuses=statuses,
        suite_error=(ran[0].get("message") or "")[:500] if not statuses else "",
        report_sha256=sha(report),
    )


def score(job):
    group, row, files, directory, server = job
    directory.mkdir(parents=True, exist_ok=True)
    if (directory / "verdict.json").exists():
        return read(directory / "verdict.json")
    if group == "todomvc":
        page = todo.write_app(files["candidate.js"], directory / "app")
        report = directory / "playwright.json"
        graded = review_evaluate.grade(server.url(page), report, row["features"])
        result = dict(
            passed=graded["all_passed"],
            official_tests=graded["total"],
            short_circuit=graded["short_circuit"],
            report_sha256=sha(report),
        )
    else:
        result = jest(row, files, directory)
    dump(directory / "verdict.json", result)
    return result


def historical_reference():
    todo_base = ROOT / "studies/todomvc_dna/results/summary.json"
    blind = ROOT / "studies/results/blind-library.json"
    duo = ROOT / "studies/webapp1k_dna/results/summary.json"
    direct = {m["model"]: m["arms"]["free"] for m in read(todo_base)["models"]}
    prior_todo = {}
    for builder, library in read(blind)["builders"].items():
        prior_todo[builder] = {
            planner: dict(
                dna_first=scores["dna"]["first"],
                dna_n=scores["dna"]["n"],
                direct_first=direct[planner]["first_all"],
                direct_n=direct[planner]["n"],
            )
            for planner, scores in library["models"].items()
        }
    prior_duo = {
        m["model"]: {
            arm: dict(first=m["arms"][arm]["first_pass"], n=m["arms"][arm]["n"])
            for arm in ["dna", "free"]
        }
        for m in read(duo)["models"]
    }
    return dict(
        reason_for_separate_reporting="These are the same target IDs under earlier models, libraries and protocols. No historical model-matched comparison to the new subscription model.",
        todomvc=prior_todo,
        webapp1k_duo=prior_duo,
        sources={str(p.relative_to(ROOT)): sha(p) for p in [todo_base, blind, duo]},
    )


def summary(workers):
    seal = read(OUT / "sealed.json")
    reg = read(OUT / "registered.json")
    planning = read(OUT / "plans-registered.json")
    menus = planning["interfaces"]
    for file, key, source in [
        ("registered.json", "registered_sha256", seal),
        ("plans-registered.json", "plan_sha256", seal),
        ("targets.json", "target_sha256", reg),
        ("build-inputs.json", "input_sha256", reg),
    ]:
        if sha(OUT / file) != source[key]:
            raise ValueError(f"Input changed: {file}")
    if (
        sha(todo.SHELL) != reg["todo_shell_sha256"]
        or sha(todo.HARNESS / "demo-todo-app.spec.ts") != reg["todo_spec_sha256"]
    ):
        raise ValueError("TodoMVC shell or pinned official tests changed")
    targets = read(OUT / "targets.json")
    arms = [
        "direct",
        *[method + "-" + rep for rep in ATTEMPTS for method in ("dna", "first")],
    ]
    rows = {}
    server = todo.Server(OUT)
    todo_jobs = {}
    try:
        for task, row in targets.items():
            rows[task] = dict(group=row["group"], arms={})
            for arm in arms:
                try:
                    files = candidate(task, row, arm, menus, seal)
                except MissingCandidate as err:
                    rows[task]["arms"][arm] = dict(passed=False, reason=str(err))
                    continue
                digest = hashlib.sha256(
                    json.dumps(files, sort_keys=True).encode()
                ).hexdigest()
                key = (task, digest)
                folder = OUT / "scoring" / task / digest
                if key not in todo_jobs:
                    todo_jobs[key] = ((row["group"], row, files, folder, server), [])
                todo_jobs[key][1].append(arm)
        keys = list(todo_jobs)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for key, verdict in zip(
                keys, pool.map(score, [todo_jobs[k][0] for k in keys])
            ):
                for arm in todo_jobs[key][1]:
                    rows[key[0]]["arms"][arm] = dict(**verdict, candidate_sha256=key[1])
    finally:
        server.close()
    registered_requests = {**reg["requests"], **planning["requests"]}
    if set(registered_requests) != set(seal["calls"]):
        raise ValueError("Sealed call set differs from registered requests")
    stages = defaultdict(Counter)
    sessions = set()
    for name, digest in seal["calls"].items():
        path = OUT / name / "status.json"
        if sha(path) != digest:
            raise ValueError(f"Status changed: {name}")
        status = read(path)
        expected = registered_requests[name]
        for suffix, key in [
            ("prompt.txt", "prompt_sha256"),
            ("schema.json", "schema_sha256"),
        ]:
            if (
                sha(path.parent / suffix) != expected[key]
                or status[key] != expected[key]
            ):
                raise ValueError(f"Request input changed: {name}/{suffix}")
        group = (
            name.split("/")[1]
            if name.startswith("build/")
            else targets[name.split("/")[-1]]["group"]
        )
        key = name.split("/")[0] + "/" + group
        stages[key]["requests"] += 1
        stages[key]["returned"] += int(status["status"] == "returned")
        if status.get("session"):
            if status["session"] in sessions:
                raise ValueError("Reused subscription session")
            sessions.add(status["session"])
        for k, v in status.get("usage", {}).items():
            if isinstance(v, int):
                stages[key][k] += v
    totals = {}
    for group in ["todomvc", "blogging", "taskmanagement", "webapp1k-duo"]:
        eligible = {
            k: r
            for k, r in rows.items()
            if (
                r["group"] != "todomvc"
                if group == "webapp1k-duo"
                else r["group"] == group
            )
        }
        passes = {
            arm: [t for t, r in eligible.items() if r["arms"][arm]["passed"]]
            for arm in arms
        }
        paired = {}
        for rep in ATTEMPTS:
            dna = set(passes["dna-" + rep])
            paired[rep] = {}
            for control in ["direct", "first-" + rep]:
                cmp = set(passes[control])
                paired[rep][control] = dict(
                    only_dna=sorted(dna - cmp),
                    only_control=sorted(cmp - dna),
                    both=len(dna & cmp),
                    neither=len(eligible) - len(dna | cmp),
                )
        totals[group] = dict(
            targets=len(eligible),
            passed={arm: len(ids) for arm, ids in passes.items()},
            paired=paired,
        )
    result = dict(
        study="public-library-transfer-extra-20261123",
        scope="First response, exact historical target files, each source paired to one shared direct target generation. WebApp1K public Jest; TodoMVC official feature-selected tests.",
        model=MODEL,
        settings=reg["settings"],
        registered=reg["registered"],
        sealed=seal["sealed"],
        artifact_dir=str(OUT.relative_to(ROOT)),
        protocol_sha256=reg["protocol_sha256"],
        sealed_sha256=sha(OUT / "sealed.json"),
        subscription=dict(
            incremental_api_usd=0,
            subscription_price_allocation=None,
            stage_and_domain_usage=dict(stages),
        ),
        builds=menus,
        totals=totals,
        rows=rows,
        historical_reference=historical_reference(),
    )
    dump(RESULT, result)
    print(json.dumps(totals, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=3)
    summary(parser.parse_args().workers)
