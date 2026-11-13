"""Boundary checks for the public-feedback implementation intervention."""
import json
import pytest
from test.library_repair import core
from test.library_repair.evaluator import public_feedback


def test_development_observations_only_enter_feedback_condition(monkeypatch):
    monkeypatch.setattr(core, 'requirements', lambda p: ['PUBLIC_REQUIREMENTS'])
    monkeypatch.setattr(core, 'original_package', lambda p, b: {'marker': 'ORIGINAL_PACKAGE'})
    public = {f'task-{k}': {'plan': {'x': k}, 'feedback': ['UNIQUE_BEHAVIOR_OBSERVATION']} for k in core.PUBLIC_TASKS}
    review = json.dumps(core.messages_for('p', 'b', 'review', public))
    feedback = json.dumps(core.messages_for('p', 'b', 'feedback', public))
    assert 'UNIQUE_BEHAVIOR_OBSERVATION' not in review
    assert 'UNIQUE_BEHAVIOR_OBSERVATION' in feedback
    assert set(core.PUBLIC_TASKS).isdisjoint(core.TEST_TASKS)
    with pytest.raises(AssertionError):
        core.messages_for('p', 'b', 'feedback', {**public, 'task-4': {'plan': {}, 'feedback': []}})


def test_feedback_rejects_other_test_files_and_removes_source():
    report = {'suites': [{'specs': [{'file': '/test/task-2.spec.js', 'title': 'Visible behavior',
        'tests': [{'results': [{'status': 'failed', 'errors': [{'message': 'Expected 3\n> 20 | hiddenSource();\n at secret.js:20'}]}]}]}]}]}
    observed = public_feedback(report, 'task-2')
    assert observed[0]['errors'] == ['Expected 3']
    with pytest.raises(AssertionError):
        public_feedback(report, 'task-6')


def test_revision_cannot_replace_schema_or_documentation(monkeypatch):
    original = {'files': {'index.html': 'old'}, 'compiler': 'old', 'plan_schema': {'type': 'object'},
                'examples': [{'plan': {}}], 'plan_documentation': 'fixed'}
    monkeypatch.setattr(core, 'compile_plan', lambda package, plan: package['files'])
    patch = {'files': {'index.html': 'new'}, 'compiler': 'new'}
    result = core.repaired_package(original, patch)
    assert result['files']['index.html'] == 'new'
    assert result['plan_schema'] == original['plan_schema']
    assert original['files']['index.html'] == 'old'
    with pytest.raises(ValueError):
        core.repaired_package(original, {**patch, 'plan_schema': {}})


def test_invalid_completed_response_falls_back_without_resampling(monkeypatch, tmp_path):
    from test.library_repair import run
    original = {'files': {'index.html': 'old'}, 'compiler': 'old', 'examples': []}
    public = {'p': {'b': {}}}
    core.dump(tmp_path / 'public-inputs.json', public)
    monkeypatch.setattr(run, 'OUT', tmp_path)
    monkeypatch.setattr(run, 'original_package', lambda p, b: original)
    monkeypatch.setattr(run, 'messages_for', lambda *args: [{'role': 'user', 'content': 'PUBLIC'}])
    class Client:
        count = 0
        def call(self, *args, **kwargs):
            self.count += 1
            return '{"plan_schema": {}}'
    client = Client()
    first = run.revise(client, 'p', 'b', 'review')
    second = run.revise(client, 'p', 'b', 'review', resume=True)
    assert first == second
    assert client.count == 1
    assert first['deployed'] == 'original_fallback'
    assert core.read(run.library_folder('p', 'b', 'review') / 'package.json') == original


def test_format_diagnostic_only_extracts_one_untouched_json_fence():
    from test.library_repair.format_replay import extract_single_fence
    body = '{"files":{"index.html":"unchanged"},"compiler":"literal source"}\n'
    assert extract_single_fence('Explanation\n```json\n' + body + '```\n') == body
    with pytest.raises(ValueError):
        extract_single_fence('```json\n{}\n```\n```json\n{}\n```')
    with pytest.raises(ValueError):
        extract_single_fence('Text before {"compiler":"do not guess"}')


def test_independent_raw_report_replay_does_not_count_skipped_tests_as_passes():
    from test.replay_library_repair import report_passed
    def report(statuses):
        return {'suites': [{'specs': [{'tests': [{'results': [{'status': s}]} for s in statuses]}]}]}
    assert report_passed(report(['passed', 'passed']))
    assert not report_passed(report(['passed', 'failed', 'skipped']))
    assert not report_passed(report(['skipped']))
    with pytest.raises(AssertionError):
        report_passed({'suites': []})
