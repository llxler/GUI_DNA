"""Tasks, plan compiler and prompts for the Web-Bench dom1 stage.

Task k (1..20) = the official task descriptions 1..k (tasks.jsonl, verbatim) and the cumulative feature list
FEATURES[:k].  A plan wires frozen atoms for exactly those features; `compile_plan` checks structure and coverage
(every enabled feature must be wired), drops anything that belongs to a disabled feature, and never looks at tests.
"""
from __future__ import annotations

import json
from pathlib import Path

from .library import COMMANDS, FEATURES, SHORTCUT_KEYS, SLOT_FEATURE, SLOTS, TOOL_BEHAVIOUR, TOOLS, library

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TASKS_FILE = HERE / 'harness' / 'tasks.jsonl'
METHODS = ['free', 'rule', 'dna', 'free_lib', 'dna_unchecked']
MENU_KINDS = ['file', 'dir', 'entries']
# Commands a kind must offer when the feature is enabled (task descriptions 7, 8, 9, 10, 20).
REQUIRED_MENU = {
    'menuEntry': {'file': ['delete'], 'dir': ['add file', 'add dir', 'delete']},
    'menuPanel': {'entries': ['add file', 'add dir']},
    'copyPaste': {'file': ['copy'], 'dir': ['copy', 'paste'], 'entries': ['paste']},
    'rename': {'file': ['rename'], 'dir': ['rename']},
    'cut': {'file': ['cut'], 'dir': ['cut']},
}
REQUIRED_SHORTCUTS = {'shortcuts': {'c': 'copy', 'v': 'paste', 'j': 'add file', 'k': 'add dir'},
                      'deleteShortcut': {'delete': 'delete', 'backspace': 'delete'}, 'cut': {'x': 'cut'}}
REQUIRED_TOOLS = {'tools': ['file', 'dir', 'del'], 'import': ['imp'], 'export': ['exp'], 'generate': ['gen'], 'filter': ['filter']}
FLAGS = {'autosave': 'autosave', 'resizer': 'resizer', 'resizerDrag': 'resizerDrag', 'filter': 'filter'}


def official_tasks():
    rows = [json.loads(line) for line in TASKS_FILE.read_text().splitlines() if line.strip()]
    return {row['id']: row for row in rows}


def tasks():
    rows = official_tasks()
    out = []
    for k in range(1, 21):
        descriptions = [f"{rows[f'task-{i}']['id']}: {rows[f'task-{i}']['description']}" for i in range(1, k + 1)]
        out.append({'id': f'task-{k}', 'k': k, 'features': FEATURES[:k], 'spec': f'task-{k}.spec.js',
                    'level': rows[f'task-{k}'].get('level'), 'descriptions': descriptions})
    return out


def _has(features, f):
    return f in features


