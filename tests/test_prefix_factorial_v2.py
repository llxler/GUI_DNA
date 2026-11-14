import json
from test.prefix_factorial_v2.run import messages_for, plan_output_schema
from test.webbench_dna import domain
from test.webbench_dna.library import library


def test_shared_schema_explicitly_matches_flat_compiler_interface():
    schema = plan_output_schema()
    assert schema['additionalProperties'] is False and 'slots' not in schema['properties']
    for slot, options in domain.SLOTS.items():
        assert schema['properties'][slot] == {'type': 'string', 'enum': options}
    assert schema['properties']['menu']['type'] == 'object'
    assert schema['properties']['shortcuts']['type'] == 'object'
    task, lib = domain.tasks()[-1], library()
    a = messages_for(task, 'plan', '<html>shared</html>', lib)
    b = messages_for(task, 'free_lib', '<html>shared</html>', lib)
    assert a[1] == b[1]
    assert json.loads(a[1]['content'])['assembly_plan_schema'] == schema
    assert 'hidden' not in json.loads(a[1]['content'])
