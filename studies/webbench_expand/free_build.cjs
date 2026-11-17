// Unrestricted JavaScript file-map builder with the exact frozen compiler.
// This is a code baseline: no plan-schema validation is applied to its input.
const fs = require('fs');
const vm = require('vm');
try {
  const input = JSON.parse(fs.readFileSync(0, 'utf8'));
  const context = vm.createContext(Object.create(null), {
    codeGeneration: { strings: false, wasm: false },
  });
  const source = 'const input = JSON.parse(' + JSON.stringify(JSON.stringify(input)) + ');\n'
    + 'const frozenCompile = (() => {\n' + input.package.compiler + '\nreturn compile;})();\n'
    + input.program + '\nJSON.stringify(build(input.package.files, frozenCompile));';
  const output = vm.runInContext(source, context, { timeout: 3000 });
  if (typeof output !== 'string') throw new Error('build must return a file map');
  process.stdout.write(output);
} catch (error) {
  process.stderr.write(String(error));
  process.exitCode = 1;
}
