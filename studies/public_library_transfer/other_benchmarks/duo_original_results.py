"""Grade and pair freshly rebuilt original-model Duo libraries with original-model deployments."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json

from studies import ledger_read
from studies.public_library_transfer_extra import evaluate as base
from studies.public_library_transfer_extra.duo_original_sources import (
    ALIASES,
    GROUPS,
    STUDY,
    PREFIX_KEY,
    parsed,
)
from studies.public_library_transfer_extra.generate import OUT, ROOT, dump, read, sha
from studies.public_library_transfer_extra.remote import DIR, MODELS
from studies.public_library_transfer_extra.remote_scores import RESULT as DIRECT_RESULT

RESULT = (
    ROOT / "studies/results/public-library-transfer-duo-original-sources-20261123.json"
)


def bundle(module, library, config):
    modules = {e["id"]: e["source"] for e in library["components"]}
    if not isinstance(config, dict) or set(config) != {"first", "second"}:
        raise ValueError("Invalid plan fields")
    selected = list(
        dict.fromkeys(v for v in [config["first"], config["second"]] if v != "NONE")
    )
    if set(selected) - set(modules):
        raise ValueError("Unknown component selector")
    files = {}
    imports = ["import React from 'react';"]
    for i, key in enumerate(selected):
        files[f"atoms/{key}.js"] = modules[key]
        imports.append(f"import Component{i} from './atoms/{key}';")
    elements = "".join(f"<Component{i} {{...props}} />" for i in range(len(selected)))
    files[module + ".js"] = (
        "\n".join(imports)
        + f"\nexport default function App(props) {{ return <>{elements}</>; }}\n"
    )
    return files


def counts(rows):
    def scored(v):
        return dict(
            passed=sum(x.get("passed", False) for x in v),
            scored=sum("passed" in x for x in v),
            scheduled=len(v),
            statuses=dict(Counter(x["status"] for x in v)),
        )

    result = {a: scored([v[a] for v in rows]) for a in ("direct", "first", "dna")}
    result["paired"] = {}
    for arm in ("direct", "first"):
        shared = [
            (r["task"], r["dna"]["passed"], r[arm]["passed"])
            for r in rows
            if "passed" in r["dna"] and "passed" in r[arm]
        ]
        result["paired"][arm] = dict(
            n=len(shared),
            scheduled=len(rows),
            dna=sum(a for _, a, b in shared),
            control=sum(b for _, a, b in shared),
            only_dna=[t for t, a, b in shared if a and not b],
            only_control=[t for t, a, b in shared if b and not a],
        )
    return result


def delivery(state):
    if not state or state.get("status") != "returned":
        return {}
    path = DIR / "requests" / state["admission"] / "raw.json"
    if sha(path) != state["raw_sha256"]:
        raise RuntimeError("Sealed delivery changed")
    raw = read(path)
    choices = raw.get("choices") or []
    choice = choices[0] if choices else {}
    text = (choice.get("message") or {}).get("content")
    return dict(
        raw_sha256=state["raw_sha256"],
        finish_reason=choice.get("finish_reason"),
        completion_tokens=(raw.get("usage") or {}).get("completion_tokens"),
        visible_content_characters=len(text) if isinstance(text, str) else 0,
    )


def run(workers):
    seal = read(STUDY / "sealed.json")
    reg = read(STUDY / "registered.json")
    if (
        sha(DIR / "transport-sealed.json") != seal["direct_seal_sha256"]
        or sha(STUDY / "builds-sealed.json") != seal["builder_seal_sha256"]
    ):
        raise RuntimeError("Source or prior direct seal changed")
    targets = {
        k: v for k, v in read(OUT / "targets.json").items() if v["group"] in GROUPS
    }
    old = read(DIRECT_RESULT)
    if old["seal_sha256"] != seal["direct_seal_sha256"]:
        raise RuntimeError("Shared direct code came from a different generation seal")
    sources = read(STUDY / "builds-sealed.json")["libraries"]
    rows = {}
    jobs = {}
    for item in reg["planned"]:
        builder, deploy, task = item["builder"], item["deployer"], item["task"]
        meta = targets[task]
        sid = builder + "/" + meta["group"]
        status = sources[sid]
        key = f"{PREFIX_KEY}/plan/{deploy}/{builder}/{task}"
        direct = old["rows"][f"{deploy}/{task}/s0"]["arms"]["direct"]
        row = rows[f"{builder}/{deploy}/{task}"] = dict(
            **item, group=meta["group"], direct=direct
        )
        if status["admission_status"] != "accepted":
            for arm in ("first", "dna"):
                row[arm] = dict(status="build_" + status["admission_status"])
                if status["admission_status"] == "invalid":
                    row[arm]["passed"] = False
            continue
        path = STUDY / "libraries" / builder / meta["group"] / "package.json"
        if sha(path) != status["package_sha256"]:
            raise RuntimeError("Frozen code changed")
        library = read(path)
        for arm, state in [("first", None), ("dna", seal["plans"][key])]:
            if state and state["status"] != "returned":
                row[arm] = dict(status="unresolved", reason=state.get("reason"))
                continue
            try:
                conf = status["menu"]["first"] if state is None else parsed(state)
                files = bundle(meta["public"]["module"], library, conf)
            except (ValueError, KeyError, TypeError, IndexError) as exc:
                row[arm] = dict(
                    status="invalid",
                    passed=False,
                    reason=str(exc)[:300],
                    **delivery(state),
                )
                continue
            digest = hashlib.sha256(
                json.dumps(files, sort_keys=True).encode()
            ).hexdigest()
            entry = row[arm] = dict(
                status="valid",
                configuration=conf,
                candidate_sha256=digest,
                **delivery(state),
            )
            ident = (task, digest)
            if ident not in jobs:
                jobs[ident] = (
                    (
                        meta["group"],
                        meta,
                        files,
                        STUDY / "scoring" / task / digest,
                        None,
                    ),
                    [],
                )
            jobs[ident][1].append(entry)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        keys = list(jobs)
        for key, v in zip(keys, pool.map(base.score, [jobs[k][0] for k in keys])):
            for row in jobs[key][1]:
                row.update(v)
    panels = {}
    for builder in ALIASES:
        for deploy in ALIASES:
            panel = {}
            for g in (*GROUPS, "webapp1k-duo"):
                subset = [
                    r
                    for r in rows.values()
                    if r["builder"] == builder
                    and r["deployer"] == deploy
                    and (r["group"] == g or g == "webapp1k-duo")
                ]
                panel[g] = counts(subset)
            panels[builder + "/" + deploy] = panel
    costs = defaultdict(Counter)
    for c in ledger_read.calls(DIR / "budget.sqlite3"):
        terms = c["purpose"].split("/")
        if terms[0] != PREFIX_KEY:
            continue
        a = costs["/".join(terms[1:3])]
        a["calls"] += 1
        a["settled_microusd"] += c["actual"] or 0
        a["exposure_microusd"] += (
            c["actual"] if c["actual"] is not None else c["reserved"]
        )
        a["unsettled"] += c["actual"] is None
    result = dict(
        study="public-library-transfer-duo-original-sources-20261123",
        registered=reg["registered"],
        sealed=seal["sealed"],
        scope="Fresh source generation by each of two original model identities from public single tests; each deployer plans over each accepted category library; raw direct candidates shared with the historical-model transfer. One intended draw per two-feature target.",
        model_ids={a: MODELS[a][0] for a in ALIASES},
        sources={k: v | delivery(v) for k, v in sources.items()},
        panels=panels,
        rows=rows,
        cost_by_phase_and_model=dict(costs),
        account=dict(
            calls=sum(v["calls"] for v in costs.values()),
            settled_usd=sum(v["settled_microusd"] for v in costs.values()) / 1e6,
            exposure_usd=sum(v["exposure_microusd"] for v in costs.values()) / 1e6,
            unsettled_calls=sum(v["unsettled"] for v in costs.values()),
        ),
        shared_ledger=seal["shared_ledger"],
        first_response_only=True,
        direct_reference_sha256=sha(DIRECT_RESULT),
        seal_sha256=sha(STUDY / "sealed.json"),
        stop_conditions={
            p.stem: read(p) for p in (STUDY / "endpoint-stops").glob("*.json")
        },
    )
    dump(RESULT, result)
    print(
        {
            k: {a: (v[a]["passed"], v[a]["scored"]) for a in ("direct", "dna", "first")}
            for k, d in panels.items()
            for v in [d["webapp1k-duo"]]
        }
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workers", type=int, default=3)
    run(p.parse_args().workers)
