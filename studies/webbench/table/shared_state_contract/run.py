"""Build and deploy two independent libraries from a public starter and shared contracts."""
import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from gui_dna.budget import BudgetStop, Ledger
from gui_dna.provider import ProviderError, parse_json
from scripts.check_openrouter_credits import check_credits
from studies.interface_blind.core import public_check, write_files
from studies.ledger_read import totals
from studies.streaming_provider_v2 import StreamingOpenRouter
from studies.study_io import ROOT, digest, dump, now, read, sha, source_files
from studies.table_library_sources.core import MODEL, starter
from studies.table_library_sources.run import file_hashes, verify
from studies.webbench_expand.core import compile_plan, config, requirements

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/contract-library-table-20261123"
BASE = ROOT / "studies/results/table-library-sources-20261123.json"
BUILDER = "openai/gpt-5"
CAP = 0.105
DEADLINE = datetime.fromisoformat("2026-11-23T06:08:00+00:00")
SEEDS = [20261123, 20261124]
TASKS = [f"task-{t}" for t in range(1, 21)]


def msg(system, value):
    return [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(value, ensure_ascii=False)}]


def freeze():
    if (OUT / "freeze.json").exists():
        verify(read(OUT / "freeze.json")["inputs"])
        return
    prior = read(ROOT / "artifacts/editorial-20261123/closing-accounting.json")
    orig = read(ROOT / "artifacts/editorial-20261123/opening-credits.json")["effective_remaining_usd"]
    old = sum(totals(ROOT / "artifacts" / n / "budget.sqlite3")["exposure_usd"] for n in prior["ledgers"])
    assert old + CAP + .08 <= min(10, orig)
    credit = check_credits(CAP)
    assert credit["sufficient"] and datetime.now(timezone.utc) < DEADLINE
    dump(OUT / "public.json", {"requirements": requirements("table"), "starter": starter(),
                               "entry": "index.js", "style": "index.css"})
    archive = read(BASE)
    assert sum(r["ai"]["first"]["passed"] is True for r in archive["targets"].values()) == 3
    paths = [HERE / "run.py", HERE / "PROTOCOL.md", HERE / "compiler.js", OUT / "public.json", BASE,
             ROOT / "studies/webbench_expand/core.py", ROOT / "studies/interface_blind/compile.cjs",
             ROOT / "studies/streaming_provider_v2.py", ROOT / "studies/library_refinement_table/adapter.py"]
    dump(OUT / "freeze.json", {"utc": now(), "inputs": file_hashes(paths), "seeds": SEEDS, "cap": CAP,
                               "prior_exposure": old, "credits": credit, "close": DEADLINE.isoformat()})


def request(api, dest, model, prompt, limit, seed, validate, repair=False):
    stages = ["first", "repair"] if repair else ["first"]
    for stage in stages:
        folder = dest / stage
        marker = folder / "result.json"
        if marker.exists():
            r = read(marker)
            assert digest(prompt) == r["prompt_sha256"]
        else:
            r = {"prompt_sha256": digest(prompt), "received": False, "valid": False}
            dump(folder / "messages.json", prompt)
            try:
                if datetime.now(timezone.utc) >= DEADLINE and not (folder / "call/request.json").exists():
                    raise BudgetStop("Independent stage deadline")
                answer = api.call(model, prompt, folder / "call", str(dest.relative_to(OUT)) + "/" + stage,
                                  max_tokens=limit, seed=seed)
                r["received"] = True
                item = validate(parse_json(answer))
                dump(folder / "accepted.json", item)
                r["valid"] = True
            except (BudgetStop, ProviderError, ValueError, TypeError, KeyError) as err:
                r["error"] = str(err)[:700]
            dump(marker, r)
        if r["valid"]:
            return read(folder / "accepted.json"), r
        if not r["received"] or stage == stages[-1]:
            return None, r
        text = read(folder / "call/response.json")["choices"][0]["message"]["content"]
        prompt = prompt + [{"role": "assistant", "content": text},
                           {"role": "user", "content": "Public validation failed: " + r["error"] + ". Return a complete corrected JSON object."}]


