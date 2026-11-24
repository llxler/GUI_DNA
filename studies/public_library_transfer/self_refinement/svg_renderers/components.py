"""Public ES-module contracts and generic mount code for the model-written renderers."""

import json
import re
import subprocess
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

from studies.public_library_transfer import browser, core

KINDS = ("line", "scatter", "step", "area", "bar", "pie")
DERIVED = {"scatter", "step", "area"}
CHART = "svg-chart"
MARK = re.compile(r"^\s*(?://|/\*)\s*FILE:\s*([^\s*]+)\s*(?:\*/)?\s*$", re.I | re.M)
GRAPHICS = "path,polyline,rect,line,circle,polygon,ellipse"


def name(kind):
    return "Chart" if kind == "base" else kind.title() + "Chart"


def path(kind):
    return f"common/{name(kind)}.js"


def strip_code(raw):
    code = raw.strip()
    fence = re.fullmatch(r"\s*`{3}(?:javascript|jsx|js|html|json|css|scss)?\s*\n(.*?)\n?\s*`{3}\s*", code, re.S | re.I)
    return fence[1] if fence else code


def source(raw, kind):
    code = strip_code(raw)
    if not re.search(r"\bexport\s+(?:class\s+" + name(kind) + r"\b|\{[^}]*\b" + name(kind) + r"\b[^}]*\})", code):
        raise ValueError("Missing named export " + name(kind))
    check = subprocess.run(["node", "--input-type=module", "--check"], input=code, capture_output=True, text=True, timeout=10)
    if check.returncode:
        raise ValueError(check.stderr[:450])
    return code


def direct(raw):
    text = strip_code(raw)
    try:
        obj = json.loads(text)
    except ValueError:
        obj = None
    if isinstance(obj, dict):
        obj = obj.get("files", obj)
        return core.files_map([{"path": k, "content": v} for k, v in obj.items()] if isinstance(obj, dict) else obj)
    markers = list(MARK.finditer(text))
    if markers:
        files = {}
        for i, m in enumerate(markers):
            filename = m[1]
            if filename in files:
                raise ValueError("Duplicate file")
            end = markers[i+1].start() if i+1 < len(markers) else len(text)
            files[filename] = strip_code(text[m.end():end])
        return core.files_map([{"path": k, "content": v} for k, v in files.items()])
    if re.match(r"^(?:<!doctype\s+html|<html)\b", text, re.I):
        return {"index.html": text}
    if text:
        check = subprocess.run(["node", "--input-type=module", "--check"], input=text, text=True, capture_output=True, timeout=10)
        if not check.returncode:
            return {"index.js": text}
    raise ValueError("No complete JS, HTML or file map")


def prompt(data, kind, parents):
    code_name = name(kind)
    parent = "LineChart" if kind in DERIVED else "Chart"
    role = ("Implement the base SVG element, reusable public layout, style, axes, grids, legends, theme and any common interactions. "
            "Expose and document the methods the concrete charts will call. The constructor creates this.svg and stores config, "
            "without drawing. Methods may create styles if needed." if kind == "base" else
            f"Implement {code_name} extending {parent}. Read the real exports and methods below. "
            "Implement all public requirements relevant to this renderer, including interactions. Use the parent methods that really exist. "
            "Its constructor must create this.svg, never invoke draw and never mount it. Your draw() method constructs the chart.")
    instruction = ("Implement just the complete ES module " + path(kind) + " in regular browser JavaScript. Return raw source. " + role +
                   " Export the class by its requested name, use only supplied local imports. Do not import a future file or alter assets. "
                   "Clients instantiate new " + code_name + "(config), mount instance.svg, then call instance.draw(). "
                   "Use config data and options, including explicit false and public defaults. No per-target or sample-id branching.")
    return core.messages(instruction, {"public_project": data, "already_generated_dependencies": parents})


def page(data, modules, enabled):
    imports = ["import {configs} from './assets/data.js';"]
    menu = []
    for kind in KINDS:
        if path(kind) in modules and enabled[kind]:
            imports.append(f"import {{{name(kind)}}} from './{path(kind)}';")
            menu.append(kind + ": " + name(kind))
    entry = "\n".join(imports) + "\nconst registry = {" + ", ".join(menu) + "};\n" + """const root = document.querySelector('.root');
for (const [id, supplied] of Object.entries(configs)) {
  const Renderer = registry[supplied.type];
  if (!Renderer) continue;
  try {
    const instance = new Renderer({...supplied, id});
    root.appendChild(instance.svg);
    instance.draw();
  } catch (error) {
    window.dispatchEvent(new ErrorEvent('error', {message: String(error), error}));
  }
}"""
    return data["starter"] | modules | {"index.js": entry}


def observe(root, where, files):
    served = browser.served_page(root, CHART, where, files)
    with browser.serve(CHART, served) as url, sync_playwright() as pw:
        chromium = pw.chromium.launch(env=browser.browser_env())
        try:
            tab = chromium.new_page(service_workers="block")
            tab.set_default_timeout(9000)
            tab.route("**/*", lambda route: route.continue_() if urlsplit(route.request.url).netloc in ("", urlsplit(url).netloc) else route.abort())
            errors = []
            tab.on("pageerror", lambda err: errors.append(str(err)[:260]))
            tab.goto(url, wait_until="networkidle", timeout=17000)
            observation = tab.evaluate("""async selector => {
              const {configs} = await import('/assets/data.js');
              const drawn = {}, mounted = {};
              for (const [id, config] of Object.entries(configs)) {
                const svg = document.getElementById(id);
                const present = svg instanceof SVGElement && !!svg.closest('.root');
                mounted[config.type] = (mounted[config.type] || 0) + Number(present);
                drawn[config.type] = (drawn[config.type] || 0) + (present ? svg.querySelectorAll(selector).length : 0);
              }
              return {drawn, mounted};
            }""", GRAPHICS)
            return {**observation, "errors": sorted(set(errors))}
        finally:
            chromium.close()
