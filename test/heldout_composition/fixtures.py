"""Evaluator-only oracle and traces; never serialized into model messages.

Public development observations are exported separately before model calls.
Hidden traces are identical across policies, preventing action order from
revealing the target policy to a fixed page.
"""
from copy import deepcopy

PUBLIC = {
    'calculator': [
        [('enter', 5), ('add',), ('save',), ('enter', 2), ('add',), ('recall',), ('clear',), ('recall',), ('history', 0)],
        [('enter', 7), ('add',), ('enter', 3), ('subtract',), ('enter', 4), ('add',), ('history', 1), ('save',), ('clear',), ('recall',), ('add',)],
    ],
    'table': [
        [('select', 'a'), ('copy',), ('edit', 9), ('sort',), ('select', 'b'), ('paste',), ('delete',)],
        [('select', 'b'), ('copy',), ('edit', 8), ('select', 'c'), ('paste',), ('sort',), ('delete',), ('select', 'a'), ('paste',)],
    ],
}
HIDDEN = {
    'calculator': [
        [('enter', 4), ('add',), ('add',), ('save',), ('enter', 3), ('subtract',), ('recall',), ('history', 0)],
        [('enter', 6), ('add',), ('save',), ('enter', -2), ('add',), ('clear',), ('recall',), ('history', 1)],
        [('enter', 9), ('subtract',), ('save',), ('enter', 2), ('add',), ('history', 0), ('recall',), ('clear',), ('recall',)],
        [('enter', 3), ('add',), ('enter', 8), ('add',), ('save',), ('history', 0), ('subtract',), ('clear',), ('history', 1), ('recall',)],
    ],
    'table': [
        [('select', 'a'), ('copy',), ('edit', 11), ('sort',), ('paste',), ('delete',)],
        [('select', 'b'), ('copy',), ('edit', -3), ('select', 'c'), ('paste',), ('sort',), ('delete',), ('select', 'a'), ('paste',)],
        [('select', 'c'), ('copy',), ('delete',), ('paste',), ('sort',), ('select', 'a'), ('edit', 2), ('sort',), ('delete',)],
        [('select', 'a'), ('edit', 2), ('copy',), ('select', 'c'), ('paste',), ('sort',), ('delete',), ('sort',), ('delete',), ('delete',), ('copy',), ('paste',)],
        [('select', 'b'), ('sort',), ('copy',), ('edit', 4), ('sort',), ('delete',), ('paste',)],
    ],
}


def initial(project):
    if project == 'calculator':
        return {'total': 0, 'memory': 0, 'entry': '', 'history': []}
    return {'rows': [['a', 7], ['b', 2], ['c', 5]], 'selected': None, 'clip': None}


def clipboard(state):
    c = state['clip']
    if c is None:
        return None
    if c[0] == 'value':
        return c[1]
    return next((r[1] for r in state['rows'] if r[0] == c[1]), None)


def snapshot(project, state):
    if project == 'calculator':
        return deepcopy(state)
    return {'rows': deepcopy(state['rows']), 'selected': state['selected'], 'clipboard': clipboard(state)}


def step(project, state, action, policy):
    name, *args = action
    if project == 'calculator':
        if name == 'enter':
            state['entry'] = str(args[0])
        elif name in ('add', 'subtract'):
            state['total'] += int(state['entry'] or 0) * (1 if name == 'add' else -1)
            state['history'].append(state['total'])
            if not policy[0]:
                state['entry'] = ''
        elif name == 'save':
            state['memory'] = state['total']
        elif name == 'recall':
            state['total'] = state['memory'] + (state['total'] if policy[1] else 0)
        elif name == 'clear':
            state['total'], state['entry'] = 0, ''
            if policy[2]:
                state['memory'] = 0
        elif name == 'history' and 0 <= args[0] < len(state['history']):
            state['total'] = state['history'][args[0]] + (state['total'] if policy[3] else 0)
        return
    rows = state['rows']
    index = next((i for i, r in enumerate(rows) if r[0] == state['selected']), None)
    if name == 'select':
        if any(r[0] == args[0] for r in rows):
            state['selected'] = args[0]
    elif name == 'sort':
        rows.sort(key=lambda r: r[1], reverse=bool(policy[0]))
        if index is not None and policy[1]:
            state['selected'] = rows[index][0]
    elif name == 'edit' and index is not None:
        rows[index][1] = args[0]
    elif name == 'copy' and index is not None:
        state['clip'] = ['id', rows[index][0]] if policy[3] else ['value', rows[index][1]]
    elif name == 'paste' and index is not None:
        value = clipboard(state)
        if value is not None:
            rows[index][1] = value
    elif name == 'delete' and index is not None:
        rows.pop(index)
        state['selected'] = rows[min(index, len(rows) - 1)][0] if policy[2] and rows else None


def cases(project, policy, public=False):
    result = []
    for actions in (PUBLIC if public else HIDDEN)[project]:
        state = initial(project)
        steps = []
        for action in actions:
            step(project, state, action, policy)
            steps.append({'action': list(action), 'expected': snapshot(project, state)})
        result.append({'initial': snapshot(project, initial(project)), 'steps': steps})
    return result
