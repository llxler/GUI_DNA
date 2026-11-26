const table = document.querySelector('.table');
const menu = document.createElement('div');
menu.className = 'menu';
menu.hidden = true;
menu.style.display = 'none';
document.body.appendChild(menu);
const ctx = {table, menu, selected: new Set(), active: null, anchor: null, target: null};
const call = (name, ...args) => {
  if (handlers[name]) return handlers[name](ctx, ...args);
};
ctx.select = (cells, active, anchor) => call('markSelection', cells, active, anchor);
const items = [
  ['Insert Row Above', 'rowAction', 'body'], ['Insert Row Below', 'rowAction', 'body'],
  ['Delete Row', 'rowAction', 'body'], ['Select Row', 'selectGroup', 'body'],
  ['Insert Col Left', 'columnAction', 'head'], ['Insert Col Right', 'columnAction', 'head'],
  ['Delete Col', 'columnAction', 'head'], ['Select Col', 'selectGroup', 'head'],
  ['Filter', 'filterColumn', 'head'], ['Sort', 'sortColumn', 'head'],
];
const buttons = items.map(([label,handler,scope]) => {
  const el = document.createElement('div');
  el.className = 'menu-item-' + label.toLowerCase().replaceAll(' ', '-');
  el.textContent = label;
  menu.appendChild(el);
  el.addEventListener('click', e => call(handler, e, ctx.target, label));
  return {el,scope};
});
document.addEventListener('contextmenu', e => {
  const cell = e.target.closest('th,td');
  if (!cell || !table.contains(cell)) return call('menuVisibility', e, null, 'hide');
  ctx.target = cell;
  const scope = cell.tagName === 'TH' ? 'head' : 'body';
  for (const b of buttons) b.el.hidden = b.scope !== scope;
  call('menuVisibility', e, cell, 'show');
});
document.addEventListener('click', e => {
  call('menuVisibility', e, null, 'hide');
  const cell=e.target.closest('th,td');
  if (cell && table.contains(cell)) call('cellClick', e, cell);
});
table.addEventListener('dblclick', e => {
  const cell=e.target.closest('th,td');
  if (cell) call('editCell', e, cell);
});
document.addEventListener('keydown', e => {
  if (['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Tab'].includes(e.key)) call('navigate', e);
  else if (['Enter','Escape','Delete','Backspace','a','A'].includes(e.key)) call('editingKeys', e);
  else if (['c','C','v','V'].includes(e.key)) call('clipboardKeys', e);
});
for (const name of ['mousedown','mousemove','mouseup','dragstart','dragover','drop','dragend']) {
  document.addEventListener(name, e => {
    const cell=e.target.closest?.('td,th') || null;
    call('resizeCells', e, cell);
    call('reorderCells', e, cell);
    call('rangePointer', e, cell);
  });
}
