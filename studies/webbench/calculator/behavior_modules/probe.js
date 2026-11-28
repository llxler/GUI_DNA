(heldout) => {
  const key = label => Array.from(document.querySelectorAll('button')).find(
      b => b.textContent.trim() === label && b.getClientRects().length && getComputedStyle(b).visibility !== 'hidden');
  const display = document.querySelector('#display');
  const read = () => String(display?.value ?? display?.textContent ?? '').trim();
  const press = label => { const k = key(label); if (k) k.click(); return Boolean(k); };
  const seq = (...labels) => labels.every(press);
  const close = (value, want) => value !== '' && Math.abs(Number(value) - want) < 1e-5;
  const clickResult = (labels, want) => seq('Clear', ...labels) && close(read(), want);
  const digits = '0123456789'.split('').every(n => clickResult([n], Number(n)));
  const arithmetic = heldout ? clickResult(['7','*','8','='],56) : clickResult(['2','+','3','='],5);
  const root = clickResult(heldout ? ['8','1','√'] : ['9','√'],heldout ? 9 : 3);
  const square = clickResult(heldout ? ['5','^2'] : ['3','^2'],heldout ? 25 : 9);
  const reciprocal = clickResult(heldout ? ['4','1/x'] : ['2','1/x'],heldout ? .25 : .5);
  const constant = clickResult(['π'],Math.PI);
  const cosine = clickResult(['0','cos'],1);
  const toggle = document.getElementById('toggle');
  const t0 = toggle?.textContent.trim().toLowerCase(); toggle?.click();
  const t1 = toggle?.textContent.trim().toLowerCase(); toggle?.click();
  const theme = ['dark','light'].includes(t0) && ['dark','light'].includes(t1)
    && t0 !== t1 && toggle.textContent.trim().toLowerCase() === t0;
  const modeKey = document.getElementById('mode');
  const m0 = modeKey?.textContent.trim(); const hadScientific = Boolean(key('√'));
  modeKey?.click(); const m1 = modeKey?.textContent.trim();
  const disappeared = !key('√') && Boolean(key('3'));
  modeKey?.click(); const mode = Boolean(modeKey && m0 !== m1 && hadScientific && disappeared && key('√'));
  const width = Number.parseFloat(getComputedStyle(display).width);
  const layout = width > 0 && Math.abs(display.getBoundingClientRect().width - document.querySelector('.buttons').getBoundingClientRect().width) <= 2;
  const a = heldout ? '6' : '4', b = heldout ? '2' : '1';
  const mem = seq('MC','Clear',a,'M+','Clear',b,'M-','Clear','MR') && close(read(),Number(a)-Number(b));
  const panel = document.getElementById('memory');
  const memoryPanel = Boolean(mem && panel?.getClientRects().length && panel.textContent.includes(String(Number(a)-Number(b))));
  const tokens = heldout ? ['3','4','1','2','9','6'] : ['1','2','3','4','7','8'];
  seq('Clear',...tokens);
  const items = Array.from(document.querySelectorAll('#clicks .history-item'));
  const labels = items.map(el=>el.textContent.trim());
  const forward = tokens.slice(1), backward = [...forward].reverse();
  const history = labels.length === 5 && [forward,backward].some(order=>order.every((v,i)=>labels[i]===v));
  const replay = history && (()=>{const before=read();items.find(el=>el.textContent.trim()===tokens[2]).click();return read()===before+tokens[2];})();
  return {digits,arithmetic,root,square,reciprocal,constant,cosine,theme,mode,layout,mem,memoryPanel,history,replay,
    loaded: (window.calculatorModuleErrors || []).length===0};
}
