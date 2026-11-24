// Inspect model output as data, without evaluating any generated JavaScript.
const fs = require('fs');
const path = require('path');
const parser = require(path.resolve('artifacts/benchmark-probe/WebApp1k/staging/node_modules/@babel/parser'));
const reply = JSON.parse(fs.readFileSync(0, 'utf8'));
const delivered = [];
const rejected = [];
const parse = (source) => parser.parse(source, {sourceType: 'module', plugins: ['jsx']}).program;

function literal(node) {
  if (node?.type === 'StringLiteral') return node.value;
  if (node?.type === 'TemplateLiteral' && !node.expressions.length) return node.quasis[0].value.cooked;
  return undefined;
}

function visit(node, callback) {
  if (!node || typeof node !== 'object') return;
  callback(node);
  for (const value of Object.values(node)) {
    if (Array.isArray(value)) value.forEach(child => visit(child, callback));
    else if (value && typeof value === 'object') visit(value, callback);
  }
}

function offer(entry, format) {
  const {id, source} = entry;
  if (typeof id !== 'string' || !/^[A-Za-z][A-Za-z0-9_]{0,63}$/.test(id) || id === 'NONE') return;
  if (typeof source !== 'string' || delivered.some(value => value.id === id)) return;
  try {
    const program = parse(source);
    if (!program.body.some(value => value.type === 'ExportDefaultDeclaration')) throw Error('no-default-export');
    visit(program, node => {
      if (node.type === 'ImportDeclaration' && !['react', 'react-router-dom'].includes(node.source.value))
        throw Error('unsupported-import');
      if (['Import', 'ImportExpression'].includes(node.type) ||
          (node.type === 'CallExpression' && node.callee.name === 'require'))
        throw Error('nonstatic-import');
    });
    delivered.push({id, source, behavior: entry.behavior || '', format});
  } catch (error) {
    rejected.push({id, format, reason: error.code || String(error.message)});
  }
}

const blocks = [...reply.matchAll(/```(?:javascript|jsx|js|json)?[^\S\r\n]*\r?\n([\s\S]*?)\r?\n```/gi)].map(value => value[1]);
for (const code of [reply, ...blocks]) {
  try {
    const value = JSON.parse(code);
    if (Array.isArray(value.components)) value.components.forEach(entry => offer(entry, 'json'));
  } catch {}
}
// A broken outer record may still contain complete JSON components.
const atom = '"(?:[^"\\\\]|\\\\.)*"';
const complete = new RegExp('\\{\\s*"id"\\s*:\\s*(' + atom + ')\\s*,\\s*"behavior"\\s*:\\s*(' + atom +
  ')\\s*,\\s*"source"\\s*:\\s*(' + atom + ')\\s*\\}', 'gs');
for (const match of reply.matchAll(complete)) {
  try {
    offer({id: JSON.parse(match[1]), behavior: JSON.parse(match[2]), source: JSON.parse(match[3])}, 'complete-json-record');
  } catch {}
}

for (const code of blocks) {
  let program;
  try { program = parse(code); } catch { continue; }
  for (const stmt of program.body) {
    for (const decl of (stmt.declaration || stmt).declarations || []) {
      if (decl.id.name !== 'components' || decl.init?.type !== 'ArrayExpression') continue;
      for (const row of decl.init.elements) {
        if (row.type !== 'ObjectExpression') continue;
        const fields = Object.fromEntries(row.properties.filter(p => p.type === 'ObjectProperty')
          .map(p => [p.key.name || p.key.value, literal(p.value)]));
        offer(fields, 'js-literal');
      }
    }
  }
  const filename = code.match(/^\s*\/\/\s*[\w./-]*components\/([A-Za-z][A-Za-z0-9_]*)\.jsx?\s*$/m);
  if (filename) offer({id: filename[1], source: code}, 'named-jsx-file');
}
process.stdout.write(JSON.stringify({delivered, rejected}));