def text_fields(obj, keys):
    if not isinstance(obj, dict) or set(obj) != set(keys) or not all(isinstance(obj[k], str) for k in keys):
        raise ValueError("Expected exactly the named string fields: " + ", ".join(keys))


def design_ok(obj):
    if not isinstance(obj, dict) or set(obj) != {"core", "contract", "features"}:
        raise ValueError("Expected core, contract, features")
    if not all(isinstance(obj[k], str) and obj[k].strip() for k in ("core", "contract")):
        raise ValueError("State contract and core responsibilities must be nonempty strings")
    features = obj["features"]
    if not isinstance(features, list) or not 2 <= len(features) <= 4:
        raise ValueError("Expected two to four independent features")
    ids = set()
    for f in features:
        text_fields(f, ["id", "behavior", "implementation"])
        key = f["id"]
        if not re.fullmatch("[A-Za-z][A-Za-z0-9_]{0,31}", key) or key == "core" or key in ids:
            raise ValueError("Expected unique, semantic JS-safe feature IDs")
        ids.add(key)
    return obj


def component_ok(obj):
    text_fields(obj, ["js", "css"])
    if not obj["js"].strip():
        raise ValueError("Missing executable component")
    result = subprocess.run(["node", "--input-type=module", "--check"], text=True, capture_output=True,
                            input="export default function install(ctx) {\n" + obj["js"] + "\n}")
    if result.returncode:
        raise ValueError(result.stderr[:600])
    return obj


DESIGN = """Design an executable application library around an unchanged public starter. Output JSON
{"core":"mandatory foundation responsibilities","contract":"specific shared ctx fields, helper signatures and DOM ownership",
"features":[{"id":"identifier","behavior":"short planner-facing description","implementation":"concrete responsibilities"}]}.
Choose two to four substantial semantic controllers covering the complete public requirements together. Design a common state
and operations that multiple UI events actually share. Respect the exact public DOM, existing labels/classes, native events and
persisted formats. Keep identifiers meaningful; no task numbers, per-milestone lookup, or placeholder features. Features are
independently selectable; core establishes state and public helper signatures, and optional parts tolerate omitted siblings.
A separate implementer will write each component with only this contract and the core. Be precise and compact."""
IMPLEMENT = """Implement the named part of this reusable library from the supplied public requirements and starter files.
Return only {"js":"...","css":"..."}; js is the executable BODY of function install(ctx) in a browser ES module,
css is an additional stylesheet string (possibly empty). Do not output import/export, a wrapper function, HTML/file maps,
or markdown. The public starter stays in place. Core is installed once as soon as the page's existing module loads; it owns
shared state and helpers. Each selected optional component installs once after core, in declared order. The supplied core
source, when present, is authoritative for shared names. Implement complete observable interactions in your responsibility,
including state mutation and the related DOM updates, and exact conventions explicitly named by the public requirements.
Read existing UI state before rendering. Use event delegation for dynamic nodes; avoid destroying the starter or duplicating
handlers owned by another module. No network, external packages or task IDs. Prefer concise working code over commentary."""
PLAN = """Return only a data plan for the frozen interface. Select all named controllers required by the public requirement
prefix, respecting later changes. The core is always installed; names are exact. Return one JSON object with only enabled."""


def assemble(public, design, parts):
    ids = [f["id"] for f in design["features"]]
    files = dict(public["starter"])
    files["library/manifest.json"] = json.dumps({"entry": public["entry"], "style": public["style"], "controllers": ids})
    for key, obj in parts.items():
        files["library/" + key + ".js"] = "export default function install(ctx) {\n" + obj["js"] + "\n}"
        files["library/" + key + ".css"] = obj["css"]
    schema = {"type": "object", "properties": {"enabled": {"type": "array", "minItems": 0, "maxItems": len(ids),
              "uniqueItems": True, "items": {"type": "string", "enum": ids}}}, "required": ["enabled"], "additionalProperties": False}
    return {"files": files, "compiler": (HERE / "compiler.js").read_text(), "plan_schema": schema,
            "plan_documentation": {"core": design["core"], "features": {f["id"]: f["behavior"] for f in design["features"]}},
            "examples": [{"enabled": []}, {"enabled": ids}]}


