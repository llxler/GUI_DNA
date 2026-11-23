"""Schedule frozen one-sample inference on one GPU with one shared read-only model."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
from pathlib import Path
import threading
import time
from unittest.mock import patch

from . import local_planner as worker

ROOT = Path(__file__).resolve().parents[2]
FULL = ROOT / "artifacts/svg-chart-full-local-20261123"
TABLE = ROOT / "artifacts/public-controller-table-20261123"
REPS = [TABLE / rep / "planning" for rep in ("rep-1", "rep-2")]


class Gate:
    def __init__(self, model):
        self.weights = model
        self.config = model.config
        self.condition = threading.Condition()
        self.executing = False
        self.queue = []
        self.table_workers = set()
        self.local = threading.local()

    @contextmanager
    def candidate_source(self, root):
        self.local.root = root
        with self.condition:
            if root in REPS:
                self.table_workers.add(root)
            self.condition.notify_all()
        try:
            yield
        finally:
            with self.condition:
                self.table_workers.discard(root)
                self.condition.notify_all()

    def to(self, device):
        assert device == "cuda"
        return self

    def eval(self):
        return self

    def generate(self, **kwargs):
        root = self.local.root
        entry = (root, object())
        with self.condition:
            self.queue.append(entry)
            while True:
                if worker.expired():
                    self.queue.remove(entry)
                    self.condition.notify_all()
                    return kwargs["input_ids"]
                eligible = [r for r in self.queue if not self.table_workers or r[0] in self.table_workers]
                if not self.executing and eligible and eligible[0] == entry:
                    self.executing = True
                    self.queue.remove(entry)
                    break
                self.condition.wait(timeout=.5)
        try:
            return self.weights.generate(**kwargs)
        finally:
            with self.condition:
                self.executing = False
                self.condition.notify_all()


def run(root, gate):
    with (root / ".local-generation.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if (root / "local-generation.json").exists():
            return
        record = {"utc": worker.now(), "worker_sha256": worker.file_hash(worker.__file__),
                  "scheduler_sha256": worker.file_hash(__file__), "inference_batch_size": 1,
                  "device": "cuda", "concurrent_gpu_generations": 1, "uses_shared_weights": True,
                  "queue": "FIFO among participating table replications; pause full-package requests while admitted table workers remain",
                  "deadline": worker.DEADLINE.isoformat()}
        marker = root / "scheduler-ready.json"
        if marker.exists():
            record["admission_sha256"] = worker.file_hash(marker)
        worker.save(root / "scheduler-admission.json", record)
        try:
            with gate.candidate_source(root):
                worker.infer(root)
        except Exception as exc:
            worker.save(root / "scheduler-error.json", {"utc": worker.now(), "error": f"{type(exc).__name__}: {exc}"})
            raise


def main():
    import torch
    from transformers import AutoModelForCausalLM

    assert (ROOT / "artifacts/svg-chart-compact-local-20261123/local-generation.json").exists()
    assert (ROOT / "artifacts/compatible-table-local-plans-20261123/local-generation.json").exists()
    model = AutoModelForCausalLM.from_pretrained(str(worker.SNAPSHOT), local_files_only=True, trust_remote_code=False,
                                                 dtype=torch.float16, attn_implementation="sdpa").to("cuda").eval()
    gate = Gate(model)
    def cached(path, **settings):
        assert path == str(worker.SNAPSHOT) and settings == {
            "local_files_only": True, "trust_remote_code": False, "dtype": torch.float16, "attn_implementation": "sdpa"}
        return gate
    jobs = {}
    # The frozen inference function remains responsible for every prompt, token, decode and receipt.
    # Replace only its model factory with the identical already-loaded instance and the serialization gate.
    with patch.object(AutoModelForCausalLM, "from_pretrained", side_effect=cached), ThreadPoolExecutor(max_workers=3) as pool:
        while not worker.expired() or any(not j.done() for j in jobs.values()):
            for root in [*REPS, FULL]:
                ready = root == FULL or (root / "scheduler-ready.json").is_file()
                if ready and root not in jobs and not worker.expired():
                    assert all((root / "prompts" / f"task-{n}.json").is_file() for n in worker.TARGETS)
                    jobs[root] = pool.submit(run, root, gate)
            if len(jobs) == 3 and all(j.done() for j in jobs.values()):
                break
            time.sleep(.5)
        for root, job in jobs.items():
            try:
                job.result()
            except Exception as error:
                print("infrastructure error", root, type(error).__name__, str(error)[:250], flush=True)


if __name__ == "__main__":
    main()
