"""Recover a malformed visible Flash schema without changing any implementation bytes."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from gui_dna.budget import BudgetStop, Ledger
from studies.study_io import ROOT, digest, now, read, sha
from .. import run as batch
from .. import resume
from ..run import browser, core, original

HERE = Path(__file__).resolve().parent
TAG = "contract-b"
OUT = batch.OUT / TAG
A_SEAL = batch.OUT / "delivery-a/seal.json"
B_SEAL = batch.OUT / "delivery-b/seal.json"
LAST = batch.OUT / "delivery-b/form/build/attempt-2/response.json"
TASKS = range(1, 21)


def register():
    paths = [HERE / "PROTOCOL.md", Path(__file__), Path(batch.__file__), Path(resume.__file__),
             Path(original.__file__), Path(browser.__file__), Path(core.__file__),
             batch.OUT / "registration.json", batch.OUT / "deployment-adapter.json",
             batch.OUT / "inputs/form/public.json", A_SEAL, B_SEAL, LAST]
    item = {"files": {str(p.relative_to(ROOT)): sha(p) for p in paths}, "scheduled": list(TASKS),
            "model": batch.MODEL, "ledger": str((batch.OUT / "budget.sqlite3").relative_to(ROOT)),
            "shared_cap_usd": batch.CAP, "deadline": batch.END.isoformat()}
    dest = OUT / "registration.json"
    if not dest.exists():
        assert not list((batch.OUT / "browser/scores").glob("**/score.json")), "Scores already available"
        assert read(A_SEAL)["build"]["status"] == "valid" and read(B_SEAL)["build"]["status"] == "build_failed"
        core.save(dest, {"utc": now(), **item})
    assert all(read(dest)[k] == v for k, v in item.items())


def with_values(raw, selected):
    patched = deepcopy(raw)
    for field in patched["controls"]:
        if field["id"] in selected:
            field["values"] = selected[field["id"]]
    return patched


def build(ledger):
    dest = OUT / "form/build"
    status = dest / "status.json"
    if status.exists():
        return read(status)
    raw = core.parse(read(LAST)["choices"][0]["message"]["content"])
    over = {c["id"]: c for c in raw["controls"] if c["type"] == "enum" and len(c["values"]) > 8}
    assert {k: len(v["values"]) for k, v in over.items()} == {"open-min-length": 9, "nps-score": 11}
    original_values = {k: v["values"] for k, v in over.items()}
    errors = {k: f"{len(c['values'])} values; permitted 2 through 8." for k, c in over.items()}
    prompt = core.messages("You wrote this public control schema. Correct ONLY the array of allowed values "
                           "for each reported field. Return one JSON object mapping each reported id directly "
                           "to exactly eight distinct original strings in their original relative order. "
                           "Keep the first and last original elements, the default and documented example, "
                           "and choose the remaining useful values from the original domain. No prose or code.",
                           {"invalid_controls": list(over.values()), "public_errors": errors})
    try:
        reply = batch.send(TAG, ledger, dest / "edit", prompt, "enum-subsets", 1000)
    except (BudgetStop, original.Unavailable) as exc:
        state = {"status": "missing", "reason": str(exc)}
    else:
        try:
            selected = core.parse(reply)
            if not isinstance(selected, dict) or set(selected) != set(over):
                raise ValueError("Every changed value domain must be named exactly once")
            removed = {}
            for name, c in over.items():
                keep = selected[name]
                orig = c["values"]
                required = {orig[0], orig[-1], c["default"], c["example"]}
                if (not isinstance(keep, list) or len(keep) != 8 or
                    keep != [v for v in orig if v in keep] or not required.issubset(keep)):
                    raise ValueError(f"Illegal replacement domain for {name}")
                removed[name] = [v for v in orig if v not in keep]
            improved = with_values(raw, selected)
            assert with_values(improved, original_values) == raw
            core.save(dest / "corrected-raw.json", improved)
            controls = lambda a: [{k: v for k, v in c.items() if k != "values"} for c in a["controls"]]
            assert controls(improved) == controls(raw)
            boundaries = {k: digest(raw[k]) for k in ("design", "anchor", "fragment", "script", "css", "files")}
            assert all(digest(improved[k]) == v for k, v in boundaries.items())
            pkg = core.package(read(batch.OUT / "inputs/form/public.json"), original.normalized(deepcopy(improved)))
            for name, plan in (("default", pkg["defaults"]), ("first", pkg["examples"][0]["plan"])):
                page = dest / name
                core.materialize("form", pkg, plan, page)
                errors = browser.public_load("form", page)
                core.save(dest / (name + "-public.json"), errors)
                if errors:
                    raise ValueError(str(errors)[:1200])
            core.save(dest / "package.json", pkg)
            state = {"status": "valid", "package_sha256": sha(dest / "package.json"),
                     "fixed": str((dest / "first").relative_to(ROOT)), "removed": removed,
                     "before": original_values, "after": selected, "unchanged_sha256": boundaries,
                     "control_metadata_sha256": digest(controls(raw)), "edited_response_sha256": sha(LAST)}
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            state = {"status": "build_failed", "reason": f"{type(exc).__name__}: {exc}"}
    core.save(status, state)
    return state


def generate():
    register()
    with browser.lock(OUT / ".generate.lock"):
        if (OUT / "seal.json").exists():
            return
        ledger = Ledger(batch.OUT / "budget.sqlite3", batch.CAP, batch.CAP)
        def send(tag, ledger, folder, messages, purpose, limit=8192):
            return batch.send(tag, ledger, folder, messages, purpose, limit)
        with patch.multiple(original, OUT=batch.OUT, MODELS={TAG: (batch.MODEL, batch.CAP, .3, .9)}, request=send):
            with patch.object(browser, "OUT", batch.OUT):
                state = build(ledger)
                with ThreadPoolExecutor(max_workers=3) as pool:
                    rows = list(pool.map(lambda n: original.target(TAG, "form", "self", n, ledger), TASKS))
        dest = OUT / "form/build"
        fixed = state.get("fixed")
        pack = dest / "package.json"
        core.save(OUT / "seal.json", {"build": state, "build_sha256": sha(dest / "status.json"),
                  "package_sha256": sha(pack) if pack.is_file() else None,
                  "fixed_files": browser.tree(ROOT / fixed) if fixed else {}, "rows": rows,
                  "row_sha256": {str(n): sha(OUT / "form/self" / str(n) / "result.json") for n in TASKS},
                  "utc": now(), "registration_sha256": sha(OUT / "registration.json"),
                  "unchanged_a_seal": sha(A_SEAL)})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["register", "generate"])
    action = parser.parse_args().action
    register() if action == "register" else generate()
