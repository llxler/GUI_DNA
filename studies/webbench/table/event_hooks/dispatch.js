function bindAuthorEvents(tableEnv, hooks) {
  const env = {table: tableEnv.table, state: {}, api: tableEnv.api};
  let active = null;
  let anchor = null;
  function dismiss(event) {
    if (active) hooks.dismiss(env, anchor, null, event, active);
  }
  window.addEventListener('contextmenu', event => {
    if (!env.table.contains(event.target)) {
      dismiss(event);
      return;
    }
    dismiss(event);
    const cell = event.target.closest('td,th');
    const node = hooks.open(env, cell, null, event, null);
    if (!(node instanceof HTMLElement)) return;
    if (!node.isConnected) document.body.appendChild(node);
    active = node;
    anchor = cell;
    event.preventDefault();
    event.stopImmediatePropagation();
  }, true);
  window.addEventListener('click', event => {
    if (!active || !active.contains(event.target)) {
      dismiss(event);
      return;
    }
    hooks.command(env, anchor, event.target, event, active);
    dismiss(event);
    event.stopImmediatePropagation();
  }, true);
  window.addEventListener('click', event => {
    const cell = event.target.closest('td,th');
    if (cell && env.table.contains(cell)) hooks.select(env, cell, null, event, active);
  });
}
