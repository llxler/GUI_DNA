"""Replay the sealed table experiment with its original source files and path hashes."""
from pathlib import Path

from studies.study_io import sha
from . import sealed_adapter_20261123, sealed_run_20261123
from .sealed_run_20261123 import rel  # Public path formatter used by report readers.


def main():
    # The shared adapter also belongs to a different freeze. Route this study's
    # archived path names to the exact source bytes used when scoring began.
    here = Path(__file__).resolve().parent
    captured = {here / 'adapter.py': Path(sealed_adapter_20261123.__file__),
                here / 'run.py': Path(sealed_run_20261123.__file__)}

    def frozen_sha(path):
        path = Path(path).resolve()
        return sha(captured.get(path, path))

    sealed_run_20261123.sha = frozen_sha
    sealed_run_20261123.bind_starter = sealed_adapter_20261123.bind_starter
    sealed_run_20261123.score_pages = sealed_adapter_20261123.score_pages
    sealed_run_20261123.main()


if __name__ == '__main__':
    main()
