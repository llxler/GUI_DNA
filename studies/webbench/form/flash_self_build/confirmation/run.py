"""Confirm visible whole-package construction using two new Flash libraries."""
import argparse
from copy import deepcopy
from pathlib import Path
import re
from unittest.mock import patch

from gui_dna.budget import BudgetStop
from scripts.check_openrouter_credits import check_credits
from studies.ledger_read import totals
from studies.study_io import ROOT, now, read, sha
from .. import run as parent, staged
from ..contract_repair.entry import ModuleTags, relocate
from ..contract_repair.subset import bounded_subset

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/flash-form-confirmation-20261125"
PILOT = parent.OUT
BRANCHES = ("fresh-a", "fresh-b")
CAP = 1.50
core, original = parent.core, parent.original

GUIDE = """Deliver a working, reusable implementation of the complete public brief. The prior
stage of this system supplies a real starter that imports a module, so put application startup
and its relative imports into the actual module path named by that starter. The script field is
classic JavaScript and cannot contain static import/export; leave it empty when using modules.
Give each publicly named question class its actual local ES module with exports and imports that agree.
Mount real instances for the public examples. Keep shared order and form state consistent across
selection, validation, navigation, and storage. Reusable core behaviors should work in the initial
page. Choose one to four meaningful semantic options, preferably Boolean, with explicit behavior
and a usable default and first example. For an enum list two to eight distinct short strings and
include the default and the example in that list. Read only the supplied public materials.
Return a single complete code package. Spend the output budget on functional source.
"""


def register(_staged=False):
    paths = [HERE / "PROTOCOL.md", Path(__file__), Path(parent.__file__), Path(staged.__file__),
             Path(original.__file__), Path(core.__file__), Path(parent.browser.__file__),
             Path(__file__).parents[1] / "contract_repair/entry.py", Path(__file__).parents[1] / "contract_repair/subset.py",
             PILOT / "seal.json", parent.OLD / "inputs/form/public.json", parent.OLD / "inputs/form/browser.json",
             PILOT / "inputs/form/public.json", parent.OLD / parent.TAG / "form/gpt5-library/1/call/request.json",
             parent.OLD / parent.TAG / "form/build/attempt-1/request.json"]
    expected = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    reg = OUT / "registration.json"
    if reg.is_file():
        assert read(reg)["files"] == expected
        return
    pilot = totals(PILOT / "budget.sqlite3")
    assert pilot["unsettled_calls"] == 0 and pilot["exposure_usd"] + CAP <= 5
    assert all((PILOT / branch / "seal.json").is_file() for branch in parent.BRANCHES)
    balance = check_credits(CAP)
    if not balance["sufficient"]:
        raise BudgetStop("Insufficient account credit")
    data = read(PILOT / "inputs/form/public.json")
    assert data == core.public_input("form")
    assert parent.browser.verify_contract("form") == read(parent.OLD / "inputs/form/browser.json")
    core.save(OUT / "inputs/form/public.json", data)
    core.save(reg, {"utc": now(), "files": expected, "branches": BRANCHES, "model": parent.MODEL,
                    "tasks": list(parent.TASKS), "pilot": pilot, "balance": balance, "cap_usd": CAP,
                    "deadline": parent.END.isoformat()})


def adapt(public, raw):
    candidate = deepcopy(raw)
    changes = {}
    for control in candidate["controls"]:
        if control.get("type") == "enum" and len(control["values"]) > 8:
            values = control["values"]
            if (not all(isinstance(v, str) for v in values) or len(set(values)) != len(values)
                    or not {control["default"], control["example"]}.issubset(values)):
                raise ValueError("Enum values must be distinct strings and include default/example")
            control["values"] = bounded_subset(control)
            changes[control["id"]] = {"submitted": values, "accepted": control["values"]}
    proof = {}
    if re.search(r"(?m)^\s*import\s+(?!\()", candidate.get("script", "")):
        parser = ModuleTags()
        parser.feed(public["starter"]["index.html"])
        if len(parser.entries) != 1 or parser.entries[0] in {f["path"] for f in candidate["files"]}:
            raise ValueError("Place all static imports into the single starter module entry and leave classic script empty")
        candidate, proof = relocate(public, candidate)
    return candidate, {"domains": changes, "entry": proof}


def prepare(tag, project, ledger):
    folder = OUT / tag / project / "build"
    status = folder / "status.json"
    if status.is_file():
        return read(status)
    public = read(OUT / "inputs/form/public.json")
    base = core.build_messages(public)
    base[0]["content"] += "\n" + GUIDE
    messages = base
    state = {"status": "build_failed", "public_errors": []}
    for attempt in (1, 2):
        dest = folder / f"attempt-{attempt}"
        try:
            text = original.request(tag, ledger, dest, messages, f"build/form/{attempt}", 16000)
        except (original.Unavailable, BudgetStop) as exc:
            state.update(status="missing", reason=str(exc))
            break
        try:
            raw, evidence = adapt(public, original.normalized(core.parse(text)))
            core.save(dest / "adaptation.json", evidence)
            package = core.package(public, raw)
            for name, plan in (("default", package["defaults"]), ("first", package["examples"][0]["plan"])):
                page = dest / name
                core.materialize("form", package, plan, page)
                evidence = staged._probe(page, [f for f in package["files"] if f.endswith((".js", ".mjs"))])
                core.save(dest / f"{name}-public.json", evidence)
                if evidence["errors"]:
                    raise ValueError("Public startup: " + "\n".join(evidence["errors"]))
            core.save(folder / "package.json", package)
            state.update(status="valid", package_sha256=sha(folder / "package.json"),
                         fixed=str((dest / "first").relative_to(ROOT)))
            break
        except (ValueError, KeyError, AttributeError, TypeError, IndexError) as exc:
            error = str(exc)[:1800]
            state["public_errors"].append(error)
            messages = base + [{"role": "assistant", "content": text[:65000]},
                               {"role": "user", "content": "Public delivery or startup check: " + error +
                                ". Return the entire corrected package; keep functional source complete."}]
    core.save(status, state)
    return state


def generate(tag):
    registered_send = parent.send

    def send(branch, ledger, folder, messages, purpose, limit=8192):
        return registered_send(branch, ledger, folder, messages, purpose, limit)

    with patch.multiple(parent, OUT=OUT, CAP=CAP, register=register, send=send), patch.object(original, "build", prepare):
        parent.generate(tag)


def seal():
    register()
    data = {"branches": {b: read(OUT / b / "seal.json") for b in BRANCHES},
            "registration_sha256": sha(OUT / "registration.json")}
    dest = OUT / "seal.json"
    if not dest.exists():
        core.save(dest, {"utc": now(), **data})
    assert all(read(dest)[k] == v for k, v in data.items())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "seal", *BRANCHES))
    action = parser.parse_args().action
    if action == "register":
        register()
    elif action == "seal":
        seal()
    else:
        generate(action)
