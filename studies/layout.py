"""Resolve the published study tree and reproduce the original on-disk paths."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile

BASE = Path(__file__).resolve().parent
MANIFEST = BASE / "frozen_study_files.json"


@lru_cache(maxsize=1)
def locations():
    data = {}
    for family in ("webbench", "public_library_transfer"):
        entries = json.loads((BASE / family / "layout.json").read_text())
        for old, target in entries.items():
            if (
                old in data
                or not old.isidentifier()
                or not target.startswith(family + "/")
                or ".." in Path(target).parts
            ):
                raise ValueError(f"Invalid or duplicate study path: {old!r}")
            data[old] = target
    return data


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def original_files(old):
    folder = BASE / locations()[old]
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        relative = path.relative_to(folder)
        if path.name == "README.frozen.txt":
            yield relative.with_name("README.md"), path
        elif (
            path.name != "README.md"
            or not path.with_name("README.frozen.txt").is_file()
        ):
            yield relative, path


def check_sources():
    expected = json.loads(MANIFEST.read_text())
    actual = {
        old: {name.as_posix(): file_hash(path) for name, path in original_files(old)}
        for old in locations()
    }
    if actual != expected:
        raise ValueError(
            "Published files differ from the registered pre-move study tree"
        )
    return actual


@contextmanager
def _layout_lock():
    # The browser experiment/replay environment runs on Linux.
    import fcntl

    cache = BASE.parent / "artifacts" / "study-layout-backups"
    cache.mkdir(parents=True, exist_ok=True)
    with (cache / ".paths.lock").open("a") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield cache


def restore():
    """Materialize exact historical files; never replace differing user data."""
    with _layout_lock():
        return _restore_files(check_sources())


def _restore_files(hashes):
    for old, expected in hashes.items():
        dest = BASE / old
        if dest.is_symlink():
            raise ValueError(f"A historical package requires a real directory: {dest}")
        for relative, source in original_files(old):
            target = dest / relative
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                # Publish a complete inode atomically, even with concurrent CLI invocations.
                with tempfile.NamedTemporaryFile(
                    dir=target.parent, delete=False
                ) as handle:
                    temporary = Path(handle.name)
                    handle.write(source.read_bytes())
                try:
                    temporary.chmod(source.stat().st_mode & 0o777)
                    try:
                        os.link(temporary, target)
                    except FileExistsError:
                        pass
                finally:
                    temporary.unlink(missing_ok=True)
            if (
                target.is_symlink()
                or file_hash(target) != expected[relative.as_posix()]
            ):
                raise ValueError(
                    f"Existing historical file differs from its frozen source: {target}"
                )
    return hashes


def tidy():
    """Move verified compatibility directories to a private backup without deleting files."""
    with _layout_lock() as cache:
        return _move_verified_copies(check_sources(), cache)


def _move_verified_copies(hashes, cache):
    active = []
    for old, expected in hashes.items():
        folder = BASE / old
        if not folder.exists():
            continue
        if folder.is_symlink() or not folder.is_dir():
            raise ValueError(f"Unexpected compatibility path: {folder}")
        files = {}
        for path in folder.rglob("*"):
            if path.is_symlink():
                raise ValueError(f"Refusing to move an unexpected symlink: {path}")
            if path.is_file() and "__pycache__" not in path.parts:
                files[path.relative_to(folder).as_posix()] = file_hash(path)
        if files != expected:
            raise ValueError(f"Keep local changes in place: {folder}")
        active.append(folder)
    if not active:
        return None
    backup = Path(tempfile.mkdtemp(prefix="frozen-", dir=cache))
    for folder in active:
        folder.rename(backup / folder.name)
    return backup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    actions.add_parser(
        "check", help="verify original bytes in the public tree without writing files"
    )
    actions.add_parser(
        "prepare",
        help="restore paths for archived Python modules and raw file manifests",
    )
    actions.add_parser(
        "tidy", help="move byte-verified compatibility copies into a local backup"
    )
    command = actions.add_parser(
        "run", help="run a frozen entry point using its registered module identity"
    )
    command.add_argument("study", help="published phase path under studies/")
    command.add_argument("module", help="module filename without the .py extension")
    command.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.action == "tidy":
        backup = tidy()
        print(
            f"Compatibility copies moved to {backup}"
            if backup
            else "Study tree is already tidy"
        )
        return
    if args.action == "run":
        aliases = {value: name for name, value in locations().items()}
        study = args.study.removeprefix("studies/").strip("/")
        if (
            study not in aliases
            or not args.module.isidentifier()
            or not (BASE / study / (args.module + ".py")).is_file()
        ):
            parser.error(
                "Choose an entry point listed under the published phase directory"
            )
        restore()
        sys.argv = [args.module, *args.arguments]
        runpy.run_module(
            f"studies.{aliases[study]}.{args.module}",
            run_name="__main__",
            alter_sys=True,
        )
        return
    evidence = check_sources() if args.action == "check" else restore()
    print(
        f"{len(evidence)} frozen phases, {sum(map(len, evidence.values()))} byte-verified files"
    )


if __name__ == "__main__":
    main()
