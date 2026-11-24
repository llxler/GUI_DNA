"""Resume the registered generation code against the pinned public observer symbol."""

import argparse
from pathlib import Path
from unittest.mock import patch
from studies.public_library_transfer import core
from studies.study_io import ROOT, now, read, sha
from . import run


def register():
    path = run.OUT / "observer-compatibility.json"
    paths = [
        run.HERE / "OBSERVE.md",
        Path(__file__),
        Path(run.observe.__file__),
        run.OUT / "registration.json",
    ]
    spec = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    if not path.exists():
        assert not (run.OUT / "seal.json").exists()
        core.save(path, {"utc": now(), "sources": spec})
    assert read(path)["sources"] == spec


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("phase", choices=("register", "generate"))
    phase = p.parse_args().phase
    register()
    if phase == "generate":
        with patch.object(run.observe, "public", run.observe.observe, create=True):
            run.generate()
