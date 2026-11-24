// This check uses only the public state and event contract, never the official suite.
const vm = require('node:vm');
const fs = require('node:fs');
const {source, features} = JSON.parse(fs.readFileSync(0, 'utf8'));
const storeName = 'react-todos';
const todos = [{id:7,title:'First note',completed:false},{id:11,title:'Second note',completed:true}];
const base = {todos,filter:'all',editing:null,nextId:12};
const observations = {};
function examine(id, feature, owners, expected, expression, predicate, initial=null) {
  if (feature!=='core' && !features.includes(feature)) return;
  const storage = new Map();
  if (initial) storage.set(storeName, JSON.stringify(initial));
  const context = vm.createContext({
    console:{log(){},warn(){},error(){}},
    localStorage:{getItem:k=>storage.get(String(k))??null,setItem:(k,v)=>storage.set(String(k),String(v)),
      removeItem:k=>storage.delete(String(k)),clear:()=>storage.clear()},
    s:JSON.parse(JSON.stringify(base)), stored:storeName,
  });
  let passed=false, actual;
  try {
    if (!source) throw Error('No complete controller');
    vm.runInContext('globalThis.window=globalThis;globalThis.location={hash:"#/"};',context);
    vm.runInContext(source, context, {timeout:120});
    const result=vm.runInContext(expression,context,{timeout:120});
    const data=result===undefined?null:JSON.parse(JSON.stringify(result));
    passed=!!predicate(data);
    actual=JSON.stringify(data).slice(0,420);
  } catch(e) { actual=String(e).slice(0,280); }
  observations[id]={owners,expected,passed,actual};
}
const reduce=e=>'window.candidate.reduce(s,'+JSON.stringify(e)+')';
const view='window.candidate.select(s)';
const eq=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
examine('initial-state','core',['init'],'Empty list, all filter, no editing, and numeric nextId when storage is empty.',
  'window.candidate.init()',v=>v&&Array.isArray(v.todos)&&!v.todos.length&&v.filter==='all'&&v.editing===null&&Number.isFinite(v.nextId));
examine('restore','core',['init'],'Initialize from the two ordered {id,title,completed} records in react-todos. Preserve their values.',
  'window.candidate.init().todos',v=>Array.isArray(v)&&v.length===2&&todos.every((t,i)=>Object.keys(t).every(k=>v[i][k]===t[k])),todos);
examine('append','core',['add'],'Add a trimmed third active item with an unused ID; retain the two earlier items.',
  reduce({type:'add',title:'  Third note  '})+'.todos',v=>Array.isArray(v)&&v.length===3&&v[0].id===7&&v[1].id===11&&v[2].title==='Third note'&&v[2].completed===false&&v[2].id!=null&&![7,11].includes(v[2].id));
examine('blank','core',['add'],'Ignore a whitespace-only title without changing the two existing todos.',
  reduce({type:'add',title:'   '})+'.todos',v=>Array.isArray(v)&&v.length===2&&v[0].id===7&&v[1].id===11);
examine('persist','core',['persist','add'],'After adding Third note, react-todos contains three ordered records with id,title,completed; no editing state in the stored array.',
  reduce({type:'add',title:'Third note'})+'; JSON.parse(localStorage.getItem(stored))',
  v=>Array.isArray(v)&&v.length===3&&v[0].id===7&&v[1].id===11&&v[2].title==='Third note'&&v[2].completed===false&&v.every(t=>Object.keys(t).sort().join(',')==='completed,id,title'));
examine('view','core',['select'],'View lists both items in order and reports hasTodos true, allCompleted false, hasCompleted true, editing null, filter all.',
  view,v=>v&&eq(v.visible?.map(t=>t.id),[7,11])&&v.hasTodos===true&&v.allCompleted===false&&v.hasCompleted===true&&v.editing===null&&v.filter==='all');
examine('empty-view','core',['select'],'For an empty state, visible is empty and hasTodos is false.',
  's.todos=[];'+view,v=>v&&eq(v.visible,[])&&v.hasTodos===false);
examine('count','counter',['select'],'With one active item the countText is 1 item left.',
  view+'.countText',v=>v==='1 item left');
examine('toggle','toggle',['toggle'],'Toggling id 7 marks it complete and leaves id 11 complete.',
  reduce({type:'toggle',id:7})+'.todos.map(t=>t.completed)',v=>eq(v,[true,true]));
examine('toggle-all','toggleAll',['toggleAll'],'With one active and one completed item, toggleAll marks both complete.',
  reduce({type:'toggleAll'})+'.todos.map(t=>t.completed)',v=>eq(v,[true,true]));
examine('edit','edit',['edit'],'Starting to edit id 7 sets state.editing to that id.',
  reduce({type:'edit',id:7})+'.editing',v=>v===7);
examine('save','edit',['save'],'Saving id 7 with a padded nonempty title trims its title and exits editing.',
  's.editing=7; s='+reduce({type:'save',id:7,title:'  Renamed  '})+'; [s.todos[0].title,s.editing]',v=>eq(v,['Renamed',null]));
examine('cancel','edit',['cancel'],'Cancelling edit keeps the original title and exits editing.',
  's.editing=7; s='+reduce({type:'cancel',id:7,title:'Proposed'})+'; [s.todos[0].title,s.editing]',v=>eq(v,['First note',null]));
examine('clear','clearCompleted',['clearCompleted'],'Clearing completed todos leaves only id 7.',
  reduce({type:'clearCompleted'})+'.todos.map(t=>t.id)',v=>eq(v,[7]));
examine('route','routing',['route'],'The completed route is recorded in the state filter.',
  reduce({type:'route',filter:'completed'})+'.filter',v=>v==='completed');
examine('filtered-view','routing',['select'],'Selecting the completed route shows only the completed item.',
  's.filter="completed";'+view+'.visible.map(t=>t.id)',v=>eq(v,[11]));
process.stdout.write(JSON.stringify(observations));
