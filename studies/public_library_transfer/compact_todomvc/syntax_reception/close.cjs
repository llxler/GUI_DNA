// Return only a unique AST repair. Insert one existing language delimiter at a token boundary.
const fs = require('node:fs');
const acorn = require(process.argv[2]);
const src = fs.readFileSync(0, 'utf8');
const options = {ecmaVersion:'latest'};
const signature = ast => JSON.stringify(ast,(k,v)=>['start','end','raw'].includes(k)?undefined:v);
let pos;
try { acorn.parse(src,options); process.stdout.write(src); process.exit(0); }
catch (e) { pos=e.pos; }
const locations = new Set([pos]);
try {
  for (const t of acorn.tokenizer(src,options)) {
    for (const offset of [t.start,t.end]) if (offset<=pos && pos-offset<=24) locations.add(offset);
  }
} catch {}
const candidates = new Map();
for (const i of locations) for (const delimiter of [')',']','}']) {
  const s=src.slice(0,i)+delimiter+src.slice(i);
  try {
    const ast=signature(acorn.parse(s,options));
    if (!candidates.has(ast)) candidates.set(ast,s);
  } catch {}
}
if (candidates.size===1) process.stdout.write(candidates.values().next().value);
