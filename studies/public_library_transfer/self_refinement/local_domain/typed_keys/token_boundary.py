"""Compare locally sampled expression programs with tokenization of the entire continuation."""
import argparse
from pathlib import Path

from studies.public_library_transfer import browser, core
from studies.schema_constrained_table.generate import SNAPSHOT
from studies.study_io import ROOT, now, read, sha
from .. import templates as t
from ..run import TASKS, row
from . import grammar, model
from .run import FIRST, HERE, OUT as TYPED, page

OUT = TYPED / "joint-tokens"


class JointTokenizer:
    """Adapt the frozen choice routine to use tokenizer-consistent prefix and suffix IDs."""

    def __init__(self, tokenizer):
        self.tokenizer = tokenizer
        self.prefix = None
        self.prefix_ids = None

    def apply_chat_template(self, *args, **kwargs):
        return self.tokenizer.apply_chat_template(*args, **kwargs)

    def __call__(self, prefix, **kwargs):
        if not prefix.endswith("return "):
            raise ValueError("Unexpected sampling boundary")
        self.prefix = prefix
        retained = prefix[:-1]
        encoded = self.tokenizer(retained, **kwargs)
        self.prefix_ids = encoded["input_ids"][0].tolist()
        return encoded

    def encode(self, text, **kwargs):
        if text == self.prefix:
            return self.prefix_ids
        joined = self.tokenizer.encode(self.prefix + text, **kwargs)
        if joined[:len(self.prefix_ids)] != self.prefix_ids:
            raise ValueError("Tokenizer does not preserve the retained prefix")
        return joined[len(self.prefix_ids):]


def freeze():
    paths = [Path(__file__), HERE / "TOKEN_BOUNDARY.md", HERE / "model.py", HERE / "grammar.py"]
    contract = {"sources": {str(f.relative_to(ROOT)): sha(f) for f in paths},
                "parent_generation": sha(model.OUT / "seal.json"), "seeds": model.SEEDS}
    target = OUT / "registered.json"
    if target.exists():
        if read(target)["contract"] != contract:
            raise ValueError("Changed token diagnostic")
    else:
        core.save(target, {"registered": now(), "contract": contract})


def generate():
    import torch
    import transformers
    freeze()
    torch.set_num_threads(3)
    torch.set_num_interop_threads(1)
    tok = transformers.AutoTokenizer.from_pretrained(str(SNAPSHOT), local_files_only=True)
    adapter = JointTokenizer(tok)
    lm = transformers.AutoModelForCausalLM.from_pretrained(str(SNAPSHOT), local_files_only=True, dtype=torch.float32,
                                                          attn_implementation="sdpa").eval()
    assert str(lm.device) == "cpu"
    codes = grammar.expressions(read(TYPED / "registered.json")["contract"]["domain_math"])
    source = read(FIRST / "public.json")["starter"]["index.html"]
    _, pair = grammar.inventory(t.descriptions(read(FIRST / "public.json")))
    rows = [r for r in read(TYPED / "seal.json")["rows"] if r["arm"] == "direct"]
    comparison = {}
    for tag, seed in model.SEEDS.items():
        base = OUT / "builds" / tag
        old = read(model.OUT / "builds" / tag / "library.json")["choices"]
        pkg = read(TYPED / "builds" / tag / "library.json")
        assigned = {}
        changes = []
        for i, (label, feature) in enumerate(pkg["inventory"].items()):
            path = base / f"key-{i}.json"
            if not path.exists():
                sampled = model.choose(torch, adapter, lm, label, feature, codes.values(), seed + i)
                core.save(path, sampled)
            expr = read(path)["expression"]
            assigned[label] = expr
            canonical = codes[pkg["direct_links"][label]] if label in pkg["direct_links"] else None
            changes.append({"label": label, "split": old[label], "joint": expr, "canonical": canonical})
        comparison[tag] = changes
        endpoints = {arm: page(t.assemble(source, assigned, pkg["model_panels"],
                             "" if arm == "A" else grammar.order_setup(pair)), base / f"page-{arm}")
                     for arm in ("A", "B")}
        core.save(base / "library.json", {"choices": assigned, "endpoints": endpoints})
        for task in TASKS:
            choice = read(TYPED / "plans" / tag / f"{task}.json")["response"]["plan"]["setting"]
            for arm, opt in [("self", choice), ("fixed-A", "A"), ("fixed-B", "B")]:
                rows.append(row(task, arm, tag, endpoints[opt]) | {"setting": opt})
    core.save(OUT / "seal.json", {"rows": rows, "comparison": comparison,
              "sources": {str(p.relative_to(OUT)): sha(p) for p in (OUT / "builds").rglob("*.json")}})
    print("Sealed 26 complete joint-token programs.")


def score():
    seal = read(OUT / "seal.json")
    for name, digest in seal["sources"].items():
        if sha(OUT / name) != digest:
            raise ValueError("Changed generated page evidence")
    contract = browser.verify_contract("calculator")
    own = [r for r in seal["rows"] if r["arm"] != "direct"]
    rows = browser.evaluate(own, OUT, {"calculator": contract}, 3)
    rows += browser.evaluate([r for r in seal["rows"] if r["arm"] == "direct"], TYPED, {"calculator": contract}, 1)
    core.save(OUT / "scores.json", {"rows": rows, "sealed": sha(OUT / "seal.json")})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["freeze", "generate", "score"])
    {"freeze": freeze, "generate": generate, "score": score}[parser.parse_args().action]()


if __name__ == "__main__":
    main()
