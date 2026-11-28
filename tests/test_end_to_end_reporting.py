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
    headers = [line.removesuffix(r'\\').strip() for line in tex.splitlines() if line.startswith('Target generator')]
    methods = ['Direct', 'Human', 'GPT-5', 'Self']
    assert [header.split(' & ')[1:] for header in headers] == [methods * 3, methods * 2]
    assert 'Bind' not in tex and 'Sonnet' not in tex
    table_row, suite_row = [line for line in tex.splitlines() if line.startswith('Qwen3.5-9B &')]
    assert '1/20' in table_row and table_row.count('0/20') == 2
    assert '1/8' in suite_row and suite_row.count('0/8') == 2
    assert r'\textcolor[gray]{0.55}{--}' in suite_row
    assert 'Gemini' not in tex and 'Claude Haiku 4.5' not in tex


def test_flash_question_form_reports_the_first_registered_library_in_the_primary_cell():
    from studies.paper_performance import render_matrix
    from studies.study_io import ROOT, read, sha
    from studies.webbench.form.flash_self_build import paper as flash

    matrix = read(ROOT / "studies/results/paper-performance-matrix.json")
    group = matrix[flash.MODEL]
    original = group["current"]["form"]
    displayed = group["panel_a_self"]["form"]
    assert original["passed"]["self"] == 0
    assert displayed["targets"] == original["targets"] == list(range(1, 21))
    assert displayed["source_sha256"] == sha(flash.COMPLETION)
    assert displayed["library"] == "file-a"
    assert displayed["passed"] == {"self": 8}
    panel_a = render_matrix(matrix).split("B. Feature subsets")[0]
    row = next(line for line in panel_a.splitlines() if line.startswith("DeepSeek V4 Flash &"))
    visible = group["form_visible_targets"]
    assert visible["targets"] == original["targets"]
    assert visible["passed"] == {"direct": 10, "human": 20, "gpt5-library": 12, "self": 11}
    assert row.split(" & ")[-4:] == [
        r"10/20", r"\textbf{20/20}", r"12/20", r"11/20 \\",
    ]


def test_paper_omits_failed_builds_and_keeps_measured_zeros():
    from studies.paper_performance import render_matrix
    from studies.study_io import ROOT, read
    from studies.webbench.form.flash_self_build import paper as flash

    matrix = read(ROOT / "studies/results/paper-performance-matrix.json")
    # Check original admission on the archived batch even after prospective rebuilds arrive.
    for model in matrix.values():
        model.pop("self_recovery", None)
        model.pop("component_followup", None)
        model.pop("extended_targets", None)
        model.pop("table_protocol_followup", None)
        model.pop("form_visible_targets", None)
        model.pop("library_capabilities", None)
        model.pop("table_state_transitions", None)
        model.pop("state_examples", None)
        model.pop("table_shared_selection", None)
        model.pop("module_rebuilds", None)
        model.pop("calculator_profiles", None)
        model.pop("duo_feature_bindings", None)
        model.pop("target_extensions", None)
        model.pop("webgen_completion", None)
        model.pop("webgen_holdout", None)
        model.pop("source_diagnosis", None)
        model.pop("webgen_functional", None)
    from studies.paper_component_followup import LABELS
    for model in LABELS:
        matrix.pop(model, None)
    tex = render_matrix(matrix)
    panel_a = tex.split("B. Feature subsets")[0]
    gemma = next(line for line in panel_a.splitlines() if line.startswith("Gemma 3 12B &"))
    qwen = next(line for line in panel_a.splitlines() if line.startswith("Qwen3.5-9B &"))
    assert gemma.removesuffix(r"\\").split("&")[-1].strip() == ""
    assert qwen.removesuffix(r"\\").split("&")[-1].strip() == "0/19"
    suite = tex.split("B. Feature subsets")[1]
    gemma = next(line for line in suite.splitlines() if line.startswith("Gemma 3 12B &"))
    duo = [part.strip() for part in gemma.removesuffix(r"\\").split("&")[5:]]
    assert duo == ["0/5", r"\textcolor[gray]{0.55}{--}", r"\textcolor[gray]{0.55}{--}", "0/5"]
    appendix = render_matrix(matrix, followups=flash.rows())
    whole = next(line for line in appendix.splitlines() if "Whole package" in line)
    assert [part.strip() for part in whole.removesuffix(r"\\").split("&")[-2:]] == ["", ""]


