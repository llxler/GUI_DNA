// Pure JSON-in/files-out execution. No project-specific binding logic lives here.
const fs = require('fs');
const vm = require('vm');
try {
  const input = JSON.parse(fs.readFileSync(0, 'utf8'));
  // Transfer only strings, then construct all data inside the VM realm.
  const context = vm.createContext(Object.create(null), {
    codeGeneration: { strings: false, wasm: false },
  });
  const source = 'const input = JSON.parse(' + JSON.stringify(JSON.stringify(input)) + ');\n'
    + input.package.compiler + '\n'
    + 'JSON.stringify(compile(input.plan, input.package.files));';
  const output = vm.runInContext(source, context, { timeout: 3000 });
  if (typeof output !== 'string') throw new Error('compiler did not return JSON');
  process.stdout.write(output);
} catch (error) {
  process.stderr.write(String(error));
  process.exitCode = 1;
}
