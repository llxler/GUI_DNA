"""Freeze, generate, and score two local model libraries and matched raw-HTML baselines."""
import argparse
import json
from pathlib import Path

from studies.public_library_transfer import core
from studies.schema_constrained_table.generate import MODEL, REVISION, SNAPSHOT, infer
from studies.study_io import ROOT, now, read, sha
from . import templates as t

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/self-local-calculator-20261124"
SEEDS = {"A": 1151, "B": 3503}
SCHEMA = core.obj({"setting": {"type": "string", "enum": ["A", "B"]}})
TASKS = range(1, 21)


def sources():
    paths = [HERE / "run.py", HERE / "templates.py", HERE / "PROTOCOL.md",
             Path(core.__file__), ROOT / "studies/schema_constrained_table/generate.py",
             ROOT / "studies/public_library_transfer/browser.py"]
    return {str(p.relative_to(ROOT)): sha(p) for p in paths}


def freeze():
    public = core.public_input("calculator")
    core.save(OUT / "public.json", public)
    registration = {"sources": sources(), "input_sha256": sha(OUT / "public.json"),
                    "model": MODEL, "revision": REVISION, "seeds": SEEDS,
                    "targets": list(TASKS), "weights": {p.name: sha(p) for p in SNAPSHOT.iterdir() if p.is_file()}}
    if (OUT / "registered.json").exists():
        if read(OUT / "registered.json")["contract"] != registration:
            raise ValueError("Registered contract changed")
        return
    core.save(OUT / "registered.json", {"registered": now(), "contract": registration})


class Model:
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
        core.save(OUT / "environment.json", {"torch": torch.__version__, "transformers": transformers.__version__,
                  "gpu": torch.cuda.get_device_name(0), "dtype": "float16", "attention": "sdpa"})

    def generate(self, path, prompts, limit, seeds=None):
        if path.is_file():
            evidence = read(path)
            if (evidence["prompts"], evidence["limit"], evidence["seeds"]) != (prompts, limit, seeds):
                raise ValueError("Generation inputs changed")
            return evidence["outputs"]
        texts = [self.tokenizer.apply_chat_template(prompt, add_generation_prompt=True, tokenize=False) for prompt in prompts]
        inputs = self.tokenizer(texts, padding=True, return_tensors="pt", add_special_tokens=False).to(self.model.device)
        options = {"do_sample": False}
        if seeds is not None:
            self.torch.manual_seed(seeds)
            options = {"do_sample": True, "temperature": 0.45, "top_p": 0.9}
        with self.torch.inference_mode():
            generated = self.model.generate(**inputs, max_new_tokens=limit, **options,
                                            pad_token_id=self.tokenizer.eos_token_id)
        output_ids = []
        for seq in generated[:, inputs["input_ids"].shape[1]:].tolist():
            if self.tokenizer.eos_token_id in seq:
                seq = seq[:seq.index(self.tokenizer.eos_token_id) + 1]
            output_ids.append(seq)
        outputs = [self.tokenizer.decode(seq, skip_special_tokens=True) for seq in output_ids]
        core.save(path, {"prompts": prompts, "limit": limit, "seeds": seeds,
                  "input_tokens": inputs["attention_mask"].sum(dim=1).tolist(), "output_ids": output_ids,
                  "outputs": outputs})
        return outputs


