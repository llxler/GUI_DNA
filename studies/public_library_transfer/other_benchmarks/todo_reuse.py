"""Replay the preselected TodoMVC all-feature page across independent feature targets."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json

from studies.public_library_transfer_extra.generate import (
    HERE,
    OUT,
    ROOT,
    dump,
    now,
    read,
    sha,
)
from studies.public_library_transfer_extra.evaluate import (
    MissingCandidate,
    RESULT,
    candidate,
    score,
)
from studies.todomvc_dna import evaluate as todo

OUTFILE = ROOT / "studies/results/public-library-transfer-todo-reuse-20261123.json"


def register():
    target_file = OUT / "targets.json"
    rows = {k: v for k, v in read(target_file).items() if v["group"] == "todomvc"}
    target = next(reversed(rows))
    if not all(
        set(r["features"]) <= set(rows[target]["features"]) for r in rows.values()
    ):
        raise ValueError("Last public target must include the features of every target")
    out = OUT / "todo-reuse-registered.json"
    if out.exists() or (OUT / "scoring").exists():
        raise RuntimeError("Must register once before scoring")
    dump(
        out,
        dict(
            registered=now(),
            protocol_sha256=sha(HERE / "TODOMVC_REUSE.md"),
            code_sha256=sha(HERE / "todo_reuse.py"),
            target_input_sha256=sha(target_file),
            selection="Last original public requirement, containing all six optional features.",
            fixed_page_target=target,
            targets=list(rows),
            arms=["direct", "dna-a", "dna-b"],
        ),
    )


def evaluate(workers):
    reg = read(OUT / "todo-reuse-registered.json")
    seal = read(OUT / "sealed.json")
    targets = read(OUT / "targets.json")
    if sha(OUT / "targets.json") != reg["target_input_sha256"]:
        raise RuntimeError("Target set changed")
    menus = read(OUT / "plans-registered.json")["interfaces"]
    study = read(RESULT)
    subject = reg["fixed_page_target"]
    scores = {}
    server = todo.Server(OUT)
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for arm in reg["arms"]:
                try:
                    files = candidate(subject, targets[subject], arm, menus, seal)
                    digest = hashlib.sha256(
                        json.dumps(files, sort_keys=True).encode()
                    ).hexdigest()
                    jobs = [
                        (
                            "todomvc",
                            targets[k],
                            files,
                            OUT / "scoring" / k / digest,
                            server,
                        )
                        for k in reg["targets"]
                    ]
                    fixed = {
                        k: g["passed"]
                        for k, g in zip(reg["targets"], pool.map(score, jobs))
                    }
                except MissingCandidate:
                    digest = None
                    fixed = {k: False for k in reg["targets"]}
                taskwise = {
                    k: study["rows"][k]["arms"][arm]["passed"] for k in reg["targets"]
                }
                scores[arm] = dict(
                    fixed_page_candidate_sha256=digest,
                    fixed_page_passed=sum(fixed.values()),
                    total=len(fixed),
                    taskwise_passed=sum(taskwise.values()),
                    rows=fixed,
                    only_fixed_page=[k for k in fixed if fixed[k] and not taskwise[k]],
                    only_taskwise=[k for k in fixed if taskwise[k] and not fixed[k]],
                )
    finally:
        server.close()
    dump(
        OUTFILE,
        dict(
            study="public-library-transfer-todo-reuse-20261123",
            scope="Replay of one public full-feature page per arm on eight independent TodoMVC scopes",
            registered=reg,
            main_result_sha256=sha(RESULT),
            results=scores,
        ),
    )
    print({a: (v["fixed_page_passed"], v["total"]) for a, v in scores.items()})


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("phase", choices=["register", "evaluate"])
    p.add_argument("--workers", type=int, default=3)
    args = p.parse_args()
    register() if args.phase == "register" else evaluate(args.workers)
