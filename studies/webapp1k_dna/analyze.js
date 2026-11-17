// Static text extraction + relabel splicing for one React atom module.
// Usage: node analyze.js <atom.js> [edits.json]
// Prints JSON {static:[{kind,value,start,end}], dynamic:[string], code, applied:[...], missing:[...]}.
// Run with NODE_PATH pointing at the WebApp1k staging node_modules (CRA ships @babel/parser + @babel/traverse).
const fs = require('fs');
const parser = require('@babel/parser');
const traverse = require('@babel/traverse').default;

const file = process.argv[2];
const edits = process.argv[3] ? JSON.parse(fs.readFileSync(process.argv[3], 'utf8')) : [];
const code = fs.readFileSync(file, 'utf8');
const ast = parser.parse(code, { sourceType: 'module', plugins: ['jsx'] });
const TEXT_ATTRS = new Set(['placeholder', 'aria-label', 'alt', 'title', 'value', 'data-testid', 'label', 'name', 'id', 'htmlFor']);
const statics = [];
const dynamics = new Set();
const norm = (s) => s.replace(/\s+/g, ' ').trim();

traverse(ast, {
  JSXText(path) {
    const raw = path.node.value;
    const value = norm(raw);
    if (!value) return;
    const lead = raw.length - raw.trimStart().length;
    const trail = raw.length - raw.trimEnd().length;
    statics.push({ kind: 'text', value, start: path.node.start + lead, end: path.node.end - trail });
  },
  JSXExpressionContainer(path) {
    const e = path.node.expression;
    if (e.type === 'StringLiteral') {
      statics.push({ kind: path.parent.type === 'JSXAttribute' ? 'attr:' + path.parent.name.name : 'text', value: norm(e.value), start: e.start, end: e.end, quoted: true });
    } else if (e.type === 'TemplateLiteral' && e.expressions.length === 0) {
      statics.push({ kind: 'text', value: norm(e.quasis.map((q) => q.value.cooked).join('')), start: e.start, end: e.end, quoted: true });
    }
  },
  JSXAttribute(path) {
    const name = path.node.name.name;
    const v = path.node.value;
    if (v && v.type === 'StringLiteral' && TEXT_ATTRS.has(name)) {
      statics.push({ kind: 'attr:' + name, value: norm(v.value), start: v.start, end: v.end, quoted: true });
    }
  },
  StringLiteral(path) {
    const p = path.parent;
    if (p.type === 'ImportDeclaration' || p.type === 'JSXAttribute') return;
    if (path.parentPath.isJSXExpressionContainer()) return;
    if (p.type === 'ObjectProperty' && p.key === path.node) return;
    const value = norm(path.node.value);
    if (value) dynamics.add(value);
  },
  TemplateLiteral(path) {
    if (path.parentPath.isJSXExpressionContainer()) return;
    const value = norm(path.node.quasis.map((q) => q.value.cooked).join(' '));
    if (value) dynamics.add(value);
  },
});

// Apply relabels by splicing source ranges (atom logic stays byte-identical outside the edited literals).
let out = code;
const applied = [];
const missing = [];
const replacements = [];
for (const edit of edits) {
  const targets = statics.filter((s) => s.value === norm(edit.from));
  if (!targets.length) { missing.push(edit.from); continue; }
  for (const t of targets) replacements.push({ ...t, to: edit.to });
  applied.push({ from: edit.from, to: edit.to, count: targets.length });
}
replacements.sort((a, b) => b.start - a.start);
for (const r of replacements) {
  const text = r.quoted ? JSON.stringify(r.to) : r.to;
  out = out.slice(0, r.start) + text + out.slice(r.end);
}
const finalStatics = replacements.length
  ? statics.map((s) => { const r = replacements.find((x) => x.start === s.start); return { kind: s.kind, value: r ? norm(r.to) : s.value }; })
  : statics.map((s) => ({ kind: s.kind, value: s.value }));
process.stdout.write(JSON.stringify({ static: finalStatics, dynamic: [...dynamics], code: out, applied, missing }));
