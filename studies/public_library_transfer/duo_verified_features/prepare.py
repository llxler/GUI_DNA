"""Assemble one same-author library from public single-feature evidence."""
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from studies.public_library_transfer import browser, core
from studies.public_library_transfer.duo_donor_library import run as donor
from studies.public_library_transfer.self_refinement.duo_components.compact import runtime
from studies.study_io import ROOT, now, read, sha

HERE = Path(__file__).resolve().parent
ART = ROOT / "artifacts"
OUT = ART / "duo-verified-features-20261128"
ORIGINAL = donor.original
MODELS = ORIGINAL.MODELS
SINGLES = ART / "duo-component-replay-20261124/single-feature-diagnosis"
SINGLE_SOURCES = ("duo-independent-components-20261124", "duo-compact-components-20261124")
SUITE_SOURCES = ("suite-self-recovery-20261125", "duo-delivery-confirmation-20261125")
CALLBACK_SOURCES = ("duo-react-callbacks-20261126", "duo-prop-contract-20261126")
FEATURES = {g: sorted(read(ORIGINAL.EXTRA / "build-inputs.json")[g]) for g in ORIGINAL.GROUPS}


def relative(path):
    return str(path.relative_to(ROOT))


def checksum(source):
    return sha256(source.encode()).hexdigest()


@lru_cache(maxsize=96)
def manifest(path):
    return read(path)


def save(path, obj):
    core.save(path, obj)


def register():
    receipts = [SINGLES / "registered.json", donor.OUT / "seal.json", donor.OUT / "libraries.json",
                *(ART / n / "seal.json" for n in (*SINGLE_SOURCES, *CALLBACK_SOURCES)),
                *(p for n in SUITE_SOURCES for p in sorted((ART / n / "duo").glob("*/*/seal.json")))]
    sources = [*receipts, HERE / "PROTOCOL.md", Path(__file__), HERE / "project_view.cjs",
               ORIGINAL.EXTRA / "build-inputs.json", ORIGINAL.EXTRA / "targets.json", donor.HERE / "result.json",
               Path(runtime.__file__), Path(donor.components.bundle.__code__.co_filename)]
    fields = {"sources": {relative(p): sha(p) for p in sources}, "models": MODELS,
              "targets": sorted(ORIGINAL.inputs()), "new_api_calls": 0}
    if not (OUT / "registration.json").exists():
        save(OUT / "registration.json", dict(fields, utc=now()))
    assert all(read(OUT / "registration.json")[k] == v for k, v in fields.items())
    assert sha(donor.OUT / "libraries.json") == read(donor.OUT / "seal.json")["libraries"]
    return fields


def sources(tag, group, name):
    model = MODELS[tag]
    first = manifest(SINGLES / "registered.json")["rows"][model][name]
    if first["component"]:
        p = SINGLES / "modules" / tag / group / (name + ".js")
        assert sha(p) == first["source_sha256"]
        yield p, p.read_text()
    for stage in SINGLE_SOURCES:
        root = ART / stage
        seal = manifest(root / "seal.json")
        for rep in ("build-a", "build-b"):
            folder = root / tag / rep / group / name
            status = folder / "status.json"
            if not status.exists():
                continue
            rec = read(status)
            assert rec["model"] == model and rec["replica"] == rep and rec in seal["components"]
            for label, trial in rec["attempts"].items():
                p = folder / label / "source.json"
                if p.exists():
                    assert sha(p) == trial["source_sha256"] == seal["files"][str(p.relative_to(root))]
                    yield p, read(p)["source"]
    for stage in SUITE_SOURCES:
        for rep in ("a", "b"):
            root = ART / stage / "duo" / tag / rep
            sealfile = root / "seal.json"
            if not sealfile.exists():
                continue
            seal = manifest(sealfile)
            assert seal["case"] == ["duo", tag, rep]
            component = seal["builds"][group]["components"].get(name, {})
            if component.get("source"):
                p = ROOT / component["source"]
                assert p.is_relative_to(root / "build" / group / name) and sha(p) == component["source_sha256"]
                yield p, read(p)["source"]
    for stage in CALLBACK_SOURCES:
        root = ART / stage
        seal = manifest(root / "seal.json")
        for rep in ("a", "b"):
            p = root / tag / rep / group / name / "component.json"
            if p.exists():
                assert sha(p) == seal["sources"][str(p.relative_to(root))]
                rec = read(p)
                if rec.get("source"):
                    yield p, rec["source"]


def measure(group, name, source):
    key = checksum(source)
    folder = OUT / "public" / group / name / key
    with browser.lock(folder / "measure.lock"):
        _, verdict = runtime.single((folder, group, name, source))
    assert verdict["source_sha256"] == key and verdict["report_sha256"] == sha(folder / "jest.json")
    return {k: verdict[k] for k in ("passed", "report_sha256", "test_sha256", "source_sha256")}


def prepare_feature(job):
    tag, group, name = job
    path = OUT / "features" / tag / group / (name + ".json")
    if path.exists():
        return read(path)
    events, seen = [], set()
    selected = None
    if tag == "gpt5":
        lib = manifest(donor.OUT / "libraries.json")[group]
        owner = lib["owners"].get(name)
        if owner:
            raw = lib["modules"][owner]
            assert owner not in ORIGINAL.inputs()
            full = measure(group, name, raw)
            events.append(dict(full, variant="whole", donor=owner))
            selected = dict(source=raw, origin=owner, public=full)
            variants = json.loads(subprocess.check_output(["node", str(HERE / "project_view.cjs")], input=raw, text=True))
            for v in variants:
                code = v["source"]
                if checksum(code) in seen:
                    continue
                seen.add(checksum(code))
                verdict = measure(group, name, code)
                events.append(dict(verdict, variant="subtree", size=v["size"], start=v["start"], donor=owner))
                if verdict["passed"]:
                    selected = dict(source=code, origin=owner, public=verdict)
                    break
    else:
        for origin, code in sources(tag, group, name):
            if checksum(code) in seen:
                continue
            seen.add(checksum(code))
            verdict = measure(group, name, code)
            events.append(dict(verdict, file=relative(origin), file_sha256=sha(origin)))
            if selected is None or verdict["passed"]:
                selected = dict(source=code, origin=relative(origin), public=verdict)
            if verdict["passed"]:
                break
    result = dict(selected=selected, events=events)
    save(path, result)
    return result


def build():
    register()
    jobs = [(tag, g, n) for g, names in FEATURES.items() for n in names for tag in ("gpt5", *MODELS)]
    with ThreadPoolExecutor(max_workers=5) as pool:
        list(pool.map(prepare_feature, jobs))
    files = {relative(p): sha(p) for p in sorted((OUT / "features").glob("*/*/*.json"))}
    assert len(files) == len(jobs)
    save(OUT / "library-seal.json", dict(registration=sha(OUT / "registration.json"), features=files))


if __name__ == "__main__":
    with browser.lock(OUT / "prepare.lock"):
        build()
