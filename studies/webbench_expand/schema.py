"""Small closed JSON-schema dialect, independent of project semantics.

Only bounded integers, booleans, identifier enums, closed objects and bounded
arrays are supported. No arbitrary strings, dynamic keys, references or code.
This is a format contract, not a proof about the generated compiler's behavior.
"""
from __future__ import annotations
import re

IDENTIFIER = re.compile(r'[A-Za-z][A-Za-z0-9_-]{0,63}\Z')


def check_schema(schema, path='$', depth=0):
    if depth > 12 or not isinstance(schema, dict):
        raise ValueError(f'{path}: schema must be an object of depth <=12')
    kind = schema.get('type')
    allowed = {'type', 'description'}
    if kind == 'object':
        allowed |= {'properties', 'required', 'additionalProperties'}
        props = schema.get('properties')
        if not isinstance(props, dict) or len(props) > 64:
            raise ValueError(f'{path}: properties must be an object with <=64 keys')
        if schema.get('additionalProperties') is not False:
            raise ValueError(f'{path}: additionalProperties must be false')
        required = schema.get('required')
        if not isinstance(required, list) or len(set(required)) != len(required) or any(k not in props for k in required):
            raise ValueError(f'{path}: required must list distinct property names')
        for key, child in props.items():
            if not IDENTIFIER.fullmatch(key):
                raise ValueError(f'{path}: property names must be simple identifiers')
            check_schema(child, f'{path}.{key}', depth + 1)
    elif kind == 'array':
        allowed |= {'items', 'minItems', 'maxItems', 'uniqueItems'}
        low, high = schema.get('minItems', 0), schema.get('maxItems')
        if type(low) is not int or type(high) is not int or not 0 <= low <= high <= 64:
            raise ValueError(f'{path}: array requires bounded minItems/maxItems within 0..64')
        if 'uniqueItems' in schema and type(schema['uniqueItems']) is not bool:
            raise ValueError(f'{path}: uniqueItems must be boolean')
        check_schema(schema.get('items'), path + '[]', depth + 1)
    elif kind == 'string':
        allowed |= {'enum'}
        values = schema.get('enum')
        if (not isinstance(values, list) or not 1 <= len(values) <= 128 or
                any(not isinstance(v, str) or not IDENTIFIER.fullmatch(v) for v in values) or
                len(set(values)) != len(values)):
            raise ValueError(f'{path}: strings require distinct identifier enum values; no free text or file paths')
    elif kind == 'integer':
        allowed |= {'minimum', 'maximum'}
        low, high = schema.get('minimum'), schema.get('maximum')
        if type(low) is not int or type(high) is not int or not -1000000 <= low <= high <= 1000000:
            raise ValueError(f'{path}: integers require minimum/maximum within +/-1000000')
    elif kind != 'boolean':
        raise ValueError(f'{path}: unsupported type {kind!r}')
    if set(schema) - allowed:
        raise ValueError(f'{path}: unsupported schema keys {sorted(set(schema) - allowed)}')
    if 'description' in schema and not isinstance(schema['description'], str):
        raise ValueError(f'{path}: description must be text')


def validate(schema, value, path='$'):
    kind = schema['type']
    if kind == 'object':
        if not isinstance(value, dict):
            raise ValueError(f'{path}: expected object')
        unknown = set(value) - set(schema['properties'])
        missing = set(schema['required']) - set(value)
        if unknown or missing:
            raise ValueError(f'{path}: unknown keys {sorted(unknown)}, missing keys {sorted(missing)}')
        for key, item in value.items():
            validate(schema['properties'][key], item, f'{path}.{key}')
    elif kind == 'array':
        if not isinstance(value, list) or not schema.get('minItems', 0) <= len(value) <= schema['maxItems']:
            raise ValueError(f'{path}: expected bounded array')
        if schema.get('uniqueItems') and any(v in value[:i] for i, v in enumerate(value)):
            raise ValueError(f'{path}: array items must be unique')
        for i, item in enumerate(value):
            validate(schema['items'], item, f'{path}[{i}]')
    elif kind == 'string':
        if not isinstance(value, str) or value not in schema['enum']:
            raise ValueError(f'{path}: expected one of {schema["enum"]}')
    elif kind == 'integer':
        if type(value) is not int or not schema['minimum'] <= value <= schema['maximum']:
            raise ValueError(f'{path}: expected bounded integer')
    elif type(value) is not bool:
        raise ValueError(f'{path}: expected boolean')
