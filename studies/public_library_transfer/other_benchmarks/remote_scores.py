"""Score sealed historical-model deployments on their registered targets and controls."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json

from studies import ledger_read
from studies.public_library_transfer_extra import evaluate as base
from studies.public_library_transfer_extra.generate import OUT, ROOT, dump, read, sha
from studies.public_library_transfer_extra.remote import DIR, MODELS
from studies.todomvc_dna import evaluate as todo

RESULT = (
    ROOT / "studies/results/public-library-transfer-historical-models-20261123.json"
)


def materialize(key, meta, seal, targets, menus, main_seal):
    if key not in seal["statuses"]:
        return dict(status="unattempted")
    path = DIR / "requests" / key
    if (
        sha(path / "body.json") != meta["body_sha256"]
        or sha(path / "status.json") != seal["statuses"][key]
    ):
        raise RuntimeError(f"Changed request or result: {key}")
    status = read(path / "status.json")
    if status["status"] != "returned":
        return dict(status="unresolved", reason=status["reason"])
    if sha(path / "raw.json") != status["raw_sha256"]:
        raise RuntimeError(f"Response changed: {key}")
    response = read(path / "raw.json")
    choices = response.get("choices", [])
    choice = choices[0] if choices else {}
    usage = response.get("usage") or {}
    content = (choice.get("message") or {}).get("content")
    delivery = dict(
        raw_sha256=status["raw_sha256"],
        finish_reason=choice.get("finish_reason"),
        visible_content_characters=len(content) if isinstance(content, str) else 0,
        completion_tokens=usage.get("completion_tokens"),
    )
    try:
        parsed = json.loads(content)
        files = base.candidate(
            meta["task"],
            targets[meta["task"]],
            meta["arm"],
            menus,
            main_seal,
            deployment=lambda _: parsed,
        )
    except (ValueError, TypeError, KeyError, IndexError, base.MissingCandidate) as exc:
        return dict(
            status="invalid",
            passed=False,
            reason=type(exc).__name__ + ": " + str(exc)[:300],
            **delivery,
        )
    digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    return dict(status="valid", candidate_sha256=digest, files=files, **delivery)


def compare(rows, first_scores):
    arms = ("direct", "dna-a", "dna-b")
    by_arm = {}
    for arm in arms:
        vals = [r["arms"][arm] for r in rows]
        by_arm[arm] = dict(
            passed=sum(v.get("passed", False) for v in vals),
            scored=sum("passed" in v for v in vals),
            scheduled=len(vals),
            status=dict(Counter(v["status"] for v in vals)),
            finish_reason=dict(
                Counter(
                    v["finish_reason"]
                    for v in vals
                    if v.get("finish_reason") is not None
                )
            ),
            returned_without_visible_content=sum(
                v.get("visible_content_characters") == 0 for v in vals
            ),
        )
    unique = list(dict.fromkeys(r["task"] for r in rows))
    fixed = {
        rep: dict(
            passed=sum(
                first_scores[t]["arms"]["first-" + rep]["passed"] for t in unique
            ),
            unique_targets=len(unique),
        )
        for rep in ("a", "b")
    }
    paired = {}
    for rep in ("a", "b"):
        one = {}
        for control in ("direct", "first-" + rep):
            pairs = []
            for row in rows:
                arm = row["arms"]["dna-" + rep]
                ctrl = (
                    row["arms"]["direct"]
                    if control == "direct"
                    else first_scores[row["task"]]["arms"][control]
                )
                if "passed" in arm and "passed" in ctrl:
                    pairs.append(
                        (
                            f"{row['task']}/s{row['sample']}",
                            arm["passed"],
                            ctrl["passed"],
                        )
                    )
            one[control] = dict(
                n=len(pairs),
                scheduled=len(rows),
                dna_passed=sum(a for _, a, b in pairs),
                control_passed=sum(b for _, a, b in pairs),
                only_dna=[k for k, a, b in pairs if a and not b],
                only_control=[k for k, a, b in pairs if b and not a],
                both=sum(a and b for _, a, b in pairs),
                neither=sum(not a and not b for _, a, b in pairs),
            )
        paired[rep] = one
    return dict(
        target_count=len(unique),
        scheduled_task_samples=len(rows),
        arms=by_arm,
        fixed_unique_targets=fixed,
        paired=paired,
    )


def report(workers, transport=False):
    reg = read(DIR / "registered.json")
    seal = read(DIR / "sealed.json")
    if (
        sha(DIR / "registered.json") != seal["registered_sha256"]
        or sha(OUT / "sealed.json") != reg["main_seal_sha256"]
    ):
        raise RuntimeError("Sealed registration changed")
    primary = seal
    seal_path = DIR / ("transport-sealed.json" if transport else "sealed.json")
    if transport:
        seal = read(seal_path)
        if seal["primary_seal_sha256"] != sha(DIR / "sealed.json"):
            raise RuntimeError("Primary seal changed")
    targets = read(OUT / "targets.json")
    menus = read(OUT / "plans-registered.json")["interfaces"]
    main_seal = read(OUT / "sealed.json")
    first = read(base.RESULT)["rows"]
    server = todo.Server(DIR)
    rows = {}
    jobs = {}
    try:
        for key, meta in reg["requests"].items():
            row_id = key.rsplit("/", 1)[0]
            row = rows.setdefault(
                row_id,
                {k: meta[k] for k in ("group", "task", "sample", "alias")}
                | {"arms": {}},
            )
            selected = seal.get("effective_admission", {}).get(key, key)
            arm = materialize(selected, meta, seal, targets, menus, main_seal)
            arm["admission"] = selected if selected in seal["statuses"] else None
            row["arms"][meta["arm"]] = arm
            if arm["status"] == "valid":
                files = arm.pop("files")
                ident = (meta["task"], arm["candidate_sha256"])
                if ident not in jobs:
                    task, digest = ident
                    jobs[ident] = (
                        (
                            meta["group"],
                            targets[task],
                            files,
                            DIR / "scoring" / task / digest,
                            server,
                        ),
                        [],
                    )
                jobs[ident][1].append(arm)
        keys = list(jobs)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for key, verdict in zip(
                keys, pool.map(base.score, [jobs[k][0] for k in keys])
            ):
                for arm in jobs[key][1]:
                    arm.update(verdict)
    finally:
        server.close()
    panels = defaultdict(dict)
    for alias in MODELS:
        for name in ("todomvc", "blogging", "taskmanagement", "webapp1k-duo"):
            rs = [
                r
                for r in rows.values()
                if r["alias"] == alias
                and (
                    r["group"] == name
                    if name != "webapp1k-duo"
                    else r["group"] != "todomvc"
                )
            ]
            if rs:
                panels[alias][name] = compare(rs, first)
    cost = defaultdict(Counter)
    for call in ledger_read.calls(DIR / "budget.sqlite3"):
        parts = call["purpose"].split("/")
        if "/".join(parts[:4]) not in reg["requests"]:
            continue
        if not transport and len(parts) > 4:
            continue
        alias, task, sample, arm = parts[:4]
        by = cost[f"{alias}/{targets[task]['group']}/{arm}"]
        by["calls"] += 1
        by["settled_microusd"] += call["actual"] or 0
        by["unsettled"] += call["actual"] is None
        by["exposure_microusd"] += (
            call["actual"] if call["actual"] is not None else call["reserved"]
        )
    result = dict(
        study="public-library-transfer-historical-models-20261123",
        models={k: v[0] for k, v in MODELS.items()},
        previously_reported_models={
            "todomvc": ["deepseek", "qwen30b", "mistral", "oss"],
            "webapp1k-duo": ["deepseek", "qwen"],
        },
        additional_deployments={"webapp1k-duo": ["mistral", "oss"]},
        builders="Two fresh independent GPT-6.2-astra subscription libraries, same sources as the main transfer. Category-specific component libraries for Duo.",
        first_received_response=True,
        network_continuation=transport,
        network_stops={
            p.stem: read(p) for p in sorted((DIR / "network-stops").glob("*.json"))
        }
        if transport
        else {},
        temperature=0.6,
        registered=reg["registered"],
        sealed=seal["sealed"],
        shared_ledger_at_seal=seal["account"],
        account=dict(
            calls=sum(v["calls"] for v in cost.values()),
            settled_usd=sum(v["settled_microusd"] for v in cost.values()) / 1e6,
            exposure_usd=sum(v["exposure_microusd"] for v in cost.values()) / 1e6,
            unsettled_calls=sum(v["unsettled"] for v in cost.values()),
            shared_cap_usd=seal["account"]["cap_usd"],
        ),
        cost_by_model_domain_arm=cost,
        endpoint_stops={
            p.stem: read(p) for p in sorted((DIR / "endpoint-stops").glob("*.json"))
        },
        panels=panels,
        rows=rows,
        fixed_reference_sha256=sha(base.RESULT),
        registered_sha256=primary["registered_sha256"],
        seal_sha256=sha(seal_path),
    )
    dest = (
        RESULT.with_name(
            "public-library-transfer-historical-models-initial-20261123.json"
        )
        if not transport
        else RESULT
    )
    dump(dest, result)
    print(
        json.dumps(
            {
                m: {
                    d: {a: (v["passed"], v["scored"]) for a, v in panel["arms"].items()}
                    for d, panel in dd.items()
                    if d in ("todomvc", "webapp1k-duo")
                }
                for m, dd in panels.items()
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--transport", action="store_true")
    args = parser.parse_args()
    report(args.workers, args.transport)
