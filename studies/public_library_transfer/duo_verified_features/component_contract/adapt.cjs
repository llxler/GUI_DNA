const fs = require('fs');
const path = require('path');
const root = path.resolve('artifacts/benchmark-probe/WebApp1k/staging/node_modules');
const {parse} = require(path.join(root,'@babel/parser'));
const {source} = JSON.parse(fs.readFileSync(0,'utf8'));
const ast = parse(source,{sourceType:'module',plugins:['jsx']});
const elements=[], names=new Set();
function walk(n) {
  if (!n || typeof n !== 'object') return;
  if (n.type==='JSXElement') elements.push(n);
  if ((n.type==='ObjectProperty' || n.type==='MemberExpression') && !n.computed) {
    const key=n.key?.name || n.property?.name;
    if (/^on[A-Z]\w*$/.test(key || '')) names.add(key);
  }
  for(const v of Object.values(n)) Array.isArray(v)?v.forEach(walk):walk(v);
}
walk(ast);
const name = el => el.openingElement.name.name;
const text = el => el.children.length===1 && el.children[0].type==='JSXText' ? el.children[0].value.trim() : '';
const attr = (el,k) => el.openingElement.attributes.find(a=>a.type==='JSXAttribute' && a.name.name===k);
const val = (el,k) => attr(el,k)?.value?.value;
const controls = elements.filter(el=>['input','select','textarea'].includes(name(el)));
const verbs = new Set(elements.filter(el=>name(el)==='button').map(text).filter(t=>/^[A-Za-z]{2,}$/.test(t)).map(t=>t.toLowerCase()));
const edits=[];
for(const label of elements.filter(el=>name(el)==='label' && text(el))) {
  const id=val(label,'htmlFor');
  const matches=controls.filter(el=>id && val(el,'id')===id);
  if(matches.length!==1) continue;
  const before=text(label);
  let after=before.replace(/\s*:\s*$/,'');
  const words=after.split(/\s+/);
  if(words.length>1 && verbs.has(words[0].toLowerCase())) {
    after=words.slice(1).join(' ').replace(/^./,c=>c.toUpperCase());
    const control=matches[0];
    if(!attr(control,'aria-label')) edits.push([control.openingElement.name.end,control.openingElement.name.end,' aria-label={'+JSON.stringify(before)+'}']);
  }
  if(after && after!==before) {
    const token=label.children[0];
    edits.push([token.start,token.end,after]);
  }
}
let labels=source;
for(const [a,b,str] of edits.sort((x,y)=>y[0]-x[0])) labels=labels.slice(0,a)+str+labels.slice(b);
function notify(code) {
  if(!names.size) return code;
  const original=parse(code,{sourceType:'module',plugins:['jsx']});
  const declaration=original.program.body.find(n=>n.type==='ExportDefaultDeclaration');
  if(!declaration) return code;
  const value=declaration.declaration;
  // Preserve the original declaration and its local name when another function references it.
  let component, keep;
  if(value.type==='Identifier') {component=value.name;keep='';}
  else if((value.type==='FunctionDeclaration'||value.type==='ClassDeclaration') && value.id) {
    component=value.id.name;keep=code.slice(value.start,value.end);
  } else {component='DuoOriginalImplementation';keep='const '+component+' = '+code.slice(value.start,value.end)+';';}
  const defaults=[...names].sort().map(n=>n+'={() => {}}').join(' ');
  return code.slice(0,declaration.start)+keep+'\nexport default function DuoFeatureHost(props) { return <'+component+' '+defaults+' {...props} />; }\n'+code.slice(declaration.end);
}
process.stdout.write(JSON.stringify({notifications:notify(source),labels,combined:notify(labels)}));
