export default function install(env) {
  const items = /*ITEMS*/;
  const actions = /*ACTIONS*/;
  let menu = null;
  function close() {
    if (menu) menu.remove();
    menu = null;
  }
  document.addEventListener('contextmenu', event => {
    close();
    if (!env.table.contains(event.target)) return;
    event.preventDefault();
    const cell = event.target.closest('td,th');
    menu = document.createElement('div');
    menu.className = 'menu';
    Object.assign(menu.style, {position:'absolute', minWidth:'100px', minHeight:'100px',
      background:'white', zIndex:'1000', left:event.pageX+'px', top:event.pageY+'px'});
    for (const entry of items) {
      if (!cell || cell.tagName.toLowerCase() !== entry.scope) continue;
      const item = document.createElement('div');
      item.className = entry.className;
      item.textContent = entry.label;
      item.addEventListener('click', click => {
        const action = actions[entry.className];
        if (action) action(env.table, cell, env.state, env.api, click);
      });
      menu.appendChild(item);
    }
    document.body.appendChild(menu);
  });
  document.addEventListener('click', close);
}
