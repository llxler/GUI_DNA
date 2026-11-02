"""Frozen atom library for the Web-Bench dom1 stage.

Atoms are the behaviours of the benchmark's own reference solution (bytedance/web-bench projects/dom1/src,
Apache-2.0), de-modularised into plain functions over a shared state object `S`, plus deliberate semantic
variants for the slots whose rules the task descriptions spell out (selection, insertion, deletion, drag/drop,
menu labels).  The compiler links exactly the atoms a plan names; atom bodies are never edited.
"""
from __future__ import annotations

import hashlib
import json
import re

# ---------------------------------------------------------------- feature ladder (cumulative, one per task)
FEATURES = ['tools', 'addFile', 'addDir', 'selection', 'delete', 'drag', 'menuEntry', 'menuPanel', 'copyPaste', 'rename',
            'import', 'export', 'autosave', 'shortcuts', 'deleteShortcut', 'generate', 'resizer', 'resizerDrag', 'filter', 'cut']
TOOLS = {'file': 'tools', 'dir': 'tools', 'del': 'tools', 'imp': 'import', 'exp': 'export', 'gen': 'generate', 'filter': 'filter'}
TOOL_BEHAVIOUR = {'file': 'addFile', 'dir': 'addDir', 'del': 'delete', 'imp': 'import', 'exp': 'export', 'gen': 'generate', 'filter': 'filter'}
COMMANDS = {'add file': 'menuEntry', 'add dir': 'menuEntry', 'delete': 'menuEntry', 'copy': 'copyPaste', 'paste': 'copyPaste',
            'rename': 'rename', 'cut': 'cut'}
SHORTCUT_KEYS = {'c': 'copy', 'v': 'paste', 'j': 'add file', 'k': 'add dir', 'x': 'cut', 'delete': 'delete', 'backspace': 'delete'}

