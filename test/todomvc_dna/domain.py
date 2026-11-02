"""Tasks, public requirement text, plan compiler and prompts for the TodoMVC stage.

External pieces: requirement sentences come from the TodoMVC app specification (tastejs/todomvc app-spec.md,
"Functionality"); hidden tests are the official Playwright demo spec (create-playwright 1.17.129,
harness/demo-todo-app.original.spec.ts).  Neither the tests nor their titles ever enter a prompt.
"""
from __future__ import annotations

import json
from pathlib import Path

from .library import AFTERS, CORE_EVENTS, EVENTS, FEATURES, INITS, ROUTES, VIEWS, VIEW_SLOTS, library

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
METHODS = ['free', 'rule', 'dna']
# View fields the compiler always emits itself; a plan may list them (the interface text mentions them) without harm.
FIXED_VIEW_FIELDS = {'hasTodos', 'editing', 'filter'}

# Feature families: every task has the core (add + persistence); the listed features are enabled on top.
FAMILIES = [
    ['counter'], ['toggle'], ['edit'],
    ['toggle', 'toggleAll'], ['toggle', 'clearCompleted'], ['toggle', 'routing'],
    ['toggle', 'edit', 'counter', 'clearCompleted'],
    ['toggle', 'toggleAll', 'edit', 'counter', 'clearCompleted', 'routing'],
]

# Official test -> features it exercises beyond the core.  Decided by reading the spec file once; used only by the
# evaluator to pick the hidden subset for a task (a task is graded on every official test whose features it enables).
TEST_FEATURES = {
    ('New Todo', 'should allow me to add todo items'): [],
    ('New Todo', 'should clear text input field when an item is added'): [],
    ('New Todo', 'should append new items to the bottom of the list'): ['counter'],
    ('Mark all as completed', 'should allow me to mark all items as completed'): ['toggleAll'],
    ('Mark all as completed', 'should allow me to clear the complete state of all items'): ['toggleAll'],
    ('Mark all as completed', 'complete all checkbox should update state when items are completed / cleared'): ['toggleAll', 'toggle'],
    ('Item', 'should allow me to mark items as complete'): ['toggle'],
    ('Item', 'should allow me to un-mark items as complete'): ['toggle'],
    ('Item', 'should allow me to edit an item'): ['edit'],
    ('Editing', 'should hide other controls when editing'): ['edit'],
    ('Editing', 'should save edits on blur'): ['edit'],
    ('Editing', 'should trim entered text'): ['edit'],
    ('Editing', 'should remove the item if an empty text string was entered'): ['edit'],
    ('Editing', 'should cancel edits on escape'): ['edit'],
    ('Counter', 'should display the current number of todo items'): ['counter'],
    ('Clear completed button', 'should display the correct text'): ['toggle', 'clearCompleted'],
    ('Clear completed button', 'should remove completed items when clicked'): ['toggle', 'clearCompleted'],
    ('Clear completed button', 'should be hidden when there are no items that are completed'): ['toggle', 'clearCompleted'],
    ('Persistence', 'should persist its data'): ['toggle'],
    ('Routing', 'should allow me to display active items'): ['toggle', 'routing'],
    ('Routing', 'should respect the back button'): ['toggle', 'routing'],
    ('Routing', 'should allow me to display completed items'): ['toggle', 'routing'],
    ('Routing', 'should allow me to display all items'): ['toggle', 'routing'],
    ('Routing', 'should highlight the currently applied filter'): ['routing'],
}

# Requirement sentences (TodoMVC app spec, Functionality section; DOM-only sentences handled by the shell are omitted).
SPEC = {
    'core': ['Build the state logic of a TodoMVC application behind the given shell; the shell owns the DOM and only calls init/reduce/select.',
             'New todo: pressing Enter creates the todo and appends it to the todo list. Make sure to .trim() the input and then check that it is not empty before creating a new todo.',
             "Persistence: the app should dynamically persist the todos to localStorage after every change, as a JSON array under the key 'react-todos' with the keys id, title, completed for each item, and load them again on init. Editing mode should not be persisted.",
             'No todos: when there are no todos, the main section and the footer are hidden (the view reports hasTodos).'],
    'toggle': ['Item: clicking the checkbox marks the todo as complete by updating its completed value; clicking it again marks it active again.'],
    'toggleAll': ['Mark all as complete: this checkbox toggles all the todos to the same state as itself. The checkbox should also be updated when single todo items are checked/unchecked, e.g. when all the todos are checked it should also get checked.'],
    'edit': ['Item: double-clicking the label activates editing mode for that todo.',
             'Editing: the edit should be saved on both blur and Enter, and editing mode left. Make sure to .trim() the input and then check that it is not empty. If it is empty the todo should instead be destroyed. If Escape is pressed during the edit, the edit state should be left and any changes discarded.'],
    'counter': ["Counter: displays the number of active todos in a pluralized form: '0 items left', '1 item left', '2 items left'."],
    'clearCompleted': ['Clear completed button: removes completed todos when clicked. Should be hidden when there are no completed todos (the view reports hasCompleted).'],
    'routing': ["Routing: the routes #/ (all, default), #/active and #/completed arrive as route events with filter 'all' | 'active' | 'completed'. When the route changes, the todo list should be filtered on a model level (the view's visible list). When an item is updated while in a filtered state, it should be updated accordingly, e.g. if the filter is Active and the item is checked, it should be hidden."],
}

