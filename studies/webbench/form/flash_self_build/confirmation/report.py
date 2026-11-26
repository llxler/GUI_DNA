"""Verify the independent Flash questionnaire confirmation against the sealed pilot and original comparators."""
import argparse
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from studies.ledger_read import totals
from studies.public_library_transfer import browser
from studies.study_io import ROOT, digest, read, sha
from .. import report as primary
from . import run

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/flash-form-confirmation-20261125"
PILOT_OUT = ROOT / "artifacts/flash-form-self-20261125"
RESULT = HERE / "result.json"
REPS = ("fresh-a", "fresh-b")
PILOT_REPORTS = (primary.RESULT, primary.RESULT.parent / "contract_repair/result.json",
                 primary.RESULT.parent / "manifest_schema/result.json")


def script_fingerprint(package):
    # Exclude guide text, control labels, file names, markup and CSS when checking identical JS.
    sources = [v for k, v in package["files"].items() if k.endswith((".js", ".mjs"))]
    if package.get("script"):
        sources.append(package["script"])
    return digest(sorted(sources)) if sources else None


def verify_fresh_build(branch, evidence):
    public = read(OUT / "inputs/form/public.json")
    original = read(primary.ORIGINAL / "inputs/form/public.json")
    assert public == original
    base = run.core.build_messages(public)
    base[0]["content"] += "\n" + run.GUIDE
    source_body = read(primary.ORIGINAL / "deepseek-flash/form/build/attempt-1/request.json")["body"]
    settings = {k: v for k, v in source_body.items() if k != "messages"}
    settings["reasoning"] = {"enabled": False}
    settings["seed"] += int(branch == "fresh-b")
    folder = OUT / branch / "form/build"
    attempts = sorted(folder.glob("attempt-*/request.json"))
    assert len(attempts) <= 2
    expected = base
    attempts_meta = []
    state = evidence["build"]
    for i, path in enumerate(attempts):
        body = read(path)["body"]
        assert body["model"] == primary.MODEL and body["max_tokens"] == 16000
        assert {k: v for k, v in body.items() if k != "messages"} == settings and body["messages"] == expected
        item = {"request_sha256": sha(path), "seed": body.get("seed")}
        response = path.with_name("response.json")
        if response.is_file():
            item.update(primary.delivery_stats(response))
            raw_text = read(response)["choices"][0]["message"].get("content") or ""
            if len(state["public_errors"]) > i:
                expected = base + [{"role": "assistant", "content": raw_text[:65000]},
                                   {"role": "user", "content": "Public delivery or startup check: " +
                                    state["public_errors"][i] + ". Return the entire corrected package; keep functional source complete."}]
        attempts_meta.append(item)
    evidence_fields = {"return_attempts": attempts_meta, "script_sha256": None}
    if state["status"] == "valid":
        assert attempts and response.is_file()
        accepted = Path(state["fixed"]).parent
        assert ROOT / accepted == response.parent
        normalized, applied = run.adapt(public, run.original.normalized(run.core.parse(raw_text)))
        rebuilt = run.core.package(public, normalized)
        assert rebuilt == read(folder / "package.json") and applied == read(response.with_name("adaptation.json"))
        probes = {k: read(response.with_name(k + "-public.json")) for k in ("default", "first")}
        assert all(not item["errors"] for item in probes.values())
        evidence_fields.update(script_sha256=script_fingerprint(rebuilt), adaptation=applied,
                               public_probe_sha256={k: sha(response.with_name(k + "-public.json")) for k in probes})
    return evidence_fields


