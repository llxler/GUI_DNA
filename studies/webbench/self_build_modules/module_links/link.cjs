// Resolve only symbols already present in the supplied ES modules.
const fs = require('node:fs');
const path = require('node:path').posix;
const load = require('node:module').createRequire(process.argv[2]);
const parser = load('@babel/parser');
const traverse = load('@babel/traverse').default;
const {files, available} = JSON.parse(fs.readFileSync(0, 'utf8'));
const modules = {}, owners = new Map(), changes=[], missing=[];
for (const [file,source] of Object.entries(files)) {
  if (!file.endsWith('.js') && !file.endsWith('.mjs')) continue;
  const ast = parser.parse(source,{sourceType:'module'});
  const m = modules[file]={names:new Set(), exports:new Set(), imports:[], free:new Set(), before:[], after:[]};
  traverse(ast, {
    Program(p) {
      for (const [name,binding] of Object.entries(p.scope.bindings)) {
        if (binding.kind==='module') continue;
        m.names.add(name);
        if (!owners.has(name)) owners.set(name,[]);
        owners.get(name).push(file);
      }
    },
    ImportDeclaration(p) {
      const n=p.node;
      if (!n.source.value.startsWith('.') && !n.source.value.startsWith('/')) return;
      const target=path.normalize(path.join(n.source.value.startsWith('/')?'':path.dirname(file),n.source.value)).replace(/^\//,'');
      m.imports.push({target,specs:n.specifiers});
      if (!available.includes(target)) missing.push({source:file,target,statement:source.slice(n.start,n.end)});
    },
    ExportDefaultDeclaration(){m.exports.add('default')},
    ExportNamedDeclaration(p) {
      const n=p.node;
      for (const x of n.specifiers) m.exports.add(x.exported.name || x.exported.value);
      if (n.declaration?.id?.name) m.exports.add(n.declaration.id.name);
      for (const x of n.declaration?.declarations || []) if (x.id.name) m.exports.add(x.id.name);
    },
    ReferencedIdentifier(p){if (!p.scope.hasBinding(p.node.name,true)) m.free.add(p.node.name)}
  });
}
function expose(file,name,out) {
  const m=modules[file];
  if (!m || m.exports.has(out) || !m.names.has(name)) return;
  m.after.push('export { '+name+(out===name?'':' as '+out)+' };');
  m.exports.add(out);
  changes.push({op:'export',file,name,out});
}
for (const [file,m] of Object.entries(modules)) {
  for (const {target,specs} of m.imports) {
    for (const x of specs) {
      if (x.type==='ImportSpecifier') expose(target,x.imported.name,x.imported.name);
      else if (x.type==='ImportDefaultSpecifier') expose(target,x.local.name,'default');
    }
  }
  for (const name of m.free) {
    const valid=owners.get(name)||[];
    if (valid.length!==1 || valid[0]===file) continue;
    const target=valid[0];
    expose(target,name,name);
    let relative=path.relative(path.dirname(file),target);
    if (!relative.startsWith('.')) relative='./'+relative;
    m.before.push('import { '+name+' } from '+JSON.stringify(relative)+';');
    changes.push({op:'import',file,name,target});
  }
}
for (const [file,m] of Object.entries(modules)) {
  if (m.before.length||m.after.length) files[file]=[...m.before,files[file],...m.after].join('\n');
}
console.log(JSON.stringify({files,changes,missing}));