ATOMS = [
    # ---- helpers (always linked) ----
    ('state', 'helper', 'core', 'Shared state: selected entry, clipboard, menu element, id counters, tool buttons.',
     "const S = { selected: null, copied: null, isCut: false, menu: null, fileUid: 0, dirUid: 0, lastKeyword: '', tools: {} };"),
    ('injectStyle', 'helper', 'core', 'Append a <style> element.',
     "function injectStyle(css) { const s = document.createElement('style'); s.textContent = css; document.head.appendChild(s); }"),
    ('entriesPanel', 'helper', 'core', 'The .entries element.',
     "function entriesPanel() { return document.querySelector('.entries'); }"),
    ('getName', 'helper', 'core', 'Name of an entry = its first text node.',
     "function getName(ent) { const n = Array.from(ent.childNodes).find((x) => x.nodeType === Node.TEXT_NODE); return n && n.nodeValue ? n.nodeValue.trim() : ''; }"),
    ('setName', 'helper', 'core', 'Rename an entry by replacing its first text node.',
     "function setName(ent, name) { const n = Array.from(ent.childNodes).find((x) => x.nodeType === Node.TEXT_NODE); if (n) n.nodeValue = name; }"),
    ('isEntry', 'helper', 'core', 'True for file or dir elements.',
     "function isEntry(ent) { return !!ent && ent.classList && (ent.classList.contains('file') || ent.classList.contains('dir')); }"),
    ('noop', 'helper', 'core', 'Does nothing (used for disabled slots).', 'function noop() {}'),
    # ---- tools ----
    ('toolsInit', 'infra', 'tools', "Create one <button> per name inside .tools (in order) and bind each to its action.",
     "function toolsInit(names, actions) { const tools = document.querySelector('.tools'); for (const name of names) { const b = document.createElement('button'); b.textContent = name; b.addEventListener('click', () => { if (actions[name]) actions[name](); }); tools.appendChild(b); S.tools[name] = b; } }"),
    ('styleEntries', 'infra', 'addFile', 'CSS for entries: selected highlight, dir caret, dir-content hidden unless dir has class open, drag states.',
     "function styleEntries() { injectStyle(\".entry{padding:3px 0 0 16px;cursor:pointer}.entry.selected,.entry:hover{background-color:#333}.dir{padding-left:0}.dir::before{width:16px;text-align:center;content:'\\u203a';display:inline-block}.dir.open::before{transform:rotate(90deg)}.dir-content{display:none;padding-left:16px;background-color:#1f1f1f}.dir.open>.dir-content{display:block}.entry.dragging{opacity:.5}.entry.dragover,.entries.dragover{border-bottom:2px solid #666}.dir.dragover,.entries.dragover{background-color:#333}\"); }"),
    # ---- selection (slot `select`) ----
    ('selectToggleDir', 'event', 'addFile', "setSelected(ent): move class 'selected' to ent (or none); if ent is a dir, toggle its class 'open'; enable the del button only when something is selected.",
     "function selectToggleDir(ent) { const old = S.selected; S.selected = ent; if (old) old.classList.remove('selected'); if (ent) { ent.classList.add('selected'); if (ent.classList.contains('dir')) ent.classList.toggle('open'); } if (S.tools.del) S.tools.del.disabled = !ent; }"),
    ('selectPlain', 'event', 'addFile', "setSelected(ent): move class 'selected' to ent (or none); never changes a dir's open state; enable the del button only when something is selected.",
     "function selectPlain(ent) { const old = S.selected; S.selected = ent; if (old) old.classList.remove('selected'); if (ent) ent.classList.add('selected'); if (S.tools.del) S.tools.del.disabled = !ent; }"),
    # ---- files ----
    ('fileCreate', 'infra', 'addFile', "Create a div.entry.file with a unique id, text = name, attribute data-content.",
     "function fileCreate(name, content) { const ent = document.createElement('div'); ent.classList.add('entry'); ent.classList.add('file'); const id = 'file-' + (S.fileUid++); ent.id = id; ent.textContent = name || id; ent.setAttribute('data-content', content); return ent; }"),
    ('fileAdd', 'event', 'addFile', 'fileAdd(target?, name?, content?): create a file (random name/content by default), make it draggable, insert it with the insert rule.',
     "function fileAdd(target, name, content) { if (name === undefined) name = 'file-' + S.fileUid + '.txt'; if (content === undefined) content = 'file content from ' + name; const ent = fileCreate(name, content); enableDrag(ent); return insertEntry(ent, target); }"),
    ('fileClickOpen', 'event', 'addFile', 'Clicking a file selects it and shows its data-content in the editor (editor remembers the file id).',
     "function fileClickOpen(ent) { setSelected(ent); const editor = document.querySelector('.editor'); if (editor) { editor.value = ent.getAttribute('data-content'); editor.setAttribute('data-file-id', ent.id); } }"),
    ('fileClickSelect', 'event', 'addFile', 'Clicking a file only selects it; the editor is untouched.',
     "function fileClickSelect(ent) { setSelected(ent); }"),
    # ---- dirs ----
    ('dirCreate', 'infra', 'addDir', 'Create a div.entry.dir with a unique id, text = name and an empty child div.dir-content.',
     "function dirCreate(name) { const ent = document.createElement('div'); ent.classList.add('entry'); ent.classList.add('dir'); const id = 'dir-' + (S.dirUid++); ent.id = id; ent.textContent = name; const c = document.createElement('div'); c.className = 'dir-content'; ent.appendChild(c); return ent; }"),
    ('dirAdd', 'event', 'addDir', 'dirAdd(target?, name?): create a dir (random name by default), make it draggable, insert it with the insert rule.',
     "function dirAdd(target, name) { if (name === undefined) name = 'dir-' + S.dirUid; const ent = dirCreate(name); enableDrag(ent); return insertEntry(ent, target); }"),
    ('dirClick', 'event', 'addDir', 'Clicking a dir selects it (the select rule decides whether that toggles open).',
     "function dirClick(ent) { setSelected(ent); }"),
    # ---- insertion (slot `insert`) ----
    ('insertRelative', 'event', 'selection', 'insertEntry(ent, target?): target defaults to the selected entry; no target or the panel -> append to the panel; a file -> insert right after it; a dir -> open it and append inside its dir-content. The new entry becomes selected.',
     "function insertRelative(ent, target) { if (target === undefined) target = S.selected; if (!target || target.classList.contains('entries')) { entriesPanel().appendChild(ent); } else if (target.classList.contains('file')) { target.after(ent); } else if (target.classList.contains('dir')) { if (!target.classList.contains('open')) target.classList.add('open'); target.querySelector('.dir-content').appendChild(ent); } setSelected(ent); return ent; }"),
    ('insertAppend', 'event', 'selection', 'insertEntry(ent, target?): a dir target -> append inside its dir-content (without opening it); anything else -> append to the end of the panel. The new entry becomes selected.',
     "function insertAppend(ent, target) { if (target && target.classList && target.classList.contains('dir')) { target.querySelector('.dir-content').appendChild(ent); } else { entriesPanel().appendChild(ent); } setSelected(ent); return ent; }"),
    # ---- deletion (slot `delete`) ----
    ('removeNextPrevParent', 'event', 'delete', 'removeEntry(ent?): delete ent (default: selected); clear the editor if it showed that file; then select its next sibling, else previous sibling, else parent dir (opening a dir).',
     "function removeNextPrevParent(ent) { if (!ent) ent = S.selected; if (!ent) return; let next = ent.nextElementSibling; if (!next) { next = ent.previousElementSibling; if (!next) next = ent.parentElement ? ent.parentElement.closest('.entry.dir') : null; } if (ent.classList.contains('file')) { const editor = document.querySelector('.editor'); if (editor && editor.value === ent.getAttribute('data-content')) editor.value = ''; } ent.remove(); if (!next) { setSelected(null); } else { next.click(); if (next.classList.contains('dir') && !next.classList.contains('open')) next.classList.add('open'); } }"),
    ('removeSimple', 'event', 'delete', 'removeEntry(ent?): delete ent (default: selected); clear the editor if it showed that file; nothing is selected afterwards.',
     "function removeSimple(ent) { if (!ent) ent = S.selected; if (!ent) return; if (ent.classList.contains('file')) { const editor = document.querySelector('.editor'); if (editor && editor.value === ent.getAttribute('data-content')) editor.value = ''; } ent.remove(); setSelected(null); }"),
    # ---- drag & drop (slot `drag`) ----
    ('dragEnable', 'infra', 'drag', 'enableDrag(el): make an entry (or the panel) a drag source and drop target; drops are resolved by the drop rule.',
     "function dragEnable(el) { el.draggable = true; el.addEventListener('dragstart', function (e) { e.stopPropagation(); this.classList.add('dragging'); if (e.dataTransfer) { e.dataTransfer.setData('text/plain', this.id); e.dataTransfer.effectAllowed = 'move'; } }); el.addEventListener('dragend', function (e) { e.stopPropagation(); this.classList.remove('dragging'); document.querySelectorAll('.entry').forEach((x) => x.classList.remove('dragover')); }); el.addEventListener('dragover', function (e) { e.preventDefault(); e.stopPropagation(); if (e.dataTransfer) e.dataTransfer.dropEffect = 'move'; this.classList.add('dragover'); }); el.addEventListener('dragleave', function (e) { e.stopPropagation(); this.classList.remove('dragover'); }); el.addEventListener('drop', function (e) { e.preventDefault(); e.stopPropagation(); const id = e.dataTransfer ? e.dataTransfer.getData('text/plain') : ''; const dragged = document.getElementById(id); if (!dragged || dragged === this || dragged.contains(this)) return; this.classList.remove('dragover'); dropRule(dragged, this, e); setSelected(dragged); }); }"),
    ('dropHalfRule', 'event', 'drag', 'dropRule(dragged, target, e): onto the panel -> append to the panel; onto a dir -> left half: open it and append inside, right half: insert after it; onto a file -> insert after it.',
     "function dropHalfRule(dragged, target, e) { if (target.classList.contains('entries')) { target.appendChild(dragged); } else if (target.classList.contains('dir')) { const r = target.getBoundingClientRect(); if (e.clientX < r.left + r.width / 2) { if (!target.classList.contains('open')) target.classList.add('open'); target.querySelector('.dir-content').appendChild(dragged); } else { target.after(dragged); } } else { target.after(dragged); } }"),
    ('dropAppendOnly', 'event', 'drag', 'dropRule(dragged, target, e): onto a dir -> append inside it; onto anything else -> append to the end of the panel.',
     "function dropAppendOnly(dragged, target, e) { if (target.classList.contains('dir')) { if (!target.classList.contains('open')) target.classList.add('open'); target.querySelector('.dir-content').appendChild(dragged); } else { entriesPanel().appendChild(dragged); } }"),
    # ---- context menu ----
    ('menuInit', 'infra', 'menuEntry', 'Create the div.menu, hide it on any click, show it on right-click of an entry or of the panel.',
     "function menuInit() { injectStyle('.menu{position:fixed;background:#2f2f2f;border:1px solid #444;padding:4px 0;min-width:150px;display:none;z-index:1000}.menu-item{padding:6px 12px;cursor:pointer}.menu-item:hover{background:#3f3f3f}'); S.menu = document.createElement('div'); S.menu.className = 'menu'; document.body.appendChild(S.menu); document.addEventListener('click', () => { S.menu.style.display = 'none'; }); entriesPanel().addEventListener('contextmenu', (e) => { const t = e.target; if (t.classList.contains('entry') || t.classList.contains('entries')) { e.preventDefault(); menuShow(t, e.pageX, e.pageY); } }); }"),
    ('menuShow', 'infra', 'menuEntry', "menuShow(target, x, y): fill the menu with the commands configured for the target kind (file / dir / entries); 'paste' is listed only while the clipboard holds an entry; each item has classes menu-item and menu-item-<command-with-dashes>.",
     "function menuShow(target, x, y) { S.menu.innerHTML = ''; const kind = target.classList.contains('entries') ? 'entries' : target.classList.contains('dir') ? 'dir' : 'file'; for (const command of (MENU[kind] || [])) { if (command === 'paste' && !S.copied) continue; const item = document.createElement('div'); item.className = 'menu-item menu-item-' + command.replace(/\\s+/g, '-'); item.textContent = menuLabel(command); item.addEventListener('click', () => { COMMANDS[command](target); }); S.menu.appendChild(item); } S.menu.style.display = 'block'; S.menu.style.left = x + 'px'; S.menu.style.top = y + 'px'; }"),
    ('menuLabelShortcut', 'view', 'shortcuts', "menuLabel(command): command text followed by its shortcut, e.g. 'copy (Cmd+C)' on macOS / 'copy (Ctrl+C)' elsewhere, 'delete (Delete|Backspace)'.",
     "function menuLabelShortcut(command) { const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0; const cmd = isMac ? 'Cmd' : 'Ctrl'; const key = SHORTCUT_OF[command]; if (!key) return command; return command + ' (' + (key === 'delete' ? 'Delete|Backspace' : cmd + '+' + key.toUpperCase()) + ')'; }"),
    ('menuLabelPlain', 'view', 'shortcuts', 'menuLabel(command): the bare command text.',
     "function menuLabelPlain(command) { return command; }"),
    # ---- clipboard ----
    ('cloneEntry', 'infra', 'copyPaste', 'Deep-clone an entry with fresh ids for it and every nested entry; clones stay draggable.',
     "function cloneEntry(ent) { const c = ent.cloneNode(true); c.id = (ent.classList.contains('file') ? 'file-' : 'dir-') + (ent.classList.contains('file') ? S.fileUid++ : S.dirUid++); c.classList.remove('selected'); enableDrag(c); c.querySelectorAll('.entry').forEach((child) => { child.id = (child.classList.contains('file') ? 'file-' : 'dir-') + (child.classList.contains('file') ? S.fileUid++ : S.dirUid++); child.classList.remove('selected'); enableDrag(child); }); return c; }"),
    ('cmdCopy', 'event', 'copyPaste', 'copy(target): remember target as the clipboard entry (not a cut).',
     "function cmdCopy(target) { if (!isEntry(target)) return; S.copied = target; S.isCut = false; }"),
    ('cmdPaste', 'event', 'copyPaste', 'paste(target): if the clipboard holds an entry, insert a clone at target with the insert rule (a cut entry is removed first); a pasted dir keeps its open state.',
     "function cmdPaste(target) { if (!S.copied) return; const wasOpen = S.copied.classList.contains('open'); if (S.isCut) removeEntry(S.copied); const c = cloneEntry(S.copied); insertEntry(c, target); if (c.classList.contains('dir')) { if (wasOpen) c.classList.add('open'); else c.classList.remove('open'); } }"),
    ('cmdCut', 'event', 'cut', 'cut(target): remember target as the clipboard entry and mark it as cut (removed when pasted).',
     "function cmdCut(target) { if (!isEntry(target)) return; S.copied = target; S.isCut = true; }"),
    # ---- rename / import / export / generate ----
    ('renameEntry', 'event', 'rename', 'rename(target): prompt for a new name; trim it; ignore empty input and names already used by a sibling.',
     "function renameEntry(target) { if (!isEntry(target)) return; const current = getName(target); let name = prompt('Rename entry:', current); if (!name || !name.trim()) return; name = name.trim(); if (name === current) return; const siblings = target.parentElement ? target.parentElement.querySelectorAll('.entry') : []; const dup = Array.from(siblings).some((x) => x !== target && getName(x) === name); if (!dup) setName(target, name); }"),
    ('toJSON', 'infra', 'export', 'Serialise an entry: {type:file,name,content} or {type:dir,name,children:[...]}.',
     "function toJSON(ent) { if (ent.classList.contains('file')) return { type: 'file', name: getName(ent), content: ent.getAttribute('data-content') }; const c = ent.querySelector('.dir-content'); return { type: 'dir', name: getName(ent), children: Array.from(c ? c.children : []).filter((x) => x.classList.contains('entry')).map(toJSON) }; }"),
    ('exportAll', 'event', 'export', 'exportAll(): alert(JSON.stringify({entries:[...]})) for the root entries.',
     "function exportAll() { const ents = Array.from(document.querySelectorAll('.entries > .entry')); alert(JSON.stringify({ entries: ents.map(toJSON) })); }"),
    ('importAll', 'event', 'import', 'importAll(): prompt for JSON {entries:[...]}; clear the panel and recreate files (name, content) and dirs (name, children) recursively.',
     "function importAll() { try { const text = prompt('JSON data to import:'); if (!text) return; const data = JSON.parse(text); if (!data || !Array.isArray(data.entries)) return; const panel = entriesPanel(); panel.innerHTML = ''; setSelected(null); const add = (item, parent) => { if (item.type === 'file') { fileAdd(parent, item.name, item.content); } else if (item.type === 'dir') { const d = dirAdd(parent, item.name); (item.children || []).forEach((child) => add(child, d)); } }; data.entries.forEach((item) => add(item, panel)); } catch (error) { console.error(error); } }"),
    ('generateEntries', 'event', 'generate', 'generateEntries(): add 100 random root entries; each generated dir gets up to 10 random children.',
     "function generateEntries() { const panel = entriesPanel(); const rnd = (n) => Math.floor(Math.random() * n); for (let i = 0; i < 100; i++) { if (rnd(2) === 0) { fileAdd(panel); } else { const d = dirAdd(panel); const n = rnd(10); for (let j = 0; j < n; j++) { if (rnd(2) === 0) fileAdd(d); else dirAdd(d); } } } }"),
    # ---- editor autosave ----
    ('autosaveInit', 'infra', 'autosave', 'On every keyup in the editor, copy its value into data-content of the file it is showing.',
     "function autosaveInit() { const editor = document.querySelector('.editor'); editor.addEventListener('keyup', (e) => { const id = editor.getAttribute('data-file-id'); if (!id) return; const file = document.getElementById(id); if (file) file.setAttribute('data-content', editor.value); }); }"),
    # ---- shortcuts ----
    ('shortcutsInit', 'infra', 'shortcuts', "shortcutsInit(map): keydown on the document; map keys 'c','v','j','k','x' need Cmd (macOS) / Ctrl; 'delete' and 'backspace' need no modifier; ignored while typing in the editor or an input; target = selected entry, else the panel (copy/cut/delete need an entry).",
     "function shortcutsInit(map) { document.addEventListener('keydown', (e) => { const tag = (document.activeElement && document.activeElement.tagName ? document.activeElement.tagName : '').toLowerCase(); if (tag === 'textarea' || tag === 'input') return; const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0; const cmdKey = isMac ? e.metaKey : e.ctrlKey; const key = e.key.toLowerCase(); const ent = S.selected || entriesPanel(); const command = map[key]; if (!command) return; const plain = key === 'delete' || key === 'backspace'; if (plain ? cmdKey : !cmdKey) return; if ((command === 'copy' || command === 'cut' || command === 'delete') && !isEntry(ent)) return; if (!COMMANDS[command]) return; COMMANDS[command](ent); e.preventDefault(); }, false); }"),
    # ---- resizer ----
    ('resizerShow', 'infra', 'resizer', 'Append div.resizer at the right edge of the leftbar (absolute, hidden; visible while the leftbar is hovered).',
     "function resizerShow() { injectStyle('.resizer{display:none;position:absolute;cursor:ew-resize;background-color:#999;width:3px;height:100%;right:0;top:0}.leftbar:hover .resizer{display:block}'); const r = document.createElement('div'); r.className = 'resizer'; document.querySelector('.leftbar').appendChild(r); }"),
    ('resizerDrag', 'infra', 'resizerDrag', 'Dragging the resizer horizontally changes the leftbar width.',
     "function resizerDrag() { const leftbar = document.querySelector('.leftbar'); const resizer = document.querySelector('.resizer'); if (!resizer) return; let dragging = false, startX = 0, startWidth = 0; resizer.addEventListener('mousedown', (e) => { dragging = true; startX = e.pageX; startWidth = leftbar.offsetWidth; }); document.addEventListener('mousemove', (e) => { if (!dragging) return; leftbar.style.width = (startWidth + e.pageX - startX) + 'px'; e.preventDefault(); }); document.addEventListener('mouseup', () => { dragging = false; }); }"),
    # ---- filter ----
    ('filterContains', 'event', 'filter', 'filterEntries(keyword): case-insensitive substring match on entry names; non-matching entries are hidden, matching ones shown with their parent dirs opened; an empty keyword shows everything.',
     "function filterContains(keyword) { if (!keyword.trim()) { document.querySelectorAll('.entry').forEach((ent) => { ent.style.display = ''; }); return; } document.querySelectorAll('.entry').forEach((ent) => { if (getName(ent).toLowerCase().includes(keyword.toLowerCase())) { ent.style.display = ''; let p = ent.parentElement; while (p && !p.classList.contains('entries')) { if (p.classList.contains('dir')) { if (!p.classList.contains('open')) p.classList.add('open'); p.style.display = ''; } p = p.parentElement; } } else { ent.style.display = 'none'; } }); }"),
    ('showFilterDialog', 'event', 'filter', 'showFilterDialog(): prompt for a keyword (remembering the last one) and apply the filter rule.',
     "function showFilterDialog() { const keyword = prompt('Enter filter keyword:', S.lastKeyword); if (keyword !== null) { S.lastKeyword = keyword; filterEntries(keyword); } }"),
]

