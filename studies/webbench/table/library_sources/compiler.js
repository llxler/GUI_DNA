function compile(plan, files) {
  const bindings = {
    contextMenu: ['menu', 'TableMenu'],
    keyboard: ['key', 'TableKeyboard'],
    rowResize: ['layout', 'TableRowResizer'],
    columnResize: ['layout', 'TableColResizer'],
    mouseSelection: ['mouse', 'TableMouse'],
    dragReorder: ['drag', 'initTableDragEvents'],
  };
  const imports = ["import { Table } from './common/table.js'"];
  const setup = [];
  for (const [name, [module, symbol]] of Object.entries(bindings)) {
    if (!plan.controllers.includes(name)) continue;
    imports.push("import { " + symbol + " } from './common/" + module + ".js'");
    setup.push(name === 'dragReorder' ? symbol + '(table)' : 'new ' + symbol + '(table)');
  }
  const script = imports.join('\n') + "\n" +
    "document.addEventListener('DOMContentLoaded', () => {\n" +
    "  const tableElement = document.querySelector('.table')\n" +
    "  if (!tableElement) return\n  const table = new Table(tableElement)\n" +
    setup.map(line => '  ' + line).join('\n') + "\n})\n";
  return { ...files, 'index.js': script };
}
