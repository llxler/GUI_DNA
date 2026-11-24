// Recover only duplicate lexical declarations in disjoint, terminating switch clauses.
const fs = require('node:fs');
const acorn = require(process.argv[2]);
const source = fs.readFileSync(0, 'utf8');
const options = { ecmaVersion: 'latest', sourceType: 'script' };
const duplicate = /^Identifier '([^']+)' has already been declared$/;

function visit(node, fn, parent = null, key = '') {
  if (!node || typeof node !== 'object') return;
  if (Array.isArray(node)) {
    for (const child of node) visit(child, fn, parent, key);
    return;
  }
  if (!node.type) return;
  fn(node, parent, key);
  for (const [field, child] of Object.entries(node)) visit(child, fn, node, field);
}

function terminates(node) {
  if (!node) return false;
  if (node.type === 'ReturnStatement' || node.type === 'ThrowStatement') return true;
  if (node.type === 'BreakStatement') return !node.label;
  if (node.type === 'IfStatement') return terminates(node.consequent) && terminates(node.alternate);
  return node.type === 'BlockStatement' && terminates(node.body.at(-1));
}

function refers(node, parent, key) {
  if (node.type !== 'Identifier') return false;
  if (parent?.type === 'MemberExpression' && key === 'property' && !parent.computed) return false;
  if (parent?.type === 'Property' && key === 'key' && !parent.computed) return false;
  return true;
}

function repair() {
  try {
    acorn.parse(source, options);
    return { status: 'already_parses' };
  } catch (e) {
    if (!duplicate.test(e.message.split(' (')[0])) return { status: 'different_parse_error', reason: e.message };
  }
  const errors = new Map();
  class DuplicateDiagnostic extends acorn.Parser {
    raiseRecoverable(pos, message) {
      const match = duplicate.exec(message);
      if (!match) return super.raiseRecoverable(pos, message);
      errors.set(pos, match[1]);
    }
  }
  const tree = DuplicateDiagnostic.parse(source, options);
  const edits = [];
  const proof = [];
  const covered = new Set();
  visit(tree, node => {
    if (node.type === 'WithStatement' || (node.type === 'Identifier' && node.name === 'eval')) {
      throw Error('dynamic_scope');
    }
    if (node.type !== 'SwitchStatement') return;
    const owners = new Map();
    const bindings = node.cases.map((clause, i) => {
      const direct = [];
      for (const stmt of clause.consequent) {
        if (stmt.type !== 'VariableDeclaration' || !['const', 'let'].includes(stmt.kind)) continue;
        for (const { id } of stmt.declarations) {
          if (id.type !== 'Identifier') continue;
          direct.push(id);
          if (!owners.has(id.name)) owners.set(id.name, []);
          owners.get(id.name).push(i);
        }
      }
      return direct;
    });
    const touched = new Set();
    for (const [name, places] of owners) {
      if (places.length < 2) continue;
      if (new Set(places).size !== places.length) throw Error('same_case_duplicate');
      for (const i of places) touched.add(i);
      for (const i of places) {
        for (const binding of bindings[i]) {
          if (binding.name === name && errors.get(binding.start) === name) covered.add(binding.start);
        }
      }
    }
    if (!touched.size) return;
    const movedNames = new Set([...touched].flatMap(i => bindings[i].map(id => id.name)));
    for (const [i, clause] of node.cases.entries()) {
      visit(clause.test, (n, p, k) => {
        if (refers(n, p, k) && movedNames.has(n.name)) throw Error('switch_label_may_read_moved_binding');
      });
      const local = new Set(bindings[i].map(id => id.name));
      visit(clause.consequent, (n, p, k) => {
        if (refers(n, p, k) && movedNames.has(n.name) && !local.has(n.name)) throw Error('cross_case_name');
      });
      if (!touched.has(i)) continue;
      if (!terminates(clause.consequent.at(-1)) || (i && !terminates(node.cases[i - 1].consequent.at(-1)))) {
        throw Error('possible_fallthrough');
      }
      for (const stmt of clause.consequent) {
        if (stmt.type === 'FunctionDeclaration' || stmt.type === 'ClassDeclaration' ||
            (stmt.type === 'VariableDeclaration' && (stmt.kind === 'var' ||
             stmt.declarations.some(({ id }) => id.type !== 'Identifier')))) throw Error('unsupported_declaration');
      }
      const start = clause.consequent[0].start;
      const end = clause.consequent.at(-1).end;
      edits.push([start, '{'], [end, '}']);
      proof.push({ switch_start: node.start, case_index: i, start, end, local: [...local].sort() });
    }
  });
  if (!errors.size || covered.size !== errors.size) throw Error('duplicate_outside_proved_clauses');
  let repaired = source;
  for (const [pos, brace] of edits.sort((a, b) => b[0] - a[0])) repaired = repaired.slice(0, pos) + brace + repaired.slice(pos);
  acorn.parse(repaired, options);
  return { status: 'scoped', source: repaired, proof, duplicates: Object.fromEntries(errors) };
}

try { console.log(JSON.stringify(repair())); }
catch (e) { console.log(JSON.stringify({ status: 'unsafe', reason: e.message })); }
