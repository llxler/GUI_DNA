"""One separately recorded retry of a rejected preparation admission."""
from __future__ import annotations

import argparse
from decimal import Decimal, ROUND_FLOOR
from datetime import datetime, timezone
import time
from pathlib import Path

from gui_dna.budget import Ledger
from scripts.check_openrouter_credits import check_credits
from studies.expression_editor_sources import browser, core
from studies.expression_editor_unseen_requirements import run as original
from studies.interface_blind.core import write_files
from studies.ledger_read import calls, totals
from studies.streaming_provider_v2 import StreamingOpenRouter
from studies.study_io import ROOT, dump, now, read, sha, source_files
from studies.table_library_sources.run import file_hashes, verify
from studies.webbench_expand.core import config

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/expression-editor-unseen-notes-admission-20261123"
ORIGINAL = original.OUT
GROUPS = ("table-library-sources-20261123", "svg-chart-interfaces-20261123",
          "expression-editor-sources-20261123", ORIGINAL.name)


def locked(name):
    marker = read(OUT / name)
    verify(marker["inputs_sha256"])
    return marker


def freeze():
    if (OUT / "freeze.json").exists():
        return locked("freeze.json")
    registration = read(OUT / "registration.json")
    if sha(HERE / "PROTOCOL.md") != registration["protocol_sha256"]:
        raise ValueError("Registration differs")
    previous = {}
    paths = [HERE / n for n in ("PROTOCOL.md","run.py","report.py")]
    for group in GROUPS:
        folder = ROOT / "artifacts" / group
        complete = folder / "generation-complete.json"
        if not complete.exists():
            raise RuntimeError(f"Await end of generation: {group}")
        rows = calls(folder / "budget.sqlite3")
        if any(r["status"]=="reserved" for r in rows):
            raise RuntimeError(f"Active provider request: {group}")
        previous[group] = totals(folder / "budget.sqlite3")
        paths.append(complete)
    origin = ORIGINAL / "preparation/direct/first/call"
    rejected = read(origin / "error.json")
    if (rejected.get("http_status") != 402 or (origin/"response.json").exists()
        or "in-flight requests" not in rejected["provider_error"]["message"]
        or sha(origin/"request.json") != registration["original_request_sha256"]
        or sha(origin/"error.json") != registration["original_rejection_sha256"]):
        raise ValueError("Only the preregistered preparation admission qualifies")
    messages = read(origin / "request.json")["body"]["messages"]
    if messages != original.public_preparation()[1]["direct"]:
        raise ValueError("Expected identical original ten-row direct prompt")
    dump(OUT / "prep-prompt.json", messages)
    credit = check_credits(0)
    previous_exposure = Decimal(str(previous[ORIGINAL.name]["exposure_usd"]))
    cap = max(Decimal(0), min(Decimal(".35"), Decimal("1.10")-previous_exposure,
                              Decimal(str(credit["effective_remaining_usd"]))))
    cap = cap.quantize(Decimal(".01"), rounding=ROUND_FLOOR)
    paths += [OUT/"registration.json", OUT/"prep-prompt.json", ORIGINAL/"freeze.json",
              ORIGINAL/"preparation-complete.json", ORIGINAL/"planning-freeze.json", origin/"error.json",
              origin/"request.json", original.HERE/"run.py", original.HERE/"report.py"]
    # The original protocol hashes include the shared compiler, scorer, role and official inputs.
    hashes = original.locked("freeze.json")["inputs_sha256"] | file_hashes(paths)
    dump(OUT/"freeze.json", {"utc":now(),"budget_usd":float(cap),"credits":credit,"prior_ledgers":previous,
                             "inputs_sha256":hashes})
    return locked("freeze.json")


def refused():
    for area in ("preparation","candidates"):
        for path in (OUT / area).rglob("error.json"):
            if read(path).get("http_status") == 402:
                return path
    return None


def respect_rate_windows(folder):
    # Error-file modification time records receipt after the upstream HTTP response.
    # Use the latest expiry, including 429s observed by sequential calls in this stage.
    errors = []
    for stage in (core.OUT, OUT):
        for area in ("preparation", "candidates"):
            for path in (stage / area).rglob("call/error.json"):
                error = read(path)
                if error.get("http_status") == 429:
                    received = path.stat().st_mtime
                    delay = max(0, int(error.get("retry_after", 30)))
                    errors.append((received + delay, received, delay, path))
    if not errors:
        return
    expires, received, delay, path = max(errors, key=lambda item:item[0])
    marker = folder / "rate-window.json"
    if not marker.exists():
        dump(marker, {"source":str(path.relative_to(ROOT)), "error_sha256":sha(path),
             "received_utc":datetime.fromtimestamp(received,timezone.utc).isoformat(),
             "retry_after_seconds":delay, "expires_utc":datetime.fromtimestamp(expires,timezone.utc).isoformat(),
             "checked_utc":now(), "initial_wait_seconds":max(0,expires-time.time())})
    while time.time() < min(expires, original.END.timestamp()):
        time.sleep(min(30, max(0, min(expires,original.END.timestamp())-time.time())))


