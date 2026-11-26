const fs=require('node:fs'), vm=require('node:vm');
const {group,fn}=JSON.parse(fs.readFileSync(0,'utf8'));
const ctx=vm.createContext({});
vm.runInContext('var op=('+fn+')',ctx,{timeout:600});
const s={grid:[['A','B','C'],['11','12','13'],['21','22','23']],active:null,anchor:null,selected:[],editing:null,menu:[],target:null,clipboard:[],rowHeights:[],colWidths:[]};
const results={};
function run(name,initial,events,ok){
 ctx.s=JSON.parse(JSON.stringify({...s,...initial}));
 try{
 for(const e of events){ctx.e={cell:null,mod:false,shift:false,key:'',...e};vm.runInContext('Object.assign(s,op(JSON.parse(JSON.stringify(s)),e)||{})',ctx,{timeout:550});}
 results[name]={passed:!!ok(ctx.s),observed:JSON.stringify(ctx.s).slice(0,550)};
 }catch(err){results[name]={passed:false,observed:String(err).slice(0,240)};}
}
const eq=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const click=(r,c)=>({kind:'click',cell:[r,c]});
const key=(k,x={})=>({kind:'key',key:k,...x});
const item=(label,r,c)=>({kind:'item',label,cell:[r,c]});
const selected={active:[1,1],anchor:[1,1],selected:[[1,1]]};
switch(group){
case 'select':run('two plain clicks replace old selection',{},[click(1,1),click(1,2)],z=>eq(z.active,[1,2])&&eq(z.selected,[[1,2]]));break;
case 'menu':run('body context exposes insertion and deletion',{},[{kind:'context',cell:[1,1]}],z=>eq(z.target,[1,1])&&z.menu.includes('Insert Row Below'));run('dismiss closes menu',{menu:['Test']},[{kind:'dismiss'}],z=>!z.menu.length);break;
case 'rows':run('insert below keeps other data',{target:[1,1]},[item('Insert Row Below',1,1)],z=>z.grid.length===4&&z.grid[3][2]==='23'&&z.grid[2].length===3);break;
case 'columns':run('insert left on all rows',{target:[0,1]},[item('Insert Col Left',0,1)],z=>z.grid.every(r=>r.length===4)&&z.grid[1][2]==='12');break;
case 'keys':run('initialize and move down',{},[key('ArrowRight'),key('ArrowDown')],z=>eq(z.active,[1,0])&&eq(z.selected,[[1,0]]));run('tab wraps row',{active:[0,2],selected:[[0,2]],anchor:[0,2]},[key('Tab')],z=>eq(z.active,[1,0]));break;
case 'edit':run('delete contents',selected,[key('Delete')],z=>z.grid[1][1]==='');run('start and escape',selected,[{kind:'double',cell:[1,1]},key('Escape')],z=>z.editing===null&&eq(z.active,[1,1]));break;
case 'copy':run('copy cell into destination',selected,[key('c',{mod:true})],z=>z.clipboard.length>0);break;
case 'range':run('drag interior rectangle',selected,[{kind:'drag',cell:[2,2],start:{cell:[1,1],right:25,bottom:20},dx:80,dy:40}],z=>[1,2].every(y=>[1,2].every(x=>z.selected.some(p=>eq(p,[y,x])))));break;
case 'size':run('resize lower edge',selected,[{kind:'drag',cell:[2,1],start:{cell:[1,1],height:40,width:80,right:42,bottom:1},dx:0,dy:28}],z=>z.rowHeights[1]>=68);break;
}
console.log(JSON.stringify(results));
