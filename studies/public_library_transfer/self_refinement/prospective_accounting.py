"""Verify the independent model-call ledgers within the three prospective budget allocations."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING
from hashlib import sha256
import json
from pathlib import Path

from studies import ledger_read
from studies.public_library_transfer import core
from studies.study_io import ROOT, read, sha

HERE = Path(__file__).resolve().parent
DEST = ROOT / "studies/results/domain-construction-accounting-20261124.json"
FINAL = ROOT / "studies/results/domain-construction-accounting-final-20261124.json"
ART = ROOT / "artifacts"
START = "2026-11-24T10:45:40+00:00"
END = "2026-11-24T11:45:40+00:00"
SVG_END = "2026-11-24T11:27:00+00:00"
FORM_END = "2026-11-24T11:23:00+00:00"
CONFIRM_END = "2026-11-24T11:35:30+00:00"
APPROVED = 3_000_000
# Fields are root directory, study report, model, cap in microdollars, provider ceilings.
BASE_ROUTES = {
    "duo-qwen": ("duo-independent-components-20261124/qwen9", "duo_components", "qwen/qwen3.5-9b", 950000, ".35", "1.20"),
    "duo-compact": ("duo-compact-components-20261124/qwen9", "duo_components/compact", "qwen/qwen3.5-9b", 550000, ".35", "1.20"),
    "duo-oss": ("duo-independent-components-20261124/oss", "duo_components", "openai/gpt-oss-120b", 1000000, ".25", "1"),
    "todomvc-gemma": ("todomvc-gemma-verified-20261124", "todomvc/verified_controller", "google/gemma-3-12b-it", 650000, ".08", ".24"),
    "svg-qwen-coder": ("qwen-svg-renderers-20261124", "svg_renderers", "qwen/qwen3-coder-30b-a3b-instruct", 400000, ".12", ".46"),
}

PATCH = "svg-runtime-patch"
FORM = "form-gpt-oss"
CONFIRM = "svg-fresh-confirmation"
ROUTES = {**BASE_ROUTES, PATCH: ("qwen-svg-runtime-patch-20261124", "svg_renderers/runtime_patch",
                               "qwen/qwen3-coder-30b-a3b-instruct", 120000, ".12", ".46"),
          FORM: ("form-independent-components-20261124", "form_components", "openai/gpt-oss-120b", 500000, ".25", "1")}
ALL_ROUTES = {**ROUTES, CONFIRM: ("qwen-svg-prospective-confirmation-20261124", "svg_renderers/confirmation",
                                 "qwen/qwen3-coder-30b-a3b-instruct", 100000, ".12", ".46")}
BUCKETS = {"Duo allocation": (1_950_000, ("duo-qwen", "duo-oss", "duo-compact", FORM)),
           "TodoMVC allocation": (650_000, ("todomvc-gemma",)),
           "SVG allocation": (400_000, ("svg-qwen-coder", PATCH, CONFIRM))}
STUDIES = {"WebApp1K-Duo": ("duo-qwen", "duo-oss", "duo-compact"), "TodoMVC": ("todomvc-gemma",),
           "Web-Bench SVG": ("svg-qwen-coder", PATCH, CONFIRM), "Web-Bench form": (FORM,)}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def micro(value):
    amount = Decimal(str(value))
    require(amount.is_finite() and amount >= 0, "Invalid monetary amount")
    return int((amount * 1_000_000).to_integral_value(rounding=ROUND_CEILING))


def fingerprint(value):
    return sha256(value.encode()).hexdigest()


def phase(route, purpose):
    fields = purpose.split("/")
    if route.startswith("duo-"):
        if fields[0] == "plan" and fields[1] in ("build-a", "build-b"):
            return "planner", fields[1]
        if len(fields) == 3 and fields[0] in ("prepare", "direct") and fields[2] in ("first", "repair"):
            return ("library" if fields[0] == "prepare" else "direct") + "/" + fields[2], fields[1]
    if route == "todomvc-gemma":
        if fields[0] == "plan" and len(fields) == 4:
            return "planner", fields[1]
        if len(fields) == 3 and fields[0] in ("library", "direct") and fields[2] in ("initial", "repair"):
            return fields[0] + "/" + fields[2], fields[1] if fields[0] == "library" else "shared-direct"
    if route == FORM:
        if len(fields) == 3 and fields[0] == "prepare" and fields[2] in ("0", "1"):
            return "library/" + ("initial" if fields[2] == "0" else "repair"), fields[1]
        if len(fields) == 2 and fields[0] in ("selected", "fixed"):
            return ("planner" if fields[0] == "selected" else "fixed-example"), fields[1]
        if len(fields) == 2 and fields[0] == "direct" and fields[1] in ("0", "1"):
            return "direct/" + ("initial" if fields[1] == "0" else "repair"), "shared-direct"
    if route == PATCH:
        if len(fields) == 2 and fields[0] in ("A", "B") and fields[1] == "edit":
            return "library/runtime-patch", fields[0]
        if len(fields) == 3 and fields[0] == "direct" and fields[2] == "edit":
            return "direct/runtime-patch", "shared-direct"
        if len(fields) == 3 and fields[0] in ("A", "B") and fields[1] == "plan":
            return "planner", fields[0]
    if route in ("svg-qwen-coder", CONFIRM):
        if len(fields) == 3 and fields[0] == "direct" and fields[2] in ("1", "2"):
            return ("direct/initial" if fields[2] == "1" else "direct/public-repair"), "shared-direct"
        if len(fields) == 3 and fields[1] == "plan":
            return "planner", fields[0]
        if len(fields) == 5 and fields[1] == "build" and fields[0] in ("A", "B"):
            if fields[3:] == ["public-repair", "1"]:
                return "library/public-repair", fields[0]
            if fields[3] == "initial" and fields[4] in ("1", "2"):
                return ("library/initial" if fields[4] == "1" else "library/syntax-repair"), fields[0]
    raise ValueError(f"Unregistered {route} purpose {purpose}")


def total(rows):
    rows = list(rows)
    billed = sum(r["actual"] or 0 for r in rows)
    open_rows = [r for r in rows if r["actual"] is None]
    reserved = sum(r["reserved"] for r in open_rows)
    return {"calls": len(rows), "unsettled_calls": len(open_rows), "settled_microusd": billed,
            "provider_receipt_usd": format(sum((Decimal(r["provider_cost_usd"]) for r in rows if r["actual"] is not None), Decimal(0)), "f"),
            "unsettled_reserved_microusd": reserved, "exposure_microusd": billed + reserved,
            "gross_reservations_microusd": sum(r["reserved"] for r in rows),
            "prompt_tokens_on_receipts": sum(r.get("prompt_tokens", 0) for r in rows),
            "completion_tokens_on_receipts": sum(r.get("completion_tokens", 0) for r in rows),
            "providers_on_receipts": dict(sorted(Counter(r["provider"] for r in rows if r.get("provider")).items()))}


def grouped(rows, field):
    groups = defaultdict(list)
    for r in rows:
        groups[r[field]].append(r)
    return {name: total(group) for name, group in sorted(groups.items())}


def expected_budget(public, route, model):
    if route.startswith("duo-"):
        return public["groups"][model]["billing"]["total"]
    return public["budget"] if route in ("svg-qwen-coder", PATCH, FORM, CONFIRM) else public["accounting"]


def match_budget(summary, published, cap):
    require(published["calls"] == summary["calls"] and published["unsettled_calls"] == summary["unsettled_calls"],
            "Ledger count mismatch")
    require(micro(published["settled_usd"]) == summary["settled_microusd"] and
            micro(published["exposure_usd"]) == summary["exposure_microusd"] and
            micro(published["cap_usd"]) == cap and micro(published["stop_usd"]) == cap and not published["halted"],
            "Ledger charges or policy differ")


def cutoff(route):
    if route == CONFIRM:
        return CONFIRM_END
    if route in ("svg-qwen-coder", PATCH):
        return SVG_END
    return FORM_END if route == FORM else END

def artifact_paths(route):
    raw_dir, study, *_ = ALL_ROUTES[route]
    base = ART / raw_dir
    beginning = base.parent if route.startswith("duo-") else base
    reg = beginning / ("registered.json" if route == "todomvc-gemma" else "registration.json")
    return base, reg, beginning / "seal.json", HERE / study / "result.json"


def verified_route(route):
    base, reg_path, seal_path, published = artifact_paths(route)
    _, _, model, cap, pin, pout = ALL_ROUTES[route]
    source = read(published)
    reg, seal = read(reg_path), read(seal_path)
    require(sha(seal_path) == source["seal_sha256"], "Final result is not from the observed generation seal")
    if "registration_sha256" in source:
        require(sha(reg_path) == source["registration_sha256"], "Published registration differs")
    else:
        require(reg["utc"] == source["registered_utc"] and reg["sources"] == source["sources"],
                "Published source registration differs from its source hashes")
    require(seal["registration_sha256"] == sha(reg_path), "Registration mismatch")
    balance_path = ART / ("duo-compact-balance-20261124.json" if route == "duo-compact" else "duo-components-balance-20261124.json")
    if route.startswith("duo-"):
        balance = read(balance_path)
    elif route in (FORM, CONFIRM):
        balance_path = ART / ("form-components-balance-20261124.json" if route == FORM else "svg-confirmation-balance-20261124.json")
        balance = read(balance_path)
        if route == CONFIRM:
            require(reg["spec"]["sources"][str(balance_path.relative_to(ROOT))] == sha(balance_path)
                    and reg["spec"]["request_cutoff"] == CONFIRM_END
                    and micro(reg["spec"]["cap_usd"]) == cap, "New SVG registration or live balance mismatch")
    elif route == PATCH:
        balance_path = base / "admission.json"
        admission = read(balance_path)
        require(admission == source["admission"] and seal["admission_sha256"] == sha(balance_path),
                "SVG repair was not linked to the live balance and original seal")
        balance = admission["balance"]
    else:
        balance_path = reg_path
        balance = reg["balance"]
    required = 1_950_000 if route in ("duo-oss", "duo-qwen") else cap
    require(balance["sufficient"] and micro(balance["required_usd"]) >= required
            and Decimal(str(balance["effective_remaining_usd"])) >= Decimal(required) / 1000000,
            "Per-stage balance did not cover the registered allocation")
    records = sorted(ledger_read.calls(base / "budget.sqlite3"), key=lambda r: (r["created"], r["id"]))
    requests = {}
    if route.startswith("duo-") or route == FORM:
        request_files = base.glob("**/call/request.json")
    elif route == "todomvc-gemma":
        request_files = (p for folder in ("source-attempts", "plans") for p in (base / folder).rglob("request.json"))
    else:
        request_files = (base / "calls").rglob("request.json")
    for req in request_files:
        raw = read(req)
        if "call_id" not in raw:
            continue
        require(raw["call_id"] not in requests, "Reservation id reused for two requests")
        requests[raw["call_id"]] = (req, raw)
    rows = []
    for item in records:
        ticket = item["id"]
        amount, reserved = item["actual"], item["reserved"]
        require(item["model"] == model, "Model on ledger differs from route")
        stage, replica = phase(route, item["purpose"])
        created = datetime.fromtimestamp(item["created"], timezone.utc).isoformat(timespec="microseconds")
        record = {"call_id_sha256": fingerprint(ticket), "purpose": item["purpose"], "phase": stage, "replica": replica,
                  "created_utc": created, "status": item["status"], "reserved": reserved, "actual": amount}
        if ticket not in requests:
            require(amount is None, "Settled call is missing its source request")
            record["reason"] = "Reservation only; no saved request"
            rows.append(record)
            continue
        req, raw = requests.pop(ticket)
        body = raw["body"]
        prices = body["provider"]["max_price"]
        require(body["model"] == model and Decimal(str(prices["prompt"])) == Decimal(pin)
                and Decimal(str(prices["completion"])) == Decimal(pout) and prices["request"] == 0, "Price/model mismatch")
        bound = len(json.dumps(body, ensure_ascii=False).encode()) + 2048
        upper = (bound * Decimal(pin) + body["max_tokens"] * Decimal(pout)) / 1000000
        require(micro(upper) == reserved and abs(Decimal(str(raw["reserved_usd"])) - upper) < Decimal("0.00000001"),
                "Reservation differs from the exact input bound and output limit")
        record["request_sha256"] = sha(req)
        if amount is None:
            err = req.with_name("error.json")
            record["reason"] = read(err)["reason"] if err.exists() else "No settled usage receipt"
        else:
            result_file = req.with_name("response.json")
            stamp = read(req.with_name("settled.json"))
            response = read(result_file)
            usage = response["usage"]
            require(stamp.get("call_id", stamp.get("ticket")) == ticket and stamp["response_sha256"] == sha(result_file),
                    "Response receipt hash or reservation id mismatch")
            require(micro(usage["cost"]) == amount and response.get("model") == model,
                    "Actual charge or served model differs from provider receipt")
            pinned = body["provider"].get("only")
            if pinned:
                require(response.get("provider") in pinned and not body["provider"]["allow_fallbacks"],
                        "Response not served by the registered pinned provider")
            record.update(response_sha256=stamp["response_sha256"], provider_cost_usd=str(usage["cost"]), provider=response.get("provider"),
                          served_model=response.get("model"), prompt_tokens=usage["prompt_tokens"],
                          completion_tokens=usage["completion_tokens"])
            if response.get("id"):
                record["generation_id_sha256"] = fingerprint(response["id"])
        rows.append(record)
    require(not requests, "Saved request with no corresponding ledger entry")
    amounts = total(rows)
    match_budget(amounts, ledger_read.totals(base / "budget.sqlite3"), cap)
    match_budget(amounts, expected_budget(source, route, model), cap)
    result = {"model": model, "cap_microusd": cap, "registered_utc": reg["utc"], "sealed_utc": seal["utc"],
            "generation_cutoff_utc": cutoff(route),
            "sufficient_balance_checked_utc": balance["checked_utc"],
            "balance_evidence_sha256": sha(balance_path),
            "balance_threshold_microusd": required, "registration_sha256": sha(reg_path), "seal_sha256": sha(seal_path),
            "result_sha256": sha(published), "calls": rows, "total": amounts, "per_phase": grouped(rows, "phase"),
            "per_replica": grouped(rows, "replica"),
            "per_phase_within_replica": {r: grouped([x for x in rows if x["replica"] == r], "phase")
                                        for r in sorted({x["replica"] for x in rows})}}
    if route == CONFIRM:
        amendment_path = base / "observer-compatibility.json"
        amendment = read(amendment_path)
        require(all(sha(ROOT/path) == stamp for path,stamp in amendment["sources"].items()),
                "New SVG observer compatibility source changed")
        result.update(observer_compatibility_sha256=sha(amendment_path),
                      observer_compatibility_utc=amendment["utc"])
    return result


def allocation_totals(reports):
    return {study: {"cap_microusd": bucket_cap,
                    **total(c for k in keys if k in reports for c in reports[k]["calls"])}
            for study, (bucket_cap, keys) in BUCKETS.items()}


def study_totals(reports):
    return {study: total(c for k in keys if k in reports for c in reports[k]["calls"])
            for study, keys in STUDIES.items() if any(k in reports for k in keys)}


def model_totals(reports):
    calls = defaultdict(list)
    for item in reports.values():
        calls[item["model"]].extend(item["calls"])
    return {model: {"total": total(rows), "per_phase": grouped(rows, "phase")}
            for model, rows in sorted(calls.items())}


def validate_release(reports, before, followup, bucket):
    if followup not in reports:
        return
    earlier = [reports[k] for k in before]
    last_seal = max(datetime.fromisoformat(r["sealed_utc"]) for r in earlier)
    remaining_exposure = sum(r["total"]["exposure_microusd"] for r in earlier)
    later = reports[followup]
    require(remaining_exposure + later["cap_microusd"] <= BUCKETS[bucket][0],
            f"Reservation ceiling for {followup} exceeds the allocation remaining at its activation")
    require(all(datetime.fromisoformat(r["created_utc"]) >= last_seal for r in later["calls"]),
            f"{followup} started before its preceding generations were sealed")

def validate(data, confirmation=False):
    require(data["authorization"] == {"start_utc": START, "end_utc": END, "cap_microusd": APPROVED},
            "Incorrect authorization window")
    required_routes = ALL_ROUTES if confirmation else ROUTES
    require(set(data["routes"]) == set(required_routes), "Missing or unexpected ledger in the completed cohort")
    unique = set()
    generations = set()
    all_rows = []
    for route, item in data["routes"].items():
        cfg = required_routes[route]
        _, _, model, cap, *_ = cfg
        _, _, _, published = artifact_paths(route)
        public = read(published)
        require(item["model"] == model and item["cap_microusd"] == cap and sha(published) == item["result_sha256"],
                "Changed source or route metadata")
        require(len(item["registration_sha256"]) == 64 and item["registration_sha256"] == public.get("registration_sha256", item["registration_sha256"])
                and item["registered_utc"] == public["registered_utc"] and item["seal_sha256"] == public["seal_sha256"],
                "Published trial hashes disagree")
        rows = item["calls"]
        deadline = cutoff(route)
        require(item["generation_cutoff_utc"] == deadline, "Changed cutoff")
        bound = datetime.fromisoformat(deadline)
        registered, sealed, balance_checked = map(datetime.fromisoformat,
            (item["registered_utc"], item["sealed_utc"], item["sufficient_balance_checked_utc"]))
        if route == CONFIRM:
            require(registered <= datetime.fromisoformat(item["observer_compatibility_utc"]) <= sealed
                    and public.get("observer_compatibility_sha256") == item["observer_compatibility_sha256"],
                    "New SVG observer compatibility record differs from the delivered study")
        require(datetime.fromisoformat(START) <= min(registered, balance_checked) and max(registered, balance_checked) <= sealed,
                "Balance/registration timing mismatch")
        for r in rows:
            timestamp = datetime.fromisoformat(r["created_utc"])
            key, actual = r["call_id_sha256"], r["actual"]
            require(max(registered, balance_checked) <= timestamp <= min(sealed, bound), "A call was reserved outside the authorized phase")
            require(len(key) == 64 and key not in unique and (r["phase"], r["replica"]) == phase(route, r["purpose"]),
                    "Duplicate request or invalid phase")
            unique.add(key)
            require(type(r["reserved"]) is int and r["reserved"] >= 0, "Invalid reservation")
            if actual is None:
                require(r["status"] in ("reserved", "uncertain") and bool(r["reason"]), "Unresolved amount dropped")
            else:
                require(r["status"] == "settled" and type(actual) is int and 0 <= actual <= r["reserved"]
                        and micro(r["provider_cost_usd"]) == actual and r["served_model"] == model
                        and len(r["response_sha256"]) == len(r["request_sha256"]) == 64, "Unverified actual charge")
                if route in ("svg-qwen-coder",PATCH,CONFIRM,"todomvc-gemma"):
                    require(r.get("provider") == ("DeepInfra" if route == "todomvc-gemma" else "SiliconFlow"),
                            "Pinned provider changed")
                identifier = r.get("generation_id_sha256")
                if identifier:
                    require(identifier not in generations, "Duplicate provider generation receipt")
                    generations.add(identifier)
        totals = total(rows)
        require(totals == item["total"] and totals["exposure_microusd"] <= cap
                and grouped(rows, "phase") == item["per_phase"] and grouped(rows, "replica") == item["per_replica"],
                "Published subtotals differ")
        require(item["per_phase_within_replica"] == {r: grouped([x for x in rows if x["replica"] == r], "phase")
                                                for r in sorted({x["replica"] for x in rows})}, "Replica phases differ")
        match_budget(totals, expected_budget(public, route, model), cap)
        all_rows.extend(rows)
    validate_release(data["routes"], ("svg-qwen-coder",), PATCH, "SVG allocation")
    if PATCH in data["routes"]:
        original = data["routes"]["svg-qwen-coder"]
        patch_admission = read(artifact_paths(PATCH)[3])["admission"]
        require(original["seal_sha256"] == patch_admission["closed_seal_sha256"], "SVG patch linked to the wrong preceding seal")
        match_budget(original["total"], patch_admission["closed_budget"], original["cap_microusd"])
    validate_release(data["routes"], ("duo-oss", "duo-qwen"), "duo-compact", "Duo allocation")
    validate_release(data["routes"], ("duo-oss", "duo-qwen", "duo-compact"), FORM, "Duo allocation")
    validate_release(data["routes"], ("svg-qwen-coder", PATCH), CONFIRM, "SVG allocation")
    require(all(group["exposure_microusd"] <= group["cap_microusd"] for group in data["allocations"].values()),
            "A funding group exceeded its shared allocation")
    require(sum(v[0] for v in BUCKETS.values()) == APPROVED
            and total(all_rows) == data["total"] and data["total"]["exposure_microusd"] <= APPROVED
            and allocation_totals(data["routes"]) == data["allocations"]
            and study_totals(data["routes"]) == data["studies"]
            and model_totals(data["routes"]) == data["models"], "Model, study or global total mismatch")


def confirmation_statement(base, last):
    validate(base)
    reports = {**base["routes"], CONFIRM: last}
    aggregates = {"authorization": base["authorization"], "models": model_totals(reports), "studies": study_totals(reports),
                  "allocations": allocation_totals(reports),
                  "total": total(call for report in reports.values() for call in report["calls"])}
    validate({**aggregates, "routes": reports}, confirmation=True)
    return {**aggregates, "seven_ledger_source_sha256": sha(DEST), "seven_ledger_total": base["total"],
            "new_ledger": last, "route_count": len(reports),
            "scope": "The confirmation uses the remaining original SVG allocation for two fresh libraries. "
                     "Its Direct pages and host controls are reused from the earlier SVG study and incur no fresh charge. "
                     "Gross reservations add the historical upper bound of every call, including released reservations. "
                     "Final exposure equals settled charges plus all still-open reservations in the three shared allocations."}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("write", "check-local", "check", "write-final", "check-final-local", "check-final"))
    action = p.parse_args().action
    if "final" in action:
        base = read(DEST)
        if action == "check-final-local":
            require(all(verified_route(key) == item for key,item in base["routes"].items()), "Previous ledger changed")
        last = read(FINAL)["new_ledger"] if action == "check-final" else verified_route(CONFIRM)
        statement = confirmation_statement(base, last)
        if action == "write-final":
            core.save(FINAL, statement)
        else:
            require(read(FINAL) == statement, "Combined accounts differ from the supplied ledger evidence")
        print(statement["route_count"], "authorized ledgers", statement["total"])
        return
    if action == "check":
        data = read(DEST)
    else:
        reports = {route: verified_route(route) for route in ROUTES}
        data = {"authorization": {"start_utc": START, "end_utc": END, "cap_microusd": APPROVED},
                "unit": "Ledger amounts are integer micro-US dollars, rounded upward per settled receipt. Provider charge sums "
                        "retain their exact decimal USD. Exposure includes every unresolved reservation at its original full amount. "
                        "The SVG patch and Web-Bench form reuse released SVG and Duo allocations after prior generation seals.",
                "routes": reports, "studies": study_totals(reports), "models": model_totals(reports),
                "allocations": allocation_totals(reports),
                "total": total(call for item in reports.values() for call in item["calls"])}
    validate(data)
    if action == "write":
        core.save(DEST, data)
    elif action == "check-local":
        require(data == read(DEST), "Raw or published accounting changed")
    print(len(data["routes"]), "authorized ledgers in three funding allocations", data["total"])


if __name__ == "__main__":
    main()
