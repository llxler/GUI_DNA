const fs=require('node:fs');
const path=require('node:path');
const parser=require(path.resolve('artifacts/benchmark-probe/WebApp1k/staging/node_modules/@babel/parser'));
const source=fs.readFileSync(0,'utf8');
const body=parser.parse(source,{sourceType:'module',plugins:['jsx']}).program.body;
const fn=body.find(node=>node.type==='FunctionDeclaration'&&node.id?.name==='View') ||
  body.flatMap(node=>node.declarations||[]).find(node=>node.id?.name==='View')?.init;
const arg=fn?.params[0];
const keys=arg?.type==='ObjectPattern' ? arg.properties.filter(p=>p.type==='ObjectProperty'&&!p.computed).map(p=>p.key.name||p.key.value) : [];
if (keys.includes('vm')) {
  const attributes=keys.includes('props')?'{...props,props,vm}':'{...props,vm}';
  process.stdout.write('View('+attributes+',vm)');
}
