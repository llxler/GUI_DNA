"""Run the frozen form transfer or verify its original registration."""

import sys
from pathlib import Path

from studies.public_library_transfer.self_replication import (
    lines_registered as registered,
)
from studies.public_library_transfer.self_refinement.line_contract import run as lines
from studies.study_io import read, sha


def main():
    prereg = registered.OUT / "transfer-protocol.json"
    if prereg.is_file():
        expected = read(prereg)
        assert expected["launcher"] == sha(Path(registered.__file__))
        assert expected["protocol"] == sha(registered.HERE / "LINE_CONTRACT.md")
        if sys.argv[1:] == ["enroll"]:
            return
    if sys.argv[1:] == ["verify"]:
        lines.configure(registered.OUT, "form", registered.MODELS, registered.END)
        lines.base.verify()
    else:
        registered.main()


if __name__ == "__main__":
    main()
