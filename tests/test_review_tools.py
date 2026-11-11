"""Guard scientific reporting boundaries and the review-stage spending controls."""
import json
import sqlite3

import pytest

from test import random_plans, review_checks, review_stage, review_metrics
from test.ledger_read import ReadOnlyLedger, totals
from test.todomvc_dna import review_evaluate
from test.rerun_failed import affected
from test.webbench_dna.continue_clean_prefix import prepare


def test_reporting_does_not_tighten_ledger_or_create_missing_database(tmp_path):
    path = tmp_path / 'budget.sqlite3'
    assert ReadOnlyLedger(path).summary()['calls'] == []
    assert not path.exists()
    with sqlite3.connect(path) as db:
        db.executescript('''
            CREATE TABLE policy (id, cap, stop, halted);
            INSERT INTO policy VALUES (1, 2800000, 2600000, 0);
            CREATE TABLE calls (id, purpose, model, status, reserved, actual, created);
            INSERT INTO calls VALUES ('a', 'test', 'model', 'settled', 20000, 5000, 'now');
            INSERT INTO calls VALUES ('b', 'test', 'model', 'reserved', 30000, NULL, 'now');
        ''')
    before = path.read_bytes()
    assert ReadOnlyLedger(path).summary()['actual_usd'] == .005
    assert totals(path)['exposure_usd'] == .035
    assert totals(path)['cap_usd'] == 2.8
    assert path.read_bytes() == before


def test_partial_enumeration_does_not_treat_missing_as_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(random_plans, 'OUT', tmp_path)
    task = {'id': 'task'}
    variants = [{'slot': 'a'}, {'slot': 'b'}]
    saved = tmp_path / 'suite/task/a/result.json'
    saved.parent.mkdir(parents=True)
    saved.write_text(json.dumps({'passed': 2, 'total': 2, 'all_passed': True}))
    result = random_plans.summarise('suite', [(task, a) for a in variants],
                                    lambda _: variants[0], lambda _: variants[1])
    assert not result['complete']
    assert result['tasks'][0]['p_pass'] is None
    assert result['tasks'][0]['rule_passes'] is None
    assert 'expected_tasks_passed' not in result


def test_protocol_comparison_uses_same_observed_candidates_in_every_column(tmp_path, monkeypatch):
    monkeypatch.setattr(review_metrics, 'ROOT', tmp_path)
    path = tmp_path / 'test/webbench_dna/results/clean-prefix.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'models': {'model': {'passes': {
        'free': [True, False], 'free_clean': [None, False],
        'dna_inc': [True, True], 'dna': [True, True]}}}}))
    result = review_metrics.matched_protocol()
    assert result['n'] == 1
    assert result['passed'] == {'free': 0, 'free_clean': 0, 'dna_inc': 1, 'dna': 1}
    assert result['models']['model']['excluded_task_numbers'] == [1]


def test_executed_plan_precedes_later_rejected_attempt(monkeypatch):
    record = {'versions': ['r0', 'r1'], 'attempts': [
        {'attempt': 0, 'plan': {'value': 'first'}},
        {'attempt': 1, 'plan': {'value': 'executed'}},
        {'attempt': 2, 'plan': {'value': 'rejected'}}]}
    monkeypatch.setattr(review_checks, 'saved_record', lambda *args: record)
    assert review_checks.saved_plan('suite', 'model', {}) == {'value': 'executed'}
    assert review_checks.saved_plan('suite', 'model', {}, phase='first_attempt') == {'value': 'first'}


def test_generation_manifest_refuses_changed_inputs(tmp_path, monkeypatch):
    monkeypatch.setattr(review_stage, 'ROOT', tmp_path)
    module = tmp_path / 'test/review_stage.py'
    module.parent.mkdir()
    module.write_text('# frozen\n')
    monkeypatch.setattr(review_stage, '__file__', str(module))
    source = tmp_path / 'source.py'
    source.write_text('value = 1\n')
    stage = tmp_path / 'stage'
    review_stage.freeze(stage, {'seed': 1}, ['source.py'], 'protocol')
    review_stage.freeze(stage, {'seed': 1}, ['source.py'], 'protocol')
    source.write_text('value = 2\n')
    with pytest.raises(ValueError, match='use a new stage'):
        review_stage.freeze(stage, {'seed': 1}, ['source.py'], 'protocol')


@pytest.mark.parametrize('arm, expected', [('dna_inc', 2), ('free_clean', 1)])
def test_transport_rerun_respects_control_dependencies(tmp_path, arm, expected):
    for k in [1, 2, 3]:
        folder = tmp_path / 'runs/model' / arm / f'task-{k}'
        folder.mkdir(parents=True)
        (folder / 'record.json').write_text(json.dumps({'attempts': [
            {'compile_error': 'ProviderError: connection dropped' if k == 2 else None}]}))
    moves = affected(tmp_path, 'webbench')
    assert len(moves) == expected
    assert {p.name for p, _ in moves} == ({'task-2', 'task-3'} if arm == 'dna_inc' else {'task-2'})


def test_continuation_preserves_source_and_archives_incomplete_requests(tmp_path):
    source, out = tmp_path / 'source', tmp_path / 'new'
    for k in [1, 2, 3]:
        folder = source / 'runs/model/free_clean' / f'task-{k}'
        folder.mkdir(parents=True)
        if k < 3:
            (folder / 'record.json').write_text(json.dumps({'attempts': [
                {'compile_error': 'ProviderError: dropped' if k == 2 else None}]}))
        else:
            (folder / 'request.json').write_text('{}')
    before = {str(p.relative_to(source)): p.read_bytes() for p in source.rglob('*') if p.is_file()}
    prepare(source, out)
    assert (out / 'runs/model/free_clean/task-1/record.json').exists()
    assert not (out / 'runs/model/free_clean/task-2').exists()
    assert not (out / 'runs/model/free_clean/task-3').exists()
    assert len(json.loads((out / 'continuation.json').read_text())['archived']) == 2
    assert before == {str(p.relative_to(source)): p.read_bytes() for p in source.rglob('*') if p.is_file()}
    prepare(source, out)


@pytest.mark.parametrize('statuses, expected', [
    (['passed', 'passed'], True), (['failed', 'skipped'], False),
    (['passed', 'skipped'], None)])
def test_early_stop_needs_counterexample_or_complete_pass(tmp_path, monkeypatch, statuses, expected):
    report = tmp_path / 'report.json'
    monkeypatch.setattr(review_evaluate.domain, 'hidden_subset', lambda _: [('group', 'one'), ('group', 'two')])
    monkeypatch.setattr(review_evaluate.evaluate, 'browser_env', lambda: {})

    def run(*args, **kwargs):
        command = args[0]
        assert command[command.index('--output') + 1] == str(report.parent / 'playwright-output')
        specs = [{'title': title, 'tests': [{'results': [{'status': status}]}]}
                 for title, status in zip(['one', 'two'], statuses)]
        report.write_text(json.dumps({'suites': [{'suites': [{'title': 'group', 'specs': specs}]}]}))
        return type('Process', (), {'stderr': ''})()

    monkeypatch.setattr(review_evaluate.subprocess, 'run', run)
    if expected is None:
        with pytest.raises(RuntimeError, match='neither a counterexample'):
            review_evaluate.grade('http://example.invalid', report, [])
    else:
        result = review_evaluate.grade('http://example.invalid', report, [])
        assert result['all_passed'] is expected
        assert result['test_counts_complete'] is expected
