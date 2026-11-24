"""Run the typed calculator library comparison under one frozen public domain adapter."""
import argparse
import json
from pathlib import Path
import re
from collections import Counter

from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, now, read, sha
from .. import templates as t
from ..run import Model, OUT as FIRST, SCHEMA, TASKS, infer, row
from . import grammar

HERE = Path(__file__).resolve().parent
OUT = FIRST / "typed-keys"
SEEDS = {"A": 9203, "B": 9923}


def freeze():
    paths = [HERE / "run.py", HERE / "grammar.py", HERE / "PROTOCOL.md", HERE.parent / "templates.py",
             HERE.parent / "run.py", Path(browser.__file__), Path(core.__file__)]
    contract = {"sources": {str(p.relative_to(ROOT)): sha(p) for p in paths},
                "seeds": SEEDS, "primary_registration": sha(FIRST / "registered.json"),
                "public_sha256": sha(FIRST / "public.json"), "targets": list(TASKS),
                "domain_math": grammar.math_properties()}
    dst = OUT / "registered.json"
    if dst.exists():
        if read(dst)["contract"] != contract:
            raise ValueError("Registered adapter changed")
    else:
        core.save(dst, {"registered": now(), "contract": contract})


def operation(lm, path, label, feature, choices, seed):
    options = list(choices)
    prompt = t.messages("Read the public calculator key definition. Choose the numbered operation that best "
                        "implements its requested effect. Return only the integer index.",
                        "Allowed operations:\n" + "\n".join(f"{i}: {k}" for i, k in enumerate(options)) +
                        "\nPublic requirement: " + feature["public_text"] +
                        f"\nThe target key is {label!r}, named {feature['name']!r}. Its operation number is")
    if path.exists():
        value = read(path)
        if value["prompt"] != prompt or value["seed"] != seed:
            raise ValueError("Altered operation query")
        return value["operation"]
    tok, model, torch = lm.tokenizer, lm.model, lm.torch
    ids = tok.apply_chat_template(prompt, add_generation_prompt=True, tokenize=True,
                                  return_dict=True, return_tensors="pt")["input_ids"].to(model.device)
    tokens = [tok.encode(str(i), add_special_tokens=False) for i in range(len(options))]
    if any(len(x) != 1 for x in tokens):
        raise ValueError("Numerical schema choices exceed one-token limit")
    with torch.inference_mode():
        state = model.model(input_ids=ids)
        scores = model.lm_head(state.last_hidden_state[:, -1:])[0, 0, [x[0] for x in tokens]].float()
        torch.manual_seed(seed)
        selected = int(torch.multinomial(torch.softmax(scores / 0.45, dim=0), 1).item())
    core.save(path, {"prompt": prompt, "seed": seed, "choices": options, "logits": scores.tolist(),
                    "selected_index": selected, "operation": options[selected], "input_tokens": ids.shape[1], "output_tokens": 1})
    return options[selected]


def page(html, directory):
    manifest = core.emit("calculator", {"index.html": html}, directory)
    return {"page": str(directory.relative_to(ROOT)), "files": manifest}


def direct_rows():
    rows = []
    for first in range(1, 21, 4):
        batch = read(FIRST / "direct" / f"batch-{first}.json")
        for task, response in zip(range(first, first + 4), batch["outputs"]):
            html = t.html_document(response)
            if html is None:
                partial = re.search(r"(?:<!doctype\s+html\s*>\s*)?<html\b[^>]*>.*?<body\b.*", response, re.I | re.S)
                html = partial[0] if partial else None
            item = page(html, OUT / "direct" / f"page-{task}") if html else None
            rows.append(row(task, "direct", None, item, missing="invalid"))
    return rows


