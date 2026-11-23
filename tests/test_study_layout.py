"""Frozen path compatibility must preserve both the published and registered bytes."""

import hashlib
import json

import pytest

from studies import layout


@pytest.fixture
def tiny_layout(tmp_path, monkeypatch):
    studies = tmp_path / "studies"
    phase = studies / "webbench" / "table" / "trial"
    phase.mkdir(parents=True)
    (studies / "public_library_transfer").mkdir()
    (studies / "webbench" / "layout.json").write_text(
        json.dumps({"old_trial": "webbench/table/trial"})
    )
    (studies / "public_library_transfer" / "layout.json").write_text("{}")
    (phase / "run.py").write_bytes(b"print('trial')\n")
    (phase / "README.md").write_bytes(b"Published navigation\n")
    (phase / "README.frozen.txt").write_bytes(b"Original navigation\n")
    fields = {"README.md": "README.frozen.txt", "run.py": "run.py"}
    manifest = studies / "hashes.json"
    manifest.write_text(
        json.dumps(
            {
                "old_trial": {
                    name: hashlib.sha256((phase / file).read_bytes()).hexdigest()
                    for name, file in fields.items()
                }
            }
        )
    )
    monkeypatch.setattr(layout, "BASE", studies)
    monkeypatch.setattr(layout, "MANIFEST", manifest)
    layout.locations.cache_clear()
    yield studies, phase
    layout.locations.cache_clear()


def test_readonly_check_then_restore_and_tidy(tiny_layout):
    root, phase = tiny_layout
    original = root / "old_trial"
    assert set(layout.check_sources()) == {"old_trial"} and not original.exists()
    layout.restore()
    assert (original / "run.py").read_bytes() == (phase / "run.py").read_bytes()
    assert (original / "README.md").read_bytes() == b"Original navigation\n"
    layout.restore()
    backup = layout.tidy()
    assert not original.exists() and (backup / "old_trial" / "run.py").is_file()
    assert (phase / "README.md").read_bytes() == b"Published navigation\n"


def test_keep_edited_compatibility_files_in_place(tiny_layout):
    root, _ = tiny_layout
    layout.restore()
    modified = root / "old_trial" / "run.py"
    modified.write_bytes(b"# local change\n")
    with pytest.raises(ValueError, match="differs"):
        layout.restore()
    with pytest.raises(ValueError, match="Keep local changes"):
        layout.tidy()
    assert modified.read_bytes() == b"# local change\n"
