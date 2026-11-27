"""Launch the registered study with the installed Node executable in its clean environment."""
import runpy
import shutil
import subprocess
from unittest.mock import patch


def main():
    node = shutil.which('node')
    if node is None:
        raise SystemExit('Install Node.js and put its executable on PATH.')
    execute = subprocess.run

    def resolve_node(args, *positional, **kwargs):
        if isinstance(args, list) and args and args[0] == 'node':
            args = [node, *args[1:]]
        return execute(args, *positional, **kwargs)

    with patch.object(subprocess, 'run', resolve_node):
        runpy.run_module('studies.public_library_transfer.compact_todomvc.state_examples.run',
                         run_name='__main__')


if __name__ == '__main__':
    main()
