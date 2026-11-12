import pytest
from test.behavior_feedback import report_cases, split_cases


def test_public_hidden_partition_is_fixed_and_disjoint():
    cases = [{'title': str(i), 'line': i, 'file': 'task-4.spec.js'} for i in range(1, 8)]
    split = split_cases('form', 'task-4', cases)
    assert split == split_cases('form', 'task-4', list(reversed(cases)))
    assert len(split['public']) == 3 and len(split['hidden']) == 4
    assert {c['line'] for c in split['public']}.isdisjoint(c['line'] for c in split['hidden'])


def test_feedback_excludes_code_snippets_and_rejects_hidden_cases():
    expected = [{'line': 10, 'title': 'public behavior'}]
    data = {'suites': [{'specs': [{'line': 10, 'title': 'public behavior', 'tests': [
        {'results': [{'status': 'failed', 'errors': [{'message': 'expected value\n\n  23 |\n> 24 | publicAssertion()\n  25 | test("HIDDEN_NEIGHBOR")\n    at /hidden/path.spec.js:24:1', 'snippet': 'HIDDEN_NEIGHBOR', 'stack': 'source'}]}]}]}]}]}
    result = report_cases(data, expected)
    assert 'HIDDEN_NEIGHBOR' not in str(result)
    assert result['tests'][0]['errors'] == ['expected value']
    assert not result['all_passed']
    data['suites'][0]['specs'][0]['line'] = 11
    with pytest.raises(ValueError, match='Unexpected test'):
        report_cases(data, expected)
