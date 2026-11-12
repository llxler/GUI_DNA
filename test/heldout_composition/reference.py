"""Independent browser reference for evaluator calibration; never a model input."""
import json

CALCULATOR = r'''
let total=0, memory=0, history=[];
document.body.innerHTML='<label>Entry <input id="entry"></label><div>Total <span id="total">0</span></div><div>Memory <span id="memory">0</span></div><button id="add">Add</button><button id="subtract">Subtract</button><button id="save">Save</button><button id="recall">Recall</button><button id="clear">Clear</button><div id="history"></div>';
const entry=document.querySelector('#entry');
function render(){
 document.querySelector('#total').textContent=total;
 document.querySelector('#memory').textContent=memory;
 document.querySelector('#history').replaceChildren(...history.map((value,index)=>{
  const button=document.createElement('button');button.dataset.historyIndex=index;button.textContent=value;
  button.onclick=()=>{total=POLICY[3]?total+value:value;render();};return button;
 }));
}
for(const [id,sign] of [['add',1],['subtract',-1]])document.getElementById(id).onclick=()=>{
 total+=sign*Number(entry.value||0);history.push(total);if(!POLICY[0])entry.value='';render();
};
document.querySelector('#save').onclick=()=>{memory=total;render();};
document.querySelector('#recall').onclick=()=>{total=POLICY[1]?total+memory:memory;render();};
document.querySelector('#clear').onclick=()=>{total=0;entry.value='';if(POLICY[2])memory=0;render();};
render();
'''
TABLE = r'''
let rows=[{id:'a',value:7},{id:'b',value:2},{id:'c',value:5}], selected=null, clip=null;
document.body.innerHTML='<table><tbody id="rows"></tbody></table><input id="edit-value"><button id="apply">Apply</button><button id="sort">Sort</button><button id="copy">Copy</button><button id="paste">Paste</button><button id="delete">Delete</button><span id="clipboard">empty</span>';
function clipValue(){if(!clip)return null;return clip.live?(rows.find(row=>row.id===clip.id)?.value??null):clip.value;}
function render(){
 document.querySelector('#rows').replaceChildren(...rows.map(row=>{
  const tr=document.createElement('tr');tr.dataset.rowId=row.id;tr.setAttribute('aria-selected',String(selected===row.id));
  const label=document.createElement('td');label.textContent=row.id;
  const value=document.createElement('td');value.className='row-value';value.textContent=row.value;
  tr.append(label,value);tr.onclick=()=>{selected=row.id;render();};return tr;
 }));
 const value=clipValue();document.querySelector('#clipboard').textContent=value===null?'empty':String(value);
}
document.querySelector('#apply').onclick=()=>{const row=rows.find(r=>r.id===selected);if(row)row.value=Number(document.querySelector('#edit-value').value);render();};
document.querySelector('#sort').onclick=()=>{const index=rows.findIndex(r=>r.id===selected);rows.sort((a,b)=>(a.value-b.value)*(POLICY[0]?-1:1));if(POLICY[1]&&index>=0)selected=rows[index].id;render();};
document.querySelector('#copy').onclick=()=>{const row=rows.find(r=>r.id===selected);if(row)clip=POLICY[3]?{live:true,id:row.id}:{live:false,value:row.value};render();};
document.querySelector('#paste').onclick=()=>{const row=rows.find(r=>r.id===selected),value=clipValue();if(row&&value!==null)row.value=value;render();};
document.querySelector('#delete').onclick=()=>{const index=rows.findIndex(r=>r.id===selected);if(index>=0){rows.splice(index,1);selected=POLICY[2]&&rows.length?rows[Math.min(index,rows.length-1)].id:null;}render();};
render();
'''


def files(project, policy):
    script = CALCULATOR if project == 'calculator' else TABLE
    return {'index.html': '<!doctype html><meta charset="utf-8"><title>Calibration reference</title>'
            '<style>body{font:16px sans-serif}td{padding:8px} [aria-selected="true"]{background:#acf}</style>'
            '<body><script>const POLICY=' + json.dumps(list(policy)) + ';\n' + script + '</script></body>'}
