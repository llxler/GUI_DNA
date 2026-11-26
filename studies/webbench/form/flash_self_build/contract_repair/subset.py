"""Score-preserving registration boundaries for a deterministic finite-domain projection."""
import argparse
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from studies.study_io import ROOT, digest, now, read, sha
from ..run import browser, core, original
from . import run as targeted

TAG = "contract-subset-b"
OUT = targeted.batch.OUT / TAG
HERE = Path(__file__).resolve().parent


def bounded_subset(control):
    values = control["values"]
    if len(values) <= 8:
        return list(values)
    keep = {values[0], values[-1], control["default"], control["example"]}
    assert keep.issubset(values)
    for value in values:
        if len(keep) >= 8:
            break
        keep.add(value)
    result = [value for value in values if value in keep]
    assert len(set(result)) == len(result) == 8
    return result


def project(raw):
    changed = {c["id"]: bounded_subset(c) for c in raw["controls"]
               if c["type"] == "enum" and len(c["values"]) > 8}
    before = {c["id"]: c["values"] for c in raw["controls"] if c["id"] in changed}
    assert {k: len(v) for k,v in before.items()} == {"open-min-length": 9, "nps-score": 11}
    after = targeted.with_values(raw, changed)
    assert targeted.with_values(after, before) == raw
    same = {k: {"old": digest(raw[k]), "new": digest(after[k])} for k in raw if k != "controls"}
    assert all(a["old"] == a["new"] for a in same.values())
    return after, {"before": before, "after": changed,
                   "removed": {k: [v for v in orig if v not in changed[k]] for k, orig in before.items()},
                   "unchanged_sha256": same}


def register():
    paths = [HERE / "subset.md", Path(__file__), Path(targeted.__file__),
             targeted.batch.OUT / "contract-b/registration.json", targeted.batch.OUT / "contract-b/seal.json",
             targeted.A_SEAL, targeted.B_SEAL, targeted.LAST, targeted.batch.OUT / "inputs/form/public.json",
             Path(targeted.batch.__file__), Path(original.__file__), Path(core.__file__), Path(browser.__file__)]
    item = {"model": targeted.batch.MODEL, "scheduled": list(targeted.TASKS), "rule": "ordered-eight",
            "files": {str(p.relative_to(ROOT)): sha(p) for p in paths},
            "shared_cap_usd": targeted.batch.CAP, "deadline": targeted.batch.END.isoformat()}
    dest = OUT / "registration.json"
    if not dest.exists():
        assert not list((targeted.batch.OUT / "browser/scores").glob("**/score.json")), "Scores already available"
        core.save(dest, {"utc": now(), **item})
    assert all(read(dest)[k] == v for k,v in item.items())


def build(_ledger):
    dest = OUT / "form/build"
    status = dest / "status.json"
    if status.exists():
        return read(status)
    raw = core.parse(read(targeted.LAST)["choices"][0]["message"]["content"])
    projected, evidence = project(raw)
    core.save(dest / "corrected-raw.json", projected)
    core.save(dest / "projection.json", evidence)
    try:
        pkg = core.package(read(targeted.batch.OUT / "inputs/form/public.json"), original.normalized(deepcopy(projected)))
        for name, plan in (("default", pkg["defaults"]), ("first", pkg["examples"][0]["plan"])):
            dest_page = dest / name
            core.materialize("form", pkg, plan, dest_page)
            errors = browser.public_load("form", dest_page)
            core.save(dest / (name + "-public.json"), errors)
            if errors:
                raise ValueError(str(errors)[:1200])
        core.save(dest / "package.json", pkg)
        state = {"status": "valid", "package_sha256": sha(dest / "package.json"),
                 "fixed": str((dest / "first").relative_to(ROOT))}
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        state = {"status": "build_failed", "reason": f"{type(exc).__name__}: {exc}"}
    core.save(status, state)
    return state


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["register", "generate"])
    action = parser.parse_args().action
    if action == "register":
        register()
    else:
        with patch.multiple(targeted, TAG=TAG, OUT=OUT, build=build, register=register):
            targeted.generate()