# Slots a plan fills with one atom name each (sorted so the rule control's default is the alphabetically first).
SLOTS = {
    'select': ['selectPlain', 'selectToggleDir'],
    'fileClick': ['fileClickOpen', 'fileClickSelect'],
    'insert': ['insertAppend', 'insertRelative'],
    'delete': ['removeNextPrevParent', 'removeSimple'],
    'drag': ['dropAppendOnly', 'dropHalfRule'],
    'menuLabel': ['menuLabelPlain', 'menuLabelShortcut'],
}
SLOT_FEATURE = {'select': 'addFile', 'fileClick': 'addFile', 'insert': 'selection', 'delete': 'delete', 'drag': 'drag', 'menuLabel': 'shortcuts'}


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def library():
    functions = []
    for name, kind, feature, description, code in ATOMS:
        m = re.search(r'function\s+\w+\s*\(([^)]*)\)', code)
        functions.append({'name': name, 'kind': kind, 'feature': feature, 'description': description,
                          'signature': f'{name}({m.group(1)})' if m else name, 'code': code})
    data = {'origin': 'Web-Bench dom1 reference solution (bytedance/web-bench, Apache-2.0) decomposed into frozen atoms plus semantic variants',
            'functions': functions}
    data['sha256'] = digest(data)
    return data
