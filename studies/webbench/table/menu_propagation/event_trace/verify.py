"""Verify the request pair, the author edits, and the provider receipts without another API call."""

from argparse import ArgumentParser
import hashlib
import json
from pathlib import Path

from studies.study_io import ROOT, dump, read, sha
from ..author_repair import report

HERE = Path(__file__).resolve().parent
RESULT = HERE / "result.json"
EVIDENCE = HERE / "build-comparison.json"


def reconstruct():
    output = {}
    for rep in "ab":
        bodies = []
        experiments = {}
        for name, ledger, source in [
            ("final-outcome", "table-menu-author-repair", report.RESULT),
            ("event-trace", "table-menu-event-trace", RESULT),
        ]:
            base = ROOT / "artifacts" / (ledger + "-20261128")
            record = read(source)
            reg = base / "registration.json"
            assert sha(reg) == record["registration"]
            build = base / rep / "builder.json"
            assert sha(build) == record["libraries"][rep]["reply"]
            receipts = list((base / rep / "request").glob("*/settled.json"))
            if not receipts:
                assert read(build)["status"] == "missing"
                experiments[name] = dict(
                    admission=record["libraries"][rep]["status"], edit=read(build), source=sha(source)
                )
                continue
            (settled,) = receipts
            request = settled.parent / "request.json"
            response = settled.parent / "response.json"
            assert sha(response) == read(settled)["response_sha256"]
            payload = read(response)
            body = read(request)["body"]
            assert body["model"] == "openai/gpt-5"
            bodies.append(body)
            experiments[name] = dict(
                seed=body["seed"],
                provider=payload.get("provider"),
                cost_usd=payload["usage"]["cost"],
                request_sha256=sha(request),
                response_sha256=sha(response),
                edit=read(build),
                admission=record["libraries"][rep]["status"],
                source=sha(source),
            )
        if len(bodies) == 2:
            a, b = bodies
            assert dict(b, messages=b["messages"][:-1]) == a
            prompt = b["messages"][-1]
            assert (
                prompt["role"] == "user" and "document" in prompt["content"] and "table" in prompt["content"]
            )
            experiments["added_observation"] = prompt
            experiments["shared_request_sha256"] = hashlib.sha256(
                json.dumps(a, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()
        output[rep] = experiments
    return output


def portable():
    observations = read(EVIDENCE)
    pairs = report.reconstruct(), report.reconstruct(RESULT)
    for rep, group in observations.items():
        for i, (name, path) in enumerate([("final-outcome", report.RESULT), ("event-trace", RESULT)]):
            phase = group[name]
            assert phase["source"] == sha(path)
            assert (rep in pairs[i]) == (phase["admission"] == "valid")
        if "added_observation" in group:
            assert group["final-outcome"]["seed"] == group["event-trace"]["seed"]
    return pairs


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--local-receipts", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.write or args.local_receipts:
        values = reconstruct()
        if args.write and not EVIDENCE.exists():
            dump(EVIDENCE, values)
        assert read(EVIDENCE) == values
    for condition, group in zip(("outcome", "trace"), portable()):
        print(
            condition,
            {
                rep: {m: len(c["passed"]) for m, c in measures["planned"].items()}
                for rep, measures in group.items()
            },
        )
