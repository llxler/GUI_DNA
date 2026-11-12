"""Requirements and split; generation exports only explicit public fields."""
from itertools import product

PROJECTS = ('calculator', 'table')
CLAUSES = {
    'calculator': (
        ('After Add or Subtract, empty the entry field.', 'After Add or Subtract, retain the entry field.'),
        ('Memory Recall replaces the total with the saved memory value.', 'Memory Recall adds the saved memory value to the total.'),
        ('Clear preserves the saved memory value.', 'Clear also resets the saved memory value to zero.'),
        ('Clicking a history item replaces the total with that recorded value.', 'Clicking a history item adds that recorded value to the total.'),
    ),
    'table': (
        ('Sort orders rows by increasing numeric value.', 'Sort orders rows by decreasing numeric value.'),
        ('After Sort, selection follows the same row identity.', 'After Sort, selection stays at its previous ordinal position.'),
        ('Delete clears the selection.', 'Delete selects the next row at the removed position, or the preceding last row if none follows.'),
        ('Copy stores a snapshot of the selected value.', 'Copy stores a live reference to the selected row; its current value is used until that source row is deleted.'),
    ),
}
BASE = {
    'calculator': '''Build a complete small accumulator calculator. It is a new synthetic task inspired by calculator memory/history interactions, not the official Web-Bench task.
Initially total=0, memory=0, entry="", history=[]. Show integer total in #total, integer memory in #memory, an editable input #entry, and buttons #add, #subtract, #save, #recall, #clear. Add/Subtract add/subtract the integer entry (empty means zero) to/from the current total, then append the resulting total to history. Save replaces memory with the current total. Recall modifies total according to the requirement below but does not add history. Clear sets total=0 and entry="", never erases history, and handles memory as specified below. History items are buttons with consecutive data-history-index="0", "1", ... and visible text equal to each recorded integer. Clicking one modifies total according to the requirement below; history itself is unchanged. Editing the entry alone changes no other state. All numbers are small integers. No persistence or network; each fresh page load starts at the initial state. Implement the whole page, event bindings, and state yourself; no shell is supplied.''',
    'table': '''Build a complete small editable numeric table. It is a new synthetic task inspired by table selection/sorting/clipboard interactions, not the official Web-Bench task.
Initially rows in order are a=7, b=2, c=5, no selection, and empty clipboard. Each row is a clickable element with data-row-id="a", "b", or "c", a child .row-value showing its integer value, and aria-selected="true" only when selected (otherwise "false"). Clicking a row selects it. Provide an editable input #edit-value and buttons #apply, #sort, #copy, #paste, #delete. Apply sets the selected row's value to the integer input; with no selection it does nothing. Sort is stable for ties and does not run automatically after edits. Copy/Paste with no selection do nothing. Copy handles its source as specified below. Paste replaces the selected value with the current clipboard value; empty clipboard does nothing. Delete removes the selected row and handles selection as specified below; deleting with no selection does nothing. When no rows remain selection is empty. Show current clipboard value as an integer in #clipboard, or exactly "empty" if absent, including when a live source was deleted. Editing, Copy and Paste never change selection or row order. No persistence or network; each fresh load restores the initial state. Implement the whole page, event bindings, and state yourself; no shell is supplied.''',
}


def requirement(project, policy):
    return BASE[project] + '\n\nBehavior requirements:\n' + '\n'.join(
        CLAUSES[project][i][bit] for i, bit in enumerate(policy))


def development(project):
    policies = [(0, 0, 0, 0)] + [tuple(int(i == j) for i in range(4)) for j in range(4)]
    return [{'id': f'dev-{i}', 'requirement': requirement(project, p), 'policy': p}
            for i, p in enumerate(policies)]


def heldout(project):
    policies = [p for p in product((0, 1), repeat=4) if sum(p) >= 2]
    return [{'id': f'heldout-{i + 1:02d}', 'requirement': requirement(project, p), 'policy': p}
            for i, p in enumerate(policies)]


def public_task(task):
    return {key: task[key] for key in ('id', 'requirement')}


def strong_tasks(project):
    selected = {(1, 1, 0, 0), (1, 1, 1, 0), (1, 1, 1, 1)}
    return [t for t in heldout(project) if tuple(t['policy']) in selected]
