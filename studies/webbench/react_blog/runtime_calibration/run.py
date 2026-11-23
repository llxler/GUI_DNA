"""Calibrate all twenty current React blog files against three fixed pages."""
import argparse
import re
import shutil
import socket
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from studies.study_io import ROOT, UPSTREAM, cases_by_file, dump, now, read, sha
from studies.table_library_sources.run import file_hashes, verify
from studies.todomvc_dna.evaluate import browser_env

HERE = Path(__file__).resolve().parent
OUT = ROOT / "artifacts/react-blog-calibration-20261123"
PROJECT = UPSTREAM / "projects/react"
UTIL = UPSTREAM / "libraries/test-util"
WORK = OUT / "runtime"
APP = WORK / "projects/react"
LOCK = UPSTREAM / "common/config/rush/pnpm-lock.yaml"
PUBLIC = ROOT / "studies/results/react-blog-calibration-20261123.json"
PAGES = {"reference": "src", "starter": "src-init", "blank": "blank"}
TASKS = tuple(f"task-{n}" for n in range(1, 21))
REVISION = "7b31ca2b786eef120dd49ce63dd03d0c0006046d"


def files(folder):
    return [p for p in folder.rglob("*") if p.is_file()]


def freeze():
    marker = OUT / "freeze.json"
    if marker.exists():
        verify(read(marker)["inputs_sha256"])
        return
    assert subprocess.check_output(["git", "-C", UPSTREAM, "rev-parse", "HEAD"], text=True).strip() == REVISION
    WORK.mkdir(parents=True, exist_ok=True)
    APP.mkdir(parents=True, exist_ok=True)
    generated = []
    for name in ["src", "src-init", "test"]:
        shutil.copytree(PROJECT / name, APP / name, dirs_exist_ok=True)
        for path in files(PROJECT / name):
            assert sha(path) == sha(APP / path.relative_to(PROJECT))
    for name in ["package.json", "vite.config.ts", "playwright.config.js", "tsconfig.json", "typings.d.ts"]:
        shutil.copyfile(PROJECT / name, APP / name)
    util = WORK / "libraries/test-util"
    shutil.copytree(UTIL, util, dirs_exist_ok=True)
    (APP / "blank").mkdir(exist_ok=True)
    (APP / "blank/index.html").write_text("<!doctype html><html><head></head><body></body></html>\n")
    (APP / "calibration.config.cjs").write_text(
        "const config = require('./playwright.config.js');\n"
        "delete config.webServer;\n"
        "config.use.baseURL = process.env.CALIBRATION_URL;\n"
        "config.reporter = [['json', { outputFile: process.env.REPORT_FILE }]];\n"
        "module.exports = config;\n"
    )
    upstream_lock = LOCK.read_text()
    header, content = upstream_lock.split("\nimporters:\n", 1)
    importers, packages = content.split("\npackages:\n", 1)
    chosen = []
    for name in ["projects/react", "libraries/test-util"]:
        match = re.search(r"(?ms)^  \.\./\.\./" + name + r":\n.*?(?=^  \S|\Z)", importers)
        assert match, name
        chosen.append(match[0].replace("  ../../", "  ", 1).rstrip())
    (WORK / "pnpm-lock.yaml").write_text(
        header + "\nimporters:\n\n  .: {}\n\n" + "\n\n".join(chosen) + "\n\npackages:\n" + packages)
    (WORK / "pnpm-workspace.yaml").write_text("packages:\n  - 'projects/*'\n  - 'libraries/*'\n")
    (WORK / ".npmrc").write_text("auto-install-peers=false\n")
    dump(WORK / "package.json", {"name": "gui-dna-react-calibration", "private": True, "packageManager": "pnpm@8.15.8"})
    generated = files(WORK)
    assert all((APP / "test" / (task + ".spec.js")).is_file() for task in TASKS)
    dump(marker, {"utc": now(), "revision": REVISION, "tasks": TASKS, "pages": PAGES,
                  "inputs_sha256": file_hashes([HERE / "run.py", HERE / "PROTOCOL.md", LOCK, PROJECT / "tasks.jsonl",
                                                *generated, *files(PROJECT), *files(UTIL)])})


