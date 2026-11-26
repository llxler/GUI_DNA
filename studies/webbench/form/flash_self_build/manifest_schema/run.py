"""Generate a compact typed manifest, then run the frozen file-wise builder."""
import argparse
import json
from pathlib import Path
from unittest.mock import patch

from studies.public_library_transfer import core
from studies.study_io import ROOT, now, read, sha
from .. import resume, run, staged

HERE = Path(__file__).resolve().parent
BRANCHES = ("staged-schema-a", "staged-schema-b")
INSTRUCTION = """
Use this exact shape. All entries illustrate types; choose your own behavior, names and values.
{"design":"short string for the future planner", "controls":[{"id":"your-switch",
"behavior":"what this option actually changes", "type":"boolean","values":[],
"default":"false","example":"true"}],"modules":[{"path":"path.js",
"api":"one string describing exports and calls","depends_on":["path/to/dependency.js"]}]}
Use 1 to 3 boolean options. Keep each API description under 45 words. Return actual arrays for
controls and modules and actual arrays of paths for dependencies. Always mount the public
questionnaire examples in the starter. Reserve switches for genuine optional behavior.
Each implementation file is requested later, so return a short manifest without source.
"""


def documented(value):
    if isinstance(value, (dict, list)) and value:
        return json.dumps(value, ensure_ascii=False)
    return value


def run_branch(branch):
    run.register(True)
    registration = run.OUT / "manifest-schema-registration.json"
    input_files = [HERE / "run.py", HERE / "PROTOCOL.md", Path(resume.__file__), Path(staged.__file__)]
    files = {str(p.relative_to(ROOT)): sha(p) for p in input_files}
    with run.browser.lock(run.OUT / ".schema-registration.lock"):
        if not registration.exists():
            assert not (run.OUT / "seal.json").exists()
            assert not (run.OUT / "browser/scores").exists()
            core.save(registration, {"utc": now(), "files": files, "branches": BRANCHES,
                                     "parent_sha256": sha(run.OUT / "staged-registration.json")})
        assert read(registration)["files"] == files

    original_parse = staged.parse_design

    def parse(text, data):
        manifest = core.parse(text)
        manifest["design"] = documented(manifest.get("design"))
        if not isinstance(manifest.get("controls"), list) or not 1 <= len(manifest["controls"]) <= 3:
            raise ValueError("controls must be an array of one to three Boolean option objects")
        for option in manifest["controls"]:
            if not isinstance(option, dict) or option.get("type") != "boolean":
                raise ValueError("Each controls entry must have type boolean and values []")
        for module in manifest["modules"]:
            module["api"] = documented(module.get("api"))
        return original_parse(json.dumps(manifest, ensure_ascii=False), data)

    with patch.object(staged, "parse_design", parse), patch.object(staged, "DESIGN", staged.DESIGN + INSTRUCTION):
        resume.resume(branch)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("branch", choices=BRANCHES)
    run_branch(parser.parse_args().branch)
