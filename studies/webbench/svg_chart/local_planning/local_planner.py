"""Run the frozen local checkpoint on independent, already prepared message arrays."""
import argparse
from datetime import datetime, timezone
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import sys
import time

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"

MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
REVISION = "7ae557604adf67be50417f59c2c2f167def9a775"
SNAPSHOT = Path.home() / ".cache/huggingface/hub/models--Qwen--Qwen2.5-0.5B-Instruct/snapshots" / REVISION
DEADLINE = datetime(2026, 11, 23, 6, 6, tzinfo=timezone.utc)
TARGETS = range(1, 21)
GENERATION = {"max_new_tokens": 768, "do_sample": False, "num_beams": 1, "repetition_penalty": 1.0,
              "bos_token_id": 151643, "pad_token_id": 151643, "eos_token_id": [151645, 151643],
              "use_cache": True}


def now():
    return datetime.now(timezone.utc).isoformat()


def expired():
    return datetime.now(timezone.utc) >= DEADLINE


def file_hash(path):
    with Path(path).open("rb") as handle:
        return __import__("hashlib").file_digest(handle, "sha256").hexdigest()


def encode_hash(value):
    return sha256(json.dumps(value, separators=(",", ":")).encode()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temp.replace(path)


def capture_inputs(root):
    return {str(n): file_hash(root / "prompts" / f"task-{n}.json") for n in TARGETS}


def infer(root):
    import torch
    import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer, GenerationConfig, StoppingCriteria, StoppingCriteriaList
    from transformers.utils import logging
    logging.disable_progress_bar()

    class DeadlineStop(StoppingCriteria):
        def __call__(self, input_ids, scores, **kwargs):
            return torch.full((input_ids.shape[0],), expired(), dtype=torch.bool, device=input_ids.device)

    root = root.resolve()
    marker = root / "local-generation.json"
    if marker.exists():
        raise SystemExit("Local generation is already sealed")
    cfg = {"model": MODEL, "revision": REVISION, "generation_config": GENERATION,
           "model_files_sha256": {p.name: file_hash(p) for p in sorted(SNAPSHOT.iterdir()) if p.is_file()},
           "prompt_sha256": capture_inputs(root), "worker_sha256": file_hash(__file__),
           "torch": torch.__version__, "transformers": transformers.__version__, "cuda": torch.version.cuda,
           "gpu": torch.cuda.get_device_name(0), "python": platform.python_version(),
           "dtype": "float16", "attention": "sdpa", "network": "offline", "batch_size": 1,
           "deadline": DEADLINE.isoformat(), "remote_code": False,
           "input": "checkpoint chat template, add_generation_prompt=True, no truncation"}
    cfg_path = root / "local-inputs.json"
    if cfg_path.exists():
        assert json.loads(cfg_path.read_text()) == cfg
    else:
        save(cfg_path, cfg)
    tokenizer = AutoTokenizer.from_pretrained(str(SNAPSHOT), local_files_only=True, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(str(SNAPSHOT), local_files_only=True, trust_remote_code=False,
                                                 dtype=torch.float16, attn_implementation="sdpa").to("cuda").eval()
    generation = GenerationConfig(**GENERATION)
    receipts = {}
    for n in TARGETS:
        dest = root / "runs" / f"task-{n}" / "response.json"
        prompt = root / "prompts" / f"task-{n}.json"
        if file_hash(prompt) != cfg["prompt_sha256"][str(n)]:
            raise ValueError("Frozen input changed")
        if dest.exists():
            row = json.loads(dest.read_text())
            assert row["prompt_sha256"] == file_hash(prompt) and row["generation_config"] == GENERATION
        else:
            messages = json.loads(prompt.read_text())
            keep = tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=True,
                                                 return_dict=True, return_tensors="pt").to("cuda")
            ids = keep["input_ids"][0].tolist()
            if len(ids) + GENERATION["max_new_tokens"] > model.config.max_position_embeddings:
                raise ValueError("Input exceeds the frozen model context limit")
            started = time.monotonic()
            raw, reason = [], "deadline"
            if not expired():
                with torch.inference_mode():
                    output = model.generate(**keep, generation_config=generation,
                                            stopping_criteria=StoppingCriteriaList([DeadlineStop()]))
                raw = output[0, len(ids):].tolist()
                if raw and raw[-1] in GENERATION["eos_token_id"]:
                    reason = "stop"
                elif len(raw) == GENERATION["max_new_tokens"]:
                    reason = "length"
            row = {"task": n, "utc": now(), "complete": reason in ("stop", "length"), "model": MODEL,
                   "revision": REVISION, "prompt_sha256": file_hash(prompt), "input_ids_sha256": encode_hash(ids),
                   "input_tokens": len(ids), "output_tokens": len(raw), "generated_token_ids": raw,
                   "text": tokenizer.decode(raw, skip_special_tokens=True, clean_up_tokenization_spaces=False),
                   "finish_reason": reason, "generation_config": GENERATION, "elapsed_seconds": time.monotonic() - started}
            save(dest, row)
        receipts[str(n)] = file_hash(dest)
        print(root.name, n, row["finish_reason"], row["output_tokens"], round(row["elapsed_seconds"], 2), flush=True)
    save(marker, {"utc": now(), "inputs_sha256": file_hash(cfg_path), "response_sha256": receipts,
                  "requests_to_remote_apis": 0})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    root = parser.parse_args().directory
    with (root / ".local-generation.lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        infer(root)
