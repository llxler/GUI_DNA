"""Verify original/exported bytes with one cached immutable manifest per version."""
from functools import lru_cache
from pathlib import Path
import json
from test.history_replay.run import ROOT, sha


@lru_cache(maxsize=2)
def _mapping(path: Path, inode: int, size: int, mtime_ns: int):
    # The caller includes file identity/version in the key. Every report itself
    # is freshly hashed, so caching cannot hide a modified report.
    return json.loads(path.read_text())


def verify_report_hash(path, original_sha256):
    actual=sha(path)
    if actual==original_sha256:
        return
    manifest=ROOT/'REPLAY-MANIFEST.json'
    assert manifest.exists(), 'Original report bytes changed without an export mapping'
    stat=manifest.stat()
    entry=_mapping(manifest,stat.st_ino,stat.st_size,stat.st_mtime_ns)[str(path.relative_to(ROOT))]
    assert entry['original_sha256']==original_sha256
    assert entry['exported_sha256']==actual
