// Public input/output examples, independent of the official browser harness.
const vm = require('node:vm');
const fs = require('node:fs');
const {group, body} = JSON.parse(fs.readFileSync(0,'utf8'));
const context = vm.createContext({}, {codeGeneration:{strings:false,wasm:false}});
const tests = [];
const shape = {rows:4,cols:5,focus:[1,2],anchor:[1,2],selected:[[1,2]],editing:null,shift:false,ctrl:false};
function test(state, expect) {tests.push({state:{...shape,...state},expect});}
test({key:'ArrowRight'}, {selection:[[1,3]]});
test({key:'ArrowDown',rows:3,cols:2,focus:null,anchor:null,selected:[]},{selection:[[0,0]]});
test({key:'ArrowLeft',shift:true},{selection:[[1,1],[1,2]]});
test({key:'Tab',focus:[1,4]}, {selection:[[2,0]]});
test({key:'Tab',shift:true,focus:[0,0]}, {selection:[[3,4]]});
test({key:'Tab',shift:true,focus:null,anchor:null,selected:[]},{selection:[[0,0]]});
test({key:'Delete',selected:[[0,1],[2,3]]},{writes:[[0,1,''],[2,3,'']]});
test({key:'a',ctrl:true,rows:2,cols:2},{selection:[[0,0],[0,1],[1,0],[1,1]]});
test({key:'Enter'},{editing:[1,2]});
test({key:'Escape',editing:[1,2]},{editing:null});
test({key:'Escape'}, {selection:[]});
const keys={arrows:['ArrowRight','ArrowDown','ArrowLeft'],tab:['Tab'],selection:['Delete','a'],editing:['Enter','Escape']};
const cases = tests.filter(t => keys[group].includes(t.state.key));
const results=[];
for (const {state,expect} of cases) {
  context.sample=JSON.stringify(state);
  try {
    const got=vm.runInContext('(function(s){const state=s;return (function(){'+body+'\n})();})(JSON.parse(sample))',context,{timeout:200});
    const pass=Object.entries(expect).every(([k,v])=>{
      const val=got?.[k];
      const normalize = x => ['selection','writes'].includes(k) && Array.isArray(x) ? [...x].map(JSON.stringify).sort() : x;
      return JSON.stringify(normalize(val))===JSON.stringify(normalize(v));
    });
    results.push({state,expect,pass,observed:got??null});
  }catch(err){results.push({state,expect,pass:false,error:String(err).slice(0,200)});}
}
console.log(JSON.stringify(results));
