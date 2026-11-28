"""Replay genuine choices against frozen implementations before independent official grading."""
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

from studies.public_library_transfer import browser
from studies.study_io import ROOT, read, sha
from . import prepare as p


def first_choice(tag, task, group):
    domain = p.FEATURES[group]
    if tag in ("mistral", "gemma", "oss"):
        stage = p.SUITE_SOURCES[tag == "mistral"]
        seal = p.ART / stage / "duo" / tag / "a/seal.json"
        row = p.manifest(seal)["rows"][task]["self"]
        setting = row.get("setting")
        if not setting:
            return dict(status=row["status"], source=p.relative(seal), sha256=sha(seal))
        names = [setting[k] for k in ("first", "second")]
        origin = seal
    elif tag == "qwen9":
        origin = p.ART / p.SINGLE_SOURCES[0] / "seal.json"
        row, = [r for r in p.manifest(origin)["plans"] if r["task"] == task and r["model"] == p.MODELS[tag] and r["replica"] == "build-a"]
        setting = row["arms"]["self"].get("plan")
        if not setting:
            return dict(status="invalid", source=p.relative(origin), sha256=sha(origin))
        names = [setting[k] for k in ("first", "second")]
    elif tag == "deepseek-flash":
        root = p.ART / p.CALLBACK_SOURCES[0]
        folder = root / tag / "deployment" / task
        rows = folder / "rows.json"
        assert p.manifest(root / "seal.json")["sources"][str(rows.relative_to(root))] == sha(rows)
        r = read(rows)["a"]
        if r["status"] != "valid":
            return dict(status=r["status"], source=p.relative(rows), sha256=sha(rows))
        origin = root / r["file"]
        assert sha(origin) == r["files_sha256"]
        # Each imported filename is the exact identifier selected from the model's numbered catalogue.
        names = [Path(f).stem for f in read(origin) if f.startswith("atoms/")]
    else:
        assert tag == "qwen"
        origin = p.ART / "backbone-suites-20261124" / tag / "targets" / task / "self/result.json"
        response = origin.parent / "call/response.json"
        rec = read(origin)
        if rec["status"] != "valid":
            return dict(status=rec["status"], source=p.relative(origin), sha256=sha(origin))
        assert sha(response) == rec["response_sha256"]
        files = origin.parent / "files.json"
        assert sha(files) == rec["files_sha256"]
        selected = [Path(f).stem for f in read(files) if f.startswith("atoms/")]
        mapping = p.manifest(p.SINGLES.parent / "seal.json")["libraries"][tag][group]["mapping"]
        inverse = {component: n for n, component in mapping.items() if component}
        assert len(inverse) == sum(bool(v) for v in mapping.values())
        if not all(n in inverse for n in selected):
            return dict(status="missing", source=p.relative(origin), sha256=sha(origin))
        names = [inverse[n] for n in selected]
    assert len(names) <= 2 and set(names) <= set(domain)
    return dict(status="valid", names=names, source=p.relative(origin), sha256=sha(origin))


def candidates():
    libseal = p.OUT / "library-seal.json"
    paths = read(libseal)["features"]
    assert all(sha(ROOT / f) == d for f, d in paths.items())
    frozen = p.OUT / "candidates.json"
    trees, records = {}, {}
    def page(row, names, library):
        modules = [dict(id=n, source=library[n]) for n in dict.fromkeys(names) if n in library]
        slots = [m["id"] for m in modules] + ["NONE", "NONE"]
        files = p.donor.components.bundle(row["public"]["module"], dict(components=modules),
                                           dict(first=slots[0], second=slots[1]))
        from studies.study_io import digest
        key = digest(files)
        if key not in trees:
            f = p.OUT / "pages" / (key + ".json")
            p.save(f, files)
            trees[key] = sha(f)
        return dict(status="valid", files=key, missing_features=[n for n in names if n not in library])
    for tag, model in p.MODELS.items():
        records[model] = {}
        for task, row in p.ORIGINAL.inputs().items():
            group = row["group"]
            selection = first_choice(tag, task, group)
            rs = {}
            for arm, builder in (("self", tag), ("gpt5-library", "gpt5"), ("gpt5-whole", "gpt5")):
                selected = {n: read(p.OUT / "features" / builder / group / (n + ".json"))["selected"] for n in p.FEATURES[group]}
                library = {n: a["source"] for n, a in selected.items() if a}
                if arm == "gpt5-whole":
                    donorlib = p.manifest(p.donor.OUT / "libraries.json")[group]
                    library = {n: donorlib["modules"][i] for n, i in donorlib["owners"].items()}
                admitted = any(a and a["public"]["passed"] for a in selected.values())
                for suffix, names in (("", selection.get("names")), ("-names", task.split("_")), ("-fixed", p.FEATURES[group][:2])):
                    if not admitted:
                        record = dict(status="build_failed")
                    elif names is None:
                        record = dict(status=selection["status"])
                    else:
                        record = page(row, names, library)
                    rs[arm + suffix] = record
            records[model][task] = dict(choice=selection, arms=rs)
    result = dict(library_seal=sha(libseal), implementation=sha(Path(__file__)), pages=trees, candidates=records)
    p.save(frozen, result)
    return result


def score():
    seal = candidates()
    tasks = p.ORIGINAL.inputs()
    specs = defaultdict(list)
    results = {}
    for model, targets in seal["candidates"].items():
        records = results[model] = []
        for task, target in targets.items():
            for arm, rec in target["arms"].items():
                row = dict(task=task, arm=arm, **rec)
                records.append(row)
                if rec["status"] == "valid":
                    specs[task, rec["files"]].append(row)
                else:
                    row["passed"] = False if rec["status"] == "invalid" else None
    def grade(job):
        (task, key), rows = job
        source = p.OUT / "pages" / (key + ".json")
        assert sha(source) == seal["pages"][key]
        dest = p.OUT / "scores" / task / key
        verdict = p.runtime.score((tasks[task]["group"], tasks[task], read(source), dest, None))
        assert sha(dest / "jest.json") == verdict["report_sha256"]
        for row in rows:
            row.update(passed=verdict["passed"], report_sha256=verdict["report_sha256"],
                       official_cases_passed=verdict["assertion_statuses"].count("passed"))
    with ThreadPoolExecutor(max_workers=5) as pool:
        list(pool.map(grade, specs.items()))
    features = {}
    for tag in ("gpt5", *p.MODELS):
        features[tag] = {}
        for g, names in p.FEATURES.items():
            for n in names:
                row = read(p.OUT / "features" / tag / g / (n + ".json"))
                sel = row["selected"]
                features[tag][n] = dict(group=g, accepted={k:v for k,v in sel.items() if k != "source"} if sel else None,
                                         attempts=row["events"])
    choices = {m: {n: r["choice"] for n, r in rows.items()} for m,rows in seal["candidates"].items()}
    p.save(p.HERE / "result.json", dict(registration=sha(p.OUT / "registration.json"), candidate_seal=sha(p.OUT / "candidates.json"),
           choices=choices, features=features, models=results, new_api_calls=0, new_usd=0))


if __name__ == "__main__":
    with browser.lock(p.OUT / "evaluate.lock"):
        score()
