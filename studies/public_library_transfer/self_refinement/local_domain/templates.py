"""Public-only prompts and the handwritten calculator-domain adapter."""
import json
import re
import subprocess
from html.parser import HTMLParser


def messages(system, text):
    return [{"role": "system", "content": system}, {"role": "user", "content": text}]


def descriptions(data):
    return [row["description"].strip() for row in data["requirements"]]


def bullet_lines(lines):
    return "\n".join("- " + line for line in lines)


def catalogue_prompt(lines):
    return messages(
        "Extract literal text for each NEW calculator key introduced in these requirements. "
        "Only include new keys on the numeric keypad. Skip controls outside that keypad. "
        "List actual visible labels, using the requested symbols and capitalization. "
        "Separate labels with | and omit prose, quotes and formatting. "
        "For example, if the specification adds 'x!' and then 'AC', answer x!|AC. "
        "If no new keys are requested, answer NONE.", bullet_lines(lines))


class ExistingButtons(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inside = False
        self.labels = []

    def handle_starttag(self, tag, attrs):
        if tag == "button":
            self.inside = True

    def handle_endtag(self, tag):
        if tag == "button":
            self.inside = False

    def handle_data(self, data):
        if self.inside and data.strip():
            self.labels.append(data.strip())


def labels_from(response, lines, seen):
    choices = []
    for candidate in re.split(r"[|,\n]", response):
        label = candidate.strip().strip("\x60'\"[] -*").strip()
        if (label and len(label) <= 12 and label.lower() != "none"
                and any(label in line for line in lines) and label.casefold() not in seen):
            choices.append(label)
            seen.add(label.casefold())
    return choices


def behavior_prompt(label, lines, error=""):
    related = [line for line in lines if label.casefold() in line.casefold()]
    request = f"New button label: {label!r}\nPublic description:\n{bullet_lines(related)}"
    if error:
        request += "\nPrior syntax error: " + error
    return messages(
        "Write exactly ONE JavaScript expression for a calculator key. Return the new display value. "
        "The available variables are n (number on display), s (display string), state (shared memory: "
        "state.memory starts at 0), and JavaScript Math. For example the key 'ten times' gives "
        "n * 10 and 'factorial approximation' could use a Math call. Use no Markdown or variable declarations. "
        "Do not write a handler or change the DOM. Output the expression only.", request)


def expression(raw):
    line = strip_fence(raw).strip().splitlines()
    if not line:
        return ""
    return re.sub(r"^return\s+", "", line[0]).rstrip(";").strip()


def strip_fence(text):
    fenced = re.search(r"```(?:javascript|js|html)?\s*\n(.*?)(?:\n```|\Z)", text, re.S | re.I)
    return (fenced[1] if fenced else text).strip()


def compile_error(js):
    return subprocess.run(["node", "--check"], input=js, text=True, capture_output=True).stderr.strip()


def panel_prompt(part, source, lines, labels):
    topic = {"appearance": "calculator layout, theme and basic/scientific mode",
             "panels": "memory, clicks history, replay and side panels"}[part]
    return messages(
        "Write raw browser JavaScript for ONE part of a calculator, limited to " + topic + ". "
        "Your code runs as function body after the original HTML and new keys are mounted. "
        "Do not add new numeric, scientific or memory keys; those are registered elsewhere. "
        "You may add controls, listeners, elements, or a style tag. For state you can read "
        "state.memory and state.history (initially empty; implement changes here); "
        "listen to document event 'calculator-change' with event.detail.label after a keypad click. "
        "Use querySelector on existing markup. Return only complete JavaScript, no HTML or explanation.",
        "Starter HTML:\n" + source + "\nRegistered new keypad labels: " + json.dumps(labels) +
        "\nPublic requirements:\n" + bullet_lines(lines))


def axis_prompt(lines):
    return messages(
        "Select ONE change to the calculator UI where earlier and later public requirements explicitly "
        "call for two different default settings. Describe the two concrete settings as two short "
        "English phrases separated by |. For instance an unrelated editor might have "
        "toolbar at top|toolbar at bottom. No code, extra lines or explanation.",
        bullet_lines(lines))


def axis_description(raw):
    parts = [part.strip(" \"'*\x60") for part in strip_fence(raw).split("|")]
    if len(parts) != 2 or any(not p or len(p) > 150 or "\n" in p for p in parts) or parts[0] == parts[1]:
        return None
    return dict(zip(("A", "B"), parts))


def option_prompt(setting, source, labels):
    return messages(
        "Write concise browser JavaScript to apply only this requested calculator UI setting. "
        "It runs once after the supplied calculator and additional named keypad keys are already present. "
        "Use existing DOM elements, creating a style tag only if needed. Treat this as a JavaScript "
        "function body; do not return HTML, explanations or Markdown.",
        "Requested setting: " + setting + "\nAdditional key labels: " + json.dumps(labels)
        + "\nStarter HTML:\n" + source)


def plan_prompt(lines, axis):
    return messages(
        "Select setting A or B so the calculator meets the MOST RECENT applicable requirement below. "
        "Output a JSON object with key setting.",
        "Requirements received so far:\n" + bullet_lines(lines) + "\nSettings:\n" + json.dumps(axis))


def direct_prompt(source, init, lines):
    return messages(
        "Write a complete working single-file HTML calculator for the final public request, including "
        "its prerequisites. Retain previously requested behavior that still applies. Start from the provided "
        "HTML. Return only the complete index.html, starting with <!doctype html>, without explanations.",
        "Initial requirement:\n" + init + "\nStarter HTML:\n" + source +
        "\nRequirements received so far:\n" + bullet_lines(lines))


def html_document(raw):
    match = re.search(r"(?:<!doctype\s+html\s*>\s*)?<html\b.*?</html\s*>", raw, re.I | re.S)
    return match.group(0) if match else None


def assemble(source, actions, panels, option):
    handlers = ",\n".join(json.dumps(k, ensure_ascii=False) + ": (n, s, state) => (" + code + ")"
                          for k, code in actions.items() if code)
    script = """
(() => {
  const state = {memory: 0, history: []};
  const display = document.getElementById('display');
  const keypad = document.querySelector('.buttons');
  const handlers = {""" + handlers + """};
  const labels = """ + json.dumps(list(actions), ensure_ascii=False) + """;
  for (const label of labels) {
    const key = document.createElement('button');
    key.textContent = label;
    keypad.appendChild(key);
    if (!Object.hasOwn(handlers, label)) { key.disabled = true; continue; }
    key.addEventListener('click', () => {
      const result = handlers[label](Number(display.value), display.value, state);
      if (result !== undefined) {
        displayValue = String(result);
        display.value = displayValue;
      }
    });
  }
  keypad.addEventListener('click', event => {
    const key = event.target.closest('button');
    if (!key) return;
    document.dispatchEvent(new CustomEvent('calculator-change', {detail: {label: key.textContent.trim()}}));
  });
  """ + "\n".join("(() => {\n" + code + "\n})();" for code in [*panels, option] if code) + """
})();
"""
    return source.replace("</body>", "<script>\n" + script.replace("</script", "<\\/script") + "\n</script>\n</body>", 1)
