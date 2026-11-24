const fs = require('node:fs');
const acorn = require(process.argv[2]);
const req = JSON.parse(fs.readFileSync(0, 'utf8'));
const parser = new acorn.Parser({ecmaVersion: 'latest'}, req.text);
parser.nextToken();
while (parser.type !== acorn.tokTypes.eof) {
  const stmt = parser.parseStatement(null, true, Object.create(null));
  if (stmt.type === 'FunctionDeclaration' && stmt.id.name === req.name &&
      !stmt.async && !stmt.generator && stmt.params.length === req.arity) {
    process.stdout.write(req.text.slice(stmt.start, stmt.end));
    process.exit(0);
  }
}
process.exit(1);
