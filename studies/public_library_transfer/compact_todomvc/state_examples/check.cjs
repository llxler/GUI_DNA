const vm=require('node:vm'), fs=require('node:fs');
const {name,source,cases}=JSON.parse(fs.readFileSync(0,'utf8'));
function matches(v, expected) {
  if(Array.isArray(expected)) return Array.isArray(v)&&v.length===expected.length&&expected.every((x,i)=>matches(v[i],x));
  if(expected && typeof expected==='object') return !!v&&Object.entries(expected).every(([k,x])=>matches(v[k],x));
  return v===expected;
}
const results=cases.map(c=>{
  const storage=new Map();
  const localStorage={getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,String(v))};
  if(c.stored)storage.set('react-todos',JSON.stringify(c.stored));
  const ctx=vm.createContext({localStorage, window:{localStorage},s:structuredClone(c.state),e:c.event});
  try {
    const value=vm.runInContext(source+'\n;'+name+'(s,e)',ctx,{timeout:150});
    let got=value;
    if(name==='persist')got=JSON.parse(storage.get('react-todos'));
    let passed;
    if(c.semantic==='append'){
      got=value?.todos;
      passed=matches(got,c.expected) && new Set(got.map(x=>x.id)).size===got.length && got.every(x=>x.id!=null);
    } else {
      passed=matches(got,c.expected);
      if(name==='init')passed=passed&&Number.isFinite(got.nextId)&&!got.todos.some(x=>x.id===got.nextId);
    }
    return {passed:!!passed,actual:JSON.stringify(got)?.slice(0,800)??null};
  } catch(e){return {passed:false,error:String(e).slice(0,180)};}
});
process.stdout.write(JSON.stringify(results));
