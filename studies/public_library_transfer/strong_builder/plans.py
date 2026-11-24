"""Describe the actual frozen plan values and the tasks on which they were returned."""

import argparse
from collections import Counter, defaultdict
from pathlib import Path

from studies.public_library_transfer import core
from studies.study_io import ROOT, digest, read, sha


HERE = Path(__file__).resolve().parent
PRIMARY = ROOT / "artifacts/strong-builder-20261124"
NATIVE = ROOT / "artifacts/strong-builder-native-20261124"
RESULT = HERE / "plans.json"
USAGE = HERE / "delivery.json"


def reconstruct():
    sources = read(PRIMARY / "sources.json")
    base = read(PRIMARY / "seal.json")["rows"]
    trials = {
        "text": [r for r in base if r["arm"] == "selected"],
        "native": read(NATIVE / "seal.json")["candidates"],
    }
    data = {}
    for replica, source in sources.items():
        package = ROOT / source["folder"] / "package.json"
        assert sha(package) == source["package_sha256"]
        first = read(package)["examples"][0]["plan"]
        arms = {}
        for label, rows in trials.items():
            groups = defaultdict(list)
            plans = {}
            invalid = []
            missing = []
            for row in sorted(
                (r for r in rows if r["replica"] == replica), key=lambda r: r["task"]
            ):
                if row["status"] == "valid":
                    code = digest(row["plan"])
                    plans[code] = row["plan"]
                    groups[code].append(row["task"])
                elif row["status"] == "invalid":
                    invalid.append(row["task"])
                elif row["status"] == "missing":
                    missing.append(row["task"])
                else:
                    raise ValueError(row["status"])
            arms[label] = {
                "settings": [{"plan": plans[k], "tasks": v} for k, v in groups.items()],
                "invalid": invalid,
                "missing": missing,
            }
        data[replica] = {
            "package_sha256": source["package_sha256"],
            "first": first,
            "arms": arms,
        }
    return {
        "project": "table",
        "deployer": "qwen/qwen3.5-9b",
        "builder": "gpt-6-astra",
        "text_seal_sha256": sha(PRIMARY / "seal.json"),
        "native_seal_sha256": sha(NATIVE / "seal.json"),
        "sources": data,
    }


def delivery():
    results = {}
    for label, root in [("text", PRIMARY), ("native", NATIVE)]:
        groups = {}
        for replica in ("replica-1", "replica-2"):
            pattern = (
                "selected/*/call/response.json"
                if label == "text"
                else "task-*/call/response.json"
            )
            paths = sorted((root / replica).glob(pattern))
            replies = [read(path) for path in paths]
            usage = [d["usage"] for d in replies]
            groups[replica] = {
                "observed_responses": len(replies),
                "providers": dict(Counter(d["provider"] for d in replies)),
                "finish_reasons": dict(
                    Counter(d["choices"][0]["finish_reason"] for d in replies)
                ),
                "prompt_tokens": sum(u["prompt_tokens"] for u in usage),
                "completion_tokens": sum(u["completion_tokens"] for u in usage),
                "reasoning_tokens": sum(
                    u["completion_tokens_details"]["reasoning_tokens"] for u in usage
                ),
                "output_limit_empty_tasks": sorted(
                    int(path.parents[1].name.removeprefix("task-"))
                    for path, reply in zip(paths, replies)
                    if reply["choices"][0]["finish_reason"] == "length"
                    and not reply["choices"][0]["message"].get("content")
                ),
            }
        results[label] = groups
    return {
        "text_result_sha256": sha(HERE / "result.json"),
        "native_result_sha256": sha(HERE / "native/result.json"),
        "provider_receipts": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    if parser.parse_args().write:
        core.save(RESULT, reconstruct())
        core.save(USAGE, delivery())
    else:
        assert reconstruct() == read(RESULT) and delivery() == read(USAGE)