def test_updated_table_uses_common_targets_and_keeps_the_original_webgen_registration():
    from studies import paper_component_followup as studies
    from studies.paper_performance import render_matrix
    from studies.study_io import ROOT, read

    matrix = read(ROOT / "studies/results/paper-performance-matrix.json")
    for entry in matrix.values():
        for g in entry.get("extended_targets", {}).values():
            old, added = map(set, (g["original_targets"], g["additional_targets"]))
            assert old.isdisjoint(added) and old | added == set(g["targets"])
            assert all(0 <= n <= g["n"] == len(g["targets"]) for n in g["passed"].values())
    tex = render_matrix(matrix)
    a, b = tex.split("B. Feature subsets and pairs", 1)
    b, c = b.split("C. WebGen-Bench", 1)
    assert all(label in b and label not in a for label in studies.LABELS.values())
    for model in read(studies.PLANNED)['models']:
        group = matrix[model]['webgen_functional']
        assert group['registered'] == 43 and group['n'] == len(set(group['targets']))
        assert all(0 <= v <= group['n'] for v in group['passed'].values())
        assert 'gpt5-library' not in group['passed']
    assert 'website operations' in c and 'Six development' not in c and 'Three held-out' not in c
    assert all(token not in tex for token in (r'\dagger',r'\ddagger',r'\textsuperscript','$^'))
    for model in read(studies.PLANNED)['models']:
        primary = matrix[model]['webgen_completion']
        assert len(primary['sites']) == 9 and primary['n'] == len(primary['targets'])
        assert all(type(v) is int and 0 <= v <= primary['n'] for v in primary['passed'].values())
    plan = read(studies.PLANNED)
    assert plan["measurements"] == [] and len({i for ids in plan["pilot_sites"].values() for i in ids}) == 6


def test_followup_panel_uses_the_joint_tasks_of_both_library_replicates():
    from studies.public_library_transfer.self_replication.paper import matched_row

    baseline = {i: i == 1 for i in range(1, 21)}
    first = {**baseline, 2: True, 20: None}
    second = {**baseline, 1: None}
    arms = {"direct": baseline, "self_a": first, "fixed_a": baseline, "self_b": second, "fixed_b": baseline}
    result = matched_row("Table editor", "Builder", "Native", arms)
    assert result["targets"] == list(range(2, 20))
    assert result["passed"] == {"direct": 0, "self_a": 1, "fixed_a": 0, "self_b": 0, "fixed_b": 0}


def test_duplicate_official_case_titles_require_a_decisive_outcome():
    from studies.public_library_transfer.backbone_suites.replay import decide

    names = ['a', 'b', 'c', 'd']
    rows = [{'fullName': name, 'status': 'passed'} for name in names]
    assert decide(names, rows) is True
    assert decide(names, rows + [{'fullName': 'a', 'status': 'failed'}]) is None
    rows[-1]['status'] = 'failed'
    assert decide(names, rows + [{'fullName': 'a', 'status': 'failed'}]) is False


def test_source_receiver_splits_real_paths_and_drops_only_headers():
    from studies.webbench.self_build_modules.source_delivery.run import extract
    source = "FILE: common/LineChart.js\nexport class LineChart {}\nFILE: index.js\nimport './common/LineChart.js'"
    assert extract(source, ["common/LineChart.js", "index.js"]) == {
        "common/LineChart.js": "export class LineChart {}", "index.js": "import './common/LineChart.js'"
    }


def test_rebuild_admission_pairs_controls_before_counting_a_measured_zero():
    from studies.public_library_transfer.self_refinement.suite_recovery.paper import paired

    cell = {
        "project": "duo", "original_shared": ["a", "b"],
        "original": {"direct": {"a": False, "b": True}},
        "builds": {"a": {"groups": {"one": "valid", "two": "build_failed"}, "seal_sha256": "x",
                         "arms": {"self": {"a": {"passed": False}, "b": {"passed": None}},
                                  "fixed": {"a": {"status": "valid", "passed": True},
                                            "b": {"status": "build_failed", "passed": None}}}}},
    }
    group = paired(cell, "a")
    assert group["targets"] == ["a"] and group["passed"] == {"direct": 0, "self": 0}
    assert group["fixed_passed"] == 1 and group["complete"]
    cell["builds"]["a"]["arms"]["self"]["a"]["passed"] = None
    missing = paired(cell, "a")
    assert not missing["complete"] and "self" not in missing["passed"]


