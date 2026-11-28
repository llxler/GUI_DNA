"""Expose a sealed page under the entry point imported by its unchanged official suite."""

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import re

from studies.public_library_transfer import browser
from studies.study_io import digest, now, read, sha
from ... import prepare as p
from .. import run as first
from ..router import run as router

HERE = Path(__file__).resolve().parent
OUT = p.ART / "duo-official-entries-20261128"
IMPORT = re.compile(r"""\bfrom\s+['"]\./([a-zA-Z_$][\w$]*)['"]""")
MODEL = "deepseek/deepseek-v4-flash"


def entry_name(test):
    names = set(IMPORT.findall(test))
    if len(names) != 1:
        raise ValueError(f"Expected one local component import, found {sorted(names)}")
    return names.pop()


def run():
    first_result, router_result = (
        first.HERE / "result.json",
        router.HERE / "result.json",
    )
    original = read(first_result)
    required = (HERE / "PROTOCOL.md", Path(__file__), first_result, router_result)
    sources = {p.relative(path): sha(path) for path in required}
    targets = read(first.OUT / "registration.json")["targets"]
    entries = {}
    for task, target in targets.items():
        spec = p.ROOT / target["test"]
        assert (
            sha(spec) == target["test_sha256"] == original["test_files"][task]["sha256"]
        )
        entries[task] = entry_name(spec.read_text())
    register = OUT / "registration.json"
    if not register.exists():
        p.save(register, dict(sources=sources, entries=entries, utc=now()))
    assert read(register)["sources"] == sources and read(register)["entries"] == entries
    jobs = defaultdict(list)
    phases = {}
    for phase, result in (("initial", original), ("router", read(router_result))):
        phase_rows = phases[phase] = []
        for old in result["models"][MODEL]:
            task, key = old["task"], old["file"]
            row = dict(old, source_file=key, previous_report=old["report_sha256"])
            root = router.OUT if old.get("changed_modules") else first.OUT
            page = root / "pages" / (key + ".json")
            files = read(page)
            assert digest(files) == key
            if task != entries[task]:
                alias = entries[task] + ".js"
                assert alias not in files and task + ".js" in files
                files[alias] = "export {default} from './" + task + "';\n"
                key = digest(files)
                p.save(OUT / "pages" / (key + ".json"), files)
                row["file"] = key
                jobs[task, key].append(row)
            phase_rows.append(row)
    seal = OUT / "seal.json"
    p.save(
        seal,
        dict(
            registration=sha(register),
            candidates={
                phase: [
                    {k: r[k] for k in ("arm", "task", "source_file", "file")}
                    for r in rows
                ]
                for phase, rows in phases.items()
            },
        ),
    )

    def score(job):
        (task, key), rows = job
        target = targets[task]
        folder = OUT / "scores" / task / key
        files = read(OUT / "pages" / (key + ".json"))
        assert digest(files) == key
        verdict = p.runtime.score((target["group"], target, files, folder, None))
        assert sha(folder / "jest.json") == verdict["report_sha256"]
        for row in rows:
            row.update(
                passed=verdict["passed"],
                official_cases=verdict["assertion_statuses"],
                report_sha256=verdict["report_sha256"],
            )

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(score, jobs.items()))
    assert all(
        len(r["official_cases"]) == 4
        and set(r["official_cases"]) <= {"passed", "failed"}
        and r["passed"] == all(v == "passed" for v in r["official_cases"])
        for rows in phases.values()
        for r in rows
    )
    p.save(
        HERE / "result.json",
        dict(
            sources=sources,
            registration=sha(register),
            seal=sha(seal),
            model=MODEL,
            entries=entries,
            test_files=original["test_files"],
            phases=phases,
            new_api_calls=0,
        ),
    )


if __name__ == "__main__":
    with browser.lock(OUT / "study.lock"):
        run()
