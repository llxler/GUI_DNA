"""Information-boundary and compiler-access checks for the draw protocol."""
import pytest
from test.webbench_draw.core import planner_messages, requirements, output_files


def package():
    return {'design':'small fixture','plan_documentation':'toggle behavior',
        'plan_schema':{'type':'object','properties':{'enabled':{'type':'boolean'}},
            'required':['enabled'],'additionalProperties':False},
        'files':{'index.html':'<!doctype html><body>source</body>'},
        'compiler':"function compile(plan, files) { return {'index.html':'<!doctype html><body>'+String(plan.enabled)+'</body>'}; }",
        'examples':[]}


def test_same_library_information_and_cumulative_public_prefix():
    frozen = package()
    plan = planner_messages(4,'plan',frozen)
    code = planner_messages(4,'free_lib',frozen)
    assert plan[1] == code[1]
    assert all(set(row) == {'id','description'} for row in requirements())
    assert '"id": "task-4"' in plan[1]['content']
    assert '"id": "task-5"' not in plan[1]['content']
    assert 'test.beforeEach' not in plan[1]['content']


def test_free_code_can_call_compiler_outside_closed_plan_schema():
    frozen = package()
    with pytest.raises(ValueError):
        output_files('plan',frozen,{'enabled':'outside_schema'})
    files = output_files('free_lib',frozen,{'program':
        "function build(files, compile) { return compile({enabled:'outside_schema'}, files); }"})
    assert 'outside_schema' in files['index.html']
    assert frozen['files']['index.html'].endswith('source</body>')


def test_candidate_paths_cannot_escape_page_root(tmp_path):
    from test.webbench_draw.core import write_source
    with pytest.raises(ValueError):
        write_source(tmp_path/'page',{'index.html':'ok','../outside.js':'no'})
    assert not (tmp_path/'outside.js').exists()
