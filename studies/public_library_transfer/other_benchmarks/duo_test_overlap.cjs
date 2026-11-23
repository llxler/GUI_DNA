// Hash each complete top-level test call after normalizing its component import binding.
const fs = require('fs');
const crypto = require('crypto');
const path = require('path');
const { parserDir, inputs } = JSON.parse(fs.readFileSync(0, 'utf8'));
const parser = require(path.join(parserDir, '@babel/parser'));
const hash = text => crypto.createHash('sha256').update(text).digest('hex');
const result = {};
for (const [id, source] of Object.entries(inputs)) {
  const ast = parser.parse(source, { sourceType: 'module', plugins: ['jsx'] });
  const binding = ast.program.body.find(node => node.type === 'ImportDeclaration' &&
    node.source.value.startsWith('./')).specifiers[0].local.name;
  const jsx = new RegExp('(<\\/?' + ')' + binding + '(?=[\\s/>])', 'g');
  const tests = [];
  for (const node of ast.program.body) {
    if (node.type !== 'ExpressionStatement' || node.expression.type !== 'CallExpression' ||
        node.expression.callee.name !== 'test') continue;
    const raw = source.slice(node.start, node.end).replace(/\r\n/g, '\n');
    tests.push({ title: node.expression.arguments[0].value, raw: hash(raw),
                 normalized: hash(raw.replace(jsx, '$1SubjectUnderTest')) });
  }
  result[id] = tests;
}
process.stdout.write(JSON.stringify(result));
