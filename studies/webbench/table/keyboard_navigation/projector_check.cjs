// Check the membership projection independently of cell geometry or a particular DOM order.
const fs = require('node:fs');
const vm = require('node:vm');
const source = JSON.parse(fs.readFileSync(0, 'utf8'));
const fixture = `(() => {
  const cells = Array.from({length: 4}, () => ({
    classList: {add() {}, remove() {}, toggle() {}}, tagName: 'TD'
  }));
  const ctx = {table: {querySelectorAll: () => cells}, selected: new Set(), active: null, anchor: null};
  const trials = [
    ['single', [cells[2]], cells[2], cells[2]],
    ['disjoint', new Set([cells[0],cells[3]]), cells[3], cells[0]],
    ['empty', [], null, null]
  ];
  const results = {};
  for (const [name, selected, active, anchor] of trials) {
    try {
      markSelection(ctx, selected, active, anchor);
      results[name] = ctx.selected instanceof Set && ctx.selected.size === [...selected].length &&
        [...selected].every(c => ctx.selected.has(c)) && ctx.active === active && ctx.anchor === anchor;
    } catch (error) {
      results[name] = false;
    }
  }
  return results;
})()`;
try {
  const result = vm.runInNewContext(source+'\n'+fixture, {}, {timeout: 500});
  process.stdout.write(JSON.stringify(result));
} catch (error) {
  process.stdout.write(JSON.stringify({single:false,disjoint:false,empty:false}));
}
