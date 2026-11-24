/* Express the supplied public Jest specification as ordered observations and actions. */
const fs = require('node:fs');
const path = require('node:path');
const parser = require(path.resolve('artifacts/benchmark-probe/WebApp1k/staging/node_modules/@babel/parser'));
const source = JSON.parse(fs.readFileSync(0, 'utf8'));
const tree = parser.parse(source, {sourceType:'module', plugins:['jsx']}).program;
const own = tree.body.find(x => x.type === 'ImportDeclaration' && x.source.value.startsWith('.'));
const component = own.specifiers.find(x => x.type === 'ImportDefaultSpecifier').local.name;
const snippet = node => source.slice(node.start,node.end);
function walk(node, fn) {
  if (!node || typeof node.type !== 'string') return;
  if (fn(node)) return;
  for (const val of Object.values(node)) {
    if (Array.isArray(val)) val.forEach(item => walk(item,fn)); else walk(val,fn);
  }
}
const out = [];
for (const statement of tree.body) {
  const call = statement.expression;
  if (call?.callee?.name !== 'test') continue;
  const events = [];
  walk(call.arguments[1].body, n => {
    if (n.type === 'VariableDeclarator') {
      events.push({declares:snippet(n)});
      return false;
    }
    if (n.type === 'JSXOpeningElement' && n.name.name === component) {
      events.push({render_with_props:n.attributes.map(snippet)});
      return true;
    }
    if (n.type !== 'CallExpression') return false;
    if (n.callee.type === 'MemberExpression') {
      const host = n.callee.object;
      const method = n.callee.property.name;
      if (host.name === 'fetchMock' && !['reset','restore','calls'].includes(method)) {
        events.push({network_method:method.toUpperCase(), mock_url_and_result:n.arguments.map(snippet)});
        return true;
      }
      if (host.name === 'fireEvent') {
        events.push({user_action:method, query_and_input:n.arguments.map(snippet)});
        return true;
      }
      if (host.type === 'CallExpression' && host.callee.name === 'expect') {
        events.push({observe:host.arguments.map(snippet), expectation:method, arguments:n.arguments.map(snippet)});
        return true;
      }
    }
    return false;
  });
  if (!events.some(e=>'render_with_props' in e) || !events.some(e=>'expectation' in e))
    throw Error('Missing render or assertion in supplied case');
  out.push({case:call.arguments[0].value, sequence:events});
}
if (![2,4].includes(out.length)) throw Error('Expected two or four public cases');
process.stdout.write(JSON.stringify(out));
