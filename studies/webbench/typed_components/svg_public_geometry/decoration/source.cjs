const fs=require('node:fs');
const path=require('node:path');
const parse=require(path.resolve('artifacts/benchmark-probe/WebApp1k/staging/node_modules/@babel/parser')).parse;
const {name,raw}=JSON.parse(fs.readFileSync(0,'utf8'));
const blocks=Array.from(raw.matchAll(/^s*```(?:javascript|js)?[ \t]*\n([\s\S]*?)^s*```[ \t]*$/gmi),m=>m[1]);
for(const text of [raw,...blocks]) {
  try {
    const body=parse(text,{sourceType:'module'}).program.body;
    const n=body[0]?.declaration||body[0];
    if (body.length===1 && n.type==='FunctionDeclaration' && !n.async && n.id.name===name && n.params.length===2) {
      process.stdout.write(text.slice(n.start,n.end));process.exit(0);
    }
  }catch{}
}
process.exit(1);
