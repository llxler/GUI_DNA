const handlers = HANDLERS;
const data = schema.data || {};
const ctx = {
  data,
  get: name => data[name],
  text: value => String(value ?? '').replace(/\$\{([\w.]+)\}/g, (_, name) => String(data[name] ?? '')),
  mount(parent, nodes) {
    for (const node of [].concat(nodes || [])) {
      if (!node || !handlers[node.type]) continue;
      const el = document.createElement('div');
      parent.append(el);
      handlers[node.type](el, node, ctx);
    }
  }
};
ctx.mount(document.getElementById('app'), schema);
