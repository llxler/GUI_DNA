const {readFileSync} = require('node:fs');
const {parseAst} = require(process.argv[2]);
const files = JSON.parse(readFileSync(0, 'utf8'));
const result = {};
for (const [file, content] of Object.entries(files)) {
  let ast;
  try { ast = parseAst(content); } catch { continue; }
  const spans = [];
  function visit(node) {
    if (!node || typeof node !== 'object') return;
    if (node.type === 'CallExpression' && node.callee?.type === 'MemberExpression' &&
        !node.callee.computed && node.callee.property?.name === 'add' &&
        node.callee.object?.type === 'MemberExpression' && !node.callee.object.computed &&
        node.callee.object.property?.name === 'classList' && node.arguments.length === 1) {
      const arg = node.arguments[0];
      if (arg.type === 'Identifier' || (arg.type === 'Literal' && typeof arg.value === 'string') ||
          (arg.type === 'TemplateLiteral' && arg.expressions.length === 0))
        spans.push([arg.start,arg.end]);
    }
    for (const value of Object.values(node))
      if (Array.isArray(value)) value.forEach(visit); else if (value && typeof value === 'object') visit(value);
  }
  visit(ast);
  if (spans.length) {
    let changed = content;
    for (const [start,end] of spans.sort((a,b) => b[0]-a[0])) {
      const arg = content.slice(start,end);
      const replacement = '...(v => typeof v === "string" && /[\\t\\n\\f\\r ]/.test(v) ? v.split(/[\\t\\n\\f\\r ]+/).filter(Boolean) : [v])(' + arg + ')';
      changed = changed.slice(0,start) + replacement + changed.slice(end);
    }
    parseAst(changed);
    result[file] = {source:changed, calls:spans.length};
  }
}
process.stdout.write(JSON.stringify(result));
