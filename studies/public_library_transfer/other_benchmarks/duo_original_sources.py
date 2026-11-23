"""Register and run the original Duo builder/deployer identities on fresh component menus."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import json
import time

from gui_dna.budget import BudgetStop, Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer_extra.generate import (
    HERE,
    OUT,
    ROOT,
    PLAN,
    PREFIX,
    dump,
    interface,
    now,
    read,
    sha,
)
from studies.public_library_transfer_extra.remote import CAP, DIR, END, MODELS, action

STUDY = DIR / "duo-original-sources"
PREFIX_KEY = "duo-original-sources"
ALIASES = ("deepseek", "qwen")
GROUPS = ("blogging", "taskmanagement")
STOP = {400, 401, 402, 403, 404, 422}


def body(alias, prompt, schema, role):
    model, p, c = MODELS[alias]
    return dict(
        model=model,
        messages=[dict(role="user", content=prompt)],
        temperature=0.6,
        seed=20261101,
        max_tokens=8192 if role == "build" else 550,
        provider=dict(
            allow_fallbacks=True,
            require_parameters=True,
            sort="price",
            max_price=dict(prompt=p, completion=c, request=0),
        ),
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "library" if role == "build" else "configuration",
                "strict": True,
                "schema": schema,
            },
        },
    )


def save_request(key, alias, body_json):
    path = DIR / "requests" / key / "body.json"
    if path.exists():
        if read(path) != body_json:
            raise RuntimeError("Incompatible previously registered request")
    else:
        dump(path, body_json)
    return dict(alias=alias, body_sha256=sha(path))


def register():
    dest = STUDY / "registered.json"
    if dest.exists():
        return
    credits = check_credits(0.5)
    if not credits["sufficient"]:
        raise BudgetStop("Insufficient available credit for source attempt")
    req = {}
    for alias in ALIASES:
        for group in GROUPS:
            path = OUT / "build" / group / "a"
            key = f"{PREFIX_KEY}/build/{alias}/{group}"
            req[key] = save_request(
                key,
                alias,
                body(
                    alias,
                    (path / "prompt.txt").read_text(),
                    read(path / "schema.json"),
                    "build",
                ),
            )
    targets = read(OUT / "targets.json")
    planned = [
        dict(builder=builder, deployer=alias, task=t)
        for same in (True, False)
        for builder in ALIASES
        for alias in ALIASES
        if (builder == alias) == same
        for t, m in targets.items()
        if m["group"] in GROUPS
    ]
    dump(
        dest,
        dict(
            registered=now(),
            credits=credits,
            shared_cap_usd=CAP,
            deadline=END.isoformat(),
            requests=req,
            planned=planned,
            protocol_sha256=sha(HERE / "DUO_ORIGINAL_SOURCES.md"),
            code_sha256=sha(HERE / "duo_original_sources.py"),
            main_seal_sha256=sha(OUT / "sealed.json"),
            registered_direct_sha256=sha(DIR / "registered.json"),
            original_history_report_sha256=sha(
                ROOT / "studies/webapp1k_dna/results/summary.json"
            ),
        ),
    )


def ask(key, meta, ledger):
    alias = meta["alias"]
    for stopped in [
        DIR / "endpoint-stops" / f"{alias}.json",
        DIR / "network-stops" / f"{alias}.json",
        STUDY / "endpoint-stops" / f"{alias}.json",
    ]:
        if stopped.exists():
            reason = read(stopped)["reason"]
            if (
                reason in {f"HTTP {n}" for n in STOP}
                or stopped.parent == STUDY / "endpoint-stops"
            ):
                return dict(status="unattempted", reason=reason)
    qdir = DIR / "requests" / key
    for i in range(4):
        trial = key if i == 0 else key + f"/network-admission-{i}"
        tdir = DIR / "requests" / trial
        if i:
            meta = save_request(trial, alias, read(qdir / "body.json"))
        try:
            state = action(trial, meta, ledger)
        except (RuntimeError, BudgetStop) as exc:
            dump(
                STUDY / "endpoint-stops" / f"{alias}.json",
                dict(reason=str(exc), request=trial),
            )
            return dict(status="unresolved", reason=str(exc))
        if state["status"] == "returned":
            return dict(
                status="returned", admission=trial, raw_sha256=state["raw_sha256"]
            )
        if state.get("http_status") in STOP:
            dump(
                STUDY / "endpoint-stops" / f"{alias}.json",
                dict(reason=state["reason"], request=trial),
            )
            return state
        if (tdir / "raw.json").exists():
            return state
        if i < 3:
            time.sleep(2**i)
    return state


def parsed(state):
    if state["status"] != "returned":
        raise ValueError("No received response")
    p = DIR / "requests" / state["admission"] / "raw.json"
    if sha(p) != state["raw_sha256"]:
        raise RuntimeError("Sealed response changed")
    return json.loads(read(p)["choices"][0]["message"]["content"])


def run():
    if not (DIR / "transport-sealed.json").exists() or (STUDY / "sealed.json").exists():
        raise RuntimeError(
            "Require completed prior network admission and a fresh source stage"
        )
    reg = read(STUDY / "registered.json")
    if (
        sha(HERE / "duo_original_sources.py") != reg["code_sha256"]
        or sha(OUT / "sealed.json") != reg["main_seal_sha256"]
    ):
        raise RuntimeError("Source registration changed")
    ledger = Ledger(DIR / "budget.sqlite3", CAP, CAP)

    def build_alias(alias):
        rows = {}
        for group in GROUPS:
            key = f"{PREFIX_KEY}/build/{alias}/{group}"
            state = ask(key, reg["requests"][key], ledger)
            try:
                value = parsed(state)
                menu = interface(group, value)
                package = STUDY / "libraries" / alias / group / "package.json"
                dump(package, value)
                state = state | dict(
                    admission_status="accepted", menu=menu, package_sha256=sha(package)
                )
            except (KeyError, ValueError, TypeError) as exc:
                state = state | dict(
                    admission_status="invalid"
                    if state["status"] == "returned"
                    else "missing",
                    reason=str(exc),
                )
            rows[alias + "/" + group] = state
        return rows

    bfile = STUDY / "builds-sealed.json"
    if not bfile.exists():
        with ThreadPoolExecutor(max_workers=2) as pool:
            built = {}
            for kinds in pool.map(build_alias, ALIASES):
                built.update(kinds)
        dump(bfile, dict(sealed=now(), libraries=built))
    built = read(bfile)["libraries"]
    targets = read(OUT / "targets.json")
    planfile = STUDY / "plans-registered.json"
    if not planfile.exists():
        requests = {}
        unavailable = {}
        for item in reg["planned"]:
            alias, builder, task = item["deployer"], item["builder"], item["task"]
            group = targets[task]["group"]
            key = f"{PREFIX_KEY}/plan/{alias}/{builder}/{task}"
            lib = built[builder + "/" + group]
            if lib["admission_status"] != "accepted":
                unavailable[key] = lib["admission_status"]
                continue
            menu = lib["menu"]
            prompt = (
                PREFIX
                + PLAN
                + json.dumps(
                    dict(current=targets[task]["public"], library=menu),
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n"
            )
            requests[key] = save_request(
                key, alias, body(alias, prompt, menu["schema"], "plan")
            )
        dump(
            planfile,
            dict(
                registered=now(),
                build_seal_sha256=sha(bfile),
                requests=requests,
                unavailable=unavailable,
            ),
        )
    plans = read(planfile)

    def deploy(alias):
        out = {}
        for key, meta in plans["requests"].items():
            if meta["alias"] == alias:
                out[key] = ask(key, meta, ledger)
        return out

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = {}
        for rows in pool.map(deploy, ALIASES):
            results.update(rows)
    dump(
        STUDY / "sealed.json",
        dict(
            sealed=now(),
            plans=results,
            unavailable=plans["unavailable"],
            plan_registered_sha256=sha(planfile),
            direct_seal_sha256=sha(DIR / "transport-sealed.json"),
            builder_seal_sha256=sha(bfile),
            shared_ledger=ledger_read.totals(DIR / "budget.sqlite3"),
        ),
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("phase", choices=["register", "run"])
    args = p.parse_args()
    if args.phase == "register":
        register()
    else:
        with (DIR / "lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            run()
