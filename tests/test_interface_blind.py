"""Meaningful boundaries for the new interface-discovery experiment."""
import json

import pytest

from test.interface_blind import core


def test_public_input_has_no_derived_interface(monkeypatch):
    monkeypatch.setattr(core, 'requirements', lambda project: [{'id': 'init', 'description': 'PUBLIC_SENTINEL'}])
    prompt = json.dumps(core.builder_messages('form'))
    assert 'PUBLIC_SENTINEL' in prompt
    for forbidden in ('ROUTES', 'SLOTS', 'TEST_FEATURES', 'reference_plan', 'hidden.json', 'Question.root'):
        assert forbidden not in prompt


def test_same_library_and_requirements_in_matched_prompts(monkeypatch):
    monkeypatch.setattr(core, 'requirements', lambda project: [
        {'id': 'init', 'description': 'one'}, {'id': 'task-1', 'description': 'two'},
        {'id': 'task-2', 'description': 'FUTURE_SECRET'}])
    package = {'plan_schema': 'schema', 'files': {'a.js': 'SAME_BODY'}}
    free = core.planner_messages('form', 'task-1', 'free_lib', package)
    plan = core.planner_messages('form', 'task-1', 'plan', package)
    assert free[1] == plan[1]
    assert 'FUTURE_SECRET' not in str(plan)
    assert 'SAME_BODY' in str(free)


def test_generic_compiler_uses_model_schema_and_has_no_host_access():
    package = {'files': {'body.txt': 'hello'},
               'compiler': 'function compile(p, f) { if (!p.label) throw Error("label missing"); return {"index.html": f["body.txt"] + p.label}; }'}
    assert core.compile_plan(package, {'label': ' world'}) == {'index.html': 'hello world'}
    with pytest.raises(ValueError, match='label missing'):
        core.compile_plan(package, {})
    for expression in ('process.env', 'require("fs")', 'this.constructor.constructor("return process")()'):
        package['compiler'] = f'function compile() {{ return {expression}; }}'
        with pytest.raises(ValueError):
            core.compile_plan(package, {})


@pytest.mark.parametrize('name', ['../escape', '/tmp/escape', '.', 'a/../escape', 'a\\escape'])
def test_rejects_unsafe_output_paths(name):
    with pytest.raises(ValueError):
        core.validate_files({name: 'text'})
