import pytest

from studies.end_to_end import builder_comparisons, comparison, reconstruct, unique_records


def test_shared_baseline_is_not_replicated_or_relabelled():
    baseline = {"cohort": "c", "project": "p", "model": "m", "task": "task-1",
                "method": "free", "builder": "b1", "current": True,
                "record": "actual-free-record"}
    other = {**baseline, "builder": "b2"}
    archived = {**baseline, "method": "free_lib", "record": "library-assisted-record"}
    selected = unique_records([baseline, other, archived])
    assert len(selected) == 1 and selected[0]["builder"] is None
    assert comparison(selected)["current"]["free"]["total"] == 1
    conflicting = {**other, "current": False}
    with pytest.raises(ValueError, match="Conflicting observations"):
        unique_records([baseline, conflicting])


def test_primary_view_uses_original_current_scores_and_missing_counterparts():
    data = reconstruct()
    assert {k: v["results"]["current"]["free"]["total"] for k, v in data["cohorts"].items()} == {
        "interface": 80, "expansion": 120, "draw": 10}
    for cohort in ("expansion", "draw"):
        assert data["cohorts"][cohort]["results"]["current"]["difference_pp"] > 0
    assert "frontier" not in data["cohorts"]
    assert any("No no-library" in row["reason"] for row in data["not_reported"])
    assert all(row["method"] in ("free", "plan") for row in data["records"])
    assert all("history" not in row for row in data["records"])
    assert not any("history-replay" in name for name in data["source_sha256"])
    for value in data["costs"]["draw_per_generator_scenarios"].values():
        assert value["pipeline_receipts_usd"] > value["selection_receipts_usd"]
    assert data["costs"]["draw_complete_original_study_ledger_usd"] == 3.285408


def test_builder_comparisons_match_targets_and_preserve_opposite_effects():
    data = reconstruct()
    for cohort in data["cohorts"].values():
        for groups in [cohort["by_builder"], *cohort["by_project_builder"].values(),
                       *cohort["by_generator_builder"].values()]:
            for result in groups.values():
                for endpoint in ("current",):
                    assert result[endpoint]["free"]["total"] == result[endpoint]["plan"]["total"]
    expansion = data["bom_sensitivity"]["by_builder"]
    assert expansion["openai/gpt-5"]["current"]["difference_pp"] > 0
    assert expansion["anthropic/claude-sonnet-4.5"]["current"]["difference_pp"] < 0
    for value in data["costs"]["draw_by_generator_builder"].values():
        assert value["targets_per_method"] == 5
        assert value["pipeline_usd"] == pytest.approx(value["build_usd"] + value["selection_usd"])
    free = {"project": "p", "model": "m", "task": "task-1", "method": "free",
            "builder": None, "current": True, "history": False}
    plan = {**free, "task": "task-2", "method": "plan", "builder": "b"}
    with pytest.raises(AssertionError, match="Unmatched builder comparison"):
        builder_comparisons([free, plan])


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


def test_prospective_view_charges_failed_builds_and_checks_pair_counts():
    from copy import deepcopy
    from pathlib import Path
    import json
    from studies.end_to_end import validate_matched_workflow

    saved = Path(__file__).resolve().parents[1] / 'studies/results/matched-canvas-20261118.json'
    study = json.loads(saved.read_text())
    validate_matched_workflow(study)
    for rep in (1, 2):
        group = study['groups'][f'plan-{rep}']
        assert group['observed'] == group['planned'] == 5 and group['passed'] == 0
        assert group['cost']['settled_usd'] > 0 and group['receipts_usd']['target'] == 0
    swapped = deepcopy(study)
    swapped['paired']['1']['both_pass'] += 1
    with pytest.raises(AssertionError):
        validate_matched_workflow(swapped)


def test_paper_cells_use_only_jointly_observed_positions():
    from studies.paper_end_to_end import matched_table

    study = {'project':'example','model':'openai/gpt-5','config':{'max_tokens':32000},
             'groups':{f'{arm}-{rep}':{'cost':{'settled_usd':0.25}}
                       for rep in (1, 2) for arm in ('free','plan')},
             'paired':{str(rep):{'both_pass':1,'both_fail':1,'direct_only':2,'plan_only':0}
                       for rep in (1, 2)}}
    assert matched_table([study]).count('3/4 & 1/4') == 2


def test_overall_table_intersects_all_observed_arms_and_keeps_real_zeros():
    from studies.paper_performance import joint_scores

    scores = joint_scores({
        'direct': {1: True, 2: True, 3: False},
        'astra-a': {1: True, 2: True, 3: None},
        'astra-b': {1: False, 2: None, 3: True},
        'failed_build': {1: False, 2: False, 3: False},
        'no_response': {1: None, 2: None, 3: None},
    })
    assert scores == {'n': 1, 'targets': [1],
                      'passed': {'direct': 1, 'astra-a': 1, 'astra-b': 0, 'failed_build': 0}}
    assert joint_scores({'direct': {1: True}, 'plan': {2: False}}) is None


def test_main_table_separates_unavailable_routes_from_zero_scores():
    from studies.paper_performance import BACKBONES, render_matrix

    matrix = {model: {'current': {}, 'supplied': {}, 'sources': {}, 'retrospective': {}}
              for model in BACKBONES}
    qwen = 'qwen/qwen3.5-9b'
    matrix[qwen]['current']['table'] = {'n': 20, 'passed': {'direct': 1, 'human': 0, 'self': 0}}
    matrix[qwen]['current']['todomvc'] = {'n': 8, 'passed': {'direct': 1, 'human': 0, 'self': 0}}
    tex = render_matrix(matrix)
    assert tex.count(r'\begin{table*}') == 1 and tex.count(r'\end{table*}') == 1
    assert '6.2' not in tex and 'Astra' not in tex
    table_row, suite_row = [line for line in tex.splitlines() if line.startswith('Qwen3.5-9B &')]
    assert '1/20' in table_row and table_row.count('0/20') == 2
    assert '1/8' in suite_row and suite_row.count('0/8') == 2
    unavailable = next(line for line in tex.splitlines() if '-- Unavailable in Panel A' in line)
    assert 'GPT-5,' in unavailable and 'Claude Sonnet 4.5' in unavailable


def test_duplicate_official_case_titles_require_a_decisive_outcome():
    from studies.public_library_transfer.backbone_suites.replay import decide

    names = ['a', 'b', 'c', 'd']
    rows = [{'fullName': name, 'status': 'passed'} for name in names]
    assert decide(names, rows) is True
    assert decide(names, rows + [{'fullName': 'a', 'status': 'failed'}]) is None
    rows[-1]['status'] = 'failed'
    assert decide(names, rows + [{'fullName': 'a', 'status': 'failed'}]) is False