def build(lm, tag, data):
    folder = OUT / "builds" / tag
    source = data["starter"]["index.html"]
    lines = t.descriptions(data)
    seed = SEEDS[tag]
    existing = t.ExistingButtons()
    existing.feed(source)
    seen = {name.casefold() for name in existing.labels}
    groups = [lines[i:i + 5] for i in range(0, 20, 5)]
    raw = lm.generate(folder / "catalogues.json", [t.catalogue_prompt(g) for g in groups], 100, seed)
    labels = [label for response, group in zip(raw, groups) for label in t.labels_from(response, group, seen)]
    actions = {}
    if labels:
        result = lm.generate(folder / "actions.json", [t.behavior_prompt(k, lines) for k in labels], 94, seed + 1)
        for i, (key, text) in enumerate(zip(labels, result)):
            expr = t.expression(text)
            wrapper = lambda value: "(n,s,state)=>(" + value + ")"
            error = t.compile_error(wrapper(expr))
            if error:
                text = lm.generate(folder / f"repair-{i}.json", [t.behavior_prompt(key, lines, error[:350])],
                                   94, seed + 20 + i)[0]
                expr = t.expression(text)
            actions[key] = None if t.compile_error(wrapper(expr)) else expr
    panels = []
    for i, part in enumerate(("appearance", "panels")):
        code = t.strip_fence(lm.generate(folder / f"{part}.json", [t.panel_prompt(part, source, lines, labels)],
                                         820, seed + 2 + i)[0])
        panels.append("" if t.compile_error("(() => {\n" + code + "\n})") else code)
    axis_text = lm.generate(folder / "axis.json", [t.axis_prompt(lines)], 90, seed + 4)[0]
    axis = t.axis_description(axis_text)
    if axis is None:
        redo = t.messages("Rewrite the proposed settings as exactly two short phrases in one line: "
                          "first setting|second setting. No other punctuation or explanation.",
                          t.bullet_lines(lines) + "\nPrior response: " + axis_text)
        axis = t.axis_description(lm.generate(folder / "axis-format-repair.json", [redo], 70, seed + 67)[0])
    option_bodies = {}
    if axis:
        responses = lm.generate(folder / "options.json", [t.option_prompt(s, source, labels) for s in axis.values()],
                                320, seed + 5)
        for slot, response in zip(axis, responses):
            body = t.strip_fence(response)
            err = t.compile_error("(() => {\n" + body + "\n})")
            if not body or err:
                correction = t.option_prompt(axis[slot], source, labels)
                correction[-1]["content"] += "\nYour previous response and syntax diagnostic:\n" + response + "\n" + err[:350]
                repaired = lm.generate(folder / f"option-format-repair-{slot}.json", [correction], 360,
                                       seed + 68 + ("AB".index(slot)))[0]
                body = t.strip_fence(repaired)
            if body and not t.compile_error("(() => {\n" + body + "\n})"):
                option_bodies[slot] = body
    valid = bool(labels and axis and set(option_bodies) == {"A", "B"})
    package = {"actions": actions, "panels": panels, "axis": axis, "options": option_bodies, "valid": valid}
    core.save(folder / "library.json", package)
    print("build", tag, "received", len(labels), "keys, axis", axis, "admitted", valid, flush=True)
    endpoints = {}
    if valid:
        from studies.public_library_transfer.browser import public_load
        for slot in ("A", "B"):
            page = folder / f"page-{slot}"
            html = t.assemble(source, actions, panels, option_bodies[slot])
            files = core.emit("calculator", {"index.html": html}, page)
            errors = public_load("calculator", page)
            endpoints[slot] = {"page": str(page.relative_to(ROOT)), "files": files, "public_load_errors": errors}
    core.save(folder / "endpoints.json", endpoints)
    return package, endpoints


def row(task, arm, tag, endpoint=None, missing="build_failed"):
    return dict(project="calculator", task=task, arm=arm, rep=tag, status="valid" if endpoint else missing,
                page=endpoint["page"] if endpoint else None, files=endpoint["files"] if endpoint else None)


def generate():
    freeze()
    lm = Model()
    data = read(OUT / "public.json")
    source = data["starter"]["index.html"]
    lines = t.descriptions(data)
    rows = []
    for tag in SEEDS:
        pkg, endpoints = build(lm, tag, data)
        for task in TASKS:
            selection = None
            if endpoints:
                prompt = t.plan_prompt(lines[:task], pkg["axis"])
                file = OUT / "plans" / tag / f"{task}.json"
                if not file.exists():
                    response = infer(lm.torch, lm.tokenizer, lm.model, prompt, SCHEMA)
                    core.save(file, {"prompt": prompt, "response": response})
                selection = read(file)["response"]["plan"]["setting"]
            for arm, option in [("fixed-A", "A"), ("fixed-B", "B"), ("self", selection)]:
                rows.append(row(task, arm, tag, endpoints.get(option)) | {"setting": option})
    for first in range(1, 21, 4):
        ids = list(range(first, first + 4))
        prompts = [t.direct_prompt(source, data["init"], lines[:n]) for n in ids]
        responses = lm.generate(OUT / "direct" / f"batch-{first}.json", prompts, 2048)
        for task, response in zip(ids, responses):
            html = t.html_document(response)
            endpoint = None
            if html:
                page = OUT / "direct" / f"page-{task}"
                files = core.emit("calculator", {"index.html": html}, page)
                endpoint = {"page": str(page.relative_to(ROOT)), "files": files}
            rows.append(row(task, "direct", None, endpoint, missing="invalid"))
        print("direct", ids, flush=True)
    proof = {str(f.relative_to(OUT)): sha(f) for d in ("builds", "plans", "direct")
             for f in sorted((OUT / d).rglob("*.json"))}
    core.save(OUT / "generation-seal.json", {"registration_sha256": sha(OUT / "registered.json"),
              "public_sha256": sha(OUT / "public.json"), "files_sha256": proof, "rows": rows})


def score():
    from studies.public_library_transfer import browser
    record = read(OUT / "generation-seal.json")
    for name, digest in record["files_sha256"].items():
        if sha(OUT / name) != digest:
            raise ValueError(f"Sealed generation changed: {name}")
    protocol = browser.verify_contract("calculator")
    rows = browser.evaluate(record["rows"], OUT, {"calculator": protocol}, 4)
    core.save(OUT / "scores.json", {"rows": rows, "contract": protocol, "seal_sha256": sha(OUT / "generation-seal.json")})
    print("Scored", len(rows), "matched treatment positions", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["freeze", "generate", "score"])
    args = parser.parse_args()
    {"freeze": freeze, "generate": generate, "score": score}[args.action]()


if __name__ == "__main__":
    main()
