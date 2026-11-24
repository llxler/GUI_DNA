"""A predeclared component ablation in which the local LM predicts all key programs."""
import argparse
import hashlib
import json
from pathlib import Path

from studies.public_library_transfer import browser, core
from studies.schema_constrained_table.generate import SNAPSHOT
from studies.study_io import ROOT, now, read, sha
from .. import templates as t
from ..run import TASKS, row
from . import grammar
from .run import HERE, FIRST, OUT as TYPED, page

OUT = TYPED / "model-keys"
SEEDS = {"A": 7253, "B": 8039}


def freeze():
    path = OUT / "registered.json"
    files = [Path(__file__), HERE / "MODEL.md", HERE / "grammar.py", HERE / "run.py", HERE.parent / "templates.py"]
    contract = {"sources": {str(f.relative_to(ROOT)): sha(f) for f in files}, "parent": sha(TYPED / "registered.json"),
                "seeds": SEEDS}
    if path.exists():
        assert read(path)["contract"] == contract
    else:
        core.save(path, {"registered": now(), "contract": contract})


def choose(torch, tok, lm, label, feature, exprs, seed):
    prompt = t.messages("Return just the JavaScript expression for the named calculator key. n is the current "
                        "number, s the current display string, and state.memory is a single stored number. "
                        "For example, natural logarithm gives Math.log(n) and absolute value gives Math.abs(n).",
                        f"Source request: {feature['public_text']}\nThe key to implement has the name {feature['name']} "
                        f"and shows {label!r}. Complete the JavaScript after return.")
    prefix = tok.apply_chat_template(prompt, add_generation_prompt=True, tokenize=False) + "return "
    ids = tok(prefix, add_special_tokens=False, return_tensors="pt")["input_ids"].to(lm.device)
    alternatives = sorted(set(exprs))
    # A delimiter makes shorter expressions like n+1 distinguishable from longer ones.
    candidates = {e: tok.encode(e + ";", add_special_tokens=False) for e in alternatives}
    positions = dict(candidates)
    cache = None
    branch_log = []
    output = []
    torch.manual_seed(seed)
    with torch.inference_mode():
        while not any(not seq for seq in positions.values()):
            state = lm.model(input_ids=ids, past_key_values=cache, use_cache=True)
            cache = state.past_key_values
            edges = sorted({seq[0] for seq in positions.values()})
            if len(edges) == 1:
                token = edges[0]
            else:
                logits = lm.lm_head(state.last_hidden_state[:, -1:])[0, 0, edges].float()
                index = int(torch.multinomial(torch.softmax(logits / 0.45, dim=0), 1).item())
                token = edges[index]
                branch_log.append({"ids": edges, "logits": logits.tolist(), "chosen": token})
            output.append(token)
            positions = {e: seq[1:] for e, seq in positions.items() if seq[0] == token}
            ids = torch.tensor([[token]], device=lm.device)
    if len(positions) != 1 or next(iter(positions.values())):
        raise RuntimeError("Ambiguous expression grammar")
    return {"prompt": prompt, "continuation": "return ", "input_tokens": len(tok.encode(prefix, add_special_tokens=False)),
            "output_ids": output, "expression": next(iter(positions)), "branches": branch_log, "seed": seed}


def generate():
    import torch
    import transformers
    freeze()
    torch.set_num_threads(3)
    torch.set_num_interop_threads(1)
    tok = transformers.AutoTokenizer.from_pretrained(str(SNAPSHOT), local_files_only=True)
    lm = transformers.AutoModelForCausalLM.from_pretrained(str(SNAPSHOT), local_files_only=True, dtype=torch.float32,
                                                          attn_implementation="sdpa").eval()
    core.save(OUT / "environment.json", {"torch": torch.__version__, "transformers": transformers.__version__,
              "device": str(lm.device), "dtype": str(lm.dtype), "threads": torch.get_num_threads()})
    if str(lm.device) != "cpu":
        raise ValueError("Registered CPU inference")
    exprs = list(grammar.expressions(read(TYPED / "registered.json")["contract"]["domain_math"]).values())
    source = read(FIRST / "public.json")["starter"]["index.html"]
    lines = t.descriptions(read(FIRST / "public.json"))
    _, pair = grammar.inventory(lines)
    rows = [r for r in read(TYPED / "seal.json")["rows"] if r["arm"] == "direct"]
    for tag in SEEDS:
        base = OUT / "builds" / tag
        pkg = read(TYPED / "builds" / tag / "library.json")
        choices = {}
        for i, (label, feature) in enumerate(pkg["inventory"].items()):
            f = base / f"key-{i}.json"
            if not f.exists():
                core.save(f, choose(torch, tok, lm, label, feature, exprs, SEEDS[tag] + i))
            choices[label] = read(f)["expression"]
        endpoints = {arm: page(t.assemble(source, choices, pkg["model_panels"],
                                          "" if arm == "A" else grammar.order_setup(pair)), base / f"page-{arm}")
                     for arm in ("A", "B")}
        core.save(base / "library.json", {"choices": choices, "endpoints": endpoints,
                  "source_library_sha256": sha(TYPED / "builds" / tag / "library.json")})
        for task in TASKS:
            choice = read(TYPED / "plans" / tag / f"{task}.json")["response"]["plan"]["setting"]
            for arm, opt in [("self", choice), ("fixed-A", "A"), ("fixed-B", "B")]:
                rows.append(row(task, arm, tag, endpoints[opt]) | {"setting": opt})
        print("All 13 programs generated for", tag, flush=True)
    core.save(OUT / "seal.json", {"rows": rows, "typed_generation": sha(TYPED / "seal.json"),
              "sources": {str(p.relative_to(OUT)): sha(p) for p in (OUT / "builds").rglob("*.json")}})


def score():
    seal = read(OUT / "seal.json")
    for p, h in seal["sources"].items():
        if sha(OUT / p) != h:
            raise ValueError(f"Changed model program {p}")
    # Direct pages and verdicts are shared by design; reverify the original receipt for each.
    protocol = browser.verify_contract("calculator")
    own_rows = [r for r in seal["rows"] if r["arm"] != "direct"]
    rows = browser.evaluate(own_rows, OUT, {"calculator": protocol}, 3)
    direct = [r for r in seal["rows"] if r["arm"] == "direct"]
    rows += browser.evaluate(direct, TYPED, {"calculator": protocol}, 1)
    core.save(OUT / "scores.json", {"rows": rows, "seal": sha(OUT / "seal.json")})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["freeze", "generate", "score"])
    {"freeze": freeze, "generate": generate, "score": score}[parser.parse_args().action]()


if __name__ == "__main__":
    main()
