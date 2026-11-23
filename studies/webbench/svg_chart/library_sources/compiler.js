function compile(plan, files) {
  const {renderers} = plan;
  if (!renderers || typeof renderers !== 'object' || Array.isArray(renderers)) {
    throw Error('renderers must map chart types to class names');
  }
  const classes = Object.keys(files)
    .map(name => /^common\/(\w+Chart)\.js$/.exec(name))
    .filter(Boolean).map(match => match[1]);
  if (!Object.entries(renderers).every(([key, value]) =>
    /^[a-z]+$/.test(key) && classes.includes(value))) throw Error('invalid type or class');
  const imports = classes.map(name => `import { ${name} } from './common/${name}.js';`);
  const entry = [
    "import { configs } from './assets/data.js';",
    ...imports,
    'const classes = {' + classes.join(', ') + '};',
    'const renderers = ' + JSON.stringify(renderers) + ';',
    "const root = document.querySelector('.root');",
    'for (const [id, config] of Object.entries(configs)) {',
    '  const Renderer = classes[renderers[config.type]];',
    '  if (!Renderer) continue;',
    '  const chart = new Renderer({...config, id});',
    '  chart.draw();',
    '  root.append(chart.svg);',
    '}'
  ];
  return {...files, 'index.js': entry.join('\n')};
}
