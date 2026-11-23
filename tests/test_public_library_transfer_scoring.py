import pytest

from studies.public_library_transfer.browser import TASKS, verdict, verify_page
from studies.public_library_transfer.report import MILESTONES, summarize, validate_rows
from studies.public_library_transfer.diagnostics.table_configurations.report import summary as configuration_summary
from studies.study_io import sha


def panel(arm, rep, tasks=TASKS):
    return [{'project': 'table', 'arm': arm, 'builder': None if arm == 'direct' else 'builder', 'rep': rep,
             'planner': None if arm == 'fixed' else 'planner', 'task': n, 'status': 'valid',
             'files': {'index.html': 'same'}, 'page': 'example', 'passed': n % 2 == 0} for n in tasks]


def test_shared_direct_targets_and_paired_missingness():
    first = panel('plan', 1)
    first[0].update(status='missing', files=None, page=None, passed=None)
    first[1].update(status='invalid', files=None, page=None, passed=None)
    rows = panel('direct', 0) + first + panel('plan', 2) + panel('fixed', 1) + panel('fixed', 2)
    validate_rows(rows)
    values = summarize(rows)
    direct = [r for r in values['groups'] if r['arm'] == 'direct']
    assert len(direct) == 1 and direct[0]['all_tasks']['planned'] == 20
    compared = [r for r in values['pairs'] if r['comparator'] == 'direct']
    a, b = (r['all_tasks'] for r in compared)
    assert (a['planned'], a['paired'], a['plan_passed'], a['comparator_passed']) == (20, 19, 9, 10)
    assert a['missing_tasks'] == [1] and a['comparator_only'] == 1
    assert (b['planned'], b['paired'], b['plan_passed'], b['comparator_passed']) == (20, 20, 10, 10)


def test_full_and_milestone_registrations_remain_distinct():
    short = panel('direct', 0, MILESTONES) + panel('plan', 1, MILESTONES)
    validate_rows(short)
    validate_rows(short, {'table': MILESTONES})
    assert summarize(short)['pairs'][0]['all_tasks']['paired'] == 5
    with pytest.raises(ValueError):
        validate_rows(short, {'table': TASKS})
    with pytest.raises(ValueError):
        validate_rows(panel('direct', 0) + panel('plan', 1, MILESTONES))
    with pytest.raises(ValueError):
        validate_rows(short[:-1])


def test_fixed_page_and_complete_candidate_file_manifest(tmp_path):
    rows = panel('fixed', 1)
    rows[0]['files'] = {'index.html': 'different'}
    with pytest.raises(ValueError, match='fixed control'):
        validate_rows(rows)
    page = tmp_path / 'index.html'
    page.write_text('<!DOCTYPE html>')
    manifest = {'index.html': sha(page)}
    verify_page(tmp_path, manifest, 'table')
    (tmp_path / 'extra.js').write_text('console.log(1)')
    with pytest.raises(ValueError, match='sealed file manifest'):
        verify_page(tmp_path, manifest, 'table')


def official_status(*statuses):
    specs = [{'file': 'test/task-2.spec.js', 'title': str(i), 'tests': [{'results': [{'status': s}]}]}
             for i, s in enumerate(statuses)]
    return {'suites': [{'specs': specs}]}


def test_official_verdict_requires_one_complete_file_or_a_decisive_failure():
    assert verdict(official_status('passed', 'passed'), 0, 2)
    assert not verdict(official_status('failed', 'skipped'), 1, 2)
    with pytest.raises(RuntimeError):
        verdict(official_status('passed', 'interrupted'), 1, 2)
    with pytest.raises(RuntimeError):
        verdict(official_status('passed'), 0, 3)
    infrastructure = official_status('failed')
    infrastructure['errors'] = [{'message': 'test runner crashed'}]
    with pytest.raises(RuntimeError):
        verdict(infrastructure, 1, 2)


def test_equal_counts_do_not_imply_that_one_fixed_page_covers_the_observed_set():
    settings = [
        {'id': 1, 'first_example': True, 'passed_tasks': [1, 2]},
        {'id': 2, 'first_example': False, 'passed_tasks': [2, 3]},
    ]
    actual = {'model': [{'task': 1, 'setting': 1, 'passed': True}, {'task': 3, 'setting': 2, 'passed': True}]}
    values = configuration_summary(settings, actual)
    assert values['all_best_fixed_setting_ids'] == [1, 2]
    assert values['uniform_expected_fraction'] == '2'
    assert values['oracle_passed'] == 3
    assert values['deployments']['model']['covering_setting_ids'] == []
    assert values['deployments']['model']['discordant_replays'] == []
