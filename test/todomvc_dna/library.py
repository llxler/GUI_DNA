"""Frozen atom library for the TodoMVC stage (human-written, never edited by the model).

Every atom is a complete function body over the public state protocol (see shell.html).  Variants with
different semantics coexist on purpose: the requirement text (TodoMVC app spec) decides which one is right,
so a plan has to read the spec.  The deterministic rule control always takes the alphabetically first
variant of each slot, which is documented and model-independent.
"""
from __future__ import annotations

import hashlib
import json
import re

FEATURES = ['toggle', 'toggleAll', 'edit', 'counter', 'clearCompleted', 'routing']
CORE_EVENTS = ['add']
EVENTS = {'toggle': ['toggle'], 'toggleAll': ['toggleAll'], 'edit': ['edit', 'save', 'cancel'],
          'counter': [], 'clearCompleted': ['clearCompleted'], 'routing': ['route']}
VIEW_SLOTS = {'visible': 'core', 'countText': 'counter', 'allCompleted': 'toggleAll', 'hasCompleted': 'clearCompleted'}

ATOMS = [
    # ---- init (core: persistence) ----
    ('initEmpty', 'init', 'core', 'Start with no todos every load.',
     "function initEmpty(){return {todos:[],filter:'all',editing:null,nextId:1};}"),
    ('initFromStorage', 'init', 'core', "Load todos from localStorage key 'react-todos' (JSON array of {id,title,completed}); nextId above the largest id.",
     "function initFromStorage(){let todos=[];try{todos=JSON.parse(localStorage.getItem('react-todos')||'[]');}catch(e){todos=[];}"
     "if(!Array.isArray(todos))todos=[];const nextId=todos.reduce((m,t)=>Math.max(m,Number(t.id)||0),0)+1;return {todos,filter:'all',editing:null,nextId};}"),
    # ---- add (core) ----
    ('addRaw', 'event', 'core', 'Append a todo with the title exactly as typed, even if blank.',
     "function addRaw(s,e){s.todos.push({id:s.nextId++,title:e.title,completed:false});}"),
    ('addTrimmed', 'event', 'core', 'Trim the title; ignore empty input; append the todo to the end.',
     "function addTrimmed(s,e){const title=String(e.title).trim();if(!title)return;s.todos.push({id:s.nextId++,title,completed:false});}"),
    # ---- toggle ----
    ('toggle', 'event', 'toggle', 'Flip completed of the todo with e.id.',
     "function toggle(s,e){const t=s.todos.find(x=>x.id===e.id);if(t)t.completed=!t.completed;}"),
    ('toggleOnlyComplete', 'event', 'toggle', 'Mark the todo with e.id completed; never un-marks.',
     "function toggleOnlyComplete(s,e){const t=s.todos.find(x=>x.id===e.id);if(t)t.completed=true;}"),
    # ---- toggleAll ----
    ('toggleAllComplete', 'event', 'toggleAll', 'Mark every todo completed.',
     "function toggleAllComplete(s,e){for(const t of s.todos)t.completed=true;}"),
    ('toggleAllMatch', 'event', 'toggleAll', 'If every todo is completed, mark all active; otherwise mark all completed (checkbox state semantics).',
     "function toggleAllMatch(s,e){const all=s.todos.length>0&&s.todos.every(t=>t.completed);for(const t of s.todos)t.completed=!all;}"),
    # ---- edit ----
    ('editStart', 'event', 'edit', 'Enter editing mode for e.id.',
     "function editStart(s,e){s.editing=e.id;}"),
    ('saveRaw', 'event', 'edit', 'Store the edited title as typed (no trim, blank allowed) and leave editing mode.',
     "function saveRaw(s,e){const t=s.todos.find(x=>x.id===e.id);if(t)t.title=e.title;s.editing=null;}"),
    ('saveTrimDelete', 'event', 'edit', 'Trim the edited title; if empty, destroy the todo; otherwise store it; leave editing mode.',
     "function saveTrimDelete(s,e){const title=String(e.title).trim();if(!title){s.todos=s.todos.filter(x=>x.id!==e.id);}else{const t=s.todos.find(x=>x.id===e.id);if(t)t.title=title;}s.editing=null;}"),
    ('cancelEdit', 'event', 'edit', 'Leave editing mode and discard the draft.',
     "function cancelEdit(s,e){s.editing=null;}"),
    ('cancelKeepsDraft', 'event', 'edit', 'Leave editing mode but keep the edited title e.title (behaves like save without trimming).',
     "function cancelKeepsDraft(s,e){const t=s.todos.find(x=>x.id===e.id);if(t)t.title=e.title;s.editing=null;}"),
    # ---- clearCompleted ----
    ('clearAll', 'event', 'clearCompleted', 'Remove every todo.',
     "function clearAll(s,e){s.todos=[];}"),
    ('clearCompleted', 'event', 'clearCompleted', 'Remove completed todos only.',
     "function clearCompleted(s,e){s.todos=s.todos.filter(t=>!t.completed);}"),
    # ---- routing ----
    ('routeFilter', 'event', 'routing', "Set s.filter from e.filter ('all' | 'active' | 'completed').",
     "function routeFilter(s,e){s.filter=e.filter;}"),
    # ---- after hooks ----
    ('persistTodos', 'after', 'core', "After every event, write s.todos to localStorage key 'react-todos' as JSON.",
     "function persistTodos(s,e){localStorage.setItem('react-todos',JSON.stringify(s.todos));}"),
    ('closeEditorOnRoute', 'after', 'edit', 'After a route event, leave editing mode.',
     "function closeEditorOnRoute(s,e){if(e.type==='route')s.editing=null;}"),
    # ---- view slots ----
    ('visibleAll', 'view', 'core', 'visible: every todo regardless of filter.',
     "function visibleAll(s){return s.todos.map(t=>({id:t.id,title:t.title,completed:t.completed}));}"),
    ('visibleByFilter', 'view', 'core', "visible: todos filtered by s.filter ('active' = not completed, 'completed' = completed, 'all' = every).",
     "function visibleByFilter(s){return s.todos.filter(t=>s.filter==='all'||(s.filter==='active'?!t.completed:t.completed)).map(t=>({id:t.id,title:t.title,completed:t.completed}));}"),
    ('countPluralized', 'view', 'counter', "countText: active count with 'item'/'items' pluralized, e.g. '1 item left', '2 items left'.",
     "function countPluralized(s){const n=s.todos.filter(t=>!t.completed).length;return n+' '+(n===1?'item':'items')+' left';}"),
    ('countPlain', 'view', 'counter', "countText: active count always followed by 'items left'.",
     "function countPlain(s){return s.todos.filter(t=>!t.completed).length+' items left';}"),
    ('allCompleted', 'view', 'toggleAll', 'allCompleted: true when there is at least one todo and every todo is completed.',
     "function allCompleted(s){return s.todos.length>0&&s.todos.every(t=>t.completed);}"),
    ('hasCompleted', 'view', 'clearCompleted', 'hasCompleted: true when at least one todo is completed.',
     "function hasCompleted(s){return s.todos.some(t=>t.completed);}"),
]


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def library():
    functions = []
    for name, kind, feature, description, code in ATOMS:
        params = re.search(r'function\s+\w+\s*\(([^)]*)\)', code).group(1)
        functions.append({'name': name, 'kind': kind, 'feature': feature, 'description': description,
                          'signature': f'{name}({params})', 'code': code})
    data = {'origin': 'Human-written frozen atoms for the TodoMVC stage; semantic variants coexist on purpose',
            'functions': functions}
    data['sha256'] = digest(data)
    return data


# Which atoms may serve which slot (checked compiler), sorted so the rule control's default is the first name.
ROUTES = {'add': ['addRaw', 'addTrimmed'], 'toggle': ['toggle', 'toggleOnlyComplete'],
          'toggleAll': ['toggleAllComplete', 'toggleAllMatch'], 'edit': ['editStart'],
          'save': ['saveRaw', 'saveTrimDelete'], 'cancel': ['cancelEdit', 'cancelKeepsDraft'],
          'clearCompleted': ['clearAll', 'clearCompleted'], 'route': ['routeFilter']}
INITS = ['initEmpty', 'initFromStorage']
AFTERS = {'persistTodos': 'core', 'closeEditorOnRoute': 'edit'}
VIEWS = {'visible': ['visibleAll', 'visibleByFilter'], 'countText': ['countPlain', 'countPluralized'],
         'allCompleted': ['allCompleted'], 'hasCompleted': ['hasCompleted']}
