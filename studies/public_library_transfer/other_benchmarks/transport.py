"""Resume only preregistered historical deployments with no received response."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import shutil
import time

from gui_dna.budget import BudgetStop, Ledger
from studies import ledger_read
from studies.public_library_transfer_extra.generate import HERE, dump, now, read, sha
from studies.public_library_transfer_extra.remote import DIR, CAP, MODELS, action

BLOCK = {400, 401, 402, 403, 404, 422}


def register():
    dest = DIR / "transport-registered.json"
    if dest.exists():
        return
    dump(
        dest,
        dict(
            registered=now(),
            source_sha256=sha(HERE / "transport.py"),
            protocol_sha256=sha(HERE / "TRANSPORT.md"),
            rounds=3,
            primary_registration_sha256=sha(DIR / "registered.json"),
            ledger_cap_usd=CAP,
        ),
    )


def received(key):
    status = DIR / "requests" / key / "status.json"
    if not status.is_file():
        return None
    return read(status)


def recover(alias, reg):
    ledger = Ledger(DIR / "budget.sqlite3", CAP, CAP)
    stop = DIR / "endpoint-stops" / f"{alias}.json"
    stop_meta = read(stop) if stop.exists() else {}
    if any(stop_meta.get("reason") == "HTTP " + str(n) for n in BLOCK):
        return
    for i in range(1, 4):
        for key, meta in reg["requests"].items():
            if meta["alias"] != alias:
                continue
            base = DIR / "requests" / key
            trails = [key, *[f"{key}/network-admission-{j}" for j in range(1, i + 1)]]
            before = [(trail, received(trail)) for trail in trails]
            if any(s and (s.get("http_status") in BLOCK) for _, s in before):
                return
            if any(s and s["status"] == "returned" for _, s in before):
                continue
            if any(
                (DIR / "requests" / trail / "raw.json").exists() for trail, _ in before
            ):
                continue
            target = trails[-1]
            if before[-1][1]:
                continue
            folder = DIR / "requests" / target
            folder.mkdir(exist_ok=True)
            body_file = folder / "body.json"
            if not body_file.exists():
                shutil.copyfile(base / "body.json", body_file)
            try:
                state = action(target, meta, ledger)
            except (RuntimeError, BudgetStop) as exc:
                dump(
                    DIR / "network-stops" / f"{alias}.json",
                    dict(reason=str(exc), request=target),
                )
                return
            if state.get("http_status") in BLOCK:
                dump(
                    DIR / "network-stops" / f"{alias}.json",
                    dict(reason=state["reason"], request=target),
                )
                return
            if state["status"] != "returned":
                time.sleep(1)
    print(alias, "network stage complete", flush=True)


def run():
    plan = read(DIR / "transport-registered.json")
    if (
        sha(HERE / "transport.py") != plan["source_sha256"]
        or sha(DIR / "registered.json") != plan["primary_registration_sha256"]
    ):
        raise RuntimeError("Registered network continuation changed")
    if not (DIR / "sealed.json").exists() or (DIR / "transport-sealed.json").exists():
        raise RuntimeError("Require primary seal and new continuation")
    reg = read(DIR / "registered.json")
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(lambda alias: recover(alias, reg), MODELS))
    effective = {}
    statuses = {}
    for key in reg["requests"]:
        for step in [key, *[f"{key}/network-admission-{i}" for i in range(1, 4)]]:
            path = DIR / "requests" / step / "status.json"
            if path.exists():
                statuses[step] = sha(path)
                if (
                    key not in effective
                    or received(effective[key])["status"] != "returned"
                ):
                    effective[key] = step
    dump(
        DIR / "transport-sealed.json",
        dict(
            sealed=now(),
            statuses=statuses,
            effective_admission=effective,
            primary_seal_sha256=sha(DIR / "sealed.json"),
            network_registration_sha256=sha(DIR / "transport-registered.json"),
            account=ledger_read.totals(DIR / "budget.sqlite3"),
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
