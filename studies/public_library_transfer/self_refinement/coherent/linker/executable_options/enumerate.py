"""Score every deterministic option combination after both target sets are sealed."""

from concurrent.futures import ThreadPoolExecutor
from itertools import product

from studies.public_library_transfer import browser, core
from studies.study_io import read, sha

from . import options, run


def main():
    run.verify()
    root = run.BASE
    browser.OUT = root
    data, contract = read(root / "public.json"), read(root / "browser.json")
    assert contract == browser.verify_contract("table")
    for group in run.GROUPS:
        for name, fingerprint in read(root / group / "seal.json").items():
            assert sha(root / name) == fingerprint
    jobs = []
    for group in run.GROUPS:
        base = root / group
        pkg = read(run.linker.OUT / "table" / group / "build/package.json")
        built = read(base / "build/status.json")
        assert sha(base / "build/package.json") == built["package_sha256"]
        chosen = read(base / "build/package.json")["options"]
        for bits in product((0, 1), repeat=len(chosen)):
            setting = "".join(str(x) for x in bits) or "original"
            path = base / "enumeration" / setting
            selected = [o["id"] for o, bit in zip(chosen, bits, strict=True) if bit]
            files = options.emit(data, pkg, chosen, selected, path)
            if not any(bits):
                assert files == built["files"]
            jobs.extend((group, setting, selected, n, path, files) for n in run.native.TASKS)

    def score(job):
        group, setting, selected, n, page, files = job
        report = browser.run_one(root, "table", n, page, files, contract)
        return {"group": group, "setting": setting, "alternatives": selected, "task": n, "passed": report["passed"],
                "files_digest": report["files_digest"], "report_sha256": report["report_sha256"]}

    with ThreadPoolExecutor(max_workers=4) as workers:
        values = list(workers.map(score, jobs))
    core.save(root / "enumeration.json", values)
    print("Verified configurations by target:", len(values))


if __name__ == "__main__":
    main()
