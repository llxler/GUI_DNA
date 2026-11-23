function compile(plan, files) {
  const info = JSON.parse(files["library/manifest.json"]);
  const enabled = new Set(plan.enabled);
  const imports = ["core", ...info.controllers.filter(x => enabled.has(x))];
  const load = imports.map((k,i) => "import m" + i + " from './library/" + k + ".js';").join("\n");
  const invoke = imports.map((_,i) => "m" + i + "(shared);").join("\n");
  const result = {...files};
  result[info.entry] += "\n" + load + "\n{const shared = {};\n" + invoke + "\n}\n";
  result[info.style] += "\n" + imports.map(k => files["library/" + k + ".css"]).join("\n");
  return result;
}
