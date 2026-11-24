"""Resume the registered native editor after its uncharged/unknown HTTP response."""

import argparse
import re
from pathlib import Path
from unittest.mock import patch

from gui_dna.budget import BudgetStop, Ledger
from scripts.check_openrouter_credits import check_credits
from studies.public_library_transfer import browser, core
from studies.public_library_transfer.self_refinement import report, run as shared
from studies.public_library_transfer.self_refinement.incremental import run as text_stage
from studies.public_library_transfer.self_refinement.incremental.native import provider, run as native
from studies.study_io import ROOT, read, sha
from studies.webbench.backbone_matrix.run import Unavailable

ORIGINAL = native.OUT
ORIGINAL_RESULT = native.OUTPUT
OUT = ROOT / "artifacts/native-incremental-self-table-resume-20261124"
OUTPUT = ROOT / "studies/results/native-incremental-self-table-resume-20261124.json"
BASE = OUT / native.TAG
BUILD = BASE / "build"
CAP = 1.96
MODELS = {native.TAG: (native.MODEL, CAP, 0.25, 1)}
NATIVE_CALL = provider.tool_call
ORIGINAL_REVISION = native.revision
TRANSIENT = re.compile(r"(?:HTTP (?:429|500|502|503|504)|ReadTimeout|ConnectTimeout|RemoteProtocolError|ConnectError|ReadError)")
SAVE = core.save


def register():
    if (OUT / "registered.json").exists():
        return shared.verify()
    old = read(ORIGINAL_RESULT)
    regfile = ORIGINAL / "registered.json"
    registry = read(regfile)
    assert sha(regfile) == old["registration_sha256"]
    for name, fingerprint in registry["files"].items():
        assert sha(ROOT / name) == fingerprint
    previous_cost = read(text_stage.OUTPUT)["ledger"]["exposure_usd"]
    old_cost = old["ledger"]["exposure_usd"]
    if old["build"]["reason"] != "HTTP 502" or previous_cost + old_cost + CAP > 2:
        raise BudgetStop("Original interruption or combined budget differs")
    balance = check_credits(CAP)
    if not balance["sufficient"]:
        raise BudgetStop("Insufficient credit")
    for name in ("public.json", "browser.json", "interface.json"):
        SAVE(OUT / name, read(ORIGINAL / name))
        assert sha(OUT / name) == sha(ORIGINAL / name)
    sources = [Path(__file__), Path(__file__).with_name("RECOVERY.md"), ORIGINAL_RESULT, regfile,
               OUT / "public.json", OUT / "browser.json", OUT / "interface.json"]
    SAVE(OUT / "registered.json", {**registry, "utc": core.now(), "models": MODELS, "budget_usd": CAP, "balance": balance,
         "original_tool_exposure_usd": old_cost, "text_editor_exposure_usd": previous_cost,
         "files": registry["files"] | {str(p.relative_to(ROOT)): sha(p) for p in sources}})


def inherit(folder, original):
    record = {"original": str(original.relative_to(ROOT)),
              "request_sha256": sha(original / "request.json"), "response_sha256": sha(original / "response.json"),
              "receipt_sha256": sha(original / "settled.json")}
    SAVE(folder / "inherited.json", record)


def cached_call(root, ledger, folder, model, end, messages, function, purpose, limit):
    original = ORIGINAL / native.TAG / folder.relative_to(BASE)
    old_auth = original / "request.json"
    if (original / "settled.json").exists():
        inherit(folder, original)
        # The frozen provider recomputes the exact body and verifies it against its receipt.
        return NATIVE_CALL(ORIGINAL / native.TAG, None, original, model, end, messages, function, purpose, limit)
    skipped = 0
    if old_auth.exists():
        err = original / "error.json"
        if not err.exists() or not TRANSIENT.fullmatch(read(err)["reason"]):
            raise Unavailable("Earlier unresolved non-transient request")
        SAVE(folder / "original-interruption.json", {"original": str(original.relative_to(ROOT)),
             "request_sha256": sha(old_auth), "reason": read(err)["reason"]})
        skipped = 1
    for i in range(skipped + 1, 4):
        dest = folder / f"transport-{i}"
        try:
            return NATIVE_CALL(root, ledger, dest, model, end, messages, function, purpose, limit)
        except Unavailable:
            err = dest / "error.json"
            if i == 3 or not err.exists() or not TRANSIENT.fullmatch(read(err)["reason"]):
                raise
        finally:
            auth = dest / "request.json"
            if old_auth.exists() and auth.exists() and read(old_auth)["body"] != read(auth)["body"]:
                raise RuntimeError("Retried transport body differs from original interruption")


