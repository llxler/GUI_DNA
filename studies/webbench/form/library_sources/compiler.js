function compile(plan, files) {
  const {questions, surveyTitle, exportData} = plan;
  if (!Array.isArray(questions) || questions.length > 60 ||
      !(surveyTitle === null || typeof surveyTitle === 'string') ||
      typeof exportData !== 'boolean') throw Error('invalid form configuration');
  const types = Object.keys(files).filter(name => /^common\/\w*Question\.js$/.test(name))
    .map(name => name.slice(7, -3));
  const imports = types.map(name => `import { ${name} } from './common/${name}.js';`);
  imports.push("import { Survey } from './common/Survey.js';");
  const statements = ["const form = document.querySelector('form');"];
  const plain = value => typeof value === 'boolean' || Number.isFinite(value) ||
    (typeof value === 'string' && value.length <= 500 && !/[<>]/.test(value));
  if (surveyTitle !== null) {
    if (!plain(surveyTitle)) throw Error('invalid survey title');
    statements.push('const survey = new Survey("form", ' + JSON.stringify(surveyTitle) + ');');
  }
  for (const {type, args, position} of questions) {
    if (!types.includes(type) || !['append','prepend'].includes(position) ||
        !Array.isArray(args) || !args.every(v => plain(v) || (Array.isArray(v) && v.every(plain)))) {
      throw Error('invalid question');
    }
    const instance = 'new ' + type + '(...' + JSON.stringify(args) + ')';
    statements.push(surveyTitle !== null ? `survey.${position}Question(${instance});` :
      `form.${position}((${instance}).root);`);
  }
  if (exportData) {
    if (surveyTitle === null) throw Error('export requires Survey');
    statements.push("const button = document.createElement('button'); button.type='button'; button.className='export'; button.textContent='Export'; form.append(button); button.onclick=()=>localStorage.setItem('data',JSON.stringify(survey.toJSON()));");
  }
  return {...files, 'index.js': [...imports, ...statements].join('\n')};
}
