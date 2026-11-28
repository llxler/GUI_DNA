"""Regrade the same mounted pages after adapting one React Router v5 import for v6."""
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import re
from unittest.mock import patch

from experiments.webapp1k_probe import STAGING
from studies.public_library_transfer import browser
from studies.study_io import digest, now, read, sha
from ... import diagnose, prepare as p
from .. import run as original

HERE = Path(__file__).resolve().parent
OUT = p.ART / "duo-router-compatibility-20261128"
LEGACY_HOOK = re.compile(r"""^import\s*\{\s*useHistory\s*\}\s*from\s*['"]react-router-dom['"]\s*;? *$""", re.MULTILINE)
PROBE = """import React from 'react';
import { useHistory } from 'react-router-dom';
export default function Demo() {
  const history = useHistory();
  return <><output role="status">{history.location.pathname}</output>
    <button onClick={()=>history.push('/shelf/23')}>Open</button>
    <button onClick={()=>history.replace('/shelf/42')}>Rename</button>
    <button onClick={()=>history.goBack()}>Back</button>
    <button onClick={()=>history.goForward()}>Forward</button></>;
}
"""


def adapt(source):
    if len(LEGACY_HOOK.findall(source)) != 1:
        return source
    return LEGACY_HOOK.sub(lambda _: (HERE / "bridge.jsx").read_text(), source)


def run():
    old_seal = original.OUT / "seal.json"
    old_result = original.HERE / "result.json"
    required = [HERE / "PROTOCOL.md", HERE / "bridge.jsx", HERE / "navigation.test.js",
                Path(__file__), old_result, old_seal]
    register = OUT / "registration.json"
    hashes = {p.relative(f): sha(f) for f in required}
    if not register.exists():
        p.save(register, dict(sources=hashes, utc=now()))
    assert read(register)["sources"] == hashes
    with patch.object(diagnose, "OUT", OUT / "calibration"):
        probe = diagnose.probe("router", HERE / "navigation.test.js", adapt(PROBE))
    version = read(STAGING / "node_modules/react-router-dom/package.json")["version"]
    assert version.split(".")[0] == "6"
    sealed, previous = read(old_seal), read(old_result)
    rows, work = [], defaultdict(list)
    for old in previous["models"]["deepseek/deepseek-v4-flash"]:
        task, arm = old["task"], old["arm"]
        page = original.OUT / "pages" / (old["file"] + ".json")
        assert sha(page) == sealed["files"][old["file"]]
        files = read(page)
        migrated = {k: adapt(v) for k, v in files.items()}
        changed = [k for k in files if files[k] != migrated[k]]
        row = dict(old, previous_passed=old["passed"], original_file=old["file"], changed_modules=changed)
        if changed:
            key = digest(migrated)
            p.save(OUT / "pages" / (key + ".json"), migrated)
            row["file"] = key
            work[task, key].append(row)
        rows.append(row)
    p.save(OUT / "seal.json", dict(registration=sha(register), candidates=[
        {k: row[k] for k in ("task", "arm", "file", "changed_modules")} for row in rows]))
    targets = read(original.OUT / "registration.json")["targets"]
    def score(job):
        (task, key), items = job
        target = targets[task]
        page = OUT / "pages" / (key + ".json")
        folder = OUT / "scores" / task / key
        verdict = p.runtime.score((target["group"], target, read(page), folder, None))
        assert sha(folder / "jest.json") == verdict["report_sha256"]
        for row in items:
            row.update(passed=verdict["passed"], official_cases=verdict["assertion_statuses"],
                       report_sha256=verdict["report_sha256"])
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(score, work.items()))
    p.save(HERE / "result.json", dict(sources=hashes, registration=sha(register), seal=sha(OUT / "seal.json"),
            calibration=probe, router=version, new_api_calls=0, models={"deepseek/deepseek-v4-flash":rows}))


if __name__ == "__main__":
    with browser.lock(OUT / "study.lock"):
        run()
