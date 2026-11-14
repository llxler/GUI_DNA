import json

from test.prefix_factorial.run import messages_for
from test.webbench_dna import domain
from test.webbench_dna.library import library


def test_reference_prefix_methods_receive_identical_complete_material():
    lib = library()
    for task in (domain.tasks()[0], domain.tasks()[-1]):
        code = messages_for(task, 'free_lib', '<html>same starting page</html>', lib)
        plan = messages_for(task, 'plan', '<html>same starting page</html>', lib)
        assert code[1] == plan[1] and code[0] != plan[0]
        value = json.loads(code[1]['content'])
        assert value['requirements'] == task['descriptions']
        assert value['features'] == task['features']
        assert value['frozen_library'] == lib
        assert set(value) == {'requirements', 'features', 'starting_page_html', 'shell_contract',
                              'frozen_library', 'assembly_plan_schema'}


def test_prefix_change_does_not_drop_cumulative_information():
    task, lib = domain.tasks()[10], library()
    a = json.loads(messages_for(task, 'plan', '<html>own page</html>', lib)[1]['content'])
    b = json.loads(messages_for(task, 'plan', '<html>reference page</html>', lib)[1]['content'])
    assert a.pop('starting_page_html') != b.pop('starting_page_html')
    assert a == b and len(a['requirements']) == 11
