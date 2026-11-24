async ({kind, type, modulePath, entry}) => {
  const result = {exported:false, mounted:false, public_structure:false, control:false};
  const title = 'Public question probe';
  const name = 'domain-probe';
  const choices = ['North', 'East', 'West'];
  const statements = ['First row', 'Second row'];
  const args = {
    Question: [], SingleSelectionQuestion:[choices], MultiSelectionQuestion:[choices],
    OpenQuestion:[true], RatingQuestion:[4], RankingQuestion:[choices], NpsQuestion:[],
    LikertQuestion:[choices,statements], DataQuestion:['email'],
  };
  try {
    let definition;
    if (modulePath) {
      const library = await import(modulePath);
      definition = library[type] || library.default;
    } else if (entry) {
      await import(entry);
    }
    definition ||= (kind === 'exposed' ? globalThis.__diagnosticTypes[type] : null) || globalThis[type];
    result.exported = typeof definition === 'function';
    if (!result.exported) return result;
    const instance = new definition(title,name,...args[type]);
    const root = instance.root;
    if (!(root instanceof HTMLElement)) return result;
    document.querySelector('form').append(root);
    result.mounted = root.isConnected;
    result.public_structure = root.matches('fieldset.q') && root.id===name &&
      root.querySelector('.q-title')?.textContent.includes(title) === true && !!root.querySelector('.q-body');
    const find = selector => [...root.querySelectorAll(selector)];
    const named = () => find('input,select,textarea').find(e => e.name===name);
    const checkChoices = selector => ['0','1','2'].map(v => find(selector).find(e => e.value===v));
    if (type === 'Question') result.control = result.public_structure;
    if (type === 'SingleSelectionQuestion' || type === 'MultiSelectionQuestion') {
      const multi = type === 'MultiSelectionQuestion';
      const items = checkChoices(multi ? 'input[type=checkbox]' : 'input[type=radio]');
      if (items.every(Boolean)) {
        items[1].click(); items[2].click();
        result.control = items[1].checked===multi && items[2].checked;
      }
    }
    if (type === 'OpenQuestion' || type === 'DataQuestion') {
      const el=root.querySelector(type==='OpenQuestion'?'textarea':'input[type=email]');
      if (el) { el.value=type==='OpenQuestion'?'Public multiline\nentry':'probe@example.org'; el.dispatchEvent(new Event('input',{bubbles:true})); result.control=!!el.value; }
    }
    if (type === 'RatingQuestion') {
      const stars=find('.star');
      if (stars.length===4) {
        stars[1].click();
        result.control=stars.filter(e=>e.classList.contains('active')).length===2 && Number(named()?.value)===0.5;
      }
    }
    if (type === 'RankingQuestion') result.control=find('.ranking-item').length===3 && named()?.value==='0,1,2';
    if (type === 'NpsQuestion') {
      const seven=find('.score').find(e=>e.textContent.trim()==='7');
      if (seven) { seven.click(); result.control=named()?.value==='7'; }
    }
    if (type === 'LikertQuestion') {
      const rows=statements.map((_,i)=>find('input[type=radio]').filter(e=>e.name===name+'_'+i));
      if (rows.every(r=>r.length===3)) { rows[0][1].click(); rows[1][2].click(); result.control=rows[0][1].checked && rows[1][2].checked; }
    }
    result.control=Boolean(result.control);
  } catch(error) {
    result.error=String(error.name)+': '+String(error.message).split('\n')[0].replace(/http:\/\/127\.0\.0\.1:\d+/g,'<local>');
  }
  return result;
}