INTERFACE = """Shell protocol (fixed; the shell owns all DOM and event wiring):
  window.candidate = { init(): state, reduce(state, event): state, select(state): view }
  state = { todos: [{id, title, completed}], filter: 'all'|'active'|'completed', editing: id|null, nextId: number }
  events the shell dispatches: {type:'add', title} {type:'toggle', id} {type:'toggleAll'} {type:'edit', id}
    {type:'save', id, title} {type:'cancel', id, title} {type:'clearCompleted'} {type:'route', filter} {type:'destroy', id}
  reduce may mutate and return the same state object; events of features that are not enabled are never dispatched by the tests.
  view = { visible: [{id, title, completed}], countText: string, allCompleted: boolean, hasCompleted: boolean,
           hasTodos: boolean, editing: id|null, filter: string }
  The shell renders view.visible as the list, view.countText in the counter, view.allCompleted as the toggle-all checkbox
  state, view.hasCompleted to show the Clear completed button and view.hasTodos to show the main section and footer.
  The page is a plain browser context: localStorage is available."""


def tasks():
    out = []
    for i, fs in enumerate(FAMILIES):
        sentences = list(SPEC['core'])
        for f in FEATURES:
            if f in fs:
                sentences += SPEC[f]
        out.append({'id': f'todo-{i + 1:02}', 'family': i, 'features': fs, 'requirement': ' '.join(sentences)})
    return out


def enabled_events(features):
    return CORE_EVENTS + [e for f in features for e in EVENTS[f]]


def enabled_slots(features):
    return [slot for slot, feature in VIEW_SLOTS.items() if feature == 'core' or feature in features]


def hidden_subset(features):
    """Official tests a task is graded on: those whose exercised features are all enabled."""
    return [key for key, needed in TEST_FEATURES.items() if all(f in features for f in needed)]


