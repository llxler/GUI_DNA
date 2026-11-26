const fs=require('node:fs'),path=require('node:path');
const {JSDOM}=require(path.resolve('artifacts/benchmark-probe/WebApp1k/staging/node_modules/jsdom'));
const {name,fn}=JSON.parse(fs.readFileSync(0,'utf8'));
const w=new JSDOM('<table><tbody><tr><td>a</td><td>b</td></tr></tbody></table>',{runScripts:'outside-only'}).window;
const table=w.document.querySelector('table'),[a,b]=table.querySelectorAll('td');
const ctx={table,selected:new Set(),active:null,anchor:null,target:null};
ctx.select=(list,active,anchor)=>{ctx.selected=new Set(list);ctx.active=active;ctx.anchor=anchor;};
let count=0;
try{
  const op=w.eval('('+fn+')');
  for(const cell of [a,b]){
    if(name==='cellClick')op(ctx,new w.MouseEvent('click'),cell);
    else op(ctx,[cell],cell,cell);
    if(ctx.selected.size===1&&ctx.selected.has(cell))count++;
    if(ctx.active===cell)count++;
  }
}catch{}
process.stdout.write(String(count));
w.close();
