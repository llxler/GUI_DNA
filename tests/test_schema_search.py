from test.schema_search.population import select
from test.webbench_expand.schema import validate


def test_search_covers_optional_omission_enum_integer_and_array_structure():
    schema = {'type': 'object', 'properties': {
        'optional': {'type': 'boolean'},
        'kind': {'type': 'string', 'enum': ['a', 'b']},
        'n': {'type': 'integer', 'minimum': 1, 'maximum': 9},
        'items': {'type': 'array', 'items': {'type': 'string', 'enum': ['a','b','c']},
                  'minItems': 1, 'maxItems': 3, 'uniqueItems': True}},
        'required': ['kind','n','items'], 'additionalProperties': False}
    anchor = {'optional': True, 'kind': 'a', 'n': 2, 'items': ['a','b']}
    selected = select(schema, [anchor], 100)
    values = [r['plan'] for r in selected['pool'].values()]
    for value in values: validate(schema, value)
    assert any('optional' not in v for v in values)
    assert any(v['kind'] == 'b' for v in values)
    assert {v['n'] for v in values} >= {1,2,5,9}
    assert any(v['items'] == ['b','a'] for v in values)
    assert any(v['items'] == ['a','b','c'] for v in values)
    reordered = {key: anchor[key] for key in reversed(anchor)}
    assert select(schema, [anchor], 4)['selected'] == select(schema, [reordered], 4)['selected']
