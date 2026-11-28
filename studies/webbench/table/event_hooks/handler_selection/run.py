"""Choose among the author's own event handlers using only the registered public checks."""

from itertools import combinations
from pathlib import Path
from unittest.mock import patch

from scripts.check_openrouter_credits import check_credits
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from .. import run as parent
from ..dom_contract import run as dom

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/table-handler-selection-20261128"
CAP = 0.35
ROLES = tuple(parent.ROLES)


def eligible(trial):
    return [
        (i, event)
        for i, event in enumerate(trial["events"])
        if event["checks"]["errors"]
        and all(event["checks"]["checks"][k] for k in parent.table.REQUIRED)
    ]


def register():
    dst = OUT / "registration.json"
    source = dom.OUT / "seal.json"
    previous = read(dom.OUT / "registration.json")
    seal = read(source)
    tags = [
        t
        for t, v in seal["libraries"].items()
        if v["status"] == "build_failed"
        and any(eligible(trial) for trial in v["trials"])
    ]
    paths = [
        Path(__file__),
        HERE / "PROTOCOL.md",
        Path(dom.__file__),
        Path(parent.__file__),
        parent.HERE / "dispatch.js",
        Path(parent.table.probes.__file__),
        dom.OUT / "registration.json",
        source,
    ]
    sums = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    if not dst.exists():
        upper = previous["upper"] + CAP
        assert upper <= 20
        balance = check_credits(CAP)
        assert balance["sufficient"]
        core.save(
            dst,
            dict(
                utc=now(),
                cap=CAP,
                upper=upper,
                deadline=previous["deadline"],
                sources=sums,
                balance=balance,
                models={t: previous["models"][t] for t in tags},
                contract=previous["contract"],
            ),
        )
    assert read(dst)["sources"] == sums
    return read(dst)


def build(tag, ledger, pub):
    dst = OUT / "libraries" / tag / "library.json"
    if dst.exists():
        return read(dst)
    source = read(dom.OUT / "seal.json")["libraries"][tag]
    trials = []
    adopted = None
    for trial in source["trials"]:
        origin = (
            parent.origin.structured.OUT
            / "libraries"
            / tag
            / str(trial["original_library"])
            / "attempt.json"
        )
        assert sha(origin) == trial["source_sha256"]
        old = read(origin)
        mods, base = old["design"], old["files"]
        contact = next((m["file"] for m in mods if 1 in m["requirements"]), None)
        for i, event in eligible(trial):
            hooks = event["hooks"]
            before = parent.composed(base, contact, hooks)
            prior = event["checks"]["checks"]
            observations = []
            for n in range(len(ROLES) + 1):
                for drop in combinations(ROLES, n):
                    current = {
                        role: ("" if role in drop else hooks[role]) for role in ROLES
                    }
                    parts = parent.composed(base, contact, current)
                    folder = (
                        dst.parent
                        / str(trial["attempt"])
                        / str(i)
                        / ("drop-" + ("-".join(drop) or "none"))
                    )
                    page = parent.table.emit(
                        pub, mods, parts, len(mods), folder / "page"
                    )
                    observed = parent.table.inspect(page, folder / "public")
                    ok = (
                        all(not v or observed["checks"][k] for k, v in prior.items())
                        and not observed["errors"]
                    )
                    observations.append(
                        dict(disabled=list(drop), admitted=ok, checks=observed)
                    )
                    if ok:
                        adopted = (mods, parts, before, base)
                        break
                if adopted:
                    break
            trials.append(
                dict(
                    attempt=len(trials) + 1,
                    original_library=trial["original_library"],
                    hook_build=trial["attempt"],
                    revision=i,
                    source_sha256=sha(origin),
                    checks=observations,
                    status="valid" if adopted else "build_failed",
                )
            )
            if adopted:
                break
        if adopted:
            break
    assert trials
    mods, parts, before, base = adopted or ([], {}, {}, {})
    core.save(
        dst,
        dict(
            status=trials[-1]["status"],
            attempt=trials[-1]["attempt"] if adopted else None,
            design=mods,
            parts=parts,
            before=before,
            original_modules=base,
            trials=trials,
            parent_seal=sha(dom.OUT / "seal.json"),
        ),
    )
    return read(dst)


def run():
    reg = register()
    save = core.save

    def seal_with_original(path, value):
        if Path(path) == OUT / "seal.json":
            value = dict(value)
            rows = list(value["rows"])
            for r in value["rows"]:
                if r["arm"] not in ("original-same-choice", "fixed-original"):
                    continue
                tag = r["tag"]
                lib = read(OUT / "libraries" / tag / "library.json")
                label = (
                    "unpatched-same-choice"
                    if r["arm"] == "original-same-choice"
                    else "fixed-unpatched"
                )
                if r["status"] == "valid":
                    page = parent.table.emit(
                        core.public_input("table"),
                        lib["design"],
                        lib["original_modules"],
                        r["count"],
                        OUT / "pages" / tag / label / str(r["count"]),
                    )
                else:
                    page = {"status": r["status"]}
                rows.append(
                    {k: r[k] for k in ("project", "tag", "task", "count")}
                    | dict(arm=label, **page)
                )
            value["rows"] = rows
            value["libraries"] = {
                t: {k: v for k, v in lib.items() if k != "original_modules"}
                for t, lib in value["libraries"].items()
            }
        save(path, value)

    with (
        patch.multiple(parent, OUT=OUT, CAP=CAP, build=build),
        patch.multiple(parent.table, OUT=OUT, HERE=HERE),
        patch.object(core, "save", seal_with_original),
    ):
        parent.generate(reg)
        if not (HERE / "result.json").exists():
            parent.table.score(reg)


if __name__ == "__main__":
    with browser.lock(OUT / "study.lock"):
        run()