def test_failed_rebuild_does_not_erase_an_admitted_original_zero():
    from studies.paper_performance import current_group
    original = {"n": 2, "passed": {"direct": 1, "self": 0}}
    rejected = {"complete": False, "n": 2, "passed": {"direct": 1}, "excluded_build_arms": ["self"]}
    model = {"current": {"form": original}, "self_recovery": {"form": {"first": rejected}}}
    assert current_group(model, "form") == original
    model["paper_current"] = {"form": {"n": 2, "passed": {"direct": 1}, "excluded_build_arms": ["self"]}}
    assert current_group(model, "form") == rejected


def test_library_followup_replaces_only_fully_observed_matched_targets():
    from copy import deepcopy
    from studies.paper_library_capabilities import TODO, set_method

    group = {"targets": [2, 4], "n": 2, "passed": {"direct": 1}, "excluded_build_arms": ["self"]}
    old = deepcopy(group)
    rows = [{"task": 1, "arm": "a", "status": "valid", "passed": True},
            {"task": 2, "arm": "a", "status": "valid", "passed": False},
            {"task": 4, "arm": "a", "status": "missing", "passed": None}]
    for row in rows[:2]:
        row["report_sha256"] = "0" * 64
    assert not set_method(group, "self", rows, "a", TODO, "events")
    assert group == old
    rows[2].update(status="valid", passed=False, report_sha256="1" * 64)
    assert set_method(group, "self", rows, "a", TODO, "events")
    assert group["passed"] == {"direct": 1, "self": 0}
    assert group["n"] == 2 and not group["excluded_build_arms"]


def test_lookup_tracks_method_receipts_when_protocols_share_a_row(capsys):
    import json

    from studies.lookup import main
    from studies.study_io import ROOT, read

    for method, source_arm, name, score in (
        ("Self", "file-a", "result.json", 11),
        ("GPT-5", "gpt5-library", "schema-transfer-result.json", 12),
    ):
        main(["web-bench/form", "DeepSeek V4 Flash", method])
        cell = json.loads(capsys.readouterr().out)
        assert cell["row_keys"] == ["deepseek/deepseek-v4-flash", "form_visible_targets"]
        assert cell["method_record"].endswith("/visible_targets/" + name)
        receipt = read(ROOT / cell["method_record"])
        rows = [r for r in receipt.get("cell", receipt)["rows"] if r["arm"] == source_arm]
        assert cell["score"] == sum(r["passed"] is True for r in rows) == score
        assert cell["denominator"] == len(rows) == 20


def test_lookup_separates_weighted_scores_build_failure_and_unavailable():
    from studies.lookup import MATRIX, find_cell
    from studies.study_io import ROOT, read

    matrix = read(ROOT / MATRIX)

    def query(model, method):
        return find_cell(matrix, "webgen-bench/development", model, method)

    weighted = query("deepseek/deepseek-v4-flash", "direct")
    assert (weighted["score"], weighted["denominator"], weighted["unit"]) == (35.5, 43, "functional points")
    model = "google/gemma-3-12b-it"
    development = query(model, "self")
    heldout = find_cell(matrix, "webgen-bench/heldout", model, "self")
    assert (development["denominator"], heldout["denominator"]) == (43, 21)
    assert set(development["sites"]).isdisjoint(heldout["sites"])
    for cell in (development, heldout):
        assert cell["status"] == "measured" and cell["method_record"].endswith("edit-judgments.json")
    missing = query(model, "gpt5-library")
    assert missing["status"] == "unavailable" and "score" not in missing