def compile_plan(plan, features, lib, checked=True):
    """Validate + link.  Returns the candidate JavaScript (inserted into shell.html by the evaluator)."""
    if not isinstance(plan, dict):
        raise ValueError('plan must be a JSON object')
    lookup = {f['name']: f for f in lib['functions']}
    errors = []
    tools = plan.get('tools', [])
    menu = plan.get('menu', {}) or {}
    shortcuts = plan.get('shortcuts', {}) or {}
    flags = {k: bool(plan.get(k, False)) for k in FLAGS}
    if not isinstance(tools, list) or any(not isinstance(t, str) for t in tools):
        raise ValueError('"tools" must be an array of button names; allowed: ' + json.dumps(list(TOOLS)))
    if not isinstance(menu, dict) or not isinstance(shortcuts, dict):
        raise ValueError('"menu" must be an object {file|dir|entries: [commands]} and "shortcuts" an object {key: command}')
    unknown_tools = [t for t in tools if t not in TOOLS]
    if unknown_tools:
        raise ValueError(f'unknown tool button(s) {unknown_tools}; allowed: {list(TOOLS)}')
    if len(set(tools)) != len(tools):
        raise ValueError('"tools" must not repeat a button')
    for kind, commands in menu.items():
        if kind not in MENU_KINDS or not isinstance(commands, list):
            raise ValueError(f'"menu" keys must be {MENU_KINDS} with arrays of commands; got {kind!r}')
        bad = [c for c in commands if c not in COMMANDS]
        if bad:
            raise ValueError(f'unknown menu command(s) {bad} for {kind}; allowed: {list(COMMANDS)}')
    for key, command in shortcuts.items():
        if key not in SHORTCUT_KEYS or command not in COMMANDS:
            raise ValueError(f'"shortcuts" must map keys {list(SHORTCUT_KEYS)} to commands {list(COMMANDS)}; got {key!r}: {command!r}')
    slots = {}
    for slot, options in SLOTS.items():
        value = plan.get(slot)
        if value is None:
            continue
        if not isinstance(value, str) or value not in lookup:
            raise ValueError(f'"{slot}" must name a library function; allowed: {options}')
        if value not in options:
            raise ValueError(f'"{slot}" = {value!r} is not an allowed variant; allowed: {options}')
        slots[slot] = value
    # ---- feature-aware linking: drop everything that belongs to a disabled feature
    tools = [t for t in tools if _has(features, TOOLS[t])]
    menu = {k: [c for c in menu.get(k, []) if _has(features, COMMANDS[c])] for k in MENU_KINDS} if _has(features, 'menuEntry') else {}
    if not _has(features, 'menuPanel'):
        menu.pop('entries', None)
    shortcuts = {k: c for k, c in shortcuts.items() if _has(features, COMMANDS[c]) and _has(features, 'shortcuts')
                 and (_has(features, 'deleteShortcut') or c != 'delete')} if _has(features, 'shortcuts') else {}
    flags = {k: v and _has(features, FLAGS[k]) for k, v in flags.items()}
    slots = {s: v for s, v in slots.items() if _has(features, SLOT_FEATURE[s])}
    if checked:
        for feature, needed in REQUIRED_TOOLS.items():
            if _has(features, feature):
                missing = [t for t in needed if t not in tools]
                if missing:
                    errors.append(f'feature {feature} needs tool button(s) {missing} in "tools"')
        for feature, needed in REQUIRED_MENU.items():
            if _has(features, feature):
                for kind, commands in needed.items():
                    missing = [c for c in commands if c not in menu.get(kind, [])]
                    if missing:
                        errors.append(f'feature {feature} needs menu command(s) {missing} for {kind} in "menu"')
        for feature, needed in REQUIRED_SHORTCUTS.items():
            if _has(features, feature):
                missing = [f'{k}->{c}' for k, c in needed.items() if shortcuts.get(k) != c]
                if missing:
                    errors.append(f'feature {feature} needs shortcut(s) {missing} in "shortcuts"')
        for flag, feature in FLAGS.items():
            if _has(features, feature) and not flags[flag]:
                errors.append(f'feature {feature} needs "{flag}": true')
        for slot, feature in SLOT_FEATURE.items():
            if _has(features, feature) and slot not in slots:
                errors.append(f'feature {feature} needs "{slot}" set to one of {SLOTS[slot]}')
        if errors:
            raise ValueError('plan does not cover the enabled features:\n- ' + '\n- '.join(errors))
    # ---- link
    select = slots.get('select', 'selectToggleDir')
    file_click = slots.get('fileClick', 'fileClickOpen')
    insert = slots.get('insert', 'insertAppend')
    delete = slots.get('delete', 'removeSimple')
    drop = slots.get('drag', 'dropAppendOnly')
    label = slots.get('menuLabel', 'menuLabelPlain')
    used = ['state', 'injectStyle', 'entriesPanel', 'getName', 'setName', 'isEntry', 'noop', 'toolsInit']
    def use(*names):
        for n in names:
            if n not in used:
                used.append(n)
    if _has(features, 'addFile'):
        use('styleEntries', select, 'fileCreate', 'fileAdd', file_click, insert)
    if _has(features, 'addDir'):
        use('dirCreate', 'dirAdd', 'dirClick')
    if _has(features, 'delete'):
        use(delete)
    if _has(features, 'drag'):
        use('dragEnable', drop)
    if menu:
        use('menuInit', 'menuShow', label)
    if _has(features, 'copyPaste'):
        use('cloneEntry', 'cmdCopy', 'cmdPaste')
    if _has(features, 'cut'):
        use('cmdCut')
    if _has(features, 'rename'):
        use('renameEntry')
    if _has(features, 'export'):
        use('toJSON', 'exportAll')
    if _has(features, 'import'):
        use('importAll')
    if _has(features, 'generate'):
        use('generateEntries')
    if flags['autosave']:
        use('autosaveInit')
    if flags['resizer']:
        use('resizerShow')
    if flags['resizerDrag']:
        use('resizerDrag')
    if flags['filter']:
        use('filterContains', 'showFilterDialog')
    if shortcuts:
        use('shortcutsInit')
    shortcut_of = {}
    for key, command in shortcuts.items():
        shortcut_of.setdefault(command, key)
    actions = {'file': 'fileAdd()', 'dir': 'dirAdd()', 'del': 'removeEntry()', 'imp': 'importAll()', 'exp': 'exportAll()',
               'gen': 'generateEntries()', 'filter': 'showFilterDialog()'}
    command_js = {'add file': 'fileAdd(t)', 'add dir': 'dirAdd(t)', 'delete': 'removeEntry(t)', 'copy': 'cmdCopy(t)',
                  'paste': 'cmdPaste(t)', 'rename': 'renameEntry(t)', 'cut': 'cmdCut(t)'}
    enabled_commands = [c for c in COMMANDS if _has(features, COMMANDS[c]) and (menu or shortcuts)]
    lines = [lookup[n]['code'] for n in used]
    lines += [
        f'const MENU = {json.dumps(menu)};',
        f'const SHORTCUTS = {json.dumps(shortcuts)};',
        f'const SHORTCUT_OF = {json.dumps(shortcut_of)};',
        f'const setSelected = {select if _has(features, "addFile") else "noop"};',
        f'const insertEntry = {insert if _has(features, "addFile") else "noop"};',
        f'const removeEntry = {delete if _has(features, "delete") else "noop"};',
        f'const enableDrag = {"dragEnable" if _has(features, "drag") else "noop"};',
        f'const dropRule = {drop if _has(features, "drag") else "noop"};',
        f'const fileClick = {file_click if _has(features, "addFile") else "noop"};',
        f'const menuLabel = {label if menu else "noop"};',
        f'const filterEntries = {"filterContains" if flags["filter"] else "noop"};',
        'const COMMANDS = {' + ', '.join(f'{json.dumps(c)}: (t) => {command_js[c]}' for c in enabled_commands) + '};',
        'toolsInit(' + json.dumps(tools) + ', {' + ', '.join(f'{json.dumps(t)}: () => {actions[t]}' for t in tools if _has(features, TOOL_BEHAVIOUR[t])) + '});',
    ]
    if _has(features, 'addFile'):
        lines.append('styleEntries();')
        lines.append("entriesPanel().addEventListener('click', (e) => { const t = e.target; if (t.classList.contains('entries')) { setSelected(null); } "
                     "else if (t.classList.contains('entry')) { e.stopPropagation(); if (t.classList.contains('file')) fileClick(t); else if (typeof dirClick === 'function') dirClick(t); } });")
    if _has(features, 'drag'):
        lines.append('enableDrag(entriesPanel());')
    if menu:
        lines.append('menuInit();')
    if shortcuts:
        lines.append('shortcutsInit(SHORTCUTS);')
    if flags['autosave']:
        lines.append('autosaveInit();')
    if flags['resizer']:
        lines.append('resizerShow();')
    if flags['resizerDrag']:
        lines.append('resizerDrag();')
    return '\n'.join(lines) + '\n'


