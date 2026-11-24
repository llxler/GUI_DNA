"""Enumerate small, already admitted Self libraries over the official current tasks."""

import argparse
import itertools
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, digest, read, sha

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/self-capacity-20261124"
RESULT = ROOT / "studies/results/self-capacity-20261124.json"
BATCHES = ("matrix", "extension", "form")


def freeze():
    sources = [Path(__file__), HERE / "PROTOCOL.md", Path(core.__file__), Path(browser.__file__)]
    packages = []
    for batch in BATCHES:
        source = ROOT / "artifacts" / f"backbone-{batch}-20261124"
        reg = read(source / "registered.json")
        for path in sorted(source.glob("*/*/build/package.json")):
            tag, project = path.relative_to(source).parts[:2]
            package = read(path)
            fields = package["plan_schema"]["properties"]
            options = [item.get("enum", [False, True]) for item in fields.values()]
            settings = list(itertools.product(*options))
            if len(settings) > 32:
                continue
            status = read(source / tag / "seal.json")["builds"][project]
            assert status["status"] == "valid" and status["package_sha256"] == sha(path)
            contract = browser.verify_contract(project)
            assert contract == read(source / "inputs" / project / "browser.json")
            assert read(source / "inputs" / project / "public.json") == read(
                core.OUT / "inputs" / f"{project}.json"
            )
            sources.extend(
                [
                    path,
                    source / tag / "seal.json",
                    source / "inputs" / project / "browser.json",
                    source / "inputs" / project / "public.json",
                    core.OUT / "inputs" / f"{project}.json",
                ]
            )
            pages = []
            for i, values in enumerate(settings):
                plan = dict(zip(fields, values, strict=True))
                page = OUT / "pages" / project / tag / str(i)
                files = core.materialize(project, package, plan, page)
                pages.append(
                    dict(
                        plan=plan,
                        page=str(page.relative_to(ROOT)),
                        files=files,
                        first=plan == package["examples"][0]["plan"],
                    )
                )
            assert sum(p["first"] for p in pages) == 1
            packages.append(
                dict(
                    project=project,
                    model=reg["models"][tag][0],
                    source=str(source.relative_to(ROOT)),
                    contract_sha256=digest(contract),
                    pages=pages,
                )
            )
    assert sorted((p["project"], len(p["pages"])) for p in packages) == [("form", 32), ("table", 2)]
    core.save(
        OUT / "seal.json",
        dict(
            tasks=list(browser.TASKS),
            sources={str(f.relative_to(ROOT)): sha(f) for f in sources},
            packages=packages,
        ),
    )


def evaluate(package):
    project = package["project"]
    contract = browser.verify_contract(project)
    assert digest(contract) == package["contract_sha256"]
    source = ROOT / package["source"]

    def replay(job):
        page, task = job
        files = page["files"]
        key = digest(files)
        path = source / "browser/scores" / project / f"task-{task}" / key / "score.json"
        browser.verify_page(ROOT / page["page"], files, project)
        expected = dict(project=project, task=task, files_digest=key, contract_digest=digest(contract))
        if path.is_file():
            receipt = browser.verify_receipt(source, path, expected)
        else:
            receipt = browser.run_one(OUT, project, task, ROOT / page["page"], files, contract)
        return dict(passed=receipt["passed"], report_sha256=receipt["report_sha256"])

    rows = []
    tasks = list(browser.TASKS)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for page in package["pages"]:
            receipts = dict(zip(tasks, pool.map(replay, ((page, t) for t in tasks)), strict=True))
            rows.append(
                dict(
                    plan=page["plan"],
                    first=page["first"],
                    files_sha256=digest(page["files"]),
                    tasks=receipts,
                    passed=[t for t in tasks if receipts[t]["passed"]],
                )
            )
    possible = sorted({t for r in rows for t in r["passed"]})
    return dict(
        model=package["model"],
        project=project,
        settings=rows,
        possible=possible,
        best_fixed=max(len(r["passed"]) for r in rows),
        first=next(r["passed"] for r in rows if r["first"]),
        contract_sha256=package["contract_sha256"],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "score", "check"))
    action = parser.parse_args().action
    if action == "check":
        data = read(RESULT)
        for p in data["libraries"]:
            assert p["possible"] == sorted(
                {int(t) for r in p["settings"] for t, v in r["tasks"].items() if v["passed"]}
            )
            assert p["best_fixed"] == max(len(r["passed"]) for r in p["settings"])
            for row in p["settings"]:
                assert sorted(map(int, row["tasks"])) == list(range(1, 21))
                assert row["passed"] == [int(t) for t, v in row["tasks"].items() if v["passed"]]
                assert all(len(v["report_sha256"]) == 64 for v in row["tasks"].values())
        return
    browser.OUT = OUT
    if action == "freeze":
        freeze()
        return
    seal = read(OUT / "seal.json")
    assert all(sha(ROOT / f) == value for f, value in seal["sources"].items())
    libraries = []
    for p in sorted(seal["packages"], key=lambda v: len(v["pages"])):
        result = evaluate(p)
        core.save(OUT / (p["project"] + ".json"), result)
        print(p["project"], result["possible"], flush=True)
        libraries.append(result)
    core.save(
        RESULT, dict(post_hoc=True, api_calls=0, seal_sha256=sha(OUT / "seal.json"), libraries=libraries)
    )


if __name__ == "__main__":
    main()
