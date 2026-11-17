import pytest

from studies.end_to_end import comparison, reconstruct, unique_records


def test_shared_baseline_is_not_replicated_or_relabelled():
    baseline = {"cohort": "c", "project": "p", "model": "m", "task": "task-1",
                "method": "free", "builder": "b1", "current": True,
                "history": False, "record": "actual-free-record"}
    other = {**baseline, "builder": "b2"}
    archived = {**baseline, "method": "free_lib", "record": "library-assisted-record"}
    selected = unique_records([baseline, other, archived])
    assert len(selected) == 1 and selected[0]["builder"] is None
    assert comparison(selected)["current"]["free"]["total"] == 1
    conflicting = {**other, "history": True}
    with pytest.raises(ValueError, match="Conflicting observations"):
        unique_records([baseline, conflicting])


def test_primary_view_keeps_adverse_endpoints_and_missing_counterparts():
    data = reconstruct()
    assert {k: v["results"]["current"]["free"]["total"] for k, v in data["cohorts"].items()} == {
        "interface": 80, "expansion": 120, "draw": 10}
    for cohort in ("expansion", "draw"):
        assert data["cohorts"][cohort]["results"]["current"]["difference_pp"] > 0
        assert data["cohorts"][cohort]["results"]["history"]["difference_pp"] < 0
    assert "frontier" not in data["cohorts"]
    assert any("No no-library" in row["reason"] for row in data["not_reported"])
    assert all(row["method"] in ("free", "plan") for row in data["records"])
    assert sum(x["reported_candidates"] for x in data["matched_feedback"].values()) == 27
    for value in data["costs"]["draw_per_generator_scenarios"].values():
        assert value["pipeline_receipts_usd"] > value["selection_receipts_usd"]
    assert data["costs"]["draw_complete_original_study_ledger_usd"] == 3.285408


def test_portable_export_preserves_frozen_import_paths(tmp_path):
    import subprocess
    import sys
    import zipfile
    from studies.export_review_snapshot import source_file_paths

    sources = tmp_path / "source"
    (sources / "studies").mkdir(parents=True)
    (sources / "test").symlink_to("studies", target_is_directory=True)
    (sources / "studies/__init__.py").write_text("")
    (sources / "studies/leaf.py").write_text("value = 7\n")
    (sources / "studies/entry.py").write_text("from test.leaf import value\nprint(value)\n")
    (sources / "docs").mkdir()
    (sources / "docs/results.md").write_text("Historical observations\n")
    (sources / "实验结果.md").symlink_to("docs/results.md")
    outside = tmp_path / "outside.py"
    outside.write_text("private = True\n")
    (sources / "studies/unsafe.py").symlink_to(outside)
    names = ["studies/__init__.py", "studies/leaf.py", "studies/entry.py", "studies/unsafe.py",
             "docs/results.md", "实验结果.md"]
    paths = source_file_paths(sources, names, {".py", ".md"})
    assert len(paths) == 8
    bundle = tmp_path / "portable.zip"
    with zipfile.ZipFile(bundle, "w") as archive:
        for path in paths:
            archive.writestr(path.relative_to(sources).as_posix(), path.read_bytes())
    restored = tmp_path / "restored"
    with zipfile.ZipFile(bundle) as archive:
        archive.extractall(restored)
    assert not (restored / "test").is_symlink()
    assert not (restored / "实验结果.md").is_symlink()
    assert (restored / "实验结果.md").read_text() == (restored / "docs/results.md").read_text()
    for namespace in ("studies", "test"):
        result = subprocess.run([sys.executable, "-m", namespace + ".entry"],
                                cwd=restored, capture_output=True, text=True, check=True)
        assert result.stdout == "7\n"


def test_historical_audit_does_not_write_ledger(tmp_path):
    import hashlib
    import sqlite3
    from gui_dna.budget import Ledger
    from experiments.audit_scale import read_accounting

    path = tmp_path / "budget.sqlite3"
    ledger = Ledger(path, .5, .4)
    call_id = ledger.reserve(.02, "library:example", "model")
    ledger.settle(call_id, .01)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE policy SET halted=1 WHERE id=1")
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    result = read_accounting(path)
    assert result["policy"] == {"id": 1, "cap": 500000, "stop": 400000, "halted": 1}
    assert result["library_usd"] == result["actual_usd"] == .01
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