def pilot_evidence():
    """Recover every admitted pilot's code digest from its sealed package; retain all non-admissions."""
    pilot = read(primary.RESULT)
    primary.check_public(pilot)
    assert sha(PILOT_OUT / "seal.json") == pilot["seal_sha256"]
    sources = {}
    for branch in (*primary.BRANCHES, *primary.SUPPLEMENTS):
        sealed_path = PILOT_OUT / branch / "seal.json"
        sealed = read(sealed_path)
        if branch in primary.BRANCHES:
            assert read(PILOT_OUT / "seal.json")["branches"][branch] == sealed
        else:
            assert pilot["supplemental_seal_sha256"][branch] == sha(sealed_path)
        status = sealed["build"]["status"]
        sources[branch] = {"status": status, "source_sha256": None, "script_sha256": None}
        if status == "valid":
            path = PILOT_OUT / branch / "form/build/package.json"
            assert sealed["build"]["package_sha256"] == sealed["package_sha256"] == sha(path)
            package = read(path)
            sources[branch].update(source_sha256=primary.package_source(package), script_sha256=script_fingerprint(package))
    assert pilot["branches"]["delivery-a"]["comparisons"]["direct"]["self_passed"] == 12
    assert pilot["billing"]["total"] == totals(PILOT_OUT / "budget.sqlite3")
    return {"report_sha256": sha(primary.RESULT), "seal_sha256": pilot["seal_sha256"],
            "candidate_sources": sources, "billing": pilot["billing"]["total"],
            "published_report_sha256": {str(p.relative_to(ROOT)): sha(p) for p in PILOT_REPORTS}}


def decision(branches, pilot_sources):
    previous = {row["source_sha256"] for row in pilot_sources.values() if row["source_sha256"]}
    hashes = [branches[rep]["build"]["source_sha256"] for rep in REPS]
    prior_scripts = {row["script_sha256"] for row in pilot_sources.values() if row["script_sha256"]}
    scripts = [branches[rep]["build"]["script_sha256"] for rep in REPS]
    separate = bool(all(hashes) and len(set(hashes)) == len(REPS) and all(scripts) and len(set(scripts)) == len(REPS))
    new = {rep: bool(value and value not in previous and js and js not in prior_scripts)
           for rep, value, js in zip(REPS, hashes, scripts)}
    reached = {}
    for rep in REPS:
        comparisons = branches[rep]["comparisons"]
        n = comparisons["direct"]["self_passed"]
        reached[rep] = (all(c["tasks"] == list(primary.TASKS) for c in comparisons.values())
                        and n >= 10 and n > comparisons["direct"]["comparator_passed"]
                        and n > comparisons["original-self"]["comparator_passed"])
    return {"threshold": 10, "denominator": 20, "novel_source_relative_to_pilot": new,
            "distinct_implementations": separate, "rep_passed": reached,
            "confirmed": bool(separate and all(new.values()) and all(reached.values()))}


def expenses(first, second):
    return {"calls": first["calls"] + second["calls"],
            "unsettled_calls": first["unsettled_calls"] + second["unsettled_calls"],
            **{k: round(first[k] + second[k], 6) for k in ("settled_usd", "exposure_usd")}}


def assemble(score, workers):
    registered_path = OUT / "registration.json"
    registration = read(registered_path)
    seal_path = OUT / "seal.json"
    sealed = read(seal_path)
    assert sha(registered_path) == sealed["registration_sha256"] and set(sealed["branches"]) == set(REPS)
    assert registration["utc"] <= sealed["utc"] and registration["tasks"] == list(primary.TASKS)
    assert tuple(registration["branches"]) == REPS and registration["model"] == primary.MODEL
    assert registration["cap_usd"] == 1.5
    for relative, checksum in registration["files"].items():
        assert sha(ROOT / relative) == checksum, relative
    for branch in REPS:
        assert read(OUT / branch / "seal.json") == sealed["branches"][branch]
    pilot = pilot_evidence()
    assert pilot["billing"] == registration["pilot"]
    contract = browser.verify_contract("form")
    controls = primary.historical(contract)
    with ExitStack() as context:
        context.enter_context(patch.object(primary, "OUT", OUT))
        context.enter_context(patch.object(primary, "BRANCHES", REPS))
        context.enter_context(patch.object(primary, "SUPPLEMENTS", ()))
        prepared = {rep: primary.sealed_candidates(rep, sealed["branches"][rep]) for rep in REPS}
        for rep in REPS:
            prepared[rep][0].update(verify_fresh_build(rep, sealed["branches"][rep]))
        accounting = primary.billing()
        branches = primary.score_branches(prepared, controls, contract, score, workers)
    total = accounting["total"]
    assert total["cap_usd"] == 1.5 and total["exposure_usd"] <= total["cap_usd"]
    return {"model": primary.MODEL, "project": "form", "tasks": list(primary.TASKS),
            "upstream_commit": browser.UPSTREAM_COMMIT, "contract_sha256": digest(contract),
            "registration_sha256": sha(registered_path), "seal_sha256": sha(seal_path),
            "registered_files_sha256": registration["files"], "original_report_sha256": sha(primary.BASELINE),
            "pilot": pilot, "branches": branches, "confirmation": decision(branches, pilot["candidate_sources"]),
            "billing": accounting, "pilot_and_confirmation_billing": expenses(pilot["billing"], total)}


