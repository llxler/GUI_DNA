"""Schema-only deterministic proposals, without test outcomes or project rules."""
from copy import deepcopy
from test.webbench_expand.schema import validate
from test.history_replay.run import digest


def representative(schema, high=False):
    kind = schema['type']
    if kind == 'boolean': return high
    if kind == 'integer': return schema['maximum' if high else 'minimum']
    if kind == 'string': return schema['enum'][-1 if high else 0]
    if kind == 'object':
        return {k: representative(schema['properties'][k], high) for k in schema['required']}
    count = schema.get('minItems', 0)
    if schema.get('uniqueItems') and schema['items']['type'] == 'string':
        values = schema['items']['enum']; values = list(reversed(values)) if high else values
        return values[:count]
    return [representative(schema['items'], high) for _ in range(count)]


def proposals(schema, value, path=()):
    kind = schema['type']
    if kind == 'string':
        for alt in schema['enum']:
            if alt != value: yield alt, {'path': path, 'operation': 'enum', 'value': alt}
    elif kind == 'integer':
        for alt in sorted({schema['minimum'], (schema['minimum'] + schema['maximum']) // 2, schema['maximum']}):
            if alt != value: yield alt, {'path': path, 'operation': 'integer-representative', 'value': alt}
    elif kind == 'object':
        for key, child in sorted(schema['properties'].items()):
            if key in value:
                if key not in schema['required']:
                    alt = deepcopy(value); del alt[key]
                    yield alt, {'path': (*path,key), 'operation': 'omit'}
                for replacement, op in proposals(child, value[key], (*path,key)):
                    alt = deepcopy(value); alt[key] = replacement
                    yield alt, op
            else:
                for high in (False, True):
                    alt = deepcopy(value); alt[key] = representative(child, high)
                    yield alt, {'path': (*path,key), 'operation': 'insert-max' if high else 'insert-min'}
    elif kind == 'array':
        alternatives = [('reverse', list(reversed(value))), ('rotate', value[1:] + value[:1]),
                        ('minimum-length', value[:schema.get('minItems',0)])]
        if len(value) < schema['maxItems']:
            if schema.get('uniqueItems') and schema['items']['type'] == 'string':
                rest = [v for v in schema['items']['enum'] if v not in value]
                alternatives += [('maximum-length', value + rest[:schema['maxItems'] - len(value)])]
            else:
                alternatives += [('maximum-length', value + [representative(schema['items']) for _ in range(schema['maxItems']-len(value))])]
        for name, alt in alternatives:
            if alt != value: yield alt, {'path': path, 'operation': name}
        for i, child in enumerate(value):
            for replacement, op in proposals(schema['items'], child, (*path,i)):
                alt = deepcopy(value); alt[i] = replacement
                yield alt, op


def select(schema, anchors, limit=32):
    pool, anchor_keys, rejected = {}, [], []
    for i, anchor in enumerate(anchors):
        validate(schema, anchor)
        key = digest(anchor)
        if key not in anchor_keys: anchor_keys.append(key)
        pool.setdefault(key, {'plan': anchor, 'origins': []})['origins'].append({'anchor': i, 'operation': 'unchanged'})
        for plan, operation in proposals(schema, anchor):
            try: validate(schema, plan)
            except ValueError as error:
                rejected.append({'anchor': i, 'operation': operation, 'reason': str(error)}); continue
            key = digest(plan)
            pool.setdefault(key, {'plan': plan, 'origins': []})['origins'].append({'anchor': i, **operation})
    selected = anchor_keys + [k for k in sorted(pool) if k not in anchor_keys][:max(0,limit-len(anchor_keys))]
    return {'anchors': anchors, 'pool': pool, 'rejected': rejected, 'selected': selected}
