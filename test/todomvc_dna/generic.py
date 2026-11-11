"""Table-driven copies of the TodoMVC plan prompt and compiler, for libraries other than the frozen human one.

`domain.compile_plan` and `domain.messages_for` read the admissibility tables (ROUTES, INITS, AFTERS, VIEWS) of the
human library from module constants.  The stages that swap the library (a library built blind by a model) or rename
its atoms (name / description sensitivity) need the same logic over other tables, so it is repeated here with the
tables as an argument.  `check_equivalence()` asserts that, given the human library and its tables, both functions
reproduce the originals byte for byte; the runners call it before any paid request.
"""
from __future__ import annotations

import json

from . import domain
from .library import AFTERS, INITS, ROUTES, VIEWS, library

KINDS = [('init', 'init functions'), ('event', 'event handlers (reduce)'), ('after', 'after hooks (run after every event)'),
         ('view', 'view slot functions (select)')]


def human_tables():
    return {'routes': {e: list(v) for e, v in ROUTES.items()}, 'inits': list(INITS), 'afters': dict(AFTERS),
            'views': {s: list(v) for s, v in VIEWS.items()}}


def compile_plan(plan, features, lib, tables, checked=True):
    """Same checks and the same emitted glue as domain.compile_plan, over `tables`."""
    routes, inits, afters, views = tables['routes'], tables['inits'], tables['afters'], tables['views']
    if not isinstance(plan, dict):
        raise ValueError('plan must be a JSON object')
    plan = domain._unwrap_names(plan)
    init, handlers, after, view = plan.get('init'), plan.get('handlers'), plan.get('after', []), plan.get('view')
    if not isinstance(init, str) or not isinstance(handlers, dict) or not isinstance(after, list) or not isinstance(view, dict):
        raise ValueError('required fields: "init" string, "handlers" object, "after" array, "view" object')
    lookup = {f['name']: f for f in lib['functions']}
    view = {s: n for s, n in view.items() if s not in domain.FIXED_VIEW_FIELDS}
    names = [init, *handlers.values(), *after, *view.values()]
    unknown = [n for n in names if not isinstance(n, str) or n not in lookup]
    if unknown:
        raise ValueError(f'unknown function name(s): {unknown}; use only names from the library')
    bad_events = [e for e in handlers if e not in routes]
    if bad_events:
        raise ValueError(f'unknown event name(s): {bad_events}; events are {list(routes)}')
    bad_slots = [s for s in view if s not in views]
    if bad_slots:
        raise ValueError(f'unknown view slot(s): {bad_slots}; slots are {list(views)}')
    events, slots = domain.enabled_events(features), domain.enabled_slots(features)
    handlers = {e: n for e, n in handlers.items() if e in events}
    after = [n for n in after if lookup[n]['feature'] == 'core' or lookup[n]['feature'] in features]
    view = {s: n for s, n in view.items() if s in slots}
    if checked:
        if init not in inits:
            raise ValueError(f'"init" must be one of {inits}')
        missing = [e for e in events if e not in handlers]
        wrong = [e for e, n in handlers.items() if n not in routes[e]]
        if missing or wrong:
            raise ValueError('every enabled event needs an allowed handler; missing: ' + json.dumps(missing) + ', invalid: ' + json.dumps(wrong)
                             + '; allowed: ' + json.dumps({e: routes[e] for e in events}))
        bad_after = [n for n in after if n not in afters]
        if bad_after:
            raise ValueError(f'"after" may only contain {list(afters)}; got {bad_after}')
        missing_slots = [s for s in slots if s not in view]
        wrong_slots = [s for s, n in view.items() if n not in views[s]]
        if missing_slots or wrong_slots:
            raise ValueError('every enabled view slot needs an allowed function; missing: ' + json.dumps(missing_slots) + ', invalid: '
                             + json.dumps(wrong_slots) + '; allowed: ' + json.dumps({s: views[s] for s in slots}))
    used = []
    for n in [init, *handlers.values(), *after, *view.values()]:
        if n not in used:
            used.append(n)
    cases = ''.join(f"case '{e}': {n}(s,e); break;\n" for e, n in handlers.items())
    hooks = ''.join(f'{n}(s,e);\n' for n in after)
    fields = ', '.join([f'{s}: {view[s]}(s)' if s in view else f"{s}: {json.dumps('' if s == 'countText' else False)}" for s in views])
    source = '\n'.join(lookup[n]['code'] for n in used) + '\n'
    source += ('window.candidate = {\n'
               f'  init() {{ return {init}(); }},\n'
               f'  reduce(s, e) {{ switch (e.type) {{\n{cases}}}\n{hooks}return s; }},\n'
               f'  select(s) {{ return {{ {fields}, hasTodos: s.todos.length > 0, editing: s.editing, filter: s.filter }}; }}\n'
               '};\n')
    return source


