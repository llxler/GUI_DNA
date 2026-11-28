export default function install(env) {
  const handlers = /*HANDLERS*/;
  document.addEventListener('keydown', event => {
    const entry = handlers.find(([keys]) => keys.includes(event.key.toLowerCase()));
    if (!entry) return;
    const table = env.table;
    const selected = Array.from(table.querySelectorAll('th.selected,td.selected'));
    const live = node => node instanceof Element && table.contains(node);
    const focus = live(env.state.focus) ? env.state.focus : (selected.at(-1) || null);
    const anchor = live(env.state.anchor) ? env.state.anchor : (selected[0] || null);
    entry[1](event, table, env.state, env.api, selected, focus, anchor);
  });
}
