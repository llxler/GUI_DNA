"""Keep delivered behavior code and ask Flash to repair the file named by a public diagnostic."""
import argparse
from pathlib import Path
import re
from unittest.mock import patch

from gui_dna.budget import BudgetStop
from scripts.check_openrouter_credits import check_credits
from studies.ledger_read import totals
from studies.study_io import ROOT, now, read, sha
from .. import run as parent
from ..confirmation import run as previous
from . import public_checks

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/flash-form-file-repair-20261125"
BRANCHES = ("file-a", "file-b")
CAP = 1.5
core, original = parent.core, parent.original
GUIDE = """Return the reusable working library as a complete JSON object with visible source.
Use stable interfaces among the public question modules and wire real example questions into the
starter's form. Keep the public interactions, instances, and properties consistent across the
question registry, survey, config panel and storage. Place static imports in actual ES modules.
Document what each semantic control changes and choose legal defaults and a working first example.
On a public compiler or browser error, the affected single file can be requested separately."""
PATCH_GUIDE = """Repair your own delivered website using only the public requirements, runtime
diagnostic, and your source. Make the smallest behavior-preserving change that resolves the
observed problem. Keep the registered configuration API and the rest of the library unchanged.
Return the entire replacement file as raw code, without JSON or explanations."""


def register(_staged=False):
    paths = [Path(__file__), HERE / "PROTOCOL.md", Path(public_checks.__file__), Path(parent.__file__),
             Path(previous.__file__), Path(original.__file__), Path(core.__file__), Path(parent.browser.__file__),
             Path(__file__).parents[1] / "contract_repair/entry.py", Path(__file__).parents[1] / "contract_repair/subset.py",
             parent.OLD / "inputs/form/public.json", parent.OLD / "inputs/form/browser.json",
             parent.OLD / parent.TAG / "form/build/attempt-1/request.json",
             parent.OLD / parent.TAG / "form/gpt5-library/1/call/request.json",
             previous.OUT / "registration.json", previous.PILOT / "seal.json"]
    files = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    reg = OUT / "registration.json"
    if reg.is_file():
        assert read(reg)["files"] == files
        return
    pilot = totals(previous.PILOT / "budget.sqlite3")
    previous_budget = totals(previous.OUT / "budget.sqlite3")
    assert pilot["unsettled_calls"] == 0 and pilot["exposure_usd"] + previous_budget["cap_usd"] + CAP < 5
    balance = check_credits(CAP)
    if not balance["sufficient"]:
        raise BudgetStop("Insufficient account balance")
    public = core.public_input("form")
    assert public == read(parent.OLD / "inputs/form/public.json")
    assert parent.browser.verify_contract("form") == read(parent.OLD / "inputs/form/browser.json")
    core.save(OUT / "inputs/form/public.json", public)
    core.save(reg, {"utc": now(), "branches": BRANCHES, "model": parent.MODEL, "cap_usd": CAP,
                    "tasks": list(parent.TASKS), "deadline": parent.END.isoformat(), "balance": balance,
                    "pilot": pilot, "previous_cap_usd": previous_budget["cap_usd"], "files": files})


def code_text(raw):
    text = raw.strip()
    fenced = re.fullmatch(r"```(?:javascript|js|html|css|json|mjs)?\s*\n(.*?)\n?```", text, re.I | re.S)
    return fenced[1] if fenced else text


def package_response(text, public):
    raw = original.normalized(core.parse(code_text(text)))
    candidate, evidence = previous.adapt(public, raw)
    core.package(public, candidate)
    return candidate, evidence


