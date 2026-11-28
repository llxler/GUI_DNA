"""Regenerate the three library pages from the very same plan, using local sealed sources."""

import argparse

from studies.study_io import ROOT, dump, read, sha
from ..component_contracts import report as history, run as previous
from . import generate as gen

RESULT = gen.HERE / "page-lineage.json"


def verify():
    current = read(gen.CANDIDATES)
    seal = read(gen.OUT / "seal.json")
    assert current["seal"] == sha(gen.OUT / "seal.json") and current["rows"] == seal["rows"]
    donor = read(gen.OUT / "build/gpt5/library.json")
    libs = {tag: read(p) for tag, p in gen.MODEL_LIBRARIES.items()}
    old = read(history.STAGES[-1][1])
    old["holdout"]["deepseek-flash"] = read(history.FLASH / "candidates.json")["rows"]
    old_verified = {}
    for tag, lib in libs.items():
        counts = {}
        for batch in ("development", "holdout"):
            successes = 0
            for site, arms in old[batch][tag].items():
                root = (
                    gen.native.OUT / "plans"
                    if batch == "development"
                    else (
                        gen.native.OUT.parent / "webgen-flash-transfer-20261127" / "plans"
                        if tag == "deepseek-flash"
                        else previous.OUT / "plans"
                    )
                )
                plan = read(root / tag / site / "record.json")
                if arms["self"]["status"] == "valid":
                    assert plan["status"] == "valid"
                    assert (
                        gen.self_page(tag, plan["config"], lib).encode()
                        == (ROOT / arms["self"]["file"]).read_bytes()
                    )
                    successes += 1
            counts[batch] = successes
        old_verified[tag] = counts
    checks = {}
    for tag, sites in current["rows"].items():
        checks[tag] = {}
        for site, arms in sites.items():
            folder = gen.OUT / "jobs" / tag / site
            for v in arms.values():
                if v["status"] == "valid":
                    assert sha(ROOT / v["file"]) == v["sha256"]
            plan = read(folder / "plan/record.json")
            plan_path = folder / "plan/record.json"
            assert sha(plan_path) == current["plans"][str(plan_path.relative_to(gen.OUT))]
            actions = {}
            for kind in ("direct", "plan"):
                record = read(folder / kind / "record.json")
                if record["status"] != "valid":
                    continue
                for attempt in (0, 1):
                    trial = folder / kind / str(attempt)
                    sources = sorted(trial.glob("*/settled.json"))
                    if not sources:
                        continue
                    reply = sources[-1].with_name("response.json")
                    assert sha(reply) == read(sources[-1])["response_sha256"]
                    message = read(reply)["choices"][0]["message"].get("content") or ""
                    try:
                        if kind == "direct":
                            valid = (
                                gen.direct_document(message).encode() == (ROOT / record["file"]).read_bytes()
                            )
                        else:
                            valid = gen.content.compile_plan(gen.gen.parse(message)) == record["config"]
                    except gen.gen.ERRORS:
                        valid = False
                    if valid:
                        actions[kind] = dict(attempt=attempt, raw_sha256=sha(reply))
                        break
                assert kind in actions
            same = []
            if plan["status"] == "valid":
                config = plan["config"]
                for a in ("human", "gpt5-library", "self"):
                    if arms[a]["status"] != "valid":
                        continue
                    html = (
                        gen.self_page(tag, config, libs[tag])
                        if a == "self"
                        else gen.pages.page(config, "human" if a == "human" else donor["parts"])
                    )
                    assert html.encode() == (ROOT / arms[a]["file"]).read_bytes()
                    same.append(a)
            checks[tag][site] = dict(
                same_plan=same,
                plan_sha256=sha(plan_path),
                raw_sources=actions,
                direct_closed=arms["direct"].get("closed_document"),
            )
    return dict(
        candidates=sha(gen.CANDIDATES),
        old_self_reproduced=old_verified,
        sites=checks,
        donor_public=donor["final"]["checks"],
        source_sha256=seal["sources"],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = verify()
    if args.write and not RESULT.exists():
        dump(RESULT, result)
    assert read(RESULT) == result
    print("Verified previous Self pages, source replies and all new renderer bindings.")