def test_new_full_project_rows_and_todo_method_records_match_the_registered_sources():
    from studies import paper_performance as paper, paper_target_extensions as ext
    from studies.lookup import MATRIX, find_cell
    from studies.study_io import ROOT, read

    matrix = read(ROOT / MATRIX)
    # Reproduce the registered target-extension cohort, before the later library rebuilds.
    matrix = {m: {k: v for k, v in row.items() if k not in ("module_rebuilds", "calculator_profiles")} for m, row in matrix.items()}
    for project in ("dom1", "calculator"):
        assert set(ext.WEB_MODELS.values()).issubset(paper.table_models(matrix, project))
        for model in ext.WEB_MODELS.values():
            record = matrix[model]["target_extensions"][project]
            for arm in paper.METHODS:
                info = find_cell(matrix, f"web-bench/{project}", model, arm)
                if arm in record["passed"]:
                    assert (info["score"], info["denominator"]) == (record["passed"][arm], len(record["targets"]))
                    assert info["targets"] == record["targets"]
                    rows = read(ROOT / info["method_record"])["models"][model]
                    matches = [r for r in rows if r["task"] in info["targets"]
                               and all(r[k] == v for k, v in info["record_filter"].items())]
                    assert len(matches) == info["denominator"]
                    assert sum(r["passed"] is True for r in matches) == info["score"]
                elif arm in record["excluded_build_arms"]:
                    assert info["status"] == "build_failed"
                    assert "score" not in info

    # The successful second complete-document library must not replace Gemma's failed first build.
    gemma = ext.WEB_MODELS["gemma"]
    assert read(ext.CALC)["libraries"]["gemma"]["b"]["status"] == "valid"
    rejected = find_cell(matrix, "web-bench/calculator", gemma, "self")
    assert rejected["status"] == "build_failed" and "denominator" not in rejected
    assert [r["status"] for r in rejected["build_attempts"]] == ["build_failed", "build_failed"]

    model = "mistralai/ministral-3b-2512"
    choice = find_cell(matrix, "todomvc", model, "self")
    assert choice["configuration_record"] == ext.relative(ext.CHOICES)
    assert choice["record_filter"] == {"arm": "a"}
    rows = read(ROOT / choice["method_record"])["models"][model]["rows"]
    planned = {r["task"] for r in rows if r["arm"] == "a" and r["passed"]}
    fixed = {r["task"] for r in rows if r["arm"] == "fixed-a" and r["passed"]}
    assert planned == fixed and len(planned) == choice["score"] == 6 and choice["denominator"] == 8


def test_example_choice_requires_the_selected_fixed_pages_report():
    import pytest
    from studies.paper_target_extensions import example_outcomes

    fixed = dict(arm="fixed-1", status="valid", task=2, passed=True, report_sha256="a" * 64)
    selected = dict(fixed, arm="selected", choice=1)
    assert example_outcomes([fixed, selected]) == {2: True}
    with pytest.raises(ValueError, match="same|share"):
        example_outcomes([fixed, dict(selected, report_sha256="b" * 64)])


def test_calculator_compiler_fallback_cannot_rescue_a_valid_but_incorrect_page():
    import pytest
    from studies.paper_target_extensions import compiler_outcomes

    native = dict(task=1, arm="native", status="valid", passed=False,
                  files_digest="0" * 64, report_sha256="a" * 64)
    final = dict(native, arm="final", choice=None, triggered=False)
    fixed = dict(native, arm="fixed-0", passed=True,
                 files_digest="1" * 64, report_sha256="b" * 64)
    fixed2 = dict(fixed, arm="fixed-1")
    assert compiler_outcomes([native, final, fixed, fixed2]) == {1: False}
    substituted = dict(fixed, arm="final", choice=0, triggered=True)
    with pytest.raises(ValueError, match="compiler rejection"):
        compiler_outcomes([native, substituted, fixed, fixed2])
    invalid = dict(native, status="invalid", files_digest=None, report_sha256=None)
    assert compiler_outcomes([invalid, substituted, fixed, fixed2]) == {1: True}
    missing = dict(invalid, status="missing", passed=None)
    with pytest.raises(ValueError, match="compiler rejection"):
        compiler_outcomes([missing, substituted, fixed, fixed2])


def test_file_baseline_publishes_all_four_decodings_including_malformed_deliveries():
    from studies import paper_target_extensions as ext
    from studies.lookup import MATRIX, find_cell
    from studies.study_io import ROOT, read

    matrix, corrected = read(ROOT / MATRIX), read(ext.DIRECT)
    assert corrected["paid_calls"] == 0
    assert set(corrected["models"]) == {*ext.WEB_MODELS.values(), ext.components.QWEN9, ext.components.FLASH}
    for model, rows in corrected["models"].items():
        info = find_cell(matrix, "web-bench/dom1", model, "direct")
        assert info["method_record"] == ext.relative(ext.DIRECT)
        assert sorted(r["task"] for r in rows) == info["targets"] == list(range(1, 21))
        assert all(len(r["response"]) == 64 for r in rows)
        assert all(r["passed"] is False for r in rows if r["format"] == "invalid")
        assert sum(r["passed"] is True for r in rows) == info["score"]


