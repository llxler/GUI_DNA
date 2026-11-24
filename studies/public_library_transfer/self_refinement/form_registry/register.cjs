// Instrument existing class bindings in the scope where the model declared them.
const fs = require('fs');
const path = require('path');
const parser = require(path.resolve('artifacts/benchmark-probe/WebApp1k/staging/node_modules/@babel/parser'));
const {file, source, classes} = JSON.parse(fs.readFileSync(0, 'utf8'));
let program;
try { program = parser.parse(source,{sourceType:'module'}).program; }
catch(error) { console.log(JSON.stringify({source, recorded:[], exports:[], parse_error:error.code})); process.exit(0); }
const requested = new Set(classes);
const named = new Set();
const offsets = [];
const top = new Set();
for (const stmt of program.body) {
  const def = stmt.declaration || stmt;
  if (def.type === 'ClassDeclaration' && def.id) top.add(def.id.name);
  if (stmt.type === 'ExportNamedDeclaration') {
    if (def.type === 'ClassDeclaration' && def.id) named.add(def.id.name);
    for (const spec of stmt.specifiers || []) named.add(spec.exported.name || spec.exported.value);
  }
}
function walk(node) {
  if (!node || typeof node !== 'object') return;
  if (node.type==='ClassDeclaration' && requested.has(node.id?.name)) offsets.push([node.end,node.id.name]);
  Object.values(node).forEach(value => Array.isArray(value) ? value.forEach(walk) : walk(value));
}
walk(program);
let code=source;
for (const [pos, name] of offsets.sort((a,b)=>b[0]-a[0]))
  code=code.slice(0,pos)+'\n;globalThis.__diagnosticTypes['+JSON.stringify(name)+']='+name+';\n'+code.slice(pos);
const name = path.basename(file,'.js');
const addExport = requested.has(name) && top.has(name) && !named.has(name);
if (addExport) code+='\nexport { '+name+' };\n';
console.log(JSON.stringify({source:code,recorded:offsets.map(x=>x[1]),exports:addExport?[name]:[]}));
