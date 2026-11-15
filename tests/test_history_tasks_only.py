from test.history_tasks_only.run import observed


def test_task_evidence_requires_executed_cases_and_keeps_decisive_failures():
    passed = {'passed': True, 'statuses': ['passed']}
    failed = {'passed': False, 'statuses': ['failed']}
    skipped = {'passed': False, 'statuses': ['skipped']}
    assert observed({'init': [failed], 'task-1': [skipped]}, ['task-1'])[0] is None
    assert observed({'init': [failed], 'task-1': [passed]}, ['task-1'])[0] is True
    assert observed({'task-1': [passed]}, ['task-1', 'task-2'])[0] is None
    assert observed({'task-1': [passed], 'task-2': [failed]}, ['task-1', 'task-2', 'task-3'])[0] is False
