"""Place the pinned package metadata above candidate pages as in the upstream runner."""
from pathlib import Path
import shutil

from studies.library_refinement_chart.adapter import OUT, browser
from studies.study_io import sha


def setup(directory=OUT):
    directory = Path(directory)
    if not directory.resolve().is_relative_to(OUT):
        raise ValueError("Use the isolated chart study directory")
    directory.mkdir(parents=True, exist_ok=True)
    src = browser.SOURCE / "package.json"
    dst = directory / "package.json"
    if not dst.exists():
        shutil.copyfile(src, dst)
    if sha(dst) != sha(src):
        raise ValueError("The candidate package scope is inconsistent with the pinned evaluator")
    modules = directory / "node_modules"
    if not modules.exists():
        modules.symlink_to(browser.RUNTIME / "node_modules", target_is_directory=True)
    if modules.resolve() != (browser.RUNTIME / "node_modules").resolve():
        raise ValueError("Unexpected candidate runtime")


if __name__ == "__main__":
    setup()