def paid():
    if (OUT/"paid-closed.json").exists():
        return locked("paid-closed.json")
    initial = freeze()
    cap = initial["budget_usd"]
    ledger = OUT/"budget.sqlite3"
    if cap == 0:
        return close(initial, "zero_available_cap", [], [], ledger)
    credit = check_credits(max(0, cap-(totals(ledger)["exposure_usd"] if ledger.exists() else 0)))
    if not credit["sufficient"]:
        return close(initial, "insufficient_pre_call_balance", [], [], ledger)
    cfg = config(True)
    cfg.update(models=[core.BUILDER,core.MODEL],provider_order={},budget_usd=cap,stop_new_requests_usd=cap)
    cfg["model_price_caps"][core.MODEL] = {"prompt":.2,"completion":.8}
    api = StreamingOpenRouter(cfg, Ledger(ledger,cap,cap))
    api.RATE_LIMIT_TRIES = 1
    folder = OUT/"preparation/direct"
    def save_prep(obj, dest):
        memo = core.validate_preparation("direct", obj, dest/"validation")
        dump(folder/"artifact.json", memo)
        return {"artifact_sha256":sha(folder/"artifact.json")}
    rows = []
    for stage in ("first","repair"):
        if refused() and not (folder/stage/"record.json").exists():
            break
        if stage=="repair" and (not rows[0][1]["received"] or rows[0][1]["valid"]):
            break
        prompt = read(OUT/"prep-prompt.json") if stage=="first" else original.repaired_prompt(folder/"first")
        respect_rate_windows(folder/stage)
        row = original.attempt(api, folder/stage, core.BUILDER, prompt, "prepare-direct-"+stage, 16000, save_prep)
        rows.append((stage,row))
    marker = OUT/"preparation-complete.json"
    if marker.exists():
        prep=locked(marker.name)
        if prep["attempts"] != [[s,r] for s,r in rows]:
            raise ValueError("Preparation markers changed")
    else:
        dump(marker,{"utc":now(),"attempts":rows,"inputs_sha256":file_hashes([OUT/"freeze.json",*original.folder_files(OUT/"preparation")])})
    if not rows or not rows[-1][1]["valid"]:
        return close(initial,"admission_rejected" if refused() else "no_valid_memo",rows,[],ledger)
    notes = read(folder/"artifact.json")
    if not (OUT/"planning-freeze.json").exists():
        for task in original.LATE:
            dump(OUT/"inputs"/(task+".json"),core.target_prompt("direct",task,notes))
        dump(OUT/"planning-freeze.json",{"utc":now(),"inputs_sha256":file_hashes([marker,*original.folder_files(OUT/"inputs")])})
    locked("planning-freeze.json")
    generated = []
    for task in original.LATE:
        base = OUT/"candidates/direct"/task
        def save_page(obj,dest):
            write_files(dest/"page",core.render("direct",notes,obj))
            return {"files_sha256":source_files(dest/"page")}
        first = None
        for stage in ("first","repair"):
            if refused() and not (base/stage/"record.json").exists():
                break
            if stage=="repair" and (first["valid"] or not first["received"]):
                break
            messages = read(OUT/"inputs"/(task+".json")) if stage=="first" else original.repaired_prompt(base/"first")
            respect_rate_windows(base/stage)
            row = original.attempt(api, base/stage, core.MODEL, messages, "direct-"+stage, 8192, save_page)
            generated.append((task,stage,row))
            if stage=="first":
                first = row
    return close(initial,"admission_rejected" if refused() else "completed",rows,generated,ledger)


def close(initial,reason,prep,rows,ledger):
    money = totals(ledger) if ledger.exists() else {"calls":0,"exposure_usd":0,"settled_usd":0,"unsettled_calls":0}
    base = initial["prior_ledgers"][ORIGINAL.name]["exposure_usd"]
    if money["exposure_usd"] > initial["budget_usd"] or Decimal(str(base))+Decimal(str(money["exposure_usd"])) > Decimal("1.10"):
        raise ValueError("Combined stage exposure exceeded")
    paths = [OUT/"freeze.json",*original.folder_files(OUT/"preparation"),*original.folder_files(OUT/"inputs"),
             *original.folder_files(OUT/"candidates")]
    paths.extend(OUT/f for f in ("preparation-complete.json","planning-freeze.json") if (OUT/f).exists())
    out = {"utc":now(),"reason":reason,"preparation":prep,"target_rows":rows,"ledger":money,
           "original_exposure_usd":base,"combined_exposure_usd":round(base+money["exposure_usd"],6),
           "inputs_sha256":file_hashes(paths)}
    dump(OUT/"paid-closed.json",out)
    return out


def score():
    final=locked("paid-closed.json")
    if (OUT/"scores-complete.json").exists():
        return locked("scores-complete.json")
    harness=OUT/"harness"
    if not harness.exists():
        harness.symlink_to(core.OUT/"harness",target_is_directory=True)
    browser.OUT=OUT
    results={}
    for task,stage,row in final["target_rows"]:
        if row["valid"]:
            key=f"direct/{task}/{stage}"
            page=OUT/"candidates"/key/"page"
            if row["files_sha256"] != source_files(page):
                raise ValueError(f"Candidate differs: {key}")
            results[key]=browser.score(key,task,page,False)
    paths=[OUT/"paid-closed.json",*(OUT/"scores").rglob("report.json")]
    dump(OUT/"scores-complete.json",{"utc":now(),"scores":results,"inputs_sha256":file_hashes(paths)})


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("freeze","paid","score"))
    args=parser.parse_args()
    {"freeze":freeze,"paid":paid,"score":score}[args.action]()
