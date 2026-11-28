function mountTransitions(env, programs) {
  const table = env.table;
  let anchor = null;
  let focus = null;
  const position = cell => cell && [cell.parentElement.rowIndex, cell.cellIndex];
  const element = p => Array.isArray(p) && table.rows[p[0]]?.cells[p[1]];
  window.addEventListener('keydown', event => {
    const group = programs.find(program => program.keys.includes(event.key.toLowerCase()));
    if (!group) return;
    const marked = Array.from(table.querySelectorAll('th.selected,td.selected'));
    const editing = table.querySelector('th[contenteditable="true"],td[contenteditable="true"]');
    const state = {key:event.key, ctrl:event.ctrlKey || event.metaKey, shift:event.shiftKey,
      rows:table.rows.length, cols:table.rows[0]?.cells.length || 0, selected:marked.map(position),
      focus:position(marked.includes(focus) ? focus : marked.at(-1)) || null,
      anchor:position(marked.includes(anchor) ? anchor : marked[0]) || null, editing:position(editing) || null};
    const patch = group.apply(state);
    if (!patch || typeof patch !== 'object' || !Object.keys(patch).length) return;
    if (patch.selection && !patch.selection.every(pos => element(pos))) return;
    if (patch.writes && !patch.writes.every(([r,c,v]) => element([r,c]) && typeof v === 'string')) return;
    if (patch.editing && !element(patch.editing)) return;
    if (!('selection' in patch || 'writes' in patch || 'editing' in patch)) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if (patch.selection) {
      const sel = patch.selection.map(element);
      for (const cell of marked) cell.classList.remove('selected');
      for (const cell of sel) cell.classList.add('selected');
      focus = element(patch.focus) || sel.at(-1) || null;
      anchor = element(patch.anchor) || sel[0] || null;
      Object.assign(env.state, {selected:new Set(sel), focus, anchor});
    }
    for (const [r,c,value] of (patch.writes || [])) table.rows[r].cells[c].textContent = value;
    if ('editing' in patch) {
      if (editing) { editing.contentEditable = 'false'; editing.blur(); }
      const cell = element(patch.editing) || null;
      if (cell) { cell.contentEditable = 'true'; cell.focus(); }
      env.state.editing = cell;
    }
  }, true);
}
