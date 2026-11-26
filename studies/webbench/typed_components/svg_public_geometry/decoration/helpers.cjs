const fs=require('node:fs'),path=require('node:path');
const parse=require(path.resolve('artifacts/benchmark-probe/WebApp1k/staging/node_modules/@babel/parser')).parse;
const {raw,name}=JSON.parse(fs.readFileSync(0,'utf8'));
const lines=raw.trim().split('\n');
const fenced=lines[0].trim().startsWith(String.fromCharCode(96).repeat(3))&&lines.at(-1).trim()===String.fromCharCode(96).repeat(3);
for (const text of [raw,...(fenced?[lines.slice(1,-1).join('\n')]:[])]) {
  try {
    const {body}=parse(text,{sourceType:'module'}).program;
    if(body.length<2||!body.every(x=>x.type==='FunctionDeclaration'&&x.id))continue;
    const names=body.map(x=>x.id.name);
    const target=body.find(x=>x.id.name===name);
    if(new Set(names).size!==names.length||!target||target.params.length!==2||target.async||target.generator)continue;
    process.stdout.write('const '+name+'=(()=>{\n'+text+'\nreturn '+name+';\n})();');
    process.exit(0);
  } catch {}
}
process.exit(1);
