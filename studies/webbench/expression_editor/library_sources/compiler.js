function compile(plan, files) {
  return {
    ...files,
    'configuration.js': 'export const plan = ' + JSON.stringify(plan) + ';\n',
    'index.js': "import './binding.js';\n",
  };
}
