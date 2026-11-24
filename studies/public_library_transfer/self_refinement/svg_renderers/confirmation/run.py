"""Confirm the predeclared public linkage repairs on two newly sampled chart libraries."""

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from unittest.mock import patch
import argparse
from gui_dna.budget import Ledger
from studies.public_library_transfer import core, browser
from studies.study_io import ROOT, read, sha, now
from .. import run as base, components as comp, transport
from ..module_linking import run as links
from ..dom_tokens import run as dom
from ..runtime_patch import observe

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/qwen-svg-prospective-confirmation-20261124"
OLD = dom.RESULT
BAL = ROOT / "artifacts/svg-confirmation-balance-20261124.json"
END = datetime(2026, 11, 24, 11, 35, 30, tzinfo=timezone.utc)
CAP = 0.1


def register():
    orig = base.OUT / "public.json"
    paths = [
        HERE / "PROTOCOL.md",
        Path(__file__),
        Path(base.__file__),
        Path(comp.__file__),
        Path(transport.__file__),
        Path(links.__file__),
        links.HERE / "link.cjs",
        Path(dom.__file__),
        dom.HERE / "arguments.cjs",
        Path(observe.__file__),
        OLD,
        orig,
        BAL,
        dom.OUT / "seal.json",
    ]
    rec = {
        "sources": {str(p.relative_to(ROOT)): sha(p) for p in paths},
        "model": transport.MODEL,
        "cap_usd": CAP,
        "request_cutoff": END.isoformat(),
        "targets": list(base.TASKS),
        "harness": browser.verify_contract(comp.CHART),
    }
    assert read(BAL)["sufficient"]
    f = OUT / "registration.json"
    if not f.exists():
        core.save(f, {"utc": now(), "spec": rec})
    assert read(f)["spec"] == rec
    return read(orig)


def generate():
    data = register()
    if (OUT / "seal.json").exists():
        return
    ledger = Ledger(OUT / "budget.sqlite3", CAP, CAP)
    with (
        patch.object(base, "OUT", OUT),
        patch.object(transport, "END", END),
        patch.object(links, "OUT", OUT / "links"),
        patch.object(dom, "OUT", OUT / "tokens"),
    ):
        with ThreadPoolExecutor(max_workers=2) as pool:
            built = dict(
                zip(
                    ("A", "B"),
                    pool.map(lambda g: base.prepare(ledger, g, data), ("A", "B")),
                    strict=True,
                )
            )
        rows = []
        jobs = []
        for g, b in built.items():
            mods = read(OUT / g / "modules.json")
            if b["status"] == "valid":
                linked = links.link(b["selected"])
                row = dict(
                    b["selected"], **{"page": linked["page"], "files": linked["files"]}
                )
                observation = observe.public(OUT, ROOT / row["page"], row["files"])
                chosen, edits = dom.correct(row, dom.witnessed(observation))
                b["confirmation"] = {
                    "imports": linked["edits"],
                    "dom_edits": edits,
                    "before": observation,
                }
                mods = {
                    name: (ROOT / chosen["page"] / name).read_text() for name in mods
                }
                final = base.endpoint(OUT / g / "corrected", data, mods, base.ALL, True)
                b["selected"] = final
            else:
                final = {"status": b["status"]}
            for n in base.TASKS:
                rows.append(base.row(g, "fixed", n, final))
                jobs.append((ledger, g, n, data, b, mods))
        with ThreadPoolExecutor(max_workers=10) as pool:
            for j, p in zip(
                jobs, pool.map(lambda j: base.choose(*j), jobs), strict=True
            ):
                rows.append(base.row(j[1], "planned", j[2], p))
    core.save(
        OUT / "seal.json",
        {
            "utc": now(),
            "registration_sha256": sha(OUT / "registration.json"),
            "builds": built,
            "rows": rows,
            "previous_controls_sha256": sha(OLD),
        },
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("phase", choices=["register", "generate"])
    {"register": register, "generate": generate}[p.parse_args().phase]()
