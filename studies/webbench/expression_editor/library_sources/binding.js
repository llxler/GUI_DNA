// Adapted from Web-Bench expression-editor/src/index.js, Apache-2.0.
// Reference module exports provide language semantics and interactive controllers.
import { parse } from './parser.js';
import { evaluate } from './evaluate.js';
import { setupEditorHighlighting } from './highlight.js';
import { setupAutocompletion } from './autocomplete.js';
import { EditorHistory } from './editor.js';
import { plan } from './configuration.js';

function element(tag, attributes = {}) {
  const el = document.createElement(tag);
  Object.assign(el, attributes);
  return el;
}

function mount() {
  const app = document.getElementById('app');
  const editor = element('div', {id: 'editor', contentEditable: 'true'});
  Object.assign(editor.style, {
    fontFamily: 'Menlo, Monaco, "Courier New", monospace', minHeight: '100px',
    padding: '10px', border: '1px solid #ccc', boxSizing: 'border-box', height: 'auto',
  });
  const toolbar = element('div', {id: 'toolbar'});
  Object.assign(toolbar.style, {display: 'flex', justifyContent: 'space-between', padding: '10px'});
  const left = element('div');
  const right = element('div');
  toolbar.append(left, right);
  if (plan.toolbar.length) app.append(toolbar);
  app.append(editor);

  function button(parent, name, handle) {
    const el = element('button', {textContent: name});
    el.addEventListener('click', handle);
    parent.append(el);
    return el;
  }
  if (plan.toolbar.includes('run')) {
    const result = element('div', {id: 'result-display'});
    app.append(result);
    button(left, 'Run', () => { result.textContent = String(evaluate(editor.innerText.trim())); });
  }
  if (plan.toolbar.includes('uppercase')) {
    button(right, 'Uppercase', () => {
      const selection = window.getSelection();
      if (selection.rangeCount && editor.contains(selection.anchorNode) && selection.toString()) {
        const range = selection.getRangeAt(0);
        const replacement = document.createTextNode(selection.toString().toUpperCase());
        range.deleteContents();
        range.insertNode(replacement);
      }
    });
  }
  if (plan.toolbar.includes('snippet')) {
    button(right, 'Insert Snippet', () => {
      const selection = window.getSelection();
      if (!selection.rangeCount || !editor.contains(selection.focusNode)) {
        editor.focus();
        const end = document.createRange();
        end.selectNodeContents(editor);
        end.collapse(false);
        selection.removeAllRanges();
        selection.addRange(end);
      }
      const range = selection.getRangeAt(0);
      range.deleteContents();
      const snippet = document.createTextNode('true OR false');
      range.insertNode(snippet);
      range.selectNodeContents(snippet);
      selection.removeAllRanges();
      selection.addRange(range);
      editor.focus();
    });
  }
  if (plan.toolbar.includes('documentation')) {
    const popup = element('div', {id: 'documentation-popup'});
    popup.style.display = 'none';
    popup.append(element('h2', {textContent: 'Document'}), element('p', {textContent: 'WIP'}));
    button(popup, 'Close', () => { popup.style.display = 'none'; });
    button(right, 'Documentation', () => { popup.style.display = 'block'; });
    app.append(popup);
  }

  const enabled = new Set(plan.controllers);
  if (enabled.has('pairParentheses')) {
    editor.addEventListener('input', event => {
      if (event.inputType !== 'insertText' || event.data !== '(') return;
      const selection = window.getSelection();
      const range = selection.getRangeAt(0);
      document.execCommand('insertText', false, ')');
      range.setStart(range.startContainer, range.startOffset - 1);
      range.collapse(true);
      selection.removeAllRanges();
      selection.addRange(range);
    });
  }
  if (enabled.has('syntaxErrors')) {
    const error = element('div', {id: 'syntax-error', textContent: 'Syntax Error'});
    Object.assign(error.style, {display: 'none', backgroundColor: '#ffcccc'});
    app.append(error);
    const validate = () => {
      try {
        if (editor.innerText.trim()) parse(editor.innerText.trim());
        error.style.display = 'none';
      } catch {
        error.style.display = 'block';
      }
    };
    editor.addEventListener('input', validate);
    editor.addEventListener('blur', validate);
  }
  if (enabled.has('highlight')) setupEditorHighlighting(editor);
  if (enabled.has('completion')) setupAutocompletion(editor);
  if (enabled.has('history')) new EditorHistory(editor);
  if (enabled.has('diagnosticTooltip')) {
    const tip = element('div', {className: 'tooltip'});
    Object.assign(tip.style, {display: 'none', position: 'absolute'});
    app.append(tip);
    editor.addEventListener('mouseover', event => {
      const message = event.target.dataset.diagnosticMessage;
      if (!message) return;
      const rect = event.target.getBoundingClientRect();
      tip.textContent = message;
      Object.assign(tip.style, {display: 'block', left: rect.left + 'px', top: (rect.bottom + 5) + 'px'});
    });
    editor.addEventListener('mouseout', () => { tip.style.display = 'none'; });
  }
}
document.addEventListener('DOMContentLoaded', mount);
