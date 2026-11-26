// Preserve the model-authored function body and reject unknown top-level dependencies.
const fs=require('node:fs'), path=require('node:path');
const babel=require(path.resolve('artifacts/benchmark-probe/WebApp1k/staging/node_modules/@babel/parser'));
const {name,raw}=JSON.parse(fs.readFileSync(0,'utf8'));
const blocks=[...raw.matchAll(/^```(?:javascript|jsx|js)?[^\S\n]*\n([\s\S]*?)(?:^\s*```|(?![\s\S]))/gm)].map(m=>m[1]);
for(const src of [raw,...blocks]){
  try {
    const prog=babel.parse(src,{sourceType:'module',plugins:['jsx']}).program;
    for(const s of prog.body) {
      const n=s.declaration || s;
      if(n.type==='FunctionDeclaration' && n.id?.name===name && !n.async && !n.generator) {
        process.stdout.write(src.slice(n.start,n.end));process.exit(0);
      }
      if(n.type==='VariableDeclaration') for(const d of n.declarations) {
        if(d.id?.name===name && ['ArrowFunctionExpression','FunctionExpression'].includes(d.init?.type) && !d.init.async){
          process.stdout.write('const '+name+'='+src.slice(d.init.start,d.init.end)+';');process.exit(0);
        }
      }
    }
  }catch{}
}
process.exit(1);