def setup():
    freeze()
    subprocess.run(["corepack", "pnpm@8.15.8", "install", "--frozen-lockfile", "--ignore-scripts"],
                   cwd=WORK, check=True, env=browser_env())
    for name, version in {"react": "18.3.1", "react-dom": "18.3.1", "vite": "7.1.5",
                          "@vitejs/plugin-react": "5.0.2", "@playwright/test": "1.57.0"}.items():
        assert read(APP / "node_modules" / name / "package.json")["version"] == version


@contextmanager
def server(name):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    env = browser_env() | {"EVAL_PROJECT_ROOT": PAGES[name], "EVAL_PROJECT_PORT": str(port), "EVAL": "1"}
    command = ["node", "node_modules/vite/bin/vite.js", "--config", "vite.config.ts", "--strictPort",
               "--port", str(port), "--host", "127.0.0.1"]
    with (OUT / (name + "-server.log")).open("a") as log:
        proc = subprocess.Popen(command, cwd=APP, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            for _ in range(100):
                if proc.poll() is not None:
                    raise RuntimeError(f"{name} server exited. See {log.name}")
                try:
                    with urlopen(url, timeout=1) as response:
                        if response.status == 200:
                            break
                except (OSError, URLError):
                    time.sleep(.2)
            else:
                raise RuntimeError(f"{name} server did not become ready")
            yield url
        finally:
            if proc.poll() is None:
                proc.terminate()
            proc.wait(timeout=15)


def classify(report, task):
    errors = [e for e in report.get("errors", []) if "maximum allowed failures" not in e.get("message", "")]
    assert not errors, errors
    cases = cases_by_file(report)
    assert set(cases) == {task}
    rows = cases[task]
    passed = bool(rows) and all(r["passed"] for r in rows)
    if not passed:
        assert any(s in ("failed", "timedOut") for r in rows for s in r["statuses"]), (task, rows)
    return passed


def evaluate(name):
    with server(name) as url:
        for task in TASKS:
            folder = OUT / "runs" / name / task
            report = folder / "report.json"
            marker = folder / "outcome.json"
            if marker.exists():
                assert read(marker)["report_sha256"] == sha(report)
                continue
            folder.mkdir(parents=True, exist_ok=True)
            env = browser_env() | {"CALIBRATION_URL": url, "IS_EVAL_PRODUCTION": "1", "CI": "1",
                                   "REPORT_FILE": str(report), "EVAL_PROJECT_ROOT": str(APP / PAGES[name])}
            command = [str(APP / "node_modules/.bin/playwright"), "test", "--config=calibration.config.cjs",
                       "--workers=1", "--retries=0", "--max-failures=1", "--output", str(folder / "output"),
                       f"test/{task}.spec.js"]
            with (folder / "runner.log").open("w") as log:
                result = subprocess.run(command, cwd=APP, env=env, stdout=log, stderr=subprocess.STDOUT,
                                        timeout=600)
            passed = classify(read(report), task)
            assert result.returncode == (0 if passed else 1)
            dump(marker, {"passed": passed, "report_sha256": sha(report)})


def report():
    frozen = read(OUT / "freeze.json")
    verify(frozen["inputs_sha256"])
    rows = {}
    for task in TASKS:
        rows[task] = {}
        for name in PAGES:
            folder = OUT / "runs" / name / task
            record = read(folder / "outcome.json")
            assert record["report_sha256"] == sha(folder / "report.json")
            assert record["passed"] == classify(read(folder / "report.json"), task)
            rows[task][name] = record
    return {"project": "react", "upstream": REVISION, "freeze_sha256": sha(OUT / "freeze.json"),
            "model_calls": 0, "tasks": rows,
            "passed": {k: sum(r[k]["passed"] for r in rows.values()) for k in PAGES},
            "distinguishable": [t for t, r in rows.items()
                                if r["reference"]["passed"] and not (r["starter"]["passed"] or r["blank"]["passed"])]}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["setup", "evaluate", "report", "check"])
    action = p.parse_args().action
    if action == "setup":
        setup()
    elif action == "evaluate":
        verify(read(OUT / "freeze.json")["inputs_sha256"])
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(evaluate, PAGES))
    else:
        data = report()
        if action == "report" and not PUBLIC.exists():
            dump(PUBLIC, data)
        assert data == read(PUBLIC)
        print(data["passed"], data["distinguishable"])
