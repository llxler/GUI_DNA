import copy
import pytest
from test.webbench_expand.schema import check_schema, validate
from test.webbench_expand.core import PROJECTS, builder_messages, planner_messages, requirements


def schema():
    return {'type': 'object', 'properties': {
        'enabled': {'type': 'boolean'},
        'choices': {'type': 'array', 'maxItems': 3, 'uniqueItems': True,
                    'items': {'type': 'string', 'enum': ['basic', 'advanced']}},
        'count': {'type': 'integer', 'minimum': 0, 'maximum': 5}},
        'required': ['enabled'], 'additionalProperties': False}


def test_closed_contract_rejects_code_maps_and_unknown_nested_data():
    s = schema()
    check_schema(s)
    validate(s, {'enabled': True, 'choices': ['basic'], 'count': 2})
    for invalid in ({'files': {'index.html': '<script>alert(1)</script>'}},
                    {'enabled': True, 'source': 'eval(1)'},
                    {'enabled': True, 'choices': ['eval(1)']},
                    {'enabled': True, 'count': True},
                    {'enabled': True, 'count': 100},
                    {'enabled': True, 'choices': ['basic', 'basic']},
                    {'enabled': 'true'}):
        with pytest.raises(ValueError):
            validate(s, invalid)


def test_builder_cannot_open_string_or_object_boundary():
    for bad in ({'type': 'string'}, {'type': 'string', 'enum': ['index.html']},
                {'type': 'object', 'properties': {}, 'required': [], 'additionalProperties': True},
                {'type': 'array', 'items': {'type': 'boolean'}},
                {'type': 'integer', 'minimum': 0, 'maximum': 5, 'default': 0}):
        with pytest.raises(ValueError):
            check_schema(bad)
    s = copy.deepcopy(schema())
    s['properties']['choices']['items'] = {'type': 'string', 'enum': ['<script>']}
    with pytest.raises(ValueError):
        check_schema(s)


def test_public_only_boundary_and_matched_library_inputs():
    for project in PROJECTS:
        rows = requirements(project)
        assert len(rows) == 21
        assert all(set(r) == {'id', 'description'} for r in rows)
        build = builder_messages(project)
        assert len(build) == 2 and rows[-1]['description'] in build[1]['content']
        package = {'plan_schema': schema(), 'files': {'frozen.js': '/* library */'}}
        plan = planner_messages(project, 'task-1', 'plan', package)
        code = planner_messages(project, 'task-1', 'free_lib', package)
        assert plan[1] == code[1]
        assert rows[1]['description'] in plan[1]['content']
        assert rows[-1]['description'] not in plan[1]['content']
        assert 'ALREADY PRESENT' in code[0]['content']


def test_transport_resume_retains_failed_attempt_and_its_feedback(tmp_path, monkeypatch):
    import json
    from gui_dna.budget import Ledger
    from test.webbench_expand import resume
    folder = tmp_path / 'libraries/calculator/builder'
    folder.mkdir(parents=True)
    Ledger(tmp_path / 'budget.sqlite3', 1, .9)
    messages = [{'role': 'system', 'content': 'build'}, {'role': 'user', 'content': 'public'}]
    (folder / 'messages.json').write_text(json.dumps(messages))
    (folder / 'output-0.json').write_text(json.dumps({'text': 'first invalid package'}))
    record = {'project': 'calculator', 'builder': 'builder', 'status': 'transport_incomplete',
              'attempts': [{'attempt': 0, 'feedback': ['original format error']}], 'manual_edits': []}
    path = folder / 'record.json'
    path.write_text(json.dumps(record))
    expected = resume.continuation_messages(folder, record, True)
    seen = []

    class Client:
        def call(self, model, current, out, purpose, seed):
            seen.append((current, out.name))
            assert current == expected and out.name == 'call-1'
            return '{}'

    monkeypatch.setattr(resume, 'validate_package', lambda package, target: [])
    resume.resume_one(Client(), tmp_path, path, True)
    result = json.loads(path.read_text())
    assert len(seen) == 1 and result['selected_attempt'] == 1
    assert result['attempts'][0] == record['attempts'][0]
    assert json.loads((folder / 'output-0.json').read_text())['text'] == 'first invalid package'


def test_full_compiler_is_preloaded_and_overrideable():
    from test.webbench_expand.generate import preloaded, output_files, messages_for, COMPILER_PATH, FILES_PATH
    package = {'files': {'placeholder.js': ''}, 'compiler': 'function compile(plan, files) { return {"index.html":"hello"}; }',
               'plan_schema': {'type': 'object', 'properties': {}, 'required': [], 'additionalProperties': False}}
    files = preloaded(package)
    assert files[COMPILER_PATH].startswith(package['compiler'])
    assert FILES_PATH in files
    assert 'placeholder.js' in files
    assert output_files('free_lib', package, {'files': {COMPILER_PATH: 'replaced', 'index.html': 'new'}})[COMPILER_PATH] == 'replaced'
    a = messages_for('calculator', 'task-1', 'plan', package)
    b = messages_for('calculator', 'task-1', 'free_lib', package)
    assert a[1] == b[1] and COMPILER_PATH in a[1]['content']
    built = output_files('free_lib', package, {'program': 'function build(files, compile) { const out = compile({unrestricted: true}, files); out["index.html"] += " modified"; return out; }'})
    assert built == {'index.html': 'hello modified'}
    with pytest.raises(ValueError):
        output_files('plan', package, {'unrestricted': True})


def test_planner_transport_resume_preserves_original_failed_attempt(tmp_path, monkeypatch):
    import json
    from gui_dna.budget import Ledger
    from test.webbench_expand import generate
    from test.webbench_expand.core import dump, digest
    monkeypatch.setattr(generate, 'OUT', tmp_path)
    monkeypatch.setattr(generate, 'public_check', lambda folder: [])
    Ledger(tmp_path / 'budget.sqlite3', 1, .9)
    package = {'plan_schema': {'type': 'object', 'properties': {}, 'required': [], 'additionalProperties': False},
               'files': {'index.html': 'ok'}, 'compiler': 'function compile(plan, files) { return files; }'}
    folder = tmp_path / 'runs/calculator/builder/planner/plan/task-4'
    original = generate.messages_for('calculator', 'task-4', 'plan', package)
    dump(folder / 'messages.json', original)
    dump(folder / 'output-0.json', {'text': '{"unrecognized":true}'})
    record = {'project': 'calculator', 'builder': 'builder', 'model': 'planner', 'method': 'plan',
              'task': 'task-4', 'status': 'transport_incomplete', 'versions': [], 'package_sha256': digest(package),
              'attempts': [{'attempt': 0, 'feedback': ['original schema feedback']}], 'error': 'disconnect'}
    dump(folder / 'record.json', record)
    expected = generate.continuation_messages(folder, record, False)
    calls = []

    class Client:
        def call(self, model, messages, out, purpose, seed):
            calls.append(out.name)
            assert messages == expected
            return '{}'

    result = generate.candidate(Client(), 'calculator', 'builder', 'planner', 'plan', 'task-4', package, resume=True)
    assert calls == ['call-1']
    assert result['versions'] == ['version-1'] and len(result['attempts']) == 2
    assert result['attempts'][0] == record['attempts'][0]
    assert result['status'] == 'complete'
