const fs = require('node:fs');
const acorn = require(process.argv[2]);
const source = fs.readFileSync(0, 'utf8');
const tree = acorn.parse('('+source+')', {ecmaVersion:'latest'});
const fn = tree.body[0].expression;
const edits = [];
function inspect(node) {
  if (!node || typeof node !== 'object') return;
  if (node !== fn && /Function/.test(node.type || '') &&
      (node.id?.name === 'renderNode' || node.params?.some(p => p.name === 'renderNode' || p.name === 'ctx'))) return;
  if (node.type === 'CallExpression' && node.callee.name === 'renderNode' && node.arguments.length === 2 && node.arguments[1].name === 'ctx') {
    edits.push([node.callee.start-1,node.callee.end-1,'ctx.render']);
    edits.push([node.arguments[0].end-1,node.arguments[1].end-1,'']);
  }
  for (const child of Object.values(node)) {
    if (Array.isArray(child)) child.forEach(inspect); else if (child && typeof child === 'object') inspect(child);
  }
}
inspect(fn);
let result=source;
for (const [a,b,replacement] of edits.sort((x,y)=>y[0]-x[0])) result=result.slice(0,a)+replacement+result.slice(b);
acorn.parse('('+result+')',{ecmaVersion:'latest'});
process.stdout.write(JSON.stringify({source:result, calls:edits.length/2}));