def cached_revision(ledger, batch, end, data, spec, files, feedback, max_files):
    root = ORIGINAL / native.TAG / "build"
    done = next((r for r in read(root / "status.json")["revisions"] if r["batch"] == batch), None)
    if not done:
        return ORIGINAL_REVISION(ledger, batch, end, data, spec, files, feedback, max_files)
    checkpoint = root / batch / "files.json"
    assert sha(checkpoint) == done["source_sha256"]
    assert batch == "through-4" and files == data["starter"]
    saved = read(root / f"{batch}-public-check.json")
    assert saved["load_errors"] == done["load_errors"] and saved["probe"] == done["probe"]
    browser.verify_page(root / (batch + "-page"), saved["files"], "table")
    for f in sorted((root / batch).rglob("settled.json")):
        dest = BUILD / f.parent.relative_to(root)
        inherit(dest, f.parent)
    for i, write in enumerate(done["writes"], 1):
        if write["accepted"]:
            assert sha(root / batch / f"file-{i}/accepted.json") == write["checkpoint_sha256"]
    SAVE(BUILD / batch / "files.json", read(checkpoint))
    SAVE(BUILD / f"{batch}-public-check.json", saved)
    return read(checkpoint), done, saved


def configure():
    shared.configure(OUT, "table", MODELS, native.END)
    native.OUT, native.BASE, native.BUILD = OUT, BASE, BUILD


def publish(check):
    shared.verify()
    reg = read(OUT / "registered.json")
    result = {"study": "Transport continuation of native per-file writes", "project": "table",
        "model": native.MODEL, "registered_utc": reg["utc"], "end_utc": reg["end"], "budget_usd": CAP,
        "registration_sha256": sha(OUT / "registered.json"), "files_at_registration": reg["files"],
        "tasks": reg["tasks"], "batch_ends": reg["batch_ends"], "upstream_commit": browser.UPSTREAM_COMMIT,
        "earlier_exposures_usd": {"text_editor": reg["text_editor_exposure_usd"], "native_editor": reg["original_tool_exposure_usd"]},
        **report.model_report(OUT, native.TAG, native.MODEL, "table", read(text_stage.BASELINE))}
    reused = []
    for path in sorted(BASE.rglob("inherited.json")):
        row = read(path)
        old = ROOT / row["original"]
        for file, field in (("request.json", "request_sha256"), ("response.json", "response_sha256"), ("settled.json", "receipt_sha256")):
            assert sha(old / file) == row[field]
        reused.append(row)
    result["reused_settled_tool_responses"] = reused
    assert len(reused) == len({r["request_sha256"] for r in reused})
    assert sum(result["earlier_exposures_usd"].values()) + result["ledger"]["exposure_usd"] <= 2
    if check:
        assert read(OUTPUT) == result
    else:
        SAVE(OUTPUT, result)
    print(result["summary"], result["cost_by_phase"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "generate", "score", "publish", "check"))
    action = parser.parse_args().action
    configure()
    if action == "register":
        register()
    elif action == "generate":
        with browser.lock(OUT / ".generate.lock"):
            shared.verify()
            with patch.object(native, "revision", cached_revision), patch.object(provider, "tool_call", cached_call):
                native.build(Ledger(BASE / "budget.sqlite3", CAP, CAP))
            shared.generate(native.TAG)
    elif action == "score":
        shared.score(native.TAG)
    else:
        publish(action == "check")


if __name__ == "__main__":
    main()
