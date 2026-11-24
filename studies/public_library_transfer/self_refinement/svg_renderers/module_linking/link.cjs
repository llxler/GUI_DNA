// Link only a top-level exported subclass to an unambiguous, explicitly named class export.
const {readFileSync} = require('node:fs');
const path = require('node:path').posix;
const {parseAst} = require(process.argv[2]);
const files = JSON.parse(readFileSync(0, 'utf8'));
const modules = new Map();
const exportsByName = new Map();

function bind(pattern, bindings) {
  if (!pattern) return;
  if (pattern.type === 'Identifier') bindings.add(pattern.name);
  else if (pattern.type === 'ObjectPattern')
    for (const p of pattern.properties) bind(p.value || p.argument, bindings);
  else if (pattern.type === 'ArrayPattern') pattern.elements.forEach(x => bind(x, bindings));
  else if (pattern.type === 'AssignmentPattern') bind(pattern.left, bindings);
  else if (pattern.type === 'RestElement') bind(pattern.argument, bindings);
}

for (const [filename, source] of Object.entries(files)) {
  let nodes;
  try { nodes = parseAst(source).body; } catch { continue; }
  const bindings = new Set(), parents = new Set(), classes = new Set(), named = new Set();
  for (const entry of nodes) {
    const d = entry.declaration || entry;
    if (d.type === 'ImportDeclaration') d.specifiers.forEach(s => bind(s.local, bindings));
    if (d.type === 'VariableDeclaration') d.declarations.forEach(x => bind(x.id, bindings));
    if (d.id) bind(d.id, bindings);
    if (d.type === 'ClassDeclaration' && d.id) classes.add(d.id.name);
    if (entry.type === 'ExportNamedDeclaration' && !entry.source) {
      if (d.type === 'ClassDeclaration' && d.id) named.add(d.id.name);
      for (const s of entry.specifiers || [])
        if (s.local.name === s.exported.name) named.add(s.exported.name);
    }
  }
  // Match only classes exported under their own name; plain browser scripts are untouched.
  for (const entry of nodes) {
    const d = entry.declaration || entry;
    if (d.type === 'ClassDeclaration' && classes.has(d.id?.name) && named.has(d.id.name)) {
      const name = d.id.name;
      if (!exportsByName.has(name)) exportsByName.set(name, []);
      exportsByName.get(name).push(filename);
      if (d.superClass?.type === 'Identifier' && !bindings.has(d.superClass.name))
        parents.add(d.superClass.name);
    }
  }
  modules.set(filename, parents);
}
const changes = {};
for (const [filename, parents] of modules) {
  const imports = [];
  for (const name of [...parents].sort()) {
    const candidates = exportsByName.get(name) || [];
    if (candidates.length !== 1 || candidates[0] === filename) continue;
    let from = path.relative(path.dirname(filename), candidates[0]);
    if (!from.startsWith('.')) from = './' + from;
    imports.push({name, from});
  }
  if (imports.length) changes[filename] = imports;
}
process.stdout.write(JSON.stringify(changes));
