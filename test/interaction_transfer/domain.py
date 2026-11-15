"""Public requirements only; no hidden trajectories, policies or reference code."""
PROJECTS = ('todos', 'rows')
TODO_BASE = '''Build a standalone browser checklist. Use .new-todo input (Enter appends a trimmed nonempty title and clears input), .todo-list containing li items with label, and a .destroy button per item. Duplicate titles are distinct items; actions affect the chosen item. Start empty. No framework, server or external assets. Extra working features are allowed.'''
TODO_EDIT = '''Double-click an item's label to edit it in a focused .edit input in that same li with class editing. Enter and blur commit trimmed input; empty committed input removes that item. Escape cancels without changing the saved title. While editing hide its normal controls. .destroy removes the selected item.'''
TODO_STATUS = '''Each li has .toggle checkbox and completed class matching state. #toggle-all sets ALL stored items to its checked state, even when filtered; it is checked iff the nonempty collection is all complete. .todo-count strong always counts all active items. .clear-completed removes all complete items and is hidden when none exist. .filters links All, Active, Completed use #/, #/active, #/completed and selected class; update visible membership immediately when data or route changes. .main and .footer are hidden iff no items exist. A route survives page reload.'''
TODO_STORE = '''Persist saved item identity, title and completed state to localStorage key todos-transfer after every committed mutation. Restore on reload. Do not persist editing mode or unsaved edit text. Reload retains the current URL route. Use no network.'''
ROW_BASE = '''Build a standalone keyed table. A table contains tbody rows; each tr has data-id equal to the decimal row ID, td 1 displays that ID, td 2 contains an a with the label, td 3 contains an a.remove for removal when supported. A selected row has class danger. Start empty; IDs start at 1 and increase monotonically, including after clearing or replacing data. Labels are exactly Row N for ID N. Retain the same DOM tr object for every surviving data ID across updates, selection, removal, appends and reordering; removed/replaced IDs lose their nodes. No frameworks or network. Extra working controls are allowed.'''
ROW_BATCH = '''Button #run replaces rows by 1000 fresh rows. #runlots replaces them by 10000 fresh rows. #add appends 1000 fresh rows. #clear removes all rows. Replacement and clearing clear selection. IDs never repeat during this page session.'''
ROW_UPDATE = '''Button #update appends literal " !!!" to the label of each row at current zero-based positions 0,10,20,...; repeated clicks append again. Other rows and selected identity are unchanged.'''
ROW_IDENTITY = '''Clicking the label link selects that row by ID. Clicking its a.remove removes that row only, retaining other row order and IDs; removing another row preserves selection. Removing the selected row clears selection. #swaprows exchanges the rows at zero-based indices 1 and 998 when at least 999 rows exist, otherwise does nothing. Selection follows data identity through swaps and removals.'''


def development(project):
    if project == 'todos':
        texts = [TODO_BASE+'\n'+TODO_EDIT, TODO_BASE+'\n'+TODO_STATUS, TODO_BASE+'\nEach li also has a .toggle checkbox and completed class.\n'+TODO_STORE]
    elif project == 'rows':
        texts = [ROW_BASE+'\n'+ROW_BATCH, ROW_BASE+'\n'+ROW_BATCH+'\n'+ROW_UPDATE,
                 ROW_BASE+'\n'+ROW_BATCH+'\n'+ROW_IDENTITY]
    else:
        raise ValueError(project)
    return [{'id':f'dev-{i}', 'requirement':text} for i,text in enumerate(texts)]


def target(project):
    text = '\n'.join((TODO_BASE,TODO_EDIT,TODO_STATUS,TODO_STORE)) if project == 'todos' else '\n'.join((ROW_BASE,ROW_BATCH,ROW_UPDATE,ROW_IDENTITY))
    return {'id':'full-application', 'requirement':text}
