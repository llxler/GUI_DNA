const fs = require('fs');
const vm = require('vm');
const {posix} = require('path');

async function main() {
  const sources = JSON.parse(fs.readFileSync(0, 'utf8'));
  const modules = new Map();
  const errors = [];
  for (const [name, source] of Object.entries(sources)) {
    if (!/\.m?js$/.test(name)) continue;
    try {
      modules.set(name, new vm.SourceTextModule(source, {identifier: name}));
    } catch (error) {
      errors.push(name + ': ' + error.message);
    }
  }
  const exports = {};
  const imports = {};
  for (const [name, mod] of modules) {
    imports[name] = mod.dependencySpecifiers;
    try {
      if (mod.status === 'unlinked') {
        await mod.link((specifier, importer) => {
          const key = posix.normalize(posix.join(posix.dirname(importer.identifier), specifier));
          if (!specifier.startsWith('.') || !modules.has(key)) {
            throw new Error('Unavailable import ' + specifier + ' from ' + importer.identifier);
          }
          return modules.get(key);
        });
      }
      exports[name] = Object.getOwnPropertyNames(mod.namespace);
    } catch (error) {
      errors.push(name + ': ' + error.message);
    }
  }
  process.stdout.write(JSON.stringify({exports, imports, errors}));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