def reference_plan(features):
    """Spec-correct plan for the full ladder (calibration only; the compiler trims it to the enabled features)."""
    return {'tools': ['file', 'dir', 'del', 'imp', 'exp', 'gen', 'filter'],
            'select': 'selectToggleDir', 'fileClick': 'fileClickOpen', 'insert': 'insertRelative', 'delete': 'removeNextPrevParent',
            'drag': 'dropHalfRule', 'menuLabel': 'menuLabelShortcut',
            'menu': {'file': ['rename', 'cut', 'copy', 'delete'], 'dir': ['add file', 'add dir', 'rename', 'cut', 'copy', 'delete', 'paste'],
                     'entries': ['add file', 'add dir', 'paste']},
            'shortcuts': {'c': 'copy', 'v': 'paste', 'j': 'add file', 'k': 'add dir', 'x': 'cut', 'delete': 'delete', 'backspace': 'delete'},
            'autosave': True, 'resizer': True, 'resizerDrag': True, 'filter': True}


def rule_plan(features):
    """Zero-API control: every required item, alphabetically first variant per slot, nothing read from the descriptions."""
    plan = {'tools': [], 'menu': {k: [] for k in MENU_KINDS}, 'shortcuts': {}}
    for feature, needed in REQUIRED_TOOLS.items():
        if feature in features:
            plan['tools'] += needed
    for feature, needed in REQUIRED_MENU.items():
        if feature in features:
            for kind, commands in needed.items():
                plan['menu'][kind] += [c for c in commands if c not in plan['menu'][kind]]
    for feature, needed in REQUIRED_SHORTCUTS.items():
        if feature in features:
            plan['shortcuts'].update(needed)
    for flag, feature in FLAGS.items():
        plan[flag] = feature in features
    for slot, feature in SLOT_FEATURE.items():
        if feature in features:
            plan[slot] = SLOTS[slot][0]
    return plan


