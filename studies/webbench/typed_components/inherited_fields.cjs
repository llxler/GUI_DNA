// Remove empty subclass field declarations that overwrite a known initialized ancestor field.
const fs = require('node:fs');
const path = require('node:path').posix;
const acorn = require(process.argv[2]);
const files = JSON.parse(fs.readFileSync(0,'utf8'));
const defs = new Map();
const imports = new Map();
for (const [file, source] of Object.entries(files)) {
  const tree = acorn.parse(source, {ecmaVersion:'latest', sourceType:'module'});
  const bindings = new Map();
  imports.set(file, bindings);
  for (const node of tree.body) {
    if (node.type === 'ImportDeclaration') {
      for (const spec of node.specifiers) {
        if (spec.type === 'ImportSpecifier') bindings.set(spec.local.name, [path.join(path.dirname(file),node.source.value),spec.imported.name]);
      }
    }
    const klass = node.declaration ?? node;
    if (klass.type === 'ClassDeclaration' && klass.id) defs.set(file+'#'+klass.id.name,{file,klass});
  }
}
function writes(node, fields) {
  if (!node || typeof node !== 'object') return;
  if (node.type==='AssignmentExpression' && node.operator==='=' && node.left.type==='MemberExpression' &&
      !node.left.computed && node.left.object.type==='ThisExpression') fields.add(node.left.property.name);
  for (const child of Object.values(node)) writes(child,fields);
}
function ancestorFields(def, visited) {
  const parent = def.klass.superClass?.name;
  if (!parent) return new Set();
  const route = imports.get(def.file).get(parent) ?? [def.file,parent];
  const key = route.join('#');
  if (!defs.has(key) || visited.has(key)) return new Set();
  visited.add(key);
  const base = defs.get(key);
  const fields = ancestorFields(base,visited);
  for (const member of base.klass.body.body) {
    if (member.kind === 'constructor') writes(member.value.body,fields);
    if (member.type === 'PropertyDefinition' && !member.static && !member.computed && member.value) fields.add(member.key.name);
  }
  return fields;
}
const output = {};
for (const def of defs.values()) {
  const inherited=ancestorFields(def,new Set());
  for (const member of def.klass.body.body) {
    if (member.type==='PropertyDefinition' && !member.static && !member.computed && !member.value && inherited.has(member.key.name)) {
      (output[def.file]??=[]).push({klass:def.klass.id.name,field:member.key.name,start:member.start,end:member.end});
    }
  }
}
process.stdout.write(JSON.stringify(output));
