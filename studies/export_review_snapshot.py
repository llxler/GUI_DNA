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
ALLOWED_ROOTS = {'src', 'studies', 'test', 'tests', 'experiments', 'configs', 'scripts', 'data', 'docs'}
ALLOWED_FILES = {'pyproject.toml', 'uv.lock', 'README.md', '实验结果.md', '代码逻辑.md', '.gitignore'}
EXTENSIONS = {'.py', '.js', '.cjs', '.ts', '.json', '.jsonl', '.html', '.css', '.md', '.txt', '.toml', '.lock', '.sh'}
DOCUMENT_ALIASES = {'实验结果.md': 'docs/results.md', '代码逻辑.md': 'docs/method.md',
                    'experiments/TODO.md': 'docs/roadmap.md'}


def is_document_alias(root, path):
    name = path.relative_to(root).as_posix()
    target = DOCUMENT_ALIASES.get(name)
    return bool(target and path.is_symlink() and path.is_file()
                and path.resolve() == (root / target).resolve()
                and path.resolve().is_relative_to(root.resolve()))


def source_file_paths(root, names, extensions):
    """Materialize canonical sources and historical imports in portable exports.

    ZIP consumers need not support symlinks. Only the registered test -> studies
    directory alias and named document aliases are materialized; arbitrary or
    external links are excluded.
    """
    chosen = set()
    for name in names:
        if not name or not (name in ALLOWED_FILES or
                            (Path(name).parts[0] in ALLOWED_ROOTS and Path(name).suffix in extensions)):
            continue
        path = root / name
        if not path.is_file() or (path.is_symlink() and not is_document_alias(root, path)) or not path.resolve().is_relative_to(root.resolve()):
            continue
        chosen.add(path)
        if Path(name).parts[0] == 'studies':
            legacy = root / 'test' / Path(name).relative_to('studies')
            if legacy.is_file() and legacy.resolve() == path.resolve():
                chosen.add(legacy)
    return chosen


def anonymize(text):
    # Shared redaction preserves regex syntax in exported utility source.
    from test.export_replay_bundle import scrub
    return scrub(text)


def main():
    names = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT).decode().split('\0')
    selected = sorted(p.relative_to(ROOT).as_posix() for p in source_file_paths(ROOT, names, EXTENSIONS))
    output = ROOT / 'artifacts/anonymous-review-source.zip'
    entries = {}
    for name in selected:
        path = ROOT / name
        if (path.is_symlink() and not is_document_alias(ROOT, path)) or not path.is_file():
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
