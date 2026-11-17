"""Enumerate a finite optional-field schema; no scoring protocol."""
import itertools

def population(schema):
    assert schema['type'] == 'object' and not schema['required'] and schema['additionalProperties'] is False
    keys, domains = list(schema['properties']), []
    for child in schema['properties'].values():
        values = [False, True] if child['type'] == 'boolean' else child['enum']
        assert child['type'] in ('string', 'boolean') and None not in values
        domains.append([None, *values])
    return [{k: v for k, v in zip(keys, values) if v is not None} for values in itertools.product(*domains)]
