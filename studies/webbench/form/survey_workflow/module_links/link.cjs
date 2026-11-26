const fs=require('node:fs'),path=require('node:path');
const root=path.resolve('artifacts/benchmark-probe/WebApp1k/staging/node_modules');
const parser=require(path.join(root,'@babel/parser'));
const traverse=require(path.join(root,'@babel/traverse')).default;
const {files,owner,symbol}=JSON.parse(fs.readFileSync(0,'utf8'));
const parse=s=>parser.parse(s,{sourceType:'module',plugins:['jsx']});
const exportsName=(module,n)=>module.program.body.some(d=>d.type==='ExportNamedDeclaration'&&
  (d.declaration?.id?.name===n||d.declaration?.declarations?.some(x=>x.id?.name===n)||d.specifiers?.some(x=>x.exported?.name===n)));
if(!owner.startsWith('common/')||!files[owner])process.exit(1);
let free=false;
traverse(parse(files[owner]),{ReferencedIdentifier(p){if(p.node.name===symbol&&!p.scope.hasBinding(symbol))free=true;}});
const matches=Object.keys(files).filter(k=>k!==owner&&k.startsWith('common/')&&k.endsWith('.js')&&exportsName(parse(files[k]),symbol));
if(!free||matches.length!==1)process.exit(1);
let target=path.posix.relative(path.posix.dirname(owner),matches[0]);
if(!target.startsWith('.'))target='./'+target;
process.stdout.write('import { '+symbol+' } from '+JSON.stringify(target)+';\n');
