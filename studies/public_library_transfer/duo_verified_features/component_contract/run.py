"""Repair missing host notifications and ambiguous field captions using public single checks."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
from unittest.mock import patch

from studies.public_library_transfer import browser
from studies.study_io import read, sha, now
from .. import evaluate, prepare as p

HERE = Path(__file__).resolve().parent
PARENT = p.OUT
OUT = p.ART / "duo-feature-contract-20261128"


def prepare(job):
    tag, group, name = job
    f = OUT / "features" / tag / group / (name + ".json")
    if f.exists():
        return
    prior = read(PARENT / "features" / tag / group / (name + ".json"))
    selected = prior["selected"]
    events = []
    if selected and not selected["public"]["passed"]:
        sources = [(selected["origin"],selected["source"])] if tag == "gpt5" else (
            (p.relative(file), code) for file, code in p.sources(tag, group, name))
        seen = set()
        for origin, source in sources:
            if p.checksum(source) in seen:
                continue
            changes = json.loads(subprocess.check_output(["node", str(HERE / "adapt.cjs")],
                                 input=json.dumps(dict(source=source)), text=True))
            for variant, code in {"original":source, **changes}.items():
                digest = p.checksum(code)
                if digest in seen:
                    continue
                seen.add(digest)
                if variant == "original":
                    older = PARENT / "public" / group / name / digest / "verdict.json"
                    if older.exists():
                        r = read(older)
                        assert r["report_sha256"] == sha(older.with_name("jest.json")) and r["source_sha256"] == digest
                        check = {k:r[k] for k in selected["public"]}
                    else:
                        check = p.measure(group,name,code)
                else:
                    check = p.measure(group, name, code)
                events.append(dict(check, origin=origin, variant=variant))
                if check["passed"]:
                    selected = dict(source=code, origin=origin, public=check, variant=variant)
                    break
            if selected["public"]["passed"]:
                break
    p.save(f, dict(selected=selected, events=events))


def run():
    inputs = [PARENT / "library-seal.json", PARENT / "candidates.json", p.HERE / "result.json",
              Path(p.__file__), Path(evaluate.__file__), HERE / "PROTOCOL.md", HERE / "adapt.cjs", Path(__file__)]
    reg = dict(sources={p.relative(f):sha(f) for f in inputs}, targets=sorted(p.ORIGINAL.inputs()),new_api_calls=0)
    file = OUT / "registration.json"
    if not file.exists():
        p.save(file, dict(reg,utc=now()))
    assert all(read(file)[k]==v for k,v in reg.items())
    with patch.multiple(p, OUT=OUT, HERE=HERE):
        jobs = [(t,g,n) for t in ("gpt5", *p.MODELS) for g, names in p.FEATURES.items() for n in names]
        with ThreadPoolExecutor(max_workers=5) as pool:
            list(pool.map(prepare,jobs))
        files = {p.relative(f):sha(f) for f in sorted((OUT/"features").glob("*/*/*.json"))}
        assert len(files)==len(jobs)
        p.save(OUT/"library-seal.json",dict(registration=sha(file),features=files))
        new = evaluate.candidates()
        old = read(PARENT / "candidates.json")
        for model, targets in new["candidates"].items():
            for task, row in targets.items():
                assert row["choice"] == old["candidates"][model][task]["choice"]
        evaluate.score()


if __name__ == "__main__":
    with browser.lock(OUT / "study.lock"):
        run()
