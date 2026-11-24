// Read an already delivered default-export module; never evaluate a response.
const fs = require('fs');
const path = require('path');
const parser = require(path.resolve('artifacts/benchmark-probe/WebApp1k/staging/node_modules/@babel/parser'));
const {original, raw} = JSON.parse(fs.readFileSync(0, 'utf8'));
const parse = s => parser.parse(s, {sourceType: 'module', plugins: ['jsx']}).program;
const seen = new Set();

function walk(node, visit) {
  if (!node || typeof node !== 'object') return;
  visit(node);
  for (const child of Object.values(node)) {
    if (Array.isArray(child)) child.forEach(item => walk(item, visit));
    else walk(child, visit);
  }
}
function extract(source, kind) {
  if (typeof source !== 'string' || !source.trim() || seen.has(source)) return;
  seen.add(source);
  try {
    const program = parse(source);
    if (program.body.some(stmt => stmt.type === 'ExportDefaultDeclaration')) {
      walk(program, node => {
        if ((node.type === 'ImportDeclaration' && !['react','react-router-dom'].includes(node.source.value)) ||
            ['Import', 'ImportExpression'].includes(node.type) || (node.type === 'CallExpression' && node.callee.name === 'require'))
          throw Error('unsupported dependency');
      });
      return {source, kind};
    }
    for (const stmt of program.body) {
      for (const decl of (stmt.declaration || stmt).declarations || []) {
        if (decl.init?.type !== 'ObjectExpression') continue;
        const field = decl.init.properties.find(p => p.type === 'ObjectProperty' && (p.key.name || p.key.value) === 'source');
        const node = field?.value;
        const literal = node?.type === 'StringLiteral' ? node.value :
          node?.type === 'TemplateLiteral' && !node.expressions.length ? node.quasis[0].value.cooked : null;
        const result = extract(literal, kind+'/js-literal');
        if (result) return result;
      }
    }
  } catch {}
  try {
    const value = JSON.parse(source);
    const result = extract(typeof value === 'string' ? value : value?.source, kind+'/json');
    if (result) return result;
  } catch {}
  const complete = /"source"\s*:\s*("(?:[^"\\]|\\.)*")/gs;
  for (const match of source.matchAll(complete)) {
    try { const result = extract(JSON.parse(match[1]), kind+'/closed-string'); if (result) return result; } catch {}
  }
  const blocks = /```(?:javascript|jsx|js|json)?[^\S\r\n]*\r?\n([\s\S]*?)\r?\n```/gi;
  for (const match of source.matchAll(blocks)) {
    const result = extract(match[1], kind+'/fence');
    if (result) return result;
  }
}
process.stdout.write(JSON.stringify(extract(original, 'original') || extract(raw, 'response') || null));
