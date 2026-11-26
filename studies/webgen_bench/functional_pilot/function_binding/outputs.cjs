const fs = require('node:fs');
const acorn = require(process.argv[2]);
const {source, adapt} = JSON.parse(fs.readFileSync(0, 'utf8'));
const tree = acorn.parse('('+source+')',{ecmaVersion:'latest'});
const fn = tree.body[0].expression;
if (!['FunctionExpression','ArrowFunctionExpression'].includes(fn.type) || fn.params.length !== 3 ||
    fn.params.some(p=>p.type!=='Identifier')) throw Error('Expected a three-argument renderer');
const [root,,env] = fn.params.map(p=>p.name);
const edits=[];
function walk(node) {
  if(!node || typeof node!=='object')return;
  if(node!==fn && /Function/.test(node.type||'') && node.params.some(p=>[root,env].includes(p.name)))return;
  if(node.type==='ExpressionStatement'){
    const call=node.expression, f=call.callee;
    if(call.type==='CallExpression' && f.type==='MemberExpression' && f.object.name===env &&
       !f.computed && f.property.name==='text')edits.push([call.start-1,call.end-1]);
  }
  for(const v of Object.values(node)) if(Array.isArray(v))v.forEach(walk);else if(v&&typeof v==='object')walk(v);
}
if(adapt)walk(fn);
let result=source;
for(const [a,b] of edits.sort((x,y)=>y[0]-x[0]))
  result=result.slice(0,a)+root+'.append(document.createTextNode('+result.slice(a,b)+'))'+result.slice(b);
acorn.parse('('+result+')',{ecmaVersion:'latest'});
process.stdout.write(JSON.stringify({source:result,outputs:edits.length}));