def starting_package(branch, ledger, folder, public, state):
    base = core.build_messages(public)
    base[0]["content"] += "\n" + GUIDE
    messages = base
    for i in (1, 2):
        dest = folder / f"attempt-{i}"
        text = original.request(branch, ledger, dest, messages, f"build/whole/{i}", 16000)
        try:
            raw, adaptations = package_response(text, public)
        except (ValueError, KeyError, TypeError, IndexError, AttributeError) as exc:
            state["format_errors"].append(str(exc)[:1200])
            messages = base + [{"role": "assistant", "content": text[:65000]},
                               {"role": "user", "content": "Public delivery format: " + str(exc)[:1200] +
                                ". Deliver the complete corrected package."}]
            continue
        core.save(dest / "adaptations.json", adaptations)
        core.save(dest / "normalized-raw.json", raw)
        return raw
    return None


def file_patch(branch, ledger, folder, public, raw, diagnostic, number):
    path = diagnostic.get("preferred_path")
    system = PATCH_GUIDE
    if not path:
        system += (" Choose one existing file (or script/css injection). Write FILE: relative/path "
                   "on the first line and its entire replacement content below.")
    messages = core.messages(system, {"project": public, "source": raw,
                             "only_replace": path, "public_observations": diagnostic})
    text = original.request(branch, ledger, folder / "call", messages, f"file-repair/{number}", 12000)
    text = code_text(text)
    if not path:
        heading, _, text = text.partition("\n")
        match = re.fullmatch(r"(?:/{2}\s*)?FILE:\s*(.+?)\s*", heading, flags=re.I)
        if not match:
            raise ValueError("Missing replacement file name")
        path, text = match[1].strip(), code_text(text)
    if not text.strip():
        raise ValueError("No replacement source")
    updated = public_checks.replace_source(raw, path, text)
    core.save(folder / "patch.json", {"path": path, "content": text})
    return updated


def prepare(branch, project, ledger):
    root = OUT / branch / project / "build"
    status = root / "status.json"
    if status.exists():
        return read(status)
    data = read(OUT / "inputs/form/public.json")
    state = {"status": "build_failed", "format_errors": [], "versions": []}
    accepted = None
    try:
        raw = starting_package(branch, ledger, root, data, state)
        if raw is not None:
            for version in range(4):
                dest = root / f"v{version}"
                current = public_checks.diagnose(data, raw, dest)
                core.save(dest / "raw.json", raw)
                issues = current["issues"] + current["advisories"]
                item = {"version": version, "loadable": current["loadable"], "issues": issues,
                        "diagnosis_sha256": sha(dest / "diagnosis.json"), "source_sha256": sha(dest / "raw.json")}
                state["versions"].append(item)
                if current["loadable"]:
                    if accepted is not None:
                        if len(issues) < accepted[0]:
                            accepted = (len(issues), raw, current, version)
                        break
                    accepted = (len(issues), raw, current, version)
                elif accepted is not None:
                    break
                if not issues or version == 3:
                    break
                try:
                    raw = file_patch(branch, ledger, root / f"repair-{version + 1}", data, raw, current, version + 1)
                except (KeyError, TypeError, ValueError) as exc:
                    item["repair_error"] = str(exc)[:500]
                    break
    except (original.Unavailable, BudgetStop) as exc:
        state.update(status="missing", reason=str(exc))
    if accepted is not None:
        _, raw, diagnostics, which = accepted
        package = core.package(data, raw)
        core.save(root / "package.json", package)
        state.update(status="valid", package_sha256=sha(root / "package.json"), fixed=diagnostics["fixed"],
                     selected_version=which)
    core.save(status, state)
    return state


def generate(branch):
    registered_send = parent.send

    def send(tag, ledger, folder, messages, purpose, limit=8192):
        return registered_send(tag, ledger, folder, messages, purpose, limit)

    with patch.multiple(parent, OUT=OUT, CAP=CAP, register=register, send=send), patch.object(original, "build", prepare):
        parent.generate(branch)


def seal():
    register()
    dest = OUT / "seal.json"
    payload = {"branches": {b: read(OUT / b / "seal.json") for b in BRANCHES},
               "registration_sha256": sha(OUT / "registration.json")}
    if not dest.is_file():
        core.save(dest, {"utc": now(), **payload})
    assert all(read(dest)[k] == v for k, v in payload.items())


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