def _unwrap_names(value):
    """Format tolerance only: a function reference written as {"name": "x"} (seen from small models) means "x"."""
    if isinstance(value, dict):
        if set(value) == {'name'} and isinstance(value['name'], str):
            return value['name']
        return {k: _unwrap_names(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_unwrap_names(v) for v in value]
    return value


def compile_plan(plan, features, lib, checked=True):
    """Feature-aware, policy-blind linker.  Validates names/coverage, never semantics.  Returns JS source."""
    if not isinstance(plan, dict):
        raise ValueError('plan must be a JSON object')
    plan = _unwrap_names(plan)
    init, handlers, after, view = plan.get('init'), plan.get('handlers'), plan.get('after', []), plan.get('view')
    if not isinstance(init, str) or not isinstance(handlers, dict) or not isinstance(after, list) or not isinstance(view, dict):
        raise ValueError('required fields: "init" string, "handlers" object, "after" array, "view" object')
    lookup = {f['name']: f for f in lib['functions']}
    view = {s: n for s, n in view.items() if s not in FIXED_VIEW_FIELDS}
    names = [init, *handlers.values(), *after, *view.values()]
    unknown = [n for n in names if not isinstance(n, str) or n not in lookup]
    if unknown:
        raise ValueError(f'unknown function name(s): {unknown}; use only names from the library')
    bad_events = [e for e in handlers if e not in ROUTES]
    if bad_events:
        raise ValueError(f'unknown event name(s): {bad_events}; events are {list(ROUTES)}')
    bad_slots = [s for s in view if s not in VIEWS]
    if bad_slots:
        raise ValueError(f'unknown view slot(s): {bad_slots}; slots are {list(VIEWS)}')
    events, slots = enabled_events(features), enabled_slots(features)
    handlers = {e: n for e, n in handlers.items() if e in events}          # disabled events are dropped
    after = [n for n in after if lookup[n]['feature'] == 'core' or lookup[n]['feature'] in features]
    view = {s: n for s, n in view.items() if s in slots}
    if checked:
        if init not in INITS:
            raise ValueError(f'"init" must be one of {INITS}')
        missing = [e for e in events if e not in handlers]
        wrong = [e for e, n in handlers.items() if n not in ROUTES[e]]
        if missing or wrong:
            raise ValueError('every enabled event needs an allowed handler; missing: ' + json.dumps(missing) + ', invalid: ' + json.dumps(wrong)
                             + '; allowed: ' + json.dumps({e: ROUTES[e] for e in events}))
        bad_after = [n for n in after if n not in AFTERS]
        if bad_after:
            raise ValueError(f'"after" may only contain {list(AFTERS)}; got {bad_after}')
        missing_slots = [s for s in slots if s not in view]
        wrong_slots = [s for s, n in view.items() if n not in VIEWS[s]]
        if missing_slots or wrong_slots:
            raise ValueError('every enabled view slot needs an allowed function; missing: ' + json.dumps(missing_slots) + ', invalid: '
                             + json.dumps(wrong_slots) + '; allowed: ' + json.dumps({s: VIEWS[s] for s in slots}))
    used = []
    for n in [init, *handlers.values(), *after, *view.values()]:
        if n not in used:
            used.append(n)
    cases = ''.join(f"case '{e}': {n}(s,e); break;\n" for e, n in handlers.items())
    hooks = ''.join(f'{n}(s,e);\n' for n in after)
    fields = ', '.join([f'{s}: {view[s]}(s)' if s in view else f"{s}: {json.dumps('' if s == 'countText' else False)}" for s in VIEWS])
    source = '\n'.join(lookup[n]['code'] for n in used) + '\n'
    source += ('window.candidate = {\n'
               f'  init() {{ return {init}(); }},\n'
               f'  reduce(s, e) {{ switch (e.type) {{\n{cases}}}\n{hooks}return s; }},\n'
               f'  select(s) {{ return {{ {fields}, hasTodos: s.todos.length > 0, editing: s.editing, filter: s.filter }}; }}\n'
               '};\n')
    return source


def rule_plan(features):
    """Zero-API control: alphabetically first allowed name per enabled slot, every enabled after hook."""
    events, slots = enabled_events(features), enabled_slots(features)
    return {'init': INITS[0], 'handlers': {e: ROUTES[e][0] for e in events},
            'after': [n for n, f in AFTERS.items() if f == 'core' or f in features], 'view': {s: VIEWS[s][0] for s in slots}}


def reference_plan(features):
    """Spec-correct plan (calibration only; never shown to a model)."""
    correct = {'add': 'addTrimmed', 'toggle': 'toggle', 'toggleAll': 'toggleAllMatch', 'edit': 'editStart', 'save': 'saveTrimDelete',
               'cancel': 'cancelEdit', 'clearCompleted': 'clearCompleted', 'route': 'routeFilter'}
    views = {'visible': 'visibleByFilter', 'countText': 'countPluralized', 'allCompleted': 'allCompleted', 'hasCompleted': 'hasCompleted'}
    return {'init': 'initFromStorage', 'handlers': {e: correct[e] for e in enabled_events(features)}, 'after': ['persistTodos'],
            'view': {s: views[s] for s in enabled_slots(features)}}


def library_listing(lib, features):
    lines = []
    for kind, title in [('init', 'init functions'), ('event', 'event handlers (reduce)'), ('after', 'after hooks (run after every event)'), ('view', 'view slot functions (select)')]:
        lines.append(f'### {title}')
        for f in lib['functions']:
            if f['kind'] != kind:
                continue
            lines.append(f"- `{f['signature']}` [feature: {f['feature']}] — {f['description']}\n  ```js\n  {f['code']}\n  ```")
    return '\n'.join(lines)


def messages_for(task, method, lib):
    features = task['features']
    events, slots = enabled_events(features), enabled_slots(features)
    head = (f"Enabled features for this task: core (add, persistence) + {features}. Events the shell will dispatch: {events}. "
            f"View slots the shell reads: {slots} plus hasTodos, editing, filter.\n\nRequirement:\n{task['requirement']}\n\n{INTERFACE}")
    if method == 'free':
        system = ('You implement the state logic of a small web app. Return JSON only: {"code": "<JavaScript source>"}. '
                  'The source must define window.candidate = { init, reduce, select } exactly as the shell protocol describes; '
                  'no DOM access, no imports, no frameworks.')
        return [{'role': 'system', 'content': system}, {'role': 'user', 'content': head + '\n\nReturn the complete JavaScript source as JSON.'}]
    system = ('You wire frozen, verified functions into the state logic of a small web app. You cannot write code. Return JSON only: '
              '{"init": "<init function>", "handlers": {"<event>": "<event handler>"}, "after": ["<after hook>", ...], "view": {"<slot>": "<view function>"}}. '
              'Pick, for every enabled event and view slot, the library function whose documented behaviour matches the requirement. '
              'The compiler links the chosen functions verbatim and rejects plans that miss an enabled event or slot.')
    schema = ('Plan schema: {"init": name, "handlers": {event: name for every enabled event}, "after": [names], "view": {slot: name for every enabled slot}}. '
              f'Allowed handlers per event: {json.dumps({e: ROUTES[e] for e in events})}. Allowed view functions per slot: {json.dumps({s: VIEWS[s] for s in slots})}. '
              f'Allowed init: {INITS}. Allowed after hooks: {list(AFTERS)}.')
    return [{'role': 'system', 'content': system},
            {'role': 'user', 'content': head + '\n\nFrozen library:\n' + library_listing(lib, features) + '\n\n' + schema + '\nReturn the plan as JSON only.'}]
