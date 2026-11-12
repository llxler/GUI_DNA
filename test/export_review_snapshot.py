"""Prepare a local anonymous source/summary snapshot; never publish it.

This is not the full historical replay bundle: ignored raw responses, ledgers,
candidate pages and their original manifests are deliberately outside its scope.
Source paths are normalized, so the export has its own checksums.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_ROOTS = {'src', 'test', 'tests', 'experiments', 'configs', 'scripts', 'data'}
ALLOWED_FILES = {'pyproject.toml', 'uv.lock', 'README.md', '实验结果.md', '代码逻辑.md', '.gitignore'}
EXTENSIONS = {'.py', '.js', '.cjs', '.ts', '.json', '.jsonl', '.html', '.css', '.md', '.txt', '.toml', '.lock', '.sh'}


def anonymize(text):
    # Shared redaction preserves regex syntax in exported utility source.
    from test.export_replay_bundle import scrub
    return scrub(text)


def main():
    names = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT).decode().split('\0')
    selected = sorted({name for name in names if name and
                       (name in ALLOWED_FILES or (Path(name).parts[0] in ALLOWED_ROOTS and Path(name).suffix in EXTENSIONS))})
    output = ROOT / 'artifacts/anonymous-review-source.zip'
    entries = {}
    for name in selected:
        path = ROOT / name
        if path.is_symlink() or not path.is_file():
            continue
        content = anonymize(path.read_text()).encode()
        from test.export_replay_bundle import has_identity
        if has_identity(content):
            raise ValueError(f'identity remains in {name}')
        entries[name] = content
    entries['SNAPSHOT.md'] = (
        '# Anonymous source and summary snapshot\n\n'
        'This local export has no Git history, credentials, private ledgers or author home paths. '
        'It contains source and derived tables. It does not include ignored raw experiment records, '
        'pages, responses or their historical manifests; replaying the published observations therefore '
        'requires a separate data bundle. Original frozen hashes do not describe sanitized copies. '
        'The manifest below hashes the exported bytes. This file is not evidence of publication.\n'
    ).encode()
    manifest = {name: hashlib.sha256(content).hexdigest() for name, content in entries.items()}
    entries['SNAPSHOT-MANIFEST.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    print(json.dumps({'path': str(output), 'files': len(entries), 'bytes': output.stat().st_size,
                      'sha256': hashlib.sha256(output.read_bytes()).hexdigest(), 'published': False}))


if __name__ == '__main__':
    main()
