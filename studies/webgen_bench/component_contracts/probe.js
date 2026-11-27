({kind, source}) => {
  const root = document.createElement('section');
  document.body.replaceChildren(root);
  const calls = [], checks = {};
  const leaf = label => ({type: 'panel', title:label});
  const env = {
    data:{inventory:[{name:'Linen'},{name:'Flint'}]},
    get: key => key.replace(/[$\x7b\x7d]/g,'') === 'inventory' ? [{name:'Linen'},{name:'Flint'}] : undefined,
    text: value => String(value ?? '').replace('${token}', 'Pear'),
    mount(parent, children) {
      if (!(parent instanceof Element)) throw Error('env.mount requires a DOM parent');
      for(const node of [].concat(children || [])) {
        if(node instanceof Node){parent.append(node);continue;}
        calls.push(node.type);
        if (node.type==='submit') {const b=document.createElement('button'); b.type='submit'; b.textContent=node.label; parent.append(b);}
        else if(node.type==='input-text'){const input=document.createElement('input');input.name=node.name;parent.append(input);}
        else {const mark=document.createElement('span');mark.textContent=node.title || node.tpl || '';parent.append(mark);}
      }
    }
  };
  const visible = s => root.innerText.includes(s);
  const button = s => [...root.querySelectorAll('button,[role=button],a')].find(b=>b.textContent.trim()===s);
  const childA=leaf('Autumn marker'),childB=leaf('Spring marker');
  const input={type:kind,label:'Count stacks',name:'stacks',required:true,
               options:[{label:'North',value:'N'},{label:'South',value:'S'}]};
  const configs={
    page:{title:'Branch register',body:childA},panel:{title:'Seed store',body:[childA]},container:{body:childA},
    tpl:{tpl:'Ripe ${token}'}, tabs:{tabs:[{title:'Morning',body:childA},{title:'Evening',body:[childB]}]},
    table:{source:'${inventory}',columns:[{name:'name',label:'Material'}]},
    button:{label:'Reveal',actionType:'dialog',dialog:{title:'Hidden note',body:childA}},
    dialog:{title:'Private note',body:childA},submit:{label:'Send now'},
    form:{title:'Register',body:[{type:'input-text',name:'batch'}],actions:[{type:'submit',label:'Finish'}],
          onEvent:{submitSucc:{actions:[{actionType:'toast',args:{msg:'Batch received'}}]}}}
  };
  let error=null;
  try {
    const render=Function('return ('+source+')')();
    render(root,{type:kind,...(configs[kind] || input)},env);
    if(['page','panel','container'].includes(kind)) {
      checks.child=visible('Autumn marker') && calls.includes('panel');
      if(kind!=='container') checks.heading=visible(configs[kind].title);
    } else if(kind==='tpl') checks.text=visible('Ripe Pear');
    else if(kind==='tabs') {
      checks.navigation=Boolean(button('Morning') && button('Evening'));
      checks.initial=visible('Autumn marker')&&!visible('Spring marker');
      button('Evening')?.click();
      checks.switch=visible('Spring marker')&&!visible('Autumn marker');
      button('Morning')?.click();
      checks.back=visible('Autumn marker')&&!visible('Spring marker');
    } else if(kind==='table') {
      checks.columns=visible('Material');checks.records=visible('Linen')&&visible('Flint');
    } else if(kind==='button') {
      checks.label=Boolean(button('Reveal'));button('Reveal')?.click();checks.dialog=calls.includes('dialog')&&visible('Hidden note');
    } else if(kind==='dialog') {
      checks.title=visible('Private note');checks.body=visible('Autumn marker');
    } else if(kind==='submit') checks.submit=button('Send now')?.type==='submit';
    else if(kind==='form'){
      const form=root.querySelector('form');checks.mount=Boolean(form?.elements.namedItem('batch')&&button('Finish'));
      if(checks.mount) {form.elements.namedItem('batch').value='Seed';form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));}
      checks.feedback=visible('Batch received');
    } else {
      const el=root.querySelector('input,textarea,select');
      checks.field=Boolean(el && el.name==='stacks' && el.required);
      if(kind==='select')checks.options=el?.options?.length===2;
      if(kind==='checkbox')checks.checkbox=el?.type==='checkbox';
      if(kind==='input-number')checks.number=el?.type==='number';
    }
  } catch(e){error=String(e).slice(0,220);}
  return {passed:!error && Object.keys(checks).length>0 && Object.values(checks).every(Boolean),
          checks, trace:root.innerText.slice(0,250), children:calls.slice(0,20),error};
}
