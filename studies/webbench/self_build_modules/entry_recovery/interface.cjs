// Inspect the model's literal and its actual property reads without evaluating source.
const fs = require('node:fs');
const acorn = require(process.argv[2]);
const source = fs.readFileSync(0, 'utf8');
const tree = acorn.parse(source, {ecmaVersion:'latest', sourceType:'module'});
const declarations = [];
const reads = new Set();
function walk(node) {
  if (!node || typeof node !== 'object') return;
  if (node.type === 'VariableDeclarator' && node.id.name === 'DNA_OPTIONS' && node.init?.type === 'ObjectExpression')
    declarations.push(node.init);
  if (node.type === 'MemberExpression' && node.object.name === 'DNA_OPTIONS') {
    const name = node.computed ? node.property.value : node.property.name;
    if (typeof name === 'string') reads.add(name);
  }
  for (const child of Object.values(node)) walk(child);
}
walk(tree);
if (declarations.length !== 1) throw Error('Declare exactly one const DNA_OPTIONS with a simple object literal.');
const obj = declarations[0];
const fields = {};
for (const p of obj.properties) {
  const k = p.key?.name ?? p.key?.value;
  if (p.type !== 'Property' || p.computed || !/^[A-Za-z][A-Za-z0-9_-]{0,47}$/.test(k) ||
      typeof p.value.value !== 'boolean' || Object.hasOwn(fields,k) || !reads.has(k))
    throw Error('Every named Boolean literal in DNA_OPTIONS must be read by a behavior.');
  fields[k] = p.value.value;
}
if (Object.keys(fields).length < 1 || Object.keys(fields).length > 4)
  throw Error('Declare one to four behavior options.');
console.log(JSON.stringify({fields, before:source.slice(0,obj.start), literal:source.slice(obj.start,obj.end), after:source.slice(obj.end)}));
