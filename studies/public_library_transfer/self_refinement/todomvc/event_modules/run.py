"""Generate and score two local TodoMVC event libraries and an eight-task direct baseline."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess

from studies.public_library_transfer import browser, core
from studies.public_library_transfer.backbone_suites import run as suite
from studies.public_library_transfer.other_benchmarks import evaluate
from studies.public_library_transfer.self_refinement.local_domain import run as engine
from studies.public_library_transfer.self_refinement.todomvc import run as controller
from studies.public_library_transfer.self_refinement.todomvc.source_binding import run as binding
from studies.schema_constrained_table.generate import MODEL, REVISION, SNAPSHOT, infer
from studies.study_io import ROOT, now, read, sha

from . import modules

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/todomvc-local-events-20261124"
RESULT = HERE / "result.json"
SEEDS = {"A": 2711, "B": 4513}
TASKS = binding.TASKS


def register():
    targets, builders = suite.inputs()
    public = {"builder": builders["todomvc"], "targets": {t: targets[t]["public"] for t in TASKS}}
    browser.preserve_json(OUT / "public.json", public)
    files = [HERE / "PROTOCOL.md", HERE / "function.cjs", Path(__file__), Path(modules.__file__),
             Path(engine.__file__), Path(binding.__file__), binding.HERE / "extract.cjs", binding.ACORN,
             evaluate.todo.SHELL, evaluate.todo.HARNESS / "demo-todo-app.spec.ts", OUT / "public.json",
             Path(evaluate.__file__), Path(controller.__file__), ROOT / "studies/schema_constrained_table/generate.py"]
    metadata = {"files": {str(path.relative_to(ROOT)): sha(path) for path in files}, "model": MODEL, "revision": REVISION,
                "seeds": SEEDS, "weights": {p.name: sha(p) for p in SNAPSHOT.iterdir() if p.is_file()}}
    file = OUT / "registration.json"
    if file.exists():
        assert read(file)["contract"] == metadata
    else:
        browser.preserve_json(file, {"utc": now(), "contract": metadata})


class EventModel(engine.Model):
    def __init__(self):
        import torch
        import transformers
        self.torch = torch
        self.tokenizer = transformers.AutoTokenizer.from_pretrained(str(SNAPSHOT), local_files_only=True)
        self.tokenizer.padding_side = "left"
        self.tokenizer.pad_token = self.tokenizer.eos_token
        self.model = transformers.AutoModelForCausalLM.from_pretrained(
            str(SNAPSHOT), local_files_only=True, trust_remote_code=False, dtype=torch.float16,
            attn_implementation="sdpa").to("cuda").eval()
        browser.preserve_json(OUT / "environment.json", {"gpu": torch.cuda.get_device_name(0),
            "torch": torch.__version__, "transformers": transformers.__version__, "dtype": "float16"})


def build(lm, folder, seed, public):
    functions = {}
    names = list(modules.CONTRACTS)
    for idx in range(0, len(names), 4):
        batch = names[idx:idx + 4]
        prompts = [modules.messages(n, public) for n in batch]
        raws = lm.generate(folder / f"modules-{idx}.json", prompts, 384, seed + idx)
        functions.update({n: modules.extract(n, raw) for n, raw in zip(batch, raws, strict=True)})
        missing = [n for n in batch if not functions[n]]
        if missing:
            prompts = [modules.messages(n, public, error=True) for n in missing]
            retry = lm.generate(folder / f"repair-{idx}.json", prompts, 384, seed + idx + 100)
            functions.update({n: modules.extract(n, raw) for n, raw in zip(missing, retry, strict=True)})
    browser.preserve_json(folder / "library.json", functions)
    return functions


def files_row(group, arm, task, code, plan=None):
    row = {"group": group, "arm": arm, "task": task, "status": "invalid"}
    if plan is not None:
        row["plan"] = plan
    if code:
        path = OUT / group / arm / task / "files.json"
        browser.preserve_json(path, {"candidate.js": code})
        row.update(status="valid", files_sha256=sha(path))
    return row


def generate():
    register()
    if (OUT / "seal.json").exists():
        return
    public = read(OUT / "public.json")
    lm = EventModel()
    builds, rows = {}, []
    for group, seed in SEEDS.items():
        folder = OUT / group / "preparation"
        functions = build(lm, folder, seed, public["builder"])
        present = [k for k, v in functions.items() if v]
        valid = all(k in present for k in ("init", "select", "persist", "add"))
        options = {opt: any(functions[event] for event, feature in modules.EVENTS.items() if feature == opt)
                   for opt in modules.OPTIONS}
        builds[group] = {"valid": valid, "functions": present, "available_options": options,
                         "library_sha256": sha(folder / "library.json")}
        print("built", group, builds[group], flush=True)
        schema = core.obj({k: {"type": "boolean"} for k, v in options.items() if v})
        for task in TASKS:
            first = options.copy()
            chosen = {k: False for k in options}
            if valid and schema["properties"]:
                prompt = core.messages("Enable the capabilities requested by the current TodoMVC specification. "
                                       "Return one Boolean per available option.", {"task": public["targets"][task],
                                       "capabilities": {k: public["builder"]["spec"][k] for k in schema["properties"]}})
                slot = OUT / group / "plans" / (task + ".json")
                if not slot.exists():
                    browser.preserve_json(slot, {"prompt": prompt, "response": infer(lm.torch, lm.tokenizer, lm.model, prompt, schema)})
                selected = read(slot)["response"]["plan"]
                assert set(selected) == set(schema["properties"]) and all(type(v) is bool for v in selected.values())
                chosen.update(selected)
            for arm, values in (("self", chosen), ("fixed_on", first), ("fixed_off", dict.fromkeys(options, False))):
                rows.append(files_row(group, arm, task, modules.assemble(functions, values) if valid else None, values))

    for i in range(0, len(TASKS), 4):
        batch = TASKS[i:i + 4]
        prompts = [core.messages(controller.DIRECT, public["targets"][t]) for t in batch]
        outputs = lm.generate(OUT / "direct" / f"batch-{i}.json", prompts, 2048)
        for task, raw in zip(batch, outputs, strict=True):
            p = subprocess.run(["node", str(binding.HERE / "extract.cjs"), str(binding.ACORN)],
                               input=modules.js_block(raw), text=True, capture_output=True, timeout=10)
            code = json.loads(p.stdout)["code"] if p.returncode == 0 else None
            rows.append(files_row("direct", "direct", task, code))
        print("direct", batch, flush=True)
    paths = sorted(f for f in OUT.rglob("*.json") if f.name != "seal.json")
    browser.preserve_json(OUT / "seal.json", {"utc": now(), "registration_sha256": sha(OUT / "registration.json"),
        "sources": {str(p.relative_to(OUT)): sha(p) for p in paths}, "builds": builds, "rows": rows})


def paired(rows):
    direct = {r["task"]: r["passed"] for r in rows if r["group"] == "direct"}
    assert set(direct) == set(TASKS)
    result = {}
    for g in SEEDS:
        data = {arm: {r["task"]: r["passed"] for r in rows if r["group"] == g and r["arm"] == arm}
                for arm in ("self", "fixed_on", "fixed_off")}
        assert all(set(v) == set(TASKS) for v in data.values())
        result[g] = {"passed": {a: [t for t in TASKS if v[t]] for a, v in {**data, "direct": direct}.items()},
                     "self_only": [t for t in TASKS if data["self"][t] and not direct[t]],
                     "direct_only": [t for t in TASKS if direct[t] and not data["self"][t]]}
    return result


def score():
    record = read(OUT / "seal.json")
    assert all(sha(OUT / f) == h for f, h in record["sources"].items())
    public, _ = suite.inputs()
    server = evaluate.todo.Server(OUT)
    def one(row):
        if row["status"] != "valid":
            return {**row, "passed": False}
        file = OUT / row["group"] / row["arm"] / row["task"] / "files.json"
        assert sha(file) == row["files_sha256"]
        task = row["task"]
        dest = OUT / "scores" / task / row["files_sha256"]
        with browser.lock(dest / ".lock"):
            if not (dest / "verdict.json").exists():
                with browser.browser_slot():
                    evaluate.score(("todomvc", public[task], read(file), dest, server))
        return binding.official(dest, public[task], row)
    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            rows = list(pool.map(one, record["rows"]))
    finally:
        server.close()
    usage = {}
    for group in (*SEEDS, "direct"):
        for path in (OUT / group).rglob("*.json"):
            data = read(path)
            phase = "build" if "preparation" in path.parts else "deploy"
            values = usage.setdefault(group + "/" + phase, {"input_tokens": 0, "output_tokens": 0, "calls": 0})
            if "input_tokens" in data:
                values["calls"] += len(data["outputs"])
                values["input_tokens"] += sum(data["input_tokens"])
                values["output_tokens"] += sum(map(len, data["output_ids"]))
            elif "response" in data and "prompt" in data:
                values["calls"] += 1
                values["input_tokens"] += data["response"]["input_tokens"]
                values["output_tokens"] += len(data["response"]["generated_token_ids"])
    browser.write_json(RESULT, {"model": MODEL, "revision": REVISION, "seeds": SEEDS, "budget_usd": 0,
        "registration_sha256": record["registration_sha256"], "seal_sha256": sha(OUT / "seal.json"),
        "protocol_sha256": sha(HERE / "PROTOCOL.md"), "builds": record["builds"], "usage": usage,
        "rows": rows, "paired": paired(rows)})
    check()


def check():
    data = read(RESULT)
    assert data["protocol_sha256"] == sha(HERE / "PROTOCOL.md") and data["paired"] == paired(data["rows"])
    assert len(data["rows"]) == len(set((r["arm"], r["group"], r["task"]) for r in data["rows"])) == 56
    print({g: {a: len(t) for a, t in v["passed"].items()} for g, v in data["paired"].items()})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "generate", "score", "check"))
    {"register": register, "generate": generate, "score": score, "check": check}[parser.parse_args().action]()
