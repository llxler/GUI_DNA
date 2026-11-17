"""Independent positive implementations and prespecified negative mutations."""
TODO = r'''<!doctype html><meta charset="utf-8"><title>Checklist</title>
<style>.editing .view{display:none}.edit{display:none}.editing .edit{display:block}[hidden]{display:none!important}.completed label{text-decoration:line-through}</style>
<input class="new-todo" autofocus><section class="main"><input id="toggle-all" type="checkbox"><ul class="todo-list"></ul></section>
<footer class="footer"><span class="todo-count"><strong></strong> items left</span><nav class="filters"><a href="#/">All</a> <a href="#/active">Active</a> <a href="#/completed">Completed</a></nav><button class="clear-completed">Clear completed</button></footer>
<script>
const MUTATION = "__MUTATION__";
let items=JSON.parse(localStorage.getItem('todos-transfer')||'[]'), editing=null;
let next=Math.max(0,...items.map(t=>t.id))+1;
const $=s=>document.querySelector(s);
function save(){localStorage.setItem('todos-transfer',JSON.stringify(items));}
function render(){
 const mode=location.hash.includes('completed')?'completed':location.hash.includes('active')?'active':'all';
 const visible=items.filter(t=>mode==='all'||t.completed===(mode==='completed'));
 $('.todo-list').replaceChildren();
 visible.forEach((t,index)=>{
  const li=document.createElement('li');li.className=(t.completed?'completed':'')+(editing===t.id?' editing':'');
  const view=document.createElement('div');view.className='view';
  const check=document.createElement('input');check.type='checkbox';check.className='toggle';check.checked=t.completed;
  check.onchange=()=>{t.completed=check.checked;save();render();};
  const label=document.createElement('label');label.textContent=t.title;
  const remove=document.createElement('button');remove.className='destroy';remove.textContent='×';
  remove.onclick=()=>{const id=MUTATION==='visible-index-delete'?items[index].id:t.id;items=items.filter(x=>x.id!==id);save();render();};
  const edit=document.createElement('input');edit.className='edit';edit.value=t.title;
  let done=false;
  function finish(cancel){if(done)return;done=true;editing=null;if(!cancel){const title=edit.value.trim();if(title)t.title=title;else items=items.filter(x=>x.id!==t.id);save();}render();}
  edit.onkeydown=e=>{if(e.key==='Enter')finish(false);if(e.key==='Escape')finish(true);};
  edit.onblur=()=>finish(false);
  edit.oninput=()=>{if(MUTATION==='persist-draft'){t.title=edit.value;save();}};
  label.ondblclick=()=>{editing=t.id;render();const field=$('.editing .edit');field.focus();field.select();};
  view.append(check,label,remove);li.append(view,edit);$('.todo-list').append(li);
 });
 $('.main').hidden=$('.footer').hidden=items.length===0;
 $('.todo-count strong').textContent=items.filter(t=>!t.completed).length;
 $('#toggle-all').checked=items.length>0&&items.every(t=>t.completed);
 $('.clear-completed').hidden=!items.some(t=>t.completed);
 document.querySelectorAll('.filters a').forEach(a=>a.classList.toggle('selected',(a.hash||'#/')===(location.hash||'#/')));
}
$('.new-todo').onkeydown=e=>{if(e.key==='Enter'){const title=e.target.value.trim();if(title){items.push({id:next++,title,completed:false});e.target.value='';save();render();}}};
$('#toggle-all').onchange=e=>{items.forEach(t=>t.completed=e.target.checked);save();render();};
$('.clear-completed').onclick=()=>{items=items.filter(t=>!t.completed);save();render();};
onhashchange=render;render();
</script>'''
ROWS = r'''<!doctype html><meta charset="utf-8"><title>Rows</title>
<style>.danger{background:pink}td{padding:2px 8px}a{cursor:pointer}</style>
<button id="run">Create 1000</button><button id="runlots">Create 10000</button><button id="add">Append 1000</button><button id="update">Update every 10th</button><button id="clear">Clear</button><button id="swaprows">Swap</button><table><tbody></tbody></table>
<script>
const MUTATION="__MUTATION__";let rows=[],next=1,selected=null;const nodes=new Map(),body=document.querySelector('tbody');
function render(){
 if(MUTATION==='recreate-nodes'){body.replaceChildren();nodes.clear();}
 const ids=new Set(rows.map(r=>r.id));
 for(const [id,node] of nodes)if(!ids.has(id)){node.remove();nodes.delete(id);}
 const fragment=document.createDocumentFragment();
 for(const r of rows){let tr=nodes.get(r.id);if(!tr){tr=document.createElement('tr');tr.dataset.id=r.id;tr.innerHTML='<td></td><td><a></a></td><td><a class="remove">×</a></td>';nodes.set(r.id,tr);tr.children[1].firstChild.onclick=()=>{selected=r.id;render();};tr.querySelector('.remove').onclick=()=>{rows=rows.filter(x=>x.id!==r.id);if(selected===r.id)selected=null;render();};}
 tr.children[0].textContent=r.id;tr.children[1].firstChild.textContent=r.label;tr.className=selected===r.id?'danger':'';fragment.append(tr);}
 body.append(fragment);
}
function make(n){return Array.from({length:n},()=>{const id=next++;return{id,label:'Row '+id};});}
for(const [id,n] of [['run',1000],['runlots',10000]])document.getElementById(id).onclick=()=>{rows=make(n);selected=null;render();};
document.getElementById('add').onclick=()=>{rows.push(...make(1000));render();};
document.getElementById('update').onclick=()=>{for(let i=0;i<rows.length;i+=10)rows[i].label+=' !!!';render();};
document.getElementById('clear').onclick=()=>{rows=[];selected=null;render();};
document.getElementById('swaprows').onclick=()=>{if(rows.length>=999)[rows[1],rows[998]]=[rows[998],rows[1]];render();};
render();</script>'''


def files(project,mutation='none'):
    return {'index.html':(TODO if project=='todos' else ROWS).replace('__MUTATION__',mutation)}
