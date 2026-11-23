"""Replay original Duo selections, measuring public single/combination source overlap."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import subprocess

from experiments.webapp1k_probe import STAGING
from studies.public_library_transfer_extra import evaluate as base
from studies.public_library_transfer_extra.duo_admission import DIR, GROUPS
from studies.public_library_transfer_extra.generate import (
    ATTEMPTS,
    HERE,
    OUT,
    ROOT,
    dump,
    read,
    sha,
)

RESULT = (
    ROOT / "studies/results/public-library-transfer-duo-public-admission-20261123.json"
)


def overlap(targets):
    singles = read(OUT / "build-inputs.json")
    inputs = {f"{g}/{k}": v for g in GROUPS for k, v in singles[g].items()}
    inputs.update({f"combo/{k}": v["public"]["jest"] for k, v in targets.items()})
    cmd = ["node", str(HERE / "duo_test_overlap.cjs")]
    cases = json.loads(
        subprocess.check_output(
            cmd,
            text=True,
            input=json.dumps(
                dict(parserDir=str(STAGING / "node_modules"), inputs=inputs)
            ),
        )
    )
    refs = {}
    for k, v in cases.items():
        if k.startswith("combo/"):
            continue
        if len(v) != 2:
            raise ValueError("Single test file must contain two top-level test cases")
        for case in v:
            refs.setdefault((k.split("/")[0], case["normalized"]), []).append(
                (k, case["title"])
            )
    by_task = {}
    hit = 0
    raw_hit = 0
    unique = set()
    for task, meta in targets.items():
        combo = cases["combo/" + task]
        if len(combo) != 4:
            raise ValueError("Duo test file must contain four top-level cases")
        rows = []
        for case in combo:
            matches = refs.get((meta["group"], case["normalized"]), [])
            exact = any(
                other["raw"] == case["raw"]
                for key, _ in matches
                for other in cases[key]
            )
            hit += bool(matches)
            raw_hit += exact
            unique.update((k, title) for k, title in matches)
            rows.append(
                dict(
                    title=case["title"],
                    sha256=case["normalized"],
                    sources=matches,
                    exact_without_jsx_normalization=exact,
                )
            )
        by_task[task] = rows
    return dict(
        test_cases=sum(map(len, by_task.values())),
        normalized_matches=hit,
        raw_matches=raw_hit,
        full_match_files=sum(all(t["sources"] for t in v) for v in by_task.values()),
        files=len(targets),
        unique_single_cases_reused=len(unique),
        available_public_single_cases=sum(
            len(c) for k, c in cases.items() if not k.startswith("combo/")
        ),
        details=by_task,
    )


def main(workers):
    main_seal = read(OUT / "sealed.json")
    prereg = read(DIR / "registered.json")
    if (
        sha(OUT / "sealed.json") != prereg["main_seal_sha256"]
        or sha(base.RESULT) != prereg["original_results_sha256"]
    ):
        raise ValueError("Original subscription study changed")
    sealed = read(DIR / "libraries-sealed.json")
    menus = read(OUT / "plans-registered.json")["interfaces"]
    targets = {
        k: r for k, r in read(OUT / "targets.json").items() if r["group"] != "todomvc"
    }
    orig = read(base.RESULT)["rows"]
    jobs = {}
    rows = {}
    phase_results = {}
    for task, meta in targets.items():
        group = meta["group"]
        row = dict(group=group, direct=orig[task]["arms"]["direct"]["passed"], arms={})
        rows[task] = row
        for rep in ATTEMPTS:
            key = f"{group}/{rep}"
            status = sealed["builds"][key]
            for mode in ("dna", "first"):
                arm = f"{mode}-{rep}"
                old = orig[task]["arms"][arm]["passed"]
                data = dict(
                    original_passed=old,
                    build_status=status["status"],
                    strict_policy_passed=False,
                )
                row["arms"][arm] = data
                if not status.get("source_available"):
                    continue
                path = DIR / group / rep / "frozen-library.json"
                if sha(path) != status["source_sha256"]:
                    raise ValueError("Sealed library changed")
                sources = {
                    f"atoms/{e['id']}.js": e["source"] for e in read(path)["components"]
                }
                old_files = base.candidate(task, meta, arm, menus, main_seal)
                files = {
                    p: sources[p] if p.startswith("atoms/") else text
                    for p, text in old_files.items()
                }
                h = hashlib.sha256(
                    json.dumps(files, sort_keys=True).encode()
                ).hexdigest()
                data["candidate_sha256"] = h
                ident = (task, h)
                if ident not in jobs:
                    jobs[ident] = (
                        (group, meta, files, DIR / "duo-replay" / task / h, None),
                        [],
                    )
                jobs[ident][1].append(data)
    keys = list(jobs)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for key, v in zip(keys, pool.map(base.score, [jobs[k][0] for k in keys])):
            for entry in jobs[key][1]:
                entry.update(
                    post_candidate_passed=v["passed"],
                    strict_policy_passed=entry["build_status"] == "admitted"
                    and v["passed"],
                    report_sha256=v["report_sha256"],
                )
    for group in (*GROUPS, "webapp1k-duo"):
        subset = {
            k: v
            for k, v in rows.items()
            if group == "webapp1k-duo" or group == v["group"]
        }
        phase_results[group] = dict(
            n=len(subset),
            shared_direct=sum(v["direct"] for v in subset.values()),
            arms={},
        )
        for rep in ATTEMPTS:
            for mode in ("dna", "first"):
                arm = mode + "-" + rep
                vals = {k: v["arms"][arm] for k, v in subset.items()}
                phase_results[group]["arms"][arm] = dict(
                    original=sum(r["original_passed"] for r in vals.values()),
                    post_scored=sum(
                        "post_candidate_passed" in r for r in vals.values()
                    ),
                    post_passed=sum(
                        r.get("post_candidate_passed", False) for r in vals.values()
                    ),
                    strict_policy_passed=sum(
                        r["strict_policy_passed"] for r in vals.values()
                    ),
                    strict_admitted_targets=sum(
                        r["build_status"] == "admitted" for r in vals.values()
                    ),
                    gains=[
                        k
                        for k, r in vals.items()
                        if r.get("post_candidate_passed") and not r["original_passed"]
                    ],
                    losses=[
                        k
                        for k, r in vals.items()
                        if r["original_passed"]
                        and r.get("post_candidate_passed") is False
                    ],
                )
    by_build = {}
    for k, v in sealed["builds"].items():
        by_build[k] = dict(
            status=v["status"],
            failed_before=v.get("failed_single"),
            repair_attempted=v.get("repair_attempted"),
            single_before={
                t: r["passed"] for t, r in v.get("initial_single", {}).items()
            },
            single_after={t: r["passed"] for t, r in v.get("final_single", {}).items()},
        )
    calls = {}
    for f in sorted(DIR.glob("*/*/*/status.json")):
        status = read(f)
        if f.parent.name in ("matching", "repair"):
            calls[str(f.parent.relative_to(DIR))] = dict(
                status=status["status"],
                usage=status.get("usage"),
                session=status.get("session"),
                prompt_sha256=status["prompt_sha256"],
            )
    result = dict(
        study="public-library-transfer-duo-public-admission-20261123",
        exploratory=True,
        design="Registered after viewing original Duo outcomes. Matching and one conditional repair consumed only the component menus, public single tests, original modules, and machine-extracted single-test failures. Original Duo planner outputs and first examples were replayed after all libraries were sealed.",
        registered=prereg["registered"],
        libraries_sealed=sealed["sealed"],
        source_overlap=overlap(targets),
        single_admission=by_build,
        panels=phase_results,
        rows=rows,
        subscription={
            "incremental_api_usd": 0,
            "subscription_price_allocation": None,
            "calls": calls,
        },
        original_result_sha256=sha(base.RESULT),
        protocol_sha256=prereg["protocol_sha256"],
        library_seal_sha256=sha(DIR / "libraries-sealed.json"),
    )
    dump(RESULT, result)
    print(
        json.dumps(
            dict(
                overlap={
                    k: v for k, v in result["source_overlap"].items() if k != "details"
                },
                admission=by_build,
                panels=phase_results,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workers", type=int, default=3)
    main(p.parse_args().workers)
