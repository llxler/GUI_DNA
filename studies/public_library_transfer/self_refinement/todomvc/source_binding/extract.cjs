// Inspect source as syntax only. The generated program is never evaluated here.
const fs = require('node:fs');
const acorn = require(process.argv[2]);
const source = fs.readFileSync(0, 'utf8');
const options = {ecmaVersion: 'latest', sourceType: 'script'};

function inspect(node, visit) {
  if (node && typeof node === 'object') {
    if (node.type) visit(node);
    for (const value of Object.values(node)) inspect(value, visit);
  }
}

function candidateAssignment(node) {
  return node.type === 'AssignmentExpression' && node.operator === '=' &&
    node.left.type === 'MemberExpression' && node.left.object.name === 'window' &&
    (node.left.property.name || node.left.property.value) === 'candidate';
}

let code = source;
let tree;
try {
  tree = acorn.parse(source, options);
} catch (error) {
  const parser = new acorn.Parser(options, source);
  parser.nextToken();
  let end = 0;
  try {
    while (parser.type !== acorn.tokTypes.eof) {
      const statement = parser.parseStatement(null, true, Object.create(null));
      if (statement.type === 'ExpressionStatement' && candidateAssignment(statement.expression)) {
        end = statement.end;
      }
    }
  } catch (ignored) {}
  if (!end) throw error;
  code = source.slice(0, end);
  tree = acorn.parse(code, options);
}
const literals = [];
let mentions = 0;
let assigned = false;
inspect(tree, node => {
  if (candidateAssignment(node)) assigned = true;
  if (node.type === 'Identifier' && node.name === 'DNA_CONFIG') mentions++;
  if (node.type === 'VariableDeclarator' && node.id.name === 'DNA_CONFIG' &&
      node.init?.type === 'ObjectExpression') literals.push(node.init);
});
if (!assigned) throw Error('Missing window.candidate assignment');
let binding = null;
if (literals.length === 1) {
  const obj = literals[0];
  const pairs = obj.properties.map(p => [p.key?.name ?? p.key?.value, p.value?.value]);
  if (obj.properties.every(p => p.type === 'Property' && !p.computed && p.kind === 'init') &&
      pairs.length && pairs.length <= 7 && pairs.every(([key,v]) => typeof key === 'string' && typeof v === 'boolean') &&
      new Set(pairs.map(([key]) => key)).size === pairs.length) {
    binding = {before: code.slice(0, obj.start), after: code.slice(obj.end), first: Object.fromEntries(pairs)};
  }
}
console.log(JSON.stringify({code, binding, mentions, truncated_tail: code !== source}));
