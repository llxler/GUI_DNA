"""Install the isolated pinned evaluation runtime without changing old stages."""
from __future__ import annotations
import shutil
import subprocess
from pathlib import Path
from .core import ROOT


def main():
    here = Path(__file__).resolve().parent
    target = ROOT / 'artifacts/webbench-expand-runtime-157'
    target.mkdir(parents=True, exist_ok=True)
    for source_name, name in (('runtime-package.json', 'package.json'), ('runtime-lock.json', 'package-lock.json')):
        source, destination = here / source_name, target / name
        if destination.exists():
            assert destination.read_bytes() == source.read_bytes(), f'{destination} differs; do not silently replace a scored runtime'
        else:
            shutil.copy2(source, destination)
    utility = ROOT / 'test/webbench_dna/harness/test-util'
    for path in utility.rglob('*'):
        if path.is_file():
            destination = target / 'test-util' / path.relative_to(utility)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                assert destination.read_bytes() == path.read_bytes()
            else:
                shutil.copy2(path, destination)
    if not (target / 'node_modules/@playwright/test/package.json').exists():
        subprocess.run(['npm', 'ci'], cwd=target, check=True)
    subprocess.run(['node', str(target / 'node_modules/playwright/cli.js'), 'install', 'chromium'], check=True)


if __name__ == '__main__':
    main()
