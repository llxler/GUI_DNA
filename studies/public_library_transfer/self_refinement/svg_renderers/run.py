"""Construct paired Qwen SVG libraries and seal the matched direct control before scoring."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from gui_dna.budget import BudgetStop, Ledger
from scripts.check_openrouter_credits import check_credits
from studies import ledger_read
from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, digest, now, read, sha

from . import components as comp, transport

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/qwen-svg-renderers-20261124"
RESULT = HERE / "result.json"
TASKS = tuple(range(1, 21))
ALL = dict.fromkeys(comp.KINDS, True)
CAP = .40
MISSING = (BudgetStop, transport.Unavailable)
DIRECT = ("Build the working SVG chart website for the latest public requirement including prerequisites. "
          "Start from the supplied starter and import its mounted assets. You can return one complete raw index.js, "
          "a complete HTML file, or multiple complete files, each with a // FILE: relative/path header. A JSON file map is also accepted. "
          "Use real mounted SVG and interactions. Preserve explicit options and use actual data. No tools or outside files.")


def register():
    file = OUT / "registration.json"
    if file.exists():
        rec = read(file)
        assert all(sha(ROOT / f) == h for f, h in rec["sources"].items())
        return
    balance = check_credits(CAP)
    if not balance["sufficient"]:
        raise BudgetStop("Balance below this stage allocation")
    core.save(OUT / "public.json", core.public_input(comp.CHART))
    paths = [HERE / "PROTOCOL.md", Path(__file__), Path(comp.__file__), Path(transport.__file__),
             Path(core.__file__), Path(browser.__file__), OUT / "public.json", ROOT / "src/gui_dna/budget.py"]
    core.save(file, {"utc": now(), "model": transport.MODEL, "project": comp.CHART, "cap_usd": CAP,
                     "request_cutoff": transport.END.isoformat(), "tasks": TASKS, "balance": balance,
                     "sources": {str(p.relative_to(ROOT)): sha(p) for p in paths},
                     "harness": browser.verify_contract(comp.CHART)})


def ask(ledger, name, prompt, limit, schema=None):
    return transport.ask(OUT, ledger, name, prompt, limit, schema)


def generate_module(ledger, group, kind, data, parents, previous=None):
    mode = "public-repair" if previous else "initial"
    key = f"{group}/build/{kind}/{mode}"
    prompt = comp.prompt(data, kind, parents)
    if previous:
        prompt += [{"role": "assistant", "content": previous[0]}, {"role": "user", "content":
                   "The registered public page probe found this renderer produces no graphics. "
                   "Return the complete corrected module. Public observations: " + str(previous[1])[:1400]}]
    for attempt in range(1 if previous else 2):
        try:
            raw = ask(ledger, f"{key}/{attempt+1}", prompt, 5200)
        except MISSING as error:
            return {"status": "missing", "reason": str(error)}
        try:
            return {"status": "valid", "code": comp.source(raw, kind)}
        except ValueError as error:
            reason = str(error)[:480]
            prompt += [{"role": "assistant", "content": raw}, {"role": "user", "content":
                       "Correct this public syntax/export error and return the complete module: " + reason}]
    return {"status": "invalid", "reason": reason}


def endpoint(folder, data, modules, settings, observe=False):
    files = core.emit(comp.CHART, comp.page(data, modules, settings), folder)
    result = {"status": "valid", "page": str(folder.relative_to(ROOT)), "files": files}
    if observe:
        result["public"] = comp.observe(OUT, folder, files)
    return result


def positive(observations):
    return {k for k, n in observations["drawn"].items() if n > 0}


def improved(before, after):
    previous, updated = positive(before), positive(after)
    return previous <= updated and ((previous < updated and len(after["errors"]) <= len(before["errors"]))
                                   or (previous == updated and len(after["errors"]) < len(before["errors"])))


def prepare(ledger, group, data):
    folder = OUT / group
    record = folder / "build.json"
    if record.exists():
        return read(record)
    states, modules = {}, {}
    for batch in (("base",), ("line", "bar", "pie"), ("scatter", "step", "area")):
        def generate(kind):
            deps = {n: code for n, code in modules.items() if n == comp.path("base") or
                    (kind in comp.DERIVED and n == comp.path("line"))}
            return generate_module(ledger, group, kind, data, deps)
        with ThreadPoolExecutor(max_workers=3) as pool:
            replies = list(pool.map(generate, batch))
        for kind, entry in zip(batch, replies, strict=True):
            states[kind] = {k: v for k, v in entry.items() if k != "code"}
            if "code" in entry:
                modules[comp.path(kind)] = entry["code"]
    all_usable = all(v["status"] == "valid" for v in states.values())
    result = {"states": states, "all_modules_received": all_usable, "repairs": {}}
    if all_usable:
        initial = endpoint(folder / "first", data, modules, ALL, True)
        observation = initial["public"]
        # All renderer revisions in this one round originate from the same public observation.
        missing = [k for k in comp.KINDS if k not in positive(observation)]
        proposed = dict(modules)
        def repair(k):
            deps = {n: c for n, c in modules.items() if n == comp.path("base") or (k in comp.DERIVED and n == comp.path("line"))}
            return generate_module(ledger, group, k, data, deps, (modules[comp.path(k)], observation))
        with ThreadPoolExecutor(max_workers=3) as pool:
            answers = list(pool.map(repair, missing))
        for k, answer in zip(missing, answers, strict=True):
            result["repairs"][k] = answer["status"]
            if answer["status"] == "valid":
                proposed[comp.path(k)] = answer["code"]
        chosen = initial
        if proposed != modules:
            revised = endpoint(folder / "revised", data, proposed, ALL, True)
            result["proposed_observation"] = revised["public"]
            if improved(observation, revised["public"]):
                chosen, modules = revised, proposed
        result.update(first=initial, selected=chosen, status="valid")
    else:
        result["status"] = "missing" if any(s["status"] == "missing" for s in states.values()) else "build_failed"
    core.save(folder / "modules.json", modules)
    result["modules_sha256"] = sha(folder / "modules.json")
    core.save(record, result)
    print(group, result["status"], result.get("selected", {}).get("public"), flush=True)
    return result


def from_scratch(ledger, n, data):
    folder = OUT / "direct" / str(n)
    record = folder / "candidate.json"
    if record.exists():
        return read(record)
    prompt = core.messages(DIRECT, core.prefix(data, n))
    attempts = []
    for k in range(2):
        try:
            raw = ask(ledger, f"direct/{n}/{k+1}", prompt, 6000)
        except MISSING as error:
            attempts.append({"status": "missing", "reason": str(error)})
            break
        try:
            changes = comp.direct(raw)
            if not changes:
                raise ValueError("Empty source")
            dest = folder / f"page-{k}"
            files = core.emit(comp.CHART, data["starter"] | changes, dest)
            ob = comp.observe(OUT, dest, files)
            record_page = {"status": "valid", "page": str(dest.relative_to(ROOT)), "files": files, "public": ob}
            issue = str(ob) if ob["errors"] or (n > 2 and not positive(ob)) or (n == 2 and not any(ob["mounted"].values())) else ""
        except (ValueError, KeyError, TypeError) as error:
            issue = str(error)[:500]
            record_page = {"status": "invalid", "reason": issue}
        attempts.append(record_page)
        if not issue:
            break
        prompt += [{"role": "assistant", "content": raw}, {"role": "user", "content":
                   "Public starter compilation or rendering feedback: " + issue[:1200] + ". Return the corrected complete file(s)."}]
    first, final = attempts[0], attempts[0]
    if len(attempts) == 2 and attempts[1]["status"] == "valid":
        second = attempts[1]
        if first["status"] != "valid" or improved(first["public"], second["public"]) or (
                n == 2 and not any(first["public"]["mounted"].values()) and any(second["public"]["mounted"].values()) and not second["public"]["errors"]):
            final = second
    result = {"first": first, "final": final, "attempts": attempts}
    core.save(record, result)
    return result


def choose(ledger, group, n, data, built, modules):
    if built["status"] != "valid":
        return {"status": built["status"]}
    schema = core.obj({k: {"type": "boolean"} for k in comp.KINDS})
    prompt = core.messages("Choose which real renderer types to mount for this target including prerequisites. Each true enables "
                           "the model-written renderer for public data of that type. False skips it. Return one Boolean for every field.",
                           {"current": core.prefix(data, n), "public_observations": built["selected"]["public"], "default": ALL})
    try:
        raw = ask(ledger, f"{group}/plan/{n}", prompt, 480, schema)
        selection = core.parse(raw)
        if set(selection) != set(ALL) or any(type(v) is not bool for v in selection.values()):
            raise ValueError("Invalid renderer configuration")
        code = endpoint(OUT / group / "plans" / str(n), data, modules, selection)
        return {**code, "plan": selection}
    except MISSING as error:
        return {"status": "missing", "reason": str(error)}
    except (ValueError, KeyError, TypeError) as error:
        return {"status": "invalid", "reason": str(error)[:500]}


def row(group, arm, n, candidate):
    return {"project": comp.CHART, "task": n, "group": group, "arm": arm,
            **{k: candidate[k] for k in ("status", "page", "files", "plan", "reason") if k in candidate}}


def generate():
    register()
    seal = OUT / "seal.json"
    if seal.exists():
        return
    ledger = Ledger(OUT / "budget.sqlite3", CAP, CAP)
    data = read(OUT / "public.json")
    def direct_batch():
        with ThreadPoolExecutor(max_workers=4) as pool:
            return dict(zip(TASKS, pool.map(lambda n: from_scratch(ledger, n, data), TASKS), strict=True))
    with ThreadPoolExecutor(max_workers=3) as pool:
        builds = {g: pool.submit(prepare, ledger, g, data) for g in ("A","B")}
        directs = pool.submit(direct_batch)
        builds = {g: v.result() for g, v in builds.items()}
        direct = directs.result()
    rows = [row("direct", arm, n, d[arm]) for n, d in direct.items() for arm in ("first", "final")]
    starter = {f: v for f, v in data["starter"].items() if f.endswith(".js") and f.startswith("common/")}
    host = endpoint(OUT / "host-only", data, starter, ALL)
    rows += [row("host", "only", n, host) for n in TASKS]
    for group, b in builds.items():
        modules = read(OUT / group / "modules.json")
        assert sha(OUT / group / "modules.json") == b["modules_sha256"]
        fixed = b["selected"] if b["status"] == "valid" else {"status": b["status"]}
        original = b["first"] if b["status"] == "valid" else fixed
        with ThreadPoolExecutor(max_workers=4) as pool:
            plans = list(pool.map(lambda n: choose(ledger, group, n, data, b, modules), TASKS))
        for n, plan in zip(TASKS, plans, strict=True):
            rows.extend([row(group,"planned",n,plan), row(group,"fixed",n,fixed), row(group,"initial_fixed",n,original)])
    core.save(seal, {"utc": now(), "registration_sha256": sha(OUT/"registration.json"), "builds": builds, "rows": rows})
    print("sealed", len(rows), flush=True)


def compare(rows):
    values = {(r["group"],r["arm"]): {} for r in rows}
    for r in rows:
        values[r["group"],r["arm"]][r["task"]] = r["passed"]
    assert all(set(d) == set(TASKS) for d in values.values())
    result = {}
    for g in ("A", "B"):
        methods = {"planned": values[g,"planned"], "fixed": values[g,"fixed"], "initial_fixed": values[g,"initial_fixed"],
                   "direct": values["direct","final"], "first_direct": values["direct","first"], "host": values["host","only"]}
        shared = [n for n in TASKS if all(d[n] is not None for d in methods.values())]
        result[g] = {"common_targets": shared, "passed": {k: [t for t in shared if d[t]] for k,d in methods.items()},
                     "without_asset_target": {k: sum(d[t] for t in shared if t != 1) for k,d in methods.items()},
                     "planned_only": [t for t in shared if methods["planned"][t] and not methods["direct"][t]],
                     "direct_only": [t for t in shared if methods["direct"][t] and not methods["planned"][t]]}
    return result


def score():
    record = read(OUT / "seal.json")
    registration = read(OUT / "registration.json")
    assert record["registration_sha256"] == sha(OUT / "registration.json")
    browser.OUT = OUT
    verified = browser.verify_contract(comp.CHART)
    assert verified == registration["harness"]
    scored = browser.evaluate(record["rows"], OUT, {comp.CHART: verified}, 4)
    rows = [{k: r.get(k) for k in ("group", "arm", "task", "status", "passed", "report_sha256", "plan")}
            | {"page_digest": digest(r["files"]) if r.get("files") else None} for r in scored]
    spending = ledger_read.calls(OUT / "budget.sqlite3")
    public = {"model": transport.MODEL, "project": comp.CHART, "provider": "SiliconFlow", "registered_utc": registration["utc"],
              "sealed_utc": record["utc"], "protocol_sha256": sha(HERE / "PROTOCOL.md"),
              "registration_sha256": sha(OUT / "registration.json"), "seal_sha256": sha(OUT / "seal.json"),
              "builds": {g: {k: v for k, v in b.items() if k not in ("first","selected")}
                         | {"observations": {k: b[k]["public"] for k in ("first","selected") if k in b}} for g,b in record["builds"].items()},
              "rows": rows, "paired": compare(rows), "calls": spending, "budget": ledger_read.totals(OUT / "budget.sqlite3")}
    core.save(RESULT, public)
    check()


def check():
    result = read(RESULT)
    assert result["protocol_sha256"] == sha(HERE / "PROTOCOL.md") and result["paired"] == compare(result["rows"])
    assert len(result["rows"]) == len(set((r["group"],r["arm"],r["task"]) for r in result["rows"])) == 180
    assert len(result["calls"]) == result["budget"]["calls"] and result["budget"]["exposure_usd"] <= CAP
    print({g: {"n":len(p["common_targets"]), **{k:len(v) for k,v in p["passed"].items()}} for g,p in result["paired"].items()}, result["budget"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register","generate","score","check"))
    {"register": register, "generate": generate, "score": score, "check": check}[parser.parse_args().action]()
