"""Ground literal keypad requests in the JavaScript math vocabulary and generic arithmetic."""
import itertools
import json
import re
import subprocess
import unicodedata


def inventory(lines):
    keys = {}
    swap = None
    for line in lines:
        for match in re.finditer(r"\bbutton\s+([\wπ+-]+)\s*(?:with\s+text\s*|\(text\s*)'([^']+)'", line, re.I):
            name, label = match.groups()
            keys.setdefault(label, {"name": name, "public_text": line})
        plural = re.search(r"\badd buttons ([\w, ]+?) at the end", line, re.I)
        if plural:
            for name in plural[1].split(","):
                label = name.strip()
                keys.setdefault(label, {"name": label, "public_text": line})
        pair = re.search(r"\brevert position of button ([\wπ]+),\s*button ([\wπ]+)", line, re.I)
        if pair:
            swap = list(pair.groups())
    return keys, swap


def math_properties():
    call = """Object.getOwnPropertyNames(Math).map(k => [k, typeof Math[k], typeof Math[k]==='function'?Math[k].length:null])"""
    return json.loads(subprocess.check_output(["node", "-p", "JSON.stringify(" + call + ")"], text=True))


def expressions(props):
    codes = {}
    for key, kind, arity in props:
        if kind == "number":
            codes[key] = f"Math.{key}"
        elif kind == "function" and arity == 1:
            codes[key] = f"Math.{key}(n)"
    for a, op, b in itertools.product(("n", "1", "2"), ("+", "-", "*", "/", "**"), ("n", "1", "2")):
        if a == "n" or b == "n":
            codes[f"{a}{op}{b}"] = f"{a}{op}{b}"
    for name, op in [("add to memory", "+"), ("subtract from memory", "-"),
                     ("multiply memory", "*"), ("divide memory", "/")]:
        codes[name] = f"((state.memory {op}= n), s)"
    codes.update({"store number": "((state.memory = n), s)", "reset stored number": "((state.memory = 0), s)",
                  "read stored number": "state.memory", "append stored number": "s + state.memory", "keep display": "s"})
    return codes


def ground(label, key, codes):
    props = {k.casefold(): k for k, value in codes.items() if value.startswith("Math.")}
    words = [key["name"].casefold(), label.casefold()]
    if len(label) == 1:
        words.append(unicodedata.name(label, "").lower().split(" ")[-1])
    for word in words:
        if word in props:
            return props[word]
    translated = label.replace("^", "**").replace("x", "n").replace("×", "*").replace("÷", "/")
    if translated.startswith(("+", "-", "*", "/")):
        translated = "n" + translated
    if translated in codes:
        return translated
    return None


def order_setup(pair):
    names = json.dumps(pair)
    return """
const [leftName, rightName] = """ + names + """;
const buttons = Array.from(document.querySelectorAll('.buttons button'));
const left = buttons.find(el => el.textContent.trim() === leftName);
const right = buttons.find(el => el.textContent.trim() === rightName);
if (left && right && left !== right) {
 const anchor = document.createComment('button-position');
 right.replaceWith(anchor);
 left.replaceWith(right);
 anchor.replaceWith(left);
}
"""
