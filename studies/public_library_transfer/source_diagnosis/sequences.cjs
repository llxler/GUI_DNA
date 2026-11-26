const vm = require('node:vm');
const fs = require('node:fs');
const {source} = JSON.parse(fs.readFileSync(0,'utf8'));
const tests = {};
function scenario(name,owners,test){
  const storage=new Map();
  const localStorage={getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,String(v)),removeItem:k=>storage.delete(k)};
  const scope=vm.createContext({localStorage,window:{localStorage},console:{log(){},warn(){},error(){}}});
  const invoke = expr=>vm.runInContext(expr,scope,{timeout:380});
  let log = [];
  try{
    invoke(source);invoke('var api=window.candidate; var s=api.init()');
    function view(){return JSON.parse(JSON.stringify(invoke('api.select(s)')));}
    function act(type,tail={}){scope.input={type,...tail};invoke('s=api.reduce(s,input)');return view();}
    function need(condition,message){if(!condition)throw Error(message);}
    function add(){act('add',{title:'  Almond  '});let v=act('add',{title:'Birch'});let names=v.visible.map(i=>i.title);need(names.join('|')==='Almond|Birch','Two appended titles in creation order.');need(v.visible[0].id!==v.visible[1].id,'Each new item has a distinct id.');return v.visible.map(i=>i.id);}
    test({add,act,view,need,boot:()=>invoke('s=api.init()'),storage});
    tests[name]={passed:true,owners};
  }catch(e){
    let state=null;let shown=null;try{state=JSON.parse(JSON.stringify(scope.s));shown=JSON.parse(JSON.stringify(invoke('api.select(s)')));}catch(_){}
    tests[name]={passed:false,owners,error:String(e).slice(0,180),state,shown};
  }
}
scenario('create-count',['init','add','select'],({add,view,need})=>{add();let v=view();need(v.hasTodos&&v.countText==='2 items left'&&!v.hasCompleted,'Show exactly 2 items left after two additions.');});
scenario('toggle-count',['toggle','select'],({add,act,need})=>{let [id]=add();let v=act('toggle',{id});need(v.visible[0].completed&&!v.visible[1].completed&&v.countText==='1 item left'&&v.hasCompleted,'Toggle only the first and show 1 item left.');});
scenario('all-cycle',['toggleAll','select'],({add,act,need})=>{add();let a=act('toggleAll');need(a.allCompleted&&a.visible.every(i=>i.completed),'First toggleAll completes both.');let b=act('toggleAll');need(!b.allCompleted&&b.visible.every(i=>!i.completed),'Second toggleAll reopens both.');});
scenario('filtered-toggle',['route','toggle','select'],({add,act,need})=>{let [first,second]=add();act('toggle',{id:first});let v=act('route',{filter:'active'});need(v.filter==='active'&&v.visible.length===1&&v.visible[0].id===second,'Active view contains only the uncompleted item.');v=act('route',{filter:'completed'});need(v.visible.length===1&&v.visible[0].id===first,'Completed view contains only the finished item.');});
scenario('edit-save-cancel',['edit','save','cancel','select'],({add,act,need})=>{let [id]=add();need(act('edit',{id}).editing===id,'Enter editing on selected item.');let v=act('save',{id,title:'  Ash  '});need(v.editing===null&&v.visible[0].title==='Ash','Save trimmed title and leave editing.');act('edit',{id});v=act('cancel',{id,title:'Reject'});need(v.editing===null&&v.visible[0].title==='Ash','Cancel keeps previous title and leaves editing.');});
scenario('empty-save-removes',['save','edit','select'],({add,act,need})=>{let [id,second]=add();act('edit',{id});let v=act('save',{id,title:'   '});need(v.visible.length===1&&v.visible[0].id===second,'Empty edit removes only the edited item.');});
scenario('destroy-empty',['destroy','select'],({add,act,need})=>{let [id,second]=add();act('destroy',{id});let v=act('destroy',{id:second});need(v.visible.length===0&&!v.hasTodos,'Removing both empties the list and hides its footer.');});
scenario('clear-and-restore',['clearCompleted','toggle','persist','init'],({add,act,boot,view,need,storage})=>{let [id,second]=add();act('toggle',{id});act('clearCompleted');let stored=JSON.parse(storage.get('react-todos'));need(Array.isArray(stored)&&stored.length===1&&stored[0].id===second,'Persist only the surviving item as a JSON array.');boot();let v=view();need(v.visible.length===1&&v.visible[0].id===second&&!v.visible[0].completed,'After a new initialization the active item survives.');});
scenario('restore-and-append',['persist','init','add'],({add,act,boot,view,need})=>{let original=add();boot();let v=act('add',{title:'Cedar'});need(v.visible.map(t=>t.title).join('|')==='Almond|Birch|Cedar'&&new Set(v.visible.map(t=>t.id)).size===3,'Reload, append and keep all three titles and distinct ids.');});
process.stdout.write(JSON.stringify(tests));
