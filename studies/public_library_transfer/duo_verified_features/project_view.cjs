// Keep complete JSX subtrees from the donor, including its original event bindings.
const fs = require('fs');
const path = require('path');
const parser = require(path.resolve('artifacts/benchmark-probe/WebApp1k/staging/node_modules/@babel/parser'));
const source = fs.readFileSync(0, 'utf8');
const program = parser.parse(source, {sourceType: 'module', plugins: ['jsx']});
const jsx = n => n && ['JSXElement','JSXFragment'].includes(n.type);
function walk(node, visit) {
  if (!node || typeof node !== 'object') return;
  visit(node);
  for (const child of Object.values(node)) {
    if (Array.isArray(child)) child.forEach(n => walk(n, visit));
    else walk(child, visit);
  }
}
const returns = [];
walk(program, n => {
  if (n.type === 'ReturnStatement' && jsx(n.argument)) returns.push(n.argument);
  if (n.type === 'ArrowFunctionExpression' && jsx(n.body)) returns.push(n.body);
});
const size = n => { let count=0; walk(n, ch => { if (jsx(ch)) count++; }); return count; };
const root = returns.sort((a,b) => size(b)-size(a) || a.start-b.start)[0];
const variants = [];
function descend(container, depth) {
  if (depth === 5) return;
  const children = container.children.filter(jsx);
  for (const child of children) {
    if (children.length > 1) {
      variants.push({size:size(child), start:child.start, source:source.slice(0,root.start)
        +source.slice(child.start,child.end)+source.slice(root.end)});
    }
    descend(child, depth+1);
  }
}
if (root) descend(root,0);
process.stdout.write(JSON.stringify(variants.sort((a,b) => a.size-b.size || a.start-b.start)));
