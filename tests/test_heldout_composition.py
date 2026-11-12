import json
from copy import deepcopy
from itertools import product

import pytest

from test.heldout_composition.domain import PROJECTS, development, heldout, requirement
from test.heldout_composition.fixtures import cases
from test.heldout_composition.core import builder_messages, messages_for
from test.heldout_composition.controls import delta_plan


def package():
    return {'files': {'index.html': 'public source'}, 'compiler': 'function compile(p,f){return f;}',
            'examples': [{'id': f'dev-{i}', 'plan': {'choices': {f'option-{j}': i == j + 1 for j in range(4)}}}
                         for i in range(5)]}


def test_split_and_hidden_observations_distinguish_all_configurations():
    for project in PROJECTS:
        train = {tuple(t['policy']) for t in development(project)}
        test = {tuple(t['policy']) for t in heldout(project)}
        assert len(train) == 5 and len(test) == 11 and not train & test
        assert train | test == set(product((0, 1), repeat=4))
        observed = [cases(project, p) for p in product((0, 1), repeat=4)]
        assert len({json.dumps(x, sort_keys=True) for x in observed}) == 16
        actions = [[s['action'] for trace in row for s in trace['steps']] for row in observed]
        assert all(row == actions[0] for row in actions)


def test_builder_sees_development_only_and_generator_whitelists_fields():
    for project in PROJECTS:
        build = builder_messages(project)[1]['content']
        for task in heldout(project):
            assert json.dumps(task['requirement'], ensure_ascii=False) not in build
        t = deepcopy(heldout(project)[0])
        p = package()
        original = messages_for(project, t, 'plan', p)
        t.update(policy=['SECRET_POLICY'], hidden_assertions='SECRET_ASSERTION')
        assert original == messages_for(project, t, 'plan', p)
        assert original[1] == messages_for(project, t, 'free_lib', p)[1]
        assert 'SECRET_' not in original[1]['content']


def test_delta_control_uses_only_public_sentences_and_rejects_conflicts():
    p = package()
    for project in PROJECTS:
        result = delta_plan(project, requirement(project, (1, 0, 1, 0)), p)
        assert result == {'choices': {'option-0': True, 'option-1': False, 'option-2': True, 'option-3': False}}
        conflict = deepcopy(p)
        conflict['examples'][1]['plan'] = {'choices': 'one'}
        conflict['examples'][2]['plan'] = {'choices': 'two'}
        with pytest.raises(ValueError, match='Conflicting'):
            delta_plan(project, requirement(project, (1, 1, 0, 0)), conflict)


def test_resume_preserves_valid_attempt_and_original_feedback(tmp_path, monkeypatch):
    from gui_dna.budget import Ledger
    from test.heldout_composition import run
    from test.interface_blind.core import dump
    Ledger(tmp_path / 'budget.sqlite3', 1, .9)
    folder = tmp_path / 'runs/table/no_library/model/free/heldout-01'
    initial = [{'role': 'system', 'content': 'code'}, {'role': 'user', 'content': 'public'}]
    record = {'project': 'table', 'builder': None, 'model': 'model', 'method': 'free', 'task': 'heldout-01',
              'status': 'transport_incomplete', 'attempts': [{'attempt': 0, 'feedback': ['original format failure']}], 'versions': []}
    dump(folder / 'record.json', record)
    dump(folder / 'messages.json', initial)
    dump(folder / 'output-0.json', {'text': 'first valid transport but invalid output'})
    expected = run.resume_messages(folder, record, initial, False)
    monkeypatch.setattr(run, 'public_check', lambda path: [])
    seen = []

    class Client:
        def call(self, model, messages, out, purpose, seed):
            assert messages == expected
            seen.append(out.name)
            return '{"files":{"index.html":"ok"}}'

    result = run.attempt_loop(Client(), tmp_path, folder, record, initial, False, resume=True)
    assert seen == ['call-1'] and result['status'] == 'complete'
    assert result['attempts'][0] == record['attempts'][0]
    assert result['versions'] == ['version-1']


def test_crash_after_success_does_not_trigger_an_extra_sample(tmp_path):
    from test.heldout_composition import run
    from test.interface_blind.core import dump
    initial = [{'role': 'user', 'content': 'public'}]
    record = {'status': 'in_progress', 'attempts': [{'attempt': 0, 'feedback': []}]}
    dump(tmp_path / 'record.json', record)
    dump(tmp_path / 'messages.json', initial)

    class Client:
        def call(self, *args, **kwargs):
            raise AssertionError('A successful sample must not be regenerated')

    result = run.attempt_loop(Client(), tmp_path, tmp_path, record, initial, False, resume=True)
    assert result['status'] == 'complete' and len(result['attempts']) == 1
