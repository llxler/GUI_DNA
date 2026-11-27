({kind, source, labels}) => {
  const root=document.createElement('section');
  document.body.replaceChildren(root);
  const [title, nested, action, success]=labels;
  const env={mount(parent, nodes) {
    for (const child of [].concat(nodes || [])) {
      let el;
      if(child.type==='submit'){
        el=document.createElement('button');el.type='submit';el.textContent=child.label;
      }else if(child.type==='input-text'){
        el=document.createElement('input');el.name=child.name;
      }else{
        el=document.createElement('span');el.textContent=child.title;
      }
      parent.append(el);
    }
  }};
  const brief=kind==='dialog'?{title,body:{type:'panel',title:nested}}:
    {title,body:[{type:'input-text',name:'batch'}],actions:[{type:'submit',label:action}],
     onEvent:{submitSucc:{actions:[{args:{msg:success}}]}}};
  const checks={};
  let error=null;
  try {
    Function('return ('+source+')')()(root,brief,env);
    if(kind==='dialog'){
      checks.open=root.innerText.includes(nested) && root.innerText.includes(title);
      const close=[...root.querySelectorAll('button')].find(b=>b.innerText.trim().toLowerCase()==='close');
      checks.closeButton=Boolean(close);
      close?.click();
      checks.dismiss=!root.innerText.includes(nested);
    }else{
      const form=root.querySelector('form');
      const entry=form?.elements.namedItem('batch');
      const button=form?.querySelector('button[type=submit]');
      checks.controls=Boolean(entry && button?.innerText===action);
      if(entry && button){entry.value='Amber';button.click();}
      checks.message=[...root.querySelectorAll('*')].some(el=>el.innerText===success && el.getClientRects().length>0);
    }
  }catch(e){error=String(e).slice(0,200);}
  return {passed:!error && Object.keys(checks).length>0 && Object.values(checks).every(Boolean),checks,error,
          dialogs:[...root.querySelectorAll('dialog')].map(el=>({open:el.open,text:el.textContent.slice(0,100)})),
          text:root.innerText.slice(0,220)};
}
