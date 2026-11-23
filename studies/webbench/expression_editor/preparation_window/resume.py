"""Resume the frozen window after a model returned an unrepresentable filename."""
import errno
from unittest.mock import patch

from studies.interface_blind.core import write_files

from .run import runner, window_contract


def materialize(folder, files):
    try:
        write_files(folder, files)
    except OSError as error:
        if error.errno != errno.ENAMETOOLONG:
            raise
        # Only public filesystem feedback goes into the already registered repair.
        raise ValueError("A generated file path exceeds the filesystem length limit.") from error


if __name__ == "__main__":
    with window_contract(), patch.object(runner, "write_files", materialize):
        runner.generate()