INTERFACE = ("Shell (fixed, public): a page with .explorer > .leftbar (.tools and .entries inside) and textarea.editor; layout CSS only. "
             "The candidate script runs inside that page and must create everything else from the library atoms.")


def library_listing(lib):
    lines = []
    for kind, title in [('helper', 'helpers (always linked)'), ('infra', 'infrastructure atoms'), ('event', 'behaviour atoms (several are variants of one slot)'), ('view', 'label atoms')]:
        lines.append(f'### {title}')
        for f in lib['functions']:
            if f['kind'] == kind:
                lines.append(f"- `{f['signature']}` [feature: {f['feature']}] — {f['description']}")
    return '\n'.join(lines)


def messages_for(task, method, lib):
    requirement = '\n'.join(task['descriptions'])
    if method == 'free':
        raise ValueError('free arm prompts are built by run.py from the current page (sequential protocol)')
    system = ('You wire frozen, verified functions into a file-explorer web page. You cannot write code. Return JSON only: a plan '
              '{"tools": [button names in order], "select": name, "fileClick": name, "insert": name, "delete": name, "drag": name, '
              '"menuLabel": name, "menu": {"file": [commands], "dir": [commands], "entries": [commands]}, "shortcuts": {key: command}, '
              '"autosave": bool, "resizer": bool, "resizerDrag": bool, "filter": bool}. '
              'For every slot choose the variant whose documented behaviour matches the task descriptions; include every tool button, '
              'menu command and shortcut the descriptions ask for. The compiler links the chosen atoms verbatim and rejects plans that '
              'leave an enabled feature unwired.')
    schema = ('Allowed values — tools: ' + json.dumps(list(TOOLS)) + '; slots: ' + json.dumps(SLOTS) +
              '; menu commands: ' + json.dumps(list(COMMANDS)) + ' (menu keys: file, dir, entries); shortcut keys: ' + json.dumps(SHORTCUT_KEYS) +
              ' (value = command). Items for features that are not enabled are ignored.')
    user = (f"Enabled features for this task (cumulative): {task['features']}.\n\nTask descriptions so far (the requirement):\n{requirement}\n\n"
            f"{INTERFACE}\n\nFrozen library:\n{library_listing(lib)}\n\n{schema}\nReturn the plan as JSON only.")
    return [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]


FREE_SYSTEM = ('You are a web developer working on a single-file web page. You receive the current index.html and the next task. '
               'Return JSON only: {"html": "<the complete updated index.html>"}. Keep everything that already works; use plain DOM APIs, '
               'no external resources.')


def free_messages(task, current_html, lib=None):
    rows = official_tasks()
    extra = ''
    if lib is not None:   # free_lib: the same frozen functions as the plan method, usable in any way
        extra = ('\n\nA library of verified functions for this file explorer is available; you may paste any of them verbatim into the page, '
                 'adapt them, or ignore them:\n' + '\n'.join(f"- `{f['signature']}` — {f['description']}\n  ```js\n  {f['code']}\n  ```"
                                                                 for f in lib['functions']))
    return [{'role': 'system', 'content': FREE_SYSTEM},
            {'role': 'user', 'content': f"Current index.html:\n```html\n{current_html}\n```\n\nTask {task['id']}: {rows[task['id']]['description']}{extra}\n\n"
                                        'Return the complete updated index.html as JSON.'}]