def listing(lib, descriptions=True, bodies=True):
    lines = []
    for kind, title in KINDS:
        lines.append(f'### {title}')
        for f in lib['functions']:
            if f['kind'] != kind:
                continue
            line = f"- `{f['signature']}` [feature: {f['feature']}]"
            if descriptions:
                line += f" — {f['description']}"
            if bodies:
                line += f"\n  ```js\n  {f['code']}\n  ```"
            lines.append(line)
    return '\n'.join(lines)


def head(task):
    features = task['features']
    events, slots = domain.enabled_events(features), domain.enabled_slots(features)
    return (f"Enabled features for this task: core (add, persistence) + {features}. Events the shell will dispatch: {events}. "
            f"View slots the shell reads: {slots} plus hasTodos, editing, filter.\n\nRequirement:\n{task['requirement']}\n\n{domain.INTERFACE}")


def plan_messages(task, lib, tables, descriptions=True, bodies=True):
    features = task['features']
    events, slots = domain.enabled_events(features), domain.enabled_slots(features)
    system = ('You wire frozen, verified functions into the state logic of a small web app. You cannot write code. Return JSON only: '
              '{"init": "<init function>", "handlers": {"<event>": "<event handler>"}, "after": ["<after hook>", ...], "view": {"<slot>": "<view function>"}}. '
              'Pick, for every enabled event and view slot, the library function whose documented behaviour matches the requirement. '
              'The compiler links the chosen functions verbatim and rejects plans that miss an enabled event or slot.')
    schema = ('Plan schema: {"init": name, "handlers": {event: name for every enabled event}, "after": [names], "view": {slot: name for every enabled slot}}. '
              f"Allowed handlers per event: {json.dumps({e: tables['routes'][e] for e in events})}. "
              f"Allowed view functions per slot: {json.dumps({s: tables['views'][s] for s in slots})}. "
              f"Allowed init: {tables['inits']}. Allowed after hooks: {list(tables['afters'])}.")
    return [{'role': 'system', 'content': system},
            {'role': 'user', 'content': head(task) + '\n\nFrozen library:\n' + listing(lib, descriptions, bodies) + '\n\n' + schema
                                        + '\nReturn the plan as JSON only.'}]


def free_lib_messages(task, lib):
    system = ('You implement the state logic of a small web app. Return JSON only: {"code": "<JavaScript source>"}. '
              'The source must define window.candidate = { init, reduce, select } exactly as the shell protocol describes; '
              'no DOM access, no imports, no frameworks.')
    extra = ('\n\nA library of verified functions is available; you may copy any of them verbatim into your source, adapt them, '
             'or ignore them:\n' + listing(lib))
    return [{'role': 'system', 'content': system}, {'role': 'user', 'content': head(task) + extra + '\n\nReturn the complete JavaScript source as JSON.'}]


def check_equivalence():
    """The generic copies must reproduce the originals exactly on the human library."""
    lib, tables = library(), human_tables()
    for task in domain.tasks():
        assert plan_messages(task, lib, tables) == domain.messages_for(task, 'dna', lib), task['id']
        assert free_lib_messages(task, lib) == domain.messages_for(task, 'free_lib', lib), task['id']
        for plan in (domain.reference_plan(task['features']), domain.rule_plan(task['features'])):
            assert compile_plan(plan, task['features'], lib, tables) == domain.compile_plan(plan, task['features'], lib), task['id']
        for broken in ({'init': 'initEmpty', 'handlers': {}, 'after': [], 'view': {}}, {'init': 'nope', 'handlers': {}, 'after': [], 'view': {}}):
            errors = []
            for fn in (lambda: compile_plan(broken, task['features'], lib, tables), lambda: domain.compile_plan(broken, task['features'], lib)):
                try:
                    fn()
                    errors.append(None)
                except ValueError as error:
                    errors.append(str(error))
            assert errors[0] == errors[1] and errors[0], task['id']
    return True