def check_public(result):
    assert result["tasks"] == list(primary.TASKS) and result["model"] == primary.MODEL
    assert result["original_report_sha256"] == sha(primary.BASELINE)
    assert result["pilot"]["report_sha256"] == sha(primary.RESULT)
    primary_report = read(primary.RESULT)
    primary.check_public(primary_report)
    assert result["pilot"]["billing"] == primary_report["billing"]["total"]
    assert result["pilot"]["seal_sha256"] == primary_report["seal_sha256"]
    assert set(result["pilot"]["candidate_sources"]) == set((*primary.BRANCHES, *primary.SUPPLEMENTS))
    pilots = {}
    for path in PILOT_REPORTS:
        assert sha(path) == result["pilot"]["published_report_sha256"][str(path.relative_to(ROOT))]
        for k, branch in read(path)["branches"].items():
            assert k not in pilots
            pilots[k] = branch["build"]
    assert pilots.keys() == result["pilot"]["candidate_sources"].keys()
    for k, model in pilots.items():
        for field in ("status", "source_sha256"):
            assert model[field] == result["pilot"]["candidate_sources"][k][field]
    assert set(result["branches"]) == set(REPS)
    baseline = primary_report["branches"]["delivery-a"]["rows"]
    for branch in result["branches"].values():
        rows = branch["rows"]
        assert [r["task"] for r in rows] == list(primary.TASKS)
        for row, original in zip(rows, baseline):
            for arm in primary.HISTORICAL.values():
                assert row[arm] == original[arm]
            for arm in ("self", "fixed"):
                cell = row[arm]
                if cell["status"] == "valid":
                    assert type(cell["passed"]) is bool and len(cell["report_sha256"]) == len(cell["files_digest"]) == 64
                else:
                    assert cell["status"] in ("invalid", "missing", "build_failed")
                    assert cell["passed"] is (None if cell["status"] == "missing" else False)
        for arm in (*primary.HISTORICAL.values(), "fixed"):
            assert branch["comparisons"][arm] == primary.paired(rows, arm)
    assert result["confirmation"] == decision(result["branches"], result["pilot"]["candidate_sources"])
    assert result["pilot_and_confirmation_billing"] == expenses(result["pilot"]["billing"], result["billing"]["total"])
    stages = [stage for groups in result["billing"]["by_branch"].values() for stage in groups.values()]
    assert sum(s["calls"] for s in stages) == result["billing"]["total"]["calls"]
    for key in ("exposure", "settled"):
        assert sum(s[key + "_microusd"] for s in stages) == round(result["billing"]["total"][key + "_usd"] * 1e6)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", nargs="?", default="check", choices=("score", "check", "check-public"))
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    if args.action == "check-public":
        check_public(read(RESULT))
        print("Published fresh questionnaire libraries verified")
        return
    result = assemble(args.action == "score", args.workers)
    check_public(result)
    if args.action == "score":
        with browser.lock(OUT / ".public-result.lock"):
            if not RESULT.exists():
                browser.write_json(RESULT, result)
    if read(RESULT) != result:
        raise ValueError("Published confirmation differs from sealed pages or original receipts")
    print({k: v["comparisons"]["direct"]["self_passed"] for k, v in result["branches"].items()})
    print(result["confirmation"], result["pilot_and_confirmation_billing"])


if __name__ == "__main__":
    main()
