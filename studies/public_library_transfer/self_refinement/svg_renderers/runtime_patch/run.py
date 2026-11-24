"""Repair model-owned SVG source using public runtime traces before official replay."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from gui_dna.budget import BudgetStop, Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, digest, now, read, sha

from .. import components as comp, run as base, transport
from ..module_linking import run as linking
from . import observe

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/qwen-svg-runtime-patch-20261124"
RESULT = HERE / "result.json"
CAP = .12
BOOL = {"type": "boolean"}
STR = {"type": "string"}
EDITS = core.obj({"edits": {"type": "array", "items": core.obj({
    "file": STR, "before": STR, "after": STR, "every_occurrence": BOOL})}})
PLAN = core.obj({kind: BOOL for kind in comp.KINDS})


def register():
    files = (Path(__file__), HERE / "PROTOCOL.md", Path(observe.__file__), Path(transport.__file__),
             Path(comp.__file__), linking.OUT / "registration.json", base.OUT / "registration.json")
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in files}
    dst = OUT / "registration.json"
    if not dst.exists():
        assert not base.RESULT.exists() and not linking.RESULT.exists()
        core.save(dst, {"utc": now(), "sources": hashes, "stage_cap_usd": CAP, "pooled_cap_usd": base.CAP,
                        "cutoff": transport.END.isoformat(), "model": transport.MODEL})
    assert read(dst)["sources"] == hashes


def source(row):
    browser.verify_page(ROOT / row["page"], row["files"], comp.CHART)
    return {p: (ROOT / row["page"] / p).read_text() for p in row["files"] if not p.startswith("assets/")}


def candidate(directory, contents):
    files = core.emit(comp.CHART, contents, directory)
    return {"status": "valid", "page": str(directory.relative_to(ROOT)), "files": files}


def revise(original, raw, allowed):
    value = core.parse(raw)
    if not isinstance(value, dict) or not isinstance(value.get("edits"), list) or len(value["edits"]) > 20:
        raise ValueError("Invalid edit list")
    result = dict(original)
    for change in value["edits"]:
        fn, a, b, every = (change[k] for k in ("file", "before", "after", "every_occurrence"))
        if fn not in allowed or not isinstance(a, str) or not a.strip() or not isinstance(b,str) or type(every) is not bool:
            raise ValueError("Invalid edit or out-of-scope file")
        count = result[fn].count(a)
        if not count or (count > 1 and not every):
            raise ValueError("Source substring absent or ambiguous: " + fn)
        result[fn] = result[fn].replace(a, b)
    return result


def patch(ledger, label, row, data, task=None):
    folder = OUT / label
    if (folder / "patch.json").exists():
        return read(folder / "patch.json")
    result = {"selected": row, "decision": "no_source"}
    if row["status"] == "valid":
        files = source(row)
        allowed = {p for p in files if task is not None or p in {comp.path(k) for k in ("base", *comp.KINDS)}}
        first = observe.observe(OUT, ROOT / row["page"], row["files"])
        result.update(before=first, after=first, decision="no_public_issue")
        issue = bool(first["errors"]) or ((task is None or task > 2) and not any(first["drawn"].values())) or (
                task == 2 and not any(first["mounted"].values()))
        if issue:
            prompt = core.messages(
                "Repair only your existing web source from the real public browser diagnostics. Preserve existing behavior, "
                "local named imports, public data interfaces and positive observations. Return small exact before/after "
                "substrings from editable files. Set every_occurrence true if you intentionally replace repeated identical code. "
                "Fix the root cause across the affected functions. Never specialize to a sample id. No new files or dependencies.",
                {"public_requirements": core.prefix(data, task or 20)["requirements"],
                 "editable_files": sorted(allowed), "source": files, "public_observations": first})
            try:
                raw = transport.ask(OUT, ledger, label+"/edit", prompt, 1600, EDITS)
                changed = revise(files, raw, allowed)
                result["edited_files"] = sorted(k for k in files if changed[k] != files[k])
                if changed != files:
                    trial = candidate(folder / "proposed", changed)
                    ob = observe.observe(OUT, ROOT / trial["page"], trial["files"])
                    result.update(proposed=ob, decision="no_public_gain")
                    if observe.accept(first, ob):
                        result.update(selected=trial, after=ob, decision="accepted")
                else:
                    result["decision"] = "empty_patch"
            except (ValueError, TypeError, KeyError, BudgetStop, transport.Unavailable) as exc:
                result.update(decision="no_applicable_patch", error=str(exc)[:240])
    core.save(folder / "patch.json", result)
    return result


def generate():
    register()
    if (OUT / "seal.json").exists():
        return
    linking.freeze()
    old_total = ledger_read.totals(base.OUT / "budget.sqlite3")
    if old_total["exposure_usd"] + CAP > base.CAP or not (base.OUT / "seal.json").exists():
        raise BudgetStop("Original group must have closed within the released pool")
    if not (OUT / "admission.json").exists():
        balance = check_credits(CAP)
        if not balance["sufficient"]:
            raise BudgetStop("Insufficient live balance")
        core.save(OUT / "admission.json", {"utc": now(), "balance": balance, "closed_budget": old_total,
                  "closed_seal_sha256": sha(base.OUT / "seal.json"), "linked_seal_sha256": sha(linking.OUT / "seal.json")})
    assert read(OUT / "admission.json")["closed_budget"] == old_total
    ledger = Ledger(OUT / "budget.sqlite3", CAP, CAP)
    rows = {(r["group"], r["arm"], r["task"]): r for r in read(linking.OUT / "seal.json")["rows"]}
    data = read(base.OUT / "public.json")
    jobs = [(g, rows[g,"fixed",1], None) for g in ("A","B")]
    jobs += [(f"direct/{n}", rows["direct","final",n], n) for n in base.TASKS]
    with ThreadPoolExecutor(max_workers=7) as pool:
        changes = dict(zip([job[0] for job in jobs],
                           pool.map(lambda x: patch(ledger, x[0], x[1], data, x[2]), jobs), strict=True))
    prepared = []
    for n in base.TASKS:
        for g, arm, src in (("direct", "first", rows["direct","first",n]), ("direct", "previous", rows["direct","final",n]),
                            ("direct", "final", changes[f"direct/{n}"]["selected"]), ("host", "only", rows["host","only",n])):
            prepared.append(base.row(g, arm, n, src))
    for g in ("A","B"):
        package = changes[g]["selected"]
        for n in base.TASKS:
            prepared.append(base.row(g,"fixed",n,package))
            prepared.append(base.row(g,"initial_fixed",n,rows[g,"fixed",n]))
        if package["status"] != "valid":
            for n in base.TASKS:
                for arm in ("planned","previous_plan"):
                    prepared.append(base.row(g,arm,n,package))
            continue
        modules = {p: v for p,v in source(package).items() if p in {comp.path(k) for k in ("base", *comp.KINDS)}}
        def plan(n):
            prompt = core.messages(
                "Choose enabled renderer types for all requirements through the current public target. Each true mounts "
                "the model-written renderer for public data of that type. False skips it. Return all six booleans.",
                {"current": core.prefix(data,n), "public_observations":changes[g]["after"], "default":base.ALL})
            try:
                raw = transport.ask(OUT, ledger, f"{g}/plan/{n}", prompt, 380, PLAN)
                settings = core.parse(raw)
                if not isinstance(settings,dict) or set(settings)!=set(comp.KINDS) or any(type(v) is not bool for v in settings.values()):
                    raise ValueError("Invalid render settings")
                return {**candidate(OUT/g/"plans"/str(n),comp.page(data,modules,settings)), "plan":settings}
            except (BudgetStop,transport.Unavailable) as exc:
                return {"status":"missing","reason":str(exc)}
            except (ValueError,TypeError,KeyError) as exc:
                return {"status":"invalid","reason":str(exc)[:240]}
        with ThreadPoolExecutor(max_workers=5) as pool:
            fresh = list(pool.map(plan, base.TASKS))
        for n, new in zip(base.TASKS, fresh, strict=True):
            old = rows[g,"planned",n]
            if old["status"] == "valid":
                settings = old["plan"]
                old = {**candidate(OUT/g/"previous-plans"/str(n),comp.page(data,modules,settings)), "plan":settings}
            prepared.extend([base.row(g,"planned",n,new),base.row(g,"previous_plan",n,old)])
    core.save(OUT/"seal.json", {"utc":now(), "registration_sha256":sha(OUT/"registration.json"),
              "admission_sha256":sha(OUT/"admission.json"), "rows":prepared,
              "changes":{k:{a:b for a,b in v.items() if a!="selected"} for k,v in changes.items()}})
    print("sealed",len(prepared),flush=True)


def score():
    registration = read(OUT / "registration.json")
    seal = read(OUT / "seal.json")
    assert seal["registration_sha256"] == sha(OUT / "registration.json")
    assert seal["admission_sha256"] == sha(OUT / "admission.json")
    verified = browser.verify_contract(comp.CHART)
    prior = {}
    for origin, filename in (("raw",base.RESULT), ("linked",linking.RESULT)):
        if filename.exists():
            for r in read(filename)["rows"]:
                if r["status"] == "valid":
                    prior[r["task"],r["page_digest"]] = (origin, r)
    new_jobs = [r for r in seal["rows"] if r["status"] == "valid" and (r["task"],digest(r["files"])) not in prior]
    browser.OUT = OUT
    measured = browser.evaluate(new_jobs,OUT,{comp.CHART:verified},8)
    for r in measured:
        prior[r["task"], digest(r["files"])] = ("runtime_patch",r)
    records = []
    for r in seal["rows"]:
        row = {k:r.get(k) for k in ("group","arm","task","status","plan")}
        row.update(page_digest=None, report_sha256=None, receipt_source=None,
                   passed=None if r["status"]=="missing" else False)
        if r["status"] == "valid":
            browser.verify_page(ROOT / r["page"],r["files"],comp.CHART)
            key = digest(r["files"])
            origin, report = prior[r["task"],key]
            row.update(page_digest=key, report_sha256=report["report_sha256"], receipt_source=origin, passed=report["passed"])
        records.append(row)
    account = ledger_read.totals(OUT/"budget.sqlite3")
    data = {"model":transport.MODEL,"registered_utc":registration["utc"],"sealed_utc":seal["utc"],
            "seal_sha256":sha(OUT/"seal.json"),"protocol_sha256":sha(HERE/"PROTOCOL.md"),"contract_sha256":digest(verified),
            "sources":registration["sources"], "admission":read(OUT/"admission.json"),"changes":seal["changes"],
            "rows":records, "paired":base.compare(records), "budget":account, "calls":ledger_read.calls(OUT/"budget.sqlite3")}
    core.save(RESULT,data)
    check()


def check():
    data=read(RESULT)
    for rel,h in data["sources"].items():
        if rel.startswith("studies/"):
            assert sha(ROOT/rel)==h
    assert len(data["rows"]) == len({(r["group"],r["arm"],r["task"]) for r in data["rows"]}) == 240
    assert data["protocol_sha256"]==sha(HERE/"PROTOCOL.md") and data["paired"]==base.compare(data["rows"])
    assert data["budget"]["exposure_usd"]<=CAP and data["admission"]["closed_budget"]["exposure_usd"]+CAP<=base.CAP
    for r in data["rows"]:
        assert ((type(r["passed"]) is bool and len(r["report_sha256"])==64) if r["status"]=="valid"
                else (r["passed"] is None if r["status"]=="missing" else r["passed"] is False))
    print({g:{k:len(v) for k,v in c["passed"].items()} for g,c in data["paired"].items()}, data["budget"])


if __name__=="__main__":
    actions={"register":register,"generate":generate,"score":score,"check":check}
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("action",choices=actions)
    actions[cli.parse_args().action]()
