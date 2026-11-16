// Instrument pure build-time calls; compare the complete output with saved bytes.
const fs = require('fs');
const vm = require('vm');
const crypto = require('crypto');
try {
  const input = JSON.parse(fs.readFileSync(0, 'utf8'));
  const context = vm.createContext(Object.create(null), {codeGeneration:{strings:false,wasm:false}});
  const source = 'const input = JSON.parse(' + JSON.stringify(JSON.stringify(input)) + ');\n'
    + 'const frozenCompile = (() => {\n' + input.package.compiler + '\nreturn compile;})();\n'
    + 'const auditCalls=[]; const copy=x=>x===undefined?null:JSON.parse(JSON.stringify(x));\n'
    + 'function isData(x, seen=new Set()) { if(x===null || typeof x==="string" || typeof x==="boolean") return true; if(typeof x==="number") return Number.isFinite(x); if(typeof x!=="object" || seen.has(x) || Object.getOwnPropertySymbols(x).length) return false; const a=Array.isArray(x); if(!a && Object.getPrototypeOf(x)!==Object.prototype && Object.getPrototypeOf(x)!==null) return false; const keys=Object.keys(x); if(Object.getOwnPropertyNames(x).length!==keys.length+(a?1:0)) return false; if(a && (keys.length!==x.length || keys.some((k,i)=>k!==String(i)))) return false; seen.add(x); const ok=keys.every(k=>{const d=Object.getOwnPropertyDescriptor(x,k);return "value" in d && isData(d.value,seen);}); seen.delete(x); return ok; }\n'
    + 'function observedCompile(plan, files) { const plan_data_only=isData(plan); const before=copy({plan,files}); const result=frozenCompile(plan,files); auditCalls.push({...before,plan_data_only,output:copy(result)}); return result; }\n'
    + input.program + '\nconst result=build(input.package.files,observedCompile);JSON.stringify({output:result,calls:auditCalls});';
  const observed = JSON.parse(vm.runInContext(source,context,{timeout:3000}));
  function hashes(files) {
    if (files === null || files === undefined) return null;
    return Object.fromEntries(Object.entries(files).map(([name,value])=>[name,
      crypto.createHash('sha256').update(value).digest('hex')]));
  }
  process.stdout.write(JSON.stringify({output_sha256:hashes(observed.output),calls:observed.calls.map(c=>({
    plan:c.plan===undefined?null:c.plan,plan_data_only:c.plan_data_only,input_files_sha256:hashes(c.files),output_sha256:hashes(c.output)}))}));
} catch(error) {
  process.stderr.write(String(error));process.exitCode=1;
}
