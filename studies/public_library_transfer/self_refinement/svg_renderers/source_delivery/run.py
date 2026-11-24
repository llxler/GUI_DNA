"""Reassemble actual responses on their original public assets, without modifying model source."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re

from studies.public_library_transfer import core
from studies.study_io import ROOT, now, read, sha
from .. import components, run as original

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/qwen-svg-source-delivery-20261124"
MARK = re.compile(r"^[ \t]*(?:#{1,6}[ \t]*)?(?:(?://|/\*)[ \t]*)?(?:\*\*)?\x60?FILE:[ \t]*"
                  r"(?:\*\*)?\x60?([A-Za-z0-9_./-]+)\x60?(?:\*\*)?[ \t]*(?:\*/)?[ \t]*$", re.I | re.M)
FENCE = re.compile(r"^[ \t]*(?P<delimiter>\x60{3,}|~{3,})[^\r\n]*\r?\n(?P<code>.*?)(?:\r?\n)"
                   r"[ \t]*(?P=delimiter)[ \t]*\r?$", re.M | re.S)


def register():
    files = [HERE / "PROTOCOL.md", Path(__file__), Path(components.__file__), Path(original.__file__),
             Path(core.__file__), original.OUT / "registration.json", original.OUT / "seal.json"]
    hashes = {str(f.relative_to(ROOT)): sha(f) for f in files}
    evidence = {}
    for file in (original.OUT / "calls").rglob("response.json"):
        evidence[str(file.relative_to(original.OUT))] = sha(file)
    path = OUT / "registration.json"
    if not path.exists():
        if original.RESULT.exists():
            raise RuntimeError("Source delivery must be frozen before inspecting official stage scores")
        core.save(path, {"utc": now(), "sources": hashes, "responses": evidence})
    if read(path)["sources"] != hashes or read(path)["responses"] != evidence:
        raise ValueError("Source delivery protocol or responses changed")


def web_files(entries):
    kept, removed = [], []
    if not isinstance(entries, list):
        raise ValueError("Expected a public source file list")
    for item in entries:
        name, content = item["path"], item["content"]
        parts = PurePosixPath(name).parts
        if parts and parts[0] == "assets" and ".." not in parts:
            removed.append(name)
        else:
            kept.append({"path": name, "content": content})
    result = core.files_map(kept)
    if not result:
        raise ValueError("No editable application sources")
    return result, removed


def unpack(raw):
    text = components.strip_code(raw)
    try:
        parsed = json.loads(text)
    except ValueError:
        parsed = None
    if isinstance(parsed, dict):
        payload = parsed.get("files", parsed)
        entries = [{"path": k, "content": v} for k, v in payload.items()] if isinstance(payload, dict) else payload
        src, dropped = web_files(entries)
        return src, dropped, "file_map"
    marks = list(MARK.finditer(text))
    if not marks:
        return components.direct(raw), [], "original_parser"
    entries = []
    for idx, mark in enumerate(marks):
        stop = marks[idx+1].start() if idx+1 < len(marks) else len(text)
        segment = text[mark.end():stop]
        block = FENCE.search(segment)
        if block:
            content = block["code"]
        else:
            # Only the original raw-file marker grammar accepts unwrapped text.
            if not components.MARK.fullmatch(mark[0]):
                raise ValueError("Decorated filename has no complete source fence")
            content = components.strip_code(segment)
        entries.append({"path": mark[1], "content": content})
    src, dropped = web_files(entries)
    return src, dropped, "file_labels"


def library_audit():
    records = []
    for tag in ("A", "B"):
        for path in sorted((original.OUT / "calls" / tag / "build").rglob("response.json")):
            kind = path.relative_to(original.OUT / "calls" / tag / "build").parts[0]
            raw = read(path)["choices"][0]["message"].get("content") or ""
            entry = {"sample": str(path.relative_to(original.OUT)), "response_sha256": sha(path), "kind": kind}
            try:
                code = components.source(raw, kind)
                entry.update(strict_valid=True, relaxed_valid=True, code_sha256=sha256(code.encode()).hexdigest())
            except ValueError:
                entry["strict_valid"] = False
                try:
                    files, removed, _ = unpack(raw)
                    key = components.path(kind)
                    if key not in files:
                        raise ValueError("No FILE section for the specifically requested class module")
                    code = components.source(files[key], kind)
                    entry.update(relaxed_valid=True, discarded_assets=removed, code_sha256=sha256(code.encode()).hexdigest())
                except (ValueError, KeyError, TypeError) as exc:
                    entry.update(relaxed_valid=False, reason=str(exc)[:240])
            records.append(entry)
    return records


def attempt(task, number, previous, data):
    if previous["status"] in ("missing", "valid"):
        return {**previous, "delivery": "already_accepted" if previous["status"] == "valid" else "unobserved"}
    path = original.OUT / "calls" / "direct" / str(task) / str(number) / "response.json"
    source = read(path)
    raw = source["choices"][0]["message"].get("content") or ""
    try:
        src, removed, form = unpack(raw)
        destination = OUT / "direct" / str(task) / f"attempt-{number}"
        files = core.emit(components.CHART, data["starter"] | src, destination)
        public = components.observe(OUT, destination, files)
        return {"status": "valid", "page": str(destination.relative_to(ROOT)), "files": files, "public": public,
                "discarded_public_assets": removed, "response_sha256": sha(path), "delivery": form,
                "old_rejection": previous.get("reason")}
    except (ValueError, KeyError, TypeError) as exc:
        return {"status": "invalid", "reason": str(exc)[:480], "old_rejection": previous.get("reason"),
                "response_sha256": sha(path), "delivery": "still_invalid"}


def trigger(task, candidate):
    if candidate["status"] != "valid":
        return candidate["status"] != "missing"
    ob = candidate["public"]
    return bool(ob["errors"] or (task > 2 and not original.positive(ob))
                or (task == 2 and not any(ob["mounted"].values())))


def choose(task, first, second):
    if not trigger(task, first) or second is None or second["status"] != "valid":
        return 0
    if first["status"] != "valid" or original.improved(first["public"], second["public"]):
        return 1
    a, b = first["public"], second["public"]
    return int(task == 2 and not any(a["mounted"].values()) and any(b["mounted"].values()) and not b["errors"])


def direct(task, context):
    output = OUT / "direct" / str(task) / "decision.json"
    if output.is_file():
        return read(output)
    previous = read(original.OUT / "direct" / str(task) / "candidate.json")
    candidates = [attempt(task, i, value, context) for i, value in enumerate(previous["attempts"], 1)]
    use = choose(task, candidates[0], candidates[1] if len(candidates) == 2 else None)
    result = {"task": task, "strict_status": previous["final"]["status"], "strict_files": previous["final"].get("files"),
              "candidates": candidates, "chosen_attempt": use + 1, "first": candidates[0], "final": candidates[use],
              "would_request_public_repair_after_relaxed_first": trigger(task, candidates[0]),
              "old_trigger_actually_obtained_second_response": len(candidates) == 2 and candidates[1]["status"] != "missing"}
    core.save(output, result)
    return result


def generate():
    register()
    context = read(original.OUT / "public.json")
    if (OUT / "seal.json").is_file():
        return
    audit = library_audit()
    with ThreadPoolExecutor(max_workers=4) as pool:
        decisions = list(pool.map(lambda n: direct(n, context), original.TASKS))
    rows = [original.row("direct", label, d["task"], d[label]) for d in decisions for label in ("first", "final")]
    paths = [OUT / "direct" / str(n) / "decision.json" for n in original.TASKS]
    core.save(OUT / "seal.json", {"utc": now(), "registration_sha256": sha(OUT / "registration.json"), "rows": rows,
              "candidate_records_sha256": {str(p.relative_to(OUT)): sha(p) for p in paths}, "library_audit": audit})
    print("Sealed revised source delivery for all twenty original Direct targets", flush=True)


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("action", choices=("register", "generate"))
    action = cli.parse_args().action
    {"register": register, "generate": generate}[action]()
