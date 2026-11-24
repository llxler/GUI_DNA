"""Fixed host signatures with model-authored implementations of every operation."""

import json
import re
import subprocess
from pathlib import Path

from studies.public_library_transfer import core
from studies.public_library_transfer.self_refinement.todomvc.source_binding.run import ACORN

HERE = Path(__file__).resolve().parent
EVENTS = {"add": "core", "destroy": "core", "toggle": "toggle", "toggleAll": "toggleAll",
          "edit": "edit", "save": "edit", "cancel": "edit", "clearCompleted": "clearCompleted", "route": "routing"}
OPTIONS = ("toggle", "toggleAll", "edit", "clearCompleted", "routing")
CONTRACTS = {
    "init": ("", "core", "Return the complete initial state loaded from the specified browser storage."),
    "persist": ("state", "core", "Write todos to the storage named in the specification. No return value needed."),
    "select": ("state", "view", "Return the complete view object, including the required fields with the exact names."),
    **{name: ("state, event", group, f"Handle only the {name!r} event. Return the updated state. The host calls persist afterwards.")
       for name, group in EVENTS.items()},
}


def messages(name, spec, error=None):
    params, group, objective = CONTRACTS[name]
    selected = list(spec["spec"]) if group == "view" else list(dict.fromkeys(["core", group]))
    sig = f"function {name}({params})"
    prompt = core.messages("Write just the complete JavaScript function with the supplied signature. "
                           "It runs in an ordinary browser. Work with the single shared state contract. "
                           "There are no other helper functions. No DOM code or imports.",
                           {"signature": sig, "operation": objective, "contract": spec["contract"],
                            "requirements": [line for k in selected for line in spec["spec"][k]]})
    if error:
        prompt.append({"role": "user", "content": "The previous response did not parse as " + sig +
                       ". Return that entire function including the closing brace, with no surrounding explanation."})
    return prompt


def js_block(raw):
    match = re.search(r"^`{3}(?:javascript|js)?[^\S\n]*\n(.*?)(?:^\s*`{3}|\Z)", raw, re.M | re.S | re.I)
    return match[1] if match else raw


def extract(name, raw):
    params = CONTRACTS[name][0]
    req = {"name": name, "arity": len(params.split(",")) if params else 0, "text": js_block(raw)}
    p = subprocess.run(["node", str(HERE / "function.cjs"), str(ACORN)], input=json.dumps(req),
                       text=True, capture_output=True, timeout=10)
    return p.stdout if p.returncode == 0 and p.stdout.strip() else None


def assemble(functions, config):
    parts = [code for code in functions.values() if code]
    targets = {event: symbol for event, symbol in EVENTS.items() if functions.get(event)
               and (symbol == "core" or config[symbol])}
    routes = ", ".join(f"{json.dumps(event)}: {event}" for event in targets)
    router = """const routes = {%s};
window.candidate = {init, select, reduce(state, event) {
  const fn = Object.hasOwn(routes, event.type) && routes[event.type];
  if (!fn) return state;
  const next = fn(state, event) ?? state;
  persist(next);
  return next;
}};""" % routes
    return "(function(){\n" + "\n".join(parts) + "\n" + router + "\n})();"