def prepare(api, rep, public):
    folder = OUT / f"rep-{rep}"
    marker = folder / "build.json"
    if marker.exists():
        return read(marker)
    seed = SEEDS[rep-1]
    design, r = request(api, folder / "design", BUILDER, msg(DESIGN, public), 1500, seed, design_ok, True)
    result = {"valid": False, "failed_at": "design"}
    if design:
        parts = {}
        for name in ["core", *(f["id"] for f in design["features"])]:
            inputs = {"public": public, "design": design, "component": name}
            if name != "core":
                inputs["installed_core"] = parts["core"]["js"]
            part, _ = request(api, folder / "component" / name, MODEL, msg(IMPLEMENT, inputs),
                              4096, seed, component_ok, True)
            if part is None:
                result["failed_at"] = name
                break
            parts[name] = part
        else:
            package = assemble(public, design, parts)
            dump(folder / "package.json", package)
            problems = []
            for label, example in zip(["empty", "full"], package["examples"]):
                dest = folder / "fixed" / label
                write_files(dest, compile_plan(package, example))
                problems.extend(public_check(dest))
            result = {"valid": not problems, "failed_at": "public load" if problems else None,
                      "problems": problems, "package_sha256": sha(folder / "package.json")}
    dump(marker, result)
    return result


def generate():
    freeze()
    if (OUT / "generation-complete.json").exists():
        verify(read(OUT / "generation-complete.json")["inputs"])
        return
    cfg = config()
    cfg.update(models=[BUILDER, MODEL], provider_order={}, budget_usd=CAP, stop_new_requests_usd=CAP)
    cfg["reasoning_effort"] = {BUILDER: "low"}
    cfg["model_price_caps"][MODEL] = {"prompt": .2, "completion": .8}
    api = StreamingOpenRouter(cfg, Ledger(OUT / "budget.sqlite3", CAP, CAP))
    api.RATE_LIMIT_TRIES = 1
    public = read(OUT / "public.json")
    builds = {str(rep): prepare(api, rep, public) for rep in (1, 2)}
    rows = []
    for n, task in enumerate(TASKS, 1):
        prefix = public["requirements"][:next(i for i,v in enumerate(public["requirements"]) if v["id"]==task)+1]
        for rep in (1, 2):
            folder = OUT / f"rep-{rep}"
            if not builds[str(rep)]["valid"]:
                continue
            package = read(folder / "package.json")
            payload = {"starter": public["starter"], "requirements": prefix, "interface": package["plan_documentation"],
                       "examples": package["examples"], "plan_schema": package["plan_schema"]}
            dest = folder / "plans" / task
            def check_plan(plan):
                files = compile_plan(package, plan)
                write_files(dest / "page", files)
                return {"plan": plan, "files": source_files(dest / "page")}
            item, receipt = request(api, dest, MODEL, msg(PLAN, payload), 8192, SEEDS[rep-1], check_plan)
            rows.append({"rep": rep, "task": task, "response": receipt["received"], "valid": item is not None,
                         "files": item["files"] if item else None})
    files = [p for p in OUT.rglob("*") if p.is_file() and (p.suffix in (".json", ".js", ".css", ".html") or p.name=="freeze.json")]
    dump(OUT / "generation-complete.json", {"utc": now(), "builds": builds, "rows": rows, "inputs": file_hashes(files)})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["freeze", "generate"])
    args = ap.parse_args()
    (freeze if args.phase == "freeze" else generate)()