def build(lm, tag, source, lines, keys, pair, codes):
    folder = OUT / "builds" / tag
    groundings = {}
    learned = {}
    mem_options = {k: v for k, v in codes.items() if any(w in k for w in ["memory", "stored", "store ", "keep display"])}
    for idx, (label, feature) in enumerate(keys.items()):
        key = grammar.ground(label, feature, codes)
        if key is not None:
            groundings[label] = key
        else:
            choices = mem_options if "memor" in feature["name"].lower() else codes
            learned[label] = operation(lm, folder / f"choice-{idx}.json", label, feature, choices, SEEDS[tag] + idx)
    panels = []
    for i, part in enumerate(("appearance", "panels")):
        code = t.strip_fence(lm.generate(folder / f"{part}.json", [t.panel_prompt(part, source, lines, list(keys))],
                                         820, SEEDS[tag] + 34 + i)[0])
        panels.append("" if t.compile_error("(() => {\n" + code + "\n})") else code)
    actions = {k: codes[(groundings | learned)[k]] for k in keys}
    controls = {"A": "Keep the relative order " + ", ".join(pair) + " in which the buttons were first introduced.",
                "B": "Swap the two buttons, so the relative order becomes " + ", ".join(reversed(pair)) + "."}
    endpoints = {}
    for setting in controls:
        html = t.assemble(source, actions, panels, "" if setting == "A" else grammar.order_setup(pair))
        endpoints[setting] = page(html, folder / f"page-{setting}")
    binding_actions = {k: codes[groundings[k]] if k in groundings else None for k in keys}
    endpoints["linker"] = page(t.assemble(source, binding_actions, [], ""), folder / "linker-page")
    core.save(folder / "library.json", {"inventory": keys, "direct_links": groundings, "model_operations": learned,
              "model_panels": panels, "settings": controls, "endpoints": endpoints})
    return controls, endpoints


def generate():
    freeze()
    if not (FIRST / "generation-seal.json").exists():
        raise RuntimeError("Direct and initial local builds must be sealed first")
    lm = Model()
    data = read(FIRST / "public.json")
    source = data["starter"]["index.html"]
    lines = t.descriptions(data)
    keys, pair = grammar.inventory(lines)
    if not pair or set(pair) - set(keys):
        raise ValueError("Public pair cannot be assembled")
    codes = grammar.expressions(read(OUT / "registered.json")["contract"]["domain_math"])
    rows = direct_rows()
    for tag in SEEDS:
        controls, endpoints = build(lm, tag, source, lines, keys, pair, codes)
        for task in TASKS:
            prompt = t.plan_prompt(lines[:task], controls)
            target = OUT / "plans" / tag / f"{task}.json"
            if not target.exists():
                core.save(target, {"prompt": prompt, "response": infer(lm.torch, lm.tokenizer, lm.model, prompt, SCHEMA)})
            choice = read(target)["response"]["plan"]["setting"]
            for arm, setting in [("fixed-A", "A"), ("fixed-B", "B"), ("self", choice), ("linker", "linker")]:
                rows.append(row(task, arm, tag, endpoints[setting]) | {"setting": setting})
        print("Sealed library", tag, flush=True)
    proof = {str(f.relative_to(OUT)): sha(f) for d in ("builds", "plans") for f in sorted((OUT / d).rglob("*.json"))}
    core.save(OUT / "seal.json", {"generation": proof, "registration_sha256": sha(OUT / "registered.json"),
              "original_generation_sha256": sha(FIRST / "generation-seal.json"), "rows": rows})


def score():
    record = read(OUT / "seal.json")
    for name, digest in record["generation"].items():
        if sha(OUT / name) != digest:
            raise ValueError(f"Sealed generation changed: {name}")
    rows = browser.evaluate(record["rows"], OUT, {"calculator": browser.verify_contract("calculator")}, 4)
    core.save(OUT / "scores.json", {"rows": rows, "seal_sha256": sha(OUT / "seal.json")})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["freeze", "generate", "score"])
    args = parser.parse_args()
    {"freeze": freeze, "generate": generate, "score": score}[args.action]()


if __name__ == "__main__":
    main()
