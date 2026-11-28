const fs = require('fs');
const path = require('path');
const parser = require(path.resolve('artifacts/benchmark-probe/WebApp1k/staging/node_modules/@babel/parser'));
const {source,actions} = JSON.parse(fs.readFileSync(0,'utf8'));
const ast=parser.parse(source,{sourceType:'module',plugins:['jsx']});
const inputs=[], buttons=[];
function walk(n){
  if(!n||typeof n!=='object')return;
  if(n.type==='JSXElement'){
    const tag=n.openingElement.name.name;
    if(['input','textarea','select'].includes(tag))inputs.push(n);
    if(tag==='button')buttons.push(n);
  }
  for(const value of Object.values(n)) Array.isArray(value)?value.forEach(walk):walk(value);
}
walk(ast);
const edits=[];
for(const [kind,elements] of [['change',inputs],['click',buttons]]) {
  const acts=actions.filter(a=>a.kind===kind);
  if(acts.length!==elements.length)continue;
  for(let i=0;i<elements.length;i++){
    const a=acts[i],el=elements[i],open=el.openingElement;
    if(a.by==='Text' && kind==='click'){
      if(el.children.length===1 && el.children[0].type==='JSXText')
        edits.push([el.children[0].start,el.children[0].end,'{'+JSON.stringify(a.text)+'}']);
      continue;
    }
    const name={TestId:'data-testid',LabelText:'aria-label',PlaceholderText:'placeholder',Role:'aria-label'}[a.by];
    if(!name)continue;
    const old=open.attributes.find(v=>v.name && v.name.name===name);
    if(old && (!old.value || old.value.type!=='StringLiteral'))continue;
    const value='{'+JSON.stringify(a.text)+'}';
    if(old)edits.push([old.value.start,old.value.end,value]);
    else edits.push([open.name.end,open.name.end,' '+name+'='+value]);
  }
}
let out=source;
for(const [i,j,s] of edits.sort((a,b)=>b[0]-a[0]))out=out.slice(0,i)+s+out.slice(j);
process.stdout.write(out);
