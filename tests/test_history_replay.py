"""Scoring must distinguish missing/interrupted runs from decisive failures."""
from test.history_replay.run import cases_by_file


def test_history_parser_preserves_missing_and_interruptions():
    report={'suites':[{'suites':[{'specs':[{'file':'/tmp/test/task-2.spec.js','title':'retain identity',
        'tests':[{'results':[{'status':'passed'}]},{'results':[]},{'results':[{'status':'interrupted'}]}]}]}]}]}
    result=cases_by_file(report)['task-2']
    assert [x['passed'] for x in result]==[True,False,False]
    assert result[1]['statuses']==[]
    assert result[2]['statuses']==['interrupted']


def test_history_parser_uses_file_identity_not_duplicate_test_titles():
    report={'suites':[{'specs':[{'file':f'/test/{name}.spec.js','title':'same title',
        'tests':[{'results':[{'status':status}]}]} for name,status in [('init','passed'),('task-1','failed')]]}]}
    result=cases_by_file(report)
    assert result['init'][0]['passed']
    assert not result['task-1'][0]['passed']
