const fs = require('node:fs');
const vm = require('node:vm');
const {source} = JSON.parse(fs.readFileSync(0,'utf8'));
const data = new Map();
const localStorage = {getItem:k=>data.get(k)??null,setItem:(k,v)=>data.set(k,String(v)),removeItem:k=>data.delete(k)};
const ctx = vm.createContext({window:{localStorage},localStorage,console:{log(){},error(){},warn(){}}});
const run = expression=>vm.runInContext(expression,ctx,{timeout:240});
const checks={empty:false,append:false,blank:false,store:false,restore:false};
let error=null;
try{
  run(source);
  run('var api=window.candidate;var s=api.init();var view=()=>api.select(s);var titles=()=>view().visible.map(t=>t.title);var add=title=>{s=api.reduce(s,{type:"add",title})};');
  checks.empty=run('view().hasTodos===false && view().visible.length===0');
  run('add("  public willow  ");add("public iris")');
  checks.append=run('titles().join("|")==="public willow|public iris" && new Set(view().visible.map(t=>t.id)).size===2 && view().hasTodos===true');
  run('add("     ")');
  checks.blank=run('titles().join("|")==="public willow|public iris"');
  const rows=JSON.parse(data.get('react-todos')??'null');
  checks.store=Array.isArray(rows)&&rows.map(t=>t.title).join('|')==='public willow|public iris'&&rows.every(t=>Object.keys(t).sort().join('|')==='completed|id|title'&&t.completed===false);
  run('s=api.init()');
  checks.restore=run('titles().join("|")==="public willow|public iris" && new Set(view().visible.map(t=>t.id)).size===2');
}catch(e){error=String(e).slice(0,180);}
process.stdout.write(JSON.stringify({checks,error}));
