const table=document.querySelector('table');
const menu=document.createElement('div');
menu.className='menu';
Object.assign(menu.style,{position:'absolute',minWidth:'100px',minHeight:'100px',background:'white',border:'1px solid #888',zIndex:3,display:'none'});
document.body.append(menu);
const style=document.createElement('style');style.textContent='.selected{background:#d2e7ff;outline:1px solid #3975bc}.menu>div{cursor:pointer;padding:3px 8px}';document.head.append(style);
const readGrid=()=>Array.from(table.rows,tr=>Array.from(tr.cells,c=>c.textContent));
const coord=c=>c ? [c.parentElement.rowIndex,c.cellIndex] : null;
const state={grid:readGrid(),active:null,anchor:null,selected:[],editing:null,menu:[],target:null,clipboard:[],rowHeights:[],colWidths:[]};
const valid=(p)=>Array.isArray(p)&&p.length===2&&p.every(Number.isInteger)&&table.rows[p[0]]?.cells[p[1]];
const same=(a,b)=>Array.isArray(a)&&Array.isArray(b)&&a[0]===b[0]&&a[1]===b[1];
let pos={x:0,y:0}, origin=null, moving=false;
function apply(patch) {
  if(!patch||typeof patch!=='object')return;
  const oldEdit=state.editing;
  for(const k of Object.keys(state))if(Object.hasOwn(patch,k))state[k]=patch[k];
  if(!Array.isArray(state.grid)||!state.grid.length||state.grid.length>160||state.grid.some(r=>!Array.isArray(r)||r.length>160))throw Error('Invalid grid');
  while(table.rows.length>state.grid.length)table.deleteRow(-1);
  for(let y=0;y<state.grid.length;y++){
    const row=table.rows[y]||table.tBodies[0].insertRow(), data=state.grid[y];
    while(row.cells.length>data.length)row.deleteCell(-1);
    for(let x=0;x<data.length;x++){
      let cell=row.cells[x];
      if(!cell){cell=document.createElement(y===0?'th':'td');row.append(cell);}
      if(cell.textContent!==String(data[x]??''))cell.textContent=String(data[x]??'');
      const p=[y,x];
      cell.classList.toggle('selected',Array.isArray(state.selected)&&state.selected.some(v=>same(v,p)));
      cell.contentEditable=same(state.editing,p)?'true':'false';
      if(Number.isFinite(state.rowHeights?.[y]))cell.style.height=state.rowHeights[y]+'px';
      if(Number.isFinite(state.colWidths?.[x]))cell.style.width=state.colWidths[x]+'px';
    }
  }
  if(!same(oldEdit,state.editing)&&valid(state.editing))table.rows[state.editing[0]].cells[state.editing[1]].focus();
  menu.replaceChildren();
  for(const label of Array.isArray(state.menu)?state.menu:[]){
    if(typeof label!=='string')continue;
    const item=document.createElement('div');item.textContent=label;item.className='menu-item-'+label.trim().toLowerCase().replace(/\s+/g,'-');
    item.onclick=e=>{e.stopPropagation();dispatch({kind:'item',label,cell:state.target});};menu.append(item);
  }
  menu.style.display=menu.childElementCount?'block':'none';
  menu.style.left=pos.x+'px';menu.style.top=pos.y+'px';
}
function dispatch(e){
  state.grid=readGrid();
  for(const [events,fn] of handlers){
    if(!events.includes(e.kind))continue;
    const base=structuredClone(state), change=fn(base,e);
    if(change)apply(change);
  }
}
function payload(e,kind){
 const el=e.target.closest?.('td,th');
 return {kind,cell:coord(el&&table.contains(el)?el:null),key:e.key??'',shift:!!e.shiftKey,mod:!!(e.ctrlKey||e.metaKey),
         start:origin,buttons:e.buttons??0,dx:origin?e.clientX-origin.x:0,dy:origin?e.clientY-origin.y:0};
}
document.addEventListener('contextmenu',e=>{const p=payload(e,'context');if(!p.cell)return;e.preventDefault();pos={x:e.pageX,y:e.pageY};dispatch(p);});
document.addEventListener('click',e=>{if(menu.contains(e.target))return;dispatch(payload(e,'dismiss'));if(moving){moving=false;return;}const p=payload(e,'click');if(p.cell)dispatch(p);});
table.addEventListener('dblclick',e=>dispatch(payload(e,'double')));
document.addEventListener('keydown',e=>{const p=payload(e,'key');if(!state.editing&&['Tab','Backspace','ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key))e.preventDefault();dispatch(p);});
table.addEventListener('mousedown',e=>{if(e.button!==0)return;const el=e.target.closest('td,th');if(!el)return;const b=el.getBoundingClientRect();origin={cell:coord(el),x:e.clientX,y:e.clientY,width:b.width,height:b.height,right:b.right-e.clientX,bottom:b.bottom-e.clientY};moving=false;});
document.addEventListener('mousemove',e=>{if(!origin||!(e.buttons&1))return;const p=payload(e,'drag');if(Math.abs(p.dx)+Math.abs(p.dy)>4){moving=true;dispatch(p);}});
document.addEventListener('mouseup',e=>{if(origin&&moving)dispatch(payload(e,'drop'));origin=null;});
