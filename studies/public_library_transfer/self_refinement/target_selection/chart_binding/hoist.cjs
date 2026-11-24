/* Relocate a pure declaration group after a public missing-binding error. */
const fs = require('node:fs');
const { parseAst } = require(process.argv[2]);

function children(node) {
  return Object.values(node).flatMap(value => Array.isArray(value) ? value : [value])
    .filter(value => value && typeof value.type === 'string');
}
function bound(pattern) {
  if (pattern.type === 'Identifier') return [pattern.name];
  if (pattern.type === 'ObjectPattern') return pattern.properties.flatMap(p => bound(p.value));
  if (pattern.type === 'ArrayPattern') return pattern.elements.filter(Boolean).flatMap(bound);
  return [];
}
function readOnly(node, names) {
  switch (node.type) {
    case 'Identifier': return names.has(node.name);
    case 'Literal': return typeof node.value === 'number';
    case 'SpreadElement': return readOnly(node.argument, names);
    case 'MemberExpression':
      return !node.computed && node.property.type === 'Identifier' && readOnly(node.object, names);
    case 'BinaryExpression':
      return ['+', '-', '*', '/', '%', '**'].includes(node.operator) &&
        readOnly(node.left, names) && readOnly(node.right, names);
    case 'ArrowFunctionExpression':
      return node.params.every(p => p.type === 'Identifier') &&
        readOnly(node.body, new Set([...names, ...node.params.map(p => p.name)]));
    case 'CallExpression': {
      const callee = node.callee;
      if (callee.type !== 'MemberExpression' || callee.computed) return false;
      const math = callee.object.type === 'Identifier' && callee.object.name === 'Math' &&
        ['min','max'].includes(callee.property.name);
      if (!math && callee.property.name !== 'flatMap') return false;
      return readOnly(callee.object, names) && node.arguments.every(arg => readOnly(arg, names));
    }
    default: return false;
  }
}
function repair(source, missing) {
  const tree = parseAst(source);
  const parents = new Map();
  const declarations = [];
  function visit(node, parent) {
    parents.set(node, parent);
    if (node.type === 'VariableDeclarator' && bound(node.id).includes(missing)) declarations.push(node);
    for (const child of children(node)) visit(child, node);
  }
  visit(tree, null);
  if (declarations.length !== 1) return null;
  const target = parents.get(declarations[0]);
  const inner = parents.get(target);
  const conditional = parents.get(inner);
  const outer = parents.get(conditional);
  if (inner?.type !== 'BlockStatement' || conditional?.type !== 'IfStatement' ||
      outer?.type !== 'BlockStatement' || inner !== conditional.consequent) return null;
  const elements = inner.body;
  const isConst = n => n?.type === 'VariableDeclaration' && n.kind === 'const' &&
    n.declarations.length === 1 && n.declarations[0].id.type === 'Identifier';
  let a = elements.indexOf(target), b = a;
  if (!isConst(elements[a])) return null;
  while (a && isConst(elements[a-1])) a--;
  while (b + 1 < elements.length && isConst(elements[b+1])) b++;
  const names = new Set(['Math']);
  for (const stmt of outer.body) {
    if (stmt === conditional) break;
    if (stmt.type === 'VariableDeclaration') {
      for (const decl of stmt.declarations) for (const name of bound(decl.id)) names.add(name);
    }
  }
  const group = elements.slice(a, b+1);
  for (const decl of group.map(v => v.declarations[0])) {
    if (names.has(decl.id.name) || !decl.init || !readOnly(decl.init, names)) return null;
    names.add(decl.id.name);
  }
  const chunk = source.slice(group[0].start, group.at(-1).end);
  const result = source.slice(0, conditional.start) + chunk + '\n' +
    source.slice(conditional.start, group[0].start) + source.slice(group.at(-1).end);
  parseAst(result);
  return { source: result, moved: group.map(v => v.declarations[0].id.name) };
}
const { files, missing } = JSON.parse(fs.readFileSync(0, 'utf8'));
const candidates = Object.entries(files).filter(([key]) => /\.(?:js|mjs)$/.test(key))
  .map(([key, value]) => [key, repair(value, missing)]).filter(([, value]) => value);
process.stdout.write(JSON.stringify(candidates.length === 1 ?
  { file: candidates[0][0], ...candidates[0][1] } : null));
