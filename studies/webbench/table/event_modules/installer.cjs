// Preserve local helpers and invoke the original one-argument default installer.
const acorn = require(process.argv[2]);
const fs = require('fs');
const source = fs.readFileSync(0, 'utf8');
const tree = acorn.parse(source, {ecmaVersion: 'latest', sourceType: 'module'});
const exported = tree.body.filter(n => n.type === 'ExportDefaultDeclaration');
if (exported.length !== 1 || tree.body.some(n => ['ImportDeclaration','ExportNamedDeclaration','ExportAllDeclaration'].includes(n.type))) {
  throw new Error('Expected exactly one default export and local declarations');
}
const n = exported[0], d = n.declaration;
if (!['FunctionDeclaration','ArrowFunctionExpression','FunctionExpression'].includes(d.type) || d.params.length !== 1) {
  throw new Error('Expected a one-argument installer');
}
const before = source.slice(0,n.start), after = source.slice(n.end);
const name = d.id?.name;
if (name && d.type === 'FunctionDeclaration') {
  process.stdout.write(before + source.slice(d.start,d.end) + after + '\n' + name + '(ctx);\n');
} else {
  process.stdout.write(before + 'const __moduleInstall = (' + source.slice(d.start,d.end) + ');' + after + '\n__moduleInstall(ctx);\n');
}
