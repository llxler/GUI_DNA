(() => {
  const buttons = document.querySelector('.buttons');
  const display = document.getElementById('display');
  const context = {
    buttons, display, calculator: document.querySelector('.calculator'), state: {},
    read() { return display.value; },
    write(value) { displayValue = String(value); display.value = displayValue; },
    find(label) {
      return Array.from(buttons.querySelectorAll('button')).find(el => el.textContent.trim() === label);
    },
    addKey(label, action) {
      if (this.find(label)) throw Error('Duplicate key: ' + label);
      const el = document.createElement('button');
      el.type = 'button'; el.textContent = label;
      el.addEventListener('click', () => action(el));
      buttons.appendChild(el);
      return el;
    }
  };
  const modules = [/*MODULES*/];
  const levels = /*LEVELS*/;
  window.calculatorModuleErrors = [];
  modules.forEach((install, i) => {
    if (levels[i]) {
      try { install(context, levels[i]); }
      catch (e) { window.calculatorModuleErrors.push(String(e)); }
    }
  });
})();
