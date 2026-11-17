"""Scoring must distinguish missing/interrupted runs from decisive failures."""
from studies.study_io import cases_by_file


def test_report_parser_preserves_missing_and_interruptions():
    report={'suites':[{'suites':[{'specs':[{'file':'/tmp/test/task-2.spec.js','title':'retain identity',
        'tests':[{'results':[{'status':'passed'}]},{'results':[]},{'results':[{'status':'interrupted'}]}]}]}]}]}
    result=cases_by_file(report)['task-2']
    assert [x['passed'] for x in result]==[True,False,False]
    assert result[1]['statuses']==[]
    assert result[2]['statuses']==['interrupted']


def test_report_parser_uses_file_identity_not_duplicate_test_titles():
    report={'suites':[{'specs':[{'file':f'/test/{name}.spec.js','title':'same title',
        'tests':[{'results':[{'status':status}]}]} for name,status in [('init','passed'),('task-1','failed')]]}]}
    result=cases_by_file(report)
    assert result['init'][0]['passed']
    assert not result['task-1'][0]['passed']


def test_current_file_selection_and_retired_prefix_rejection(tmp_path, monkeypatch):
    import pytest
    from studies import browser_jobs
    assert browser_jobs.current_task_specs('task-5') == ['task-5']
    for specs in (['init', 'task-1'], ['task-1', 'task-2'], ['init', 'task-1', 'task-2']):
        with pytest.raises(ValueError, match='retired'):
            browser_jobs.grade('must-not-run', {'specs': specs})
    browser_jobs.check_explicit_specs(['task-20'])
    browser_jobs.check_explicit_specs(['init', 'task-4', 'task-8', 'task-12', 'task-16'])
    with pytest.raises(ValueError):
        browser_jobs.current_task_specs('init')
