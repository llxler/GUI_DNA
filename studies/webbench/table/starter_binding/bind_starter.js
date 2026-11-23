function compile(plan, files) {
  const generated = (ORIGINAL_COMPILER)(plan, files);
  const starterHTML = STARTER_HTML;
  const starterCSS = STARTER_CSS;
  const script = /<script\b[^>]*>[\s\S]*?<\/script\s*>/gi;
  const scripts = generated['index.html'].match(script);
  if (!scripts || !/\bindex\.css\b/i.test(generated['index.html']) || typeof generated['index.css'] !== 'string') {
    throw new Error('Expected generated boot scripts and the shared index.css stylesheet.');
  }
  const shell = starterHTML.replace(script, '');
  generated['index.html'] = shell.replace(/<\/body\s*>/i, () => scripts.join('\n') + '\n</body>');
  generated['index.css'] += '\n' + starterCSS;
  return generated;
}
