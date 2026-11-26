// The selection spy in this isolated fixture is never shipped in a candidate.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {JSDOM} = require(path.resolve('artifacts/benchmark-probe/WebApp1k/staging/node_modules/jsdom'));
const req = JSON.parse(fs.readFileSync(0,'utf8'));
const tests = {};
function run(label, purpose, check) {
  const dom = new JSDOM('<table class="table"><thead><tr><th>A</th><th>B</th></tr></thead><tbody><tr><td>Red</td><td>Blue</td></tr><tr><td>3</td><td>4</td></tr></tbody></table><div class="menu" hidden style="display:none"></div>',
                       {runScripts:'outside-only'});
  const win=dom.window, doc=win.document, table=doc.querySelector('table'), menu=doc.querySelector('.menu');
  const cells=[...table.querySelectorAll('th,td')], [h,i,a,b,c,d]=cells;
  const ctx = {table,menu,selected:new Set(),active:null,anchor:null,target:null};
  ctx.select=(list,active,anchor)=>{
    const chosen=[...list].filter(Boolean);
    for(const el of cells) el.classList.toggle('selected',chosen.includes(el));
    ctx.selected=new Set(chosen);ctx.active=active;ctx.anchor=anchor;
  };
  let actual;
  try {
    const box=dom.getInternalVMContext();
    const fn=vm.runInContext('('+req.source+')',box,{timeout:300});
    const event=(type,options={})=>{const e=type==='keydown'?new win.KeyboardEvent(type,{...options,cancelable:true}):new win.MouseEvent(type,{...options,cancelable:true});
      return e;};
    actual=check({ctx,fn:(...args)=>fn(ctx,...args),event,h,i,a,b,c,d,cells,table,menu});
  } catch(e) {actual=String(e).slice(0,200);}
  tests[label]={expected:purpose,passed:actual===true,observed:actual};
  win.close();
}
const exec=(label,expected,test)=>run(label,expected,test);
switch(req.name){
case 'markSelection':
  exec('single','Given [a],a,a select exactly a, store it as active and anchor, add class selected.',({fn,a,ctx})=>{fn([a],a,a);return ctx.selected.size===1&&ctx.selected.has(a)&&ctx.active===a&&ctx.anchor===a&&a.classList.contains('selected');});
  exec('replace','A second call with [b,c],c,b must remove a and select b and c.',({fn,a,b,c,ctx})=>{fn([a],a,a);fn([b,c],c,b);return !a.classList.contains('selected')&&b.classList.contains('selected')&&c.classList.contains('selected')&&ctx.selected.size===2&&ctx.anchor===b;});
  break;
case 'cellClick':
  exec('first','Click a currently unselected td a. Use ctx.select with a real collection containing a. Active and anchor must be a and a becomes selected.',({fn,a,event,ctx})=>{fn(event('click'),a);return ctx.selected.has(a)&&a.classList.contains('selected')&&ctx.active===a&&ctx.anchor===a;});
  exec('second','Click b after a; only b is selected. Click b again; now b is contentEditable.',({fn,a,b,event,ctx})=>{fn(event('click'),a);fn(event('click'),b);fn(event('click'),b);return ctx.selected.size===1&&ctx.selected.has(b)&&String(b.contentEditable)==='true';});
  break;
case 'menuVisibility':
  exec('show','Show on right-click: remove hidden AND display:none and prevent default.',({fn,a,event,menu})=>{const e=event('contextmenu');fn(e,a,'show');return e.defaultPrevented&&!menu.hidden&&menu.style.display!=='none';});
  exec('hide','Hide with null cell after show without throwing.',({fn,a,event,menu})=>{fn(event('contextmenu'),a,'show');fn(event('click'),null,'hide');return menu.hidden||menu.style.display==='none';});
  break;
case 'rowAction':
  for(const [label,delta] of [['Insert Row Above',1],['Insert Row Below',1],['Delete Row',-1]])
    exec(label,label+' must change tbody rows by '+delta,({fn,a,event,table})=>{fn(event('click'),a,label);return table.tBodies[0].rows.length===2+delta;});
  break;
case 'columnAction':
  for(const [label,delta] of [['Insert Col Left',1],['Insert Col Right',1],['Delete Col',-1]])
    exec(label,label+' must change column count of every row by '+delta,({fn,h,event,table})=>{fn(event('click'),h,label);return [...table.rows].every(r=>r.cells.length===2+delta);});
  break;
case 'selectGroup':
  exec('row','Selecting the body row selects a,b only.',({fn,a,b,ctx,event})=>{fn(event('click'),a,'Select Row');return ctx.selected.size===2&&ctx.selected.has(a)&&ctx.selected.has(b);});
  exec('col','Selecting first column selects header and both body cells.',({fn,h,a,c,ctx,event})=>{fn(event('click'),h,'Select Col');return ctx.selected.size===3&&[h,a,c].every(n=>ctx.selected.has(n));});
  break;
case 'navigate':
  exec('initial','ArrowRight on empty selection picks top-left th.',({fn,h,event,ctx})=>{fn(event('keydown',{key:'ArrowRight'}));return ctx.active===h&&ctx.selected.has(h);});
  exec('right','ArrowRight on first selected td advances to next td.',({fn,a,b,ctx,event})=>{ctx.select([a],a,a);fn(event('keydown',{key:'ArrowRight'}));return ctx.active===b&&ctx.selected.has(b);});
  break;
case 'editingKeys':
  exec('delete','Delete clears the text of BOTH selected cells.',({fn,a,b,ctx,event})=>{ctx.select([a,b],b,a);fn(event('keydown',{key:'Delete'}));return a.textContent===''&&b.textContent==='';});
  exec('escape','Escape makes edited active cell readonly.',({fn,a,ctx,event})=>{ctx.select([a],a,a);a.contentEditable='true';fn(event('keydown',{key:'Escape'}));return String(a.contentEditable)==='false'||a.getAttribute('contenteditable')==='false';});
  break;
case 'editCell':
  exec('double','Double click a: select it AND enable editing.',({fn,a,ctx,event})=>{fn(event('dblclick'),a);return ctx.selected.has(a)&&(String(a.contentEditable)==='true'||a.getAttribute('contenteditable')==='true');});
  break;
case 'clipboardKeys':
  exec('copy','Ctrl+C then Ctrl+V into b must paste a.textContent.',({fn,a,b,ctx,event})=>{ctx.select([a],a,a);fn(event('keydown',{key:'c',ctrlKey:true}));ctx.select([b],b,b);fn(event('keydown',{key:'v',ctrlKey:true}));return b.textContent===a.textContent;});
  exec('idle','An irrelevant key with empty selection is harmless.',({fn,event,ctx})=>{fn(event('keydown',{key:'z'}));return ctx.selected.size===0;});
  break;
case 'rangePointer':case 'resizeCells':case 'reorderCells':
  exec('outside','Idle mousemove and mouseup outside table, null cell: return without throwing.',({fn,event,ctx})=>{fn(event('mousemove'),null);fn(event('mouseup'),null);return ctx.selected.size===0;});
  exec('idle','An ordinary mousemove over a with no button, one selected cell, no previous context-menu target; DOM and state stay unchanged.',({fn,event,a,ctx,table})=>{ctx.select([a],a,a);const before=table.outerHTML;fn(event('mousemove'),a);return table.outerHTML===before&&ctx.active===a;});
  break;
}
process.stdout.write(JSON.stringify(tests));
