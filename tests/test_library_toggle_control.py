from copy import deepcopy

from test.library_toggle_control.run import boolean_paths, variant
from test.webbench_expand.schema import validate


def test_boolean_slice_keeps_integers_structure_and_source_unchanged():
    anchor = {'zero': 0, 'one': 1, 'flags': {'enabled': True}, 'items': [False, {'n': 2, 'b': True}]}
    before = deepcopy(anchor)
    paths = boolean_paths(anchor)
    assert paths == [('flags', 'enabled'), ('items', 0), ('items', 1, 'b')]
    observed = set()
    for mask in range(8):
        changed = variant(anchor, paths, mask)
        assert changed['zero'] == 0 and type(changed['zero']) is int
        assert changed['one'] == 1 and type(changed['one']) is int
        assert changed['items'][1]['n'] == 2 and len(changed['items']) == 2
        observed.add((changed['flags']['enabled'], changed['items'][0], changed['items'][1]['b']))
    assert len(observed) == 8 and anchor == before


def test_boolean_slice_does_not_populate_optional_schema_fields():
    schema = {'type': 'object', 'properties': {'omitted': {'type': 'boolean'},
        'present': {'type': 'boolean'}, 'size': {'type': 'integer', 'minimum': 0, 'maximum': 2}},
        'required': ['present', 'size'], 'additionalProperties': False}
    anchor = {'present': True, 'size': 1}
    for mask in range(2):
        plan = variant(anchor, boolean_paths(anchor), mask)
        validate(schema, plan)
        assert set(plan) == set(anchor) and plan['size'] == 1
    assert variant({'size': 1}, [], 0) == {'size': 1}
