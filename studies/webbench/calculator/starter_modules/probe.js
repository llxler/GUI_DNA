(action) => {
  const captions=()=>Array.from(document.querySelectorAll('button,[role=button]')).map(b=>[b.textContent.trim(),b]);
  const button=(s)=>captions().find(([t])=>t===s)?.[1];
  const click=(s)=>{const b=button(s);if(!b)return false;b.click();return true;};
  const display=()=>document.querySelector('#display')?.value;
  const plus=()=>['2','+','3','='].every(click)&&Number(display())===5;
  if(action==='base')return plus();
  if(action==='powers')return click('9')&&click('√')&&Number(display())===3;
  if(action==='trigonometry')return click('0')&&click('cos')&&Number(display())===1;
  if(action==='memory')return click('5')&&click('M+')&&click('Clear')&&click('MR')&&Number(display())===5;
  if(action==='history'){
    click('2');click('+');click('3');
    const items=document.querySelectorAll('#clicks .history-item');
    return items.length>0&&Array.from(items).some(el=>el.textContent.includes('3'));
  }
  if(action==='theme'||action==='mode'){
    const key=action==='theme'?'toggle':'mode',b=document.getElementById(key);
    if(!b)return false;
    const state=()=>[document.body.className,document.querySelector('.calculator')?.className,b.textContent,getComputedStyle(document.body).backgroundColor].join('|');
    const x=state();b.click();const y=state();b.click();return x!==y&&state()===x;
  }
  const clear=button('Clear');return !!clear&&getComputedStyle(clear).gridColumn.includes('3');
}
