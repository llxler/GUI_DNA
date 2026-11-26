// Extract Boolean options the submitted source actually references. Other initializers stay in place.
const fs = require('node:fs');
const acorn = require(process.argv[2]);
const src = fs.readFileSync(0, 'utf8');
const tree = acorn.parse(src, {ecmaVersion:'latest',sourceType:'module'});
const declarations = [];
const referenced = new Set();
function walk(node) {
  if (!node || typeof node !== 'object') return;
  if (node.type === 'VariableDeclarator' && node.id.name === 'DNA_OPTIONS' && node.init?.type === 'ObjectExpression')
    declarations.push(node.init);
  if (node.type === 'MemberExpression' && node.object.name === 'DNA_OPTIONS') {
    const key = node.computed ? node.property.value : node.property.name;
    if (typeof key === 'string') referenced.add(key);
  }
  Object.values(node).forEach(walk);
}
walk(tree);
if (declarations.length !== 1) throw Error('Expected one DNA_OPTIONS object literal');
const obj=declarations[0], fields=[];
const counts=new Map();
for (const p of obj.properties) {
  const name=p.key?.name ?? p.key?.value;
  counts.set(name,(counts.get(name) || 0)+1);
}
for (const p of obj.properties) {
  const name=p.key?.name ?? p.key?.value;
  if (p.type==='Property' && !p.computed && p.kind==='init' && counts.get(name)===1 &&
      typeof p.value.value==='boolean' && /^[A-Za-z][A-Za-z0-9_-]{0,47}$/.test(name) && referenced.has(name)) {
    const key=name.replace(/([a-z0-9])([A-Z])/g,'$1-$2').replaceAll('_','-').toLowerCase();
    if (!fields.some(x=>x.key===key) && fields.length<6) fields.push({name,key,value:p.value.value});
  }
}
if (!fields.length) throw Error('No directly referenced Boolean choice');
process.stdout.write(JSON.stringify({fields, before:src.slice(0,obj.start), literal:src.slice(obj.start,obj.end), after:src.slice(obj.end)}));