def test_module_rebuild_scores_and_missing_delivery_are_traceable_to_receipts():
    from studies import paper_module_rebuilds as rebuilds
    from studies.lookup import MATRIX, find_cell
    from studies.paper_component_followup import outcomes
    from studies.study_io import ROOT, read

    matrix = read(ROOT / MATRIX)
    # Audit the original 403 receipt independently of the subsequent GPT-5 delivery.
    matrix = {m: {k: v for k, v in row.items() if k not in ("calculator_profiles", "table_shared_selection")} for m, row in matrix.items()}
    earlier = {
        model: {k: v for k, v in row.items() if k not in ("module_rebuilds", "calculator_profiles")}
        for model, row in matrix.items()
    }
    for model, entry in matrix.items():
        for project, row in entry.get("module_rebuilds", {}).items():
            dataset = "web-bench/" + project
            for method in row["inherited_methods"]:
                assert find_cell(matrix, dataset, model, method) == find_cell(earlier, dataset, model, method)
            for method in ("self", "gpt5-library"):
                if method in row["inherited_methods"]:
                    continue
                cell = find_cell(matrix, dataset, model, method)
                record = read(ROOT / cell["method_record"])
                arm = cell["record_filter"]["arm"]
                observations = outcomes(record["models"][model], arm)
                assert set(observations) == set(row["targets"]) == set(range(1, 21))
                if cell["status"] == "measured":
                    assert None not in observations.values()
                    assert (cell["score"], cell["denominator"]) == (sum(observations.values()), 20)
                else:
                    assert "score" not in cell and "denominator" not in cell
                    assert all(v is None for v in observations.values())
                    prior = find_cell(earlier, dataset, model, method)
                    if prior["status"] == "measured":
                        assert cell["previous_measurement"]["score"] == prior["score"]
                        assert cell["previous_measurement"]["denominator"] == prior["denominator"]
                if project == "calculator" and method == "gpt5-library":
                    assert cell["status"] == "unavailable" and "403" in cell["unavailable_reason"]
                    assert ROOT / cell["historical_method_record"] == rebuilds.previous.FALLBACK
                    assert find_cell(earlier, dataset, model, method)["score"] == 10
                if project == "table" and method == "gpt5-library":
                    assert arm == "combined" and ROOT / cell["method_record"] == rebuilds.TABLE
                    profiles = {
                        a: {r["task"]: r["profile"] for r in record["models"][model] if r["arm"] == a}
                        for a in ("original", "review", "trace", "combined")
                    }
                    assert all(p == profiles["original"] for p in profiles.values())


def test_frozen_table_event_handlers_share_target_choices_with_the_original_implementation():
    from studies import paper_module_rebuilds as builds
    from studies.study_io import read

    result = read(builds.HOOKS)
    for rows in result["models"].values():
        planned = {r["task"]: r["count"] for r in rows if r["arm"] == "self"}
        original = {r["task"]: r["count"] for r in rows if r["arm"] == "original-same-choice"}
        assert planned == original and set(planned) == set(range(1, 21))
        assert not any(r["passed"] for r in rows if r["arm"] == "binding-only")
    for library in result["libraries"].values():
        if library["status"] == "valid":
            admitted = [t for t in library["trials"] if t["status"] == "valid"]
            assert len(admitted) == 1 and admitted[0]["attempt"] == library["attempt"]
            final = admitted[0]["events"][-1]["checks"]
            assert not final["errors"] and all(final["checks"][k] for k in ("menu", "insert", "outside", "click"))


def test_handler_subsets_keep_the_first_admitted_composition_and_compare_identical_choices():
    from studies import paper_module_rebuilds as builds
    from studies.study_io import read

    selected, prior = read(builds.SELECT), read(builds.DOM)
    for tag, library in selected["libraries"].items():
        assert prior["libraries"][tag]["status"] == "build_failed"
        tested = [obs for trial in library["trials"] for obs in trial["checks"]]
        if library["status"] == "valid":
            assert not any(t["admitted"] for t in tested[:-1]) and tested[-1]["admitted"]
            final = tested[-1]["checks"]
            assert not final["errors"] and all(final["checks"][key] for key in ("menu", "insert", "outside", "click"))
        else:
            assert not any(t["admitted"] for t in tested)
    for rows in selected["models"].values():
        counts = {
            arm: {r["task"]: r["count"] for r in rows if r["arm"] == arm}
            for arm in ("self", "original-same-choice", "unpatched-same-choice")
        }
        assert set(counts["self"]) == set(range(1, 21))
        assert counts["self"] == counts["original-same-choice"] == counts["unpatched-same-choice"]
