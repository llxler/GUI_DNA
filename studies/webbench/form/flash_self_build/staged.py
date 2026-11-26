"""Independent, file-wise Self construction with the original public assembler."""
from concurrent.futures import ThreadPoolExecutor
from graphlib import TopologicalSorter
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, read, sha
from studies.webbench.backbone_matrix.run import normalized


DESIGN = """Design a reusable implementation for the given public website. Return one small JSON
object with design (an informative planning guide), controls (the given schema), and modules
in dependency order. For each module return path, api (exact exports, constructor/argument order,
methods, interface and responsibilities), and depends_on (an array of local paths).
Include every publicly named module path and both starter JS and CSS entry files. Split large
behaviors into reusable code. The last integrated application must mount real working controls in
the original starter, including the specified public examples, interactions and persistence.
Select 1–6 independent semantic options that correspond to real variations. Document EXACTLY what
each value enables, select valid defaults and a useful first example now. Plans may not contain
code, task numbers, or task-index modes. The original compiler sets globalThis.APP_CONFIG to
these values before it loads the starter entry. Write no source code in this response."""

SOURCE = """Write ONLY the complete raw source for the single requested file. Implement the
public facts relevant to this file and the agreed API with functional code. Use the actual
constructor signatures, working example instances, DOM names and event behavior in the public
requirements. Honor the manifest's option semantics. Use relative ES module imports with
explicit extensions. Match named/default exports to actual dependencies. Keep starter HTML intact,
use the existing entry files, work entirely offline, and share application state across controls.
The browser entry must instantiate and mount the specified examples together, in the publicly
requested order. Wire validation, changing order, configuration changes, and persistence to
the actual mounted instances; avoid isolated demo stubs or a separate shadow state model.
Return direct JavaScript or CSS; no bundle, markdown, explanation, tool calls, or task dispatch."""

PATCH = """One public browser check failed. Correct precisely one of your own source files.
Return JSON with path and content (the entire replacement source). Keep the existing options
and interfaces. Use only the original public brief, submitted sources and public diagnostic."""

EXCEPTIONS = (ValueError, KeyError, TypeError, AttributeError, IndexError)


def _ask(folder, ask, system, body, purpose, limit):
    saved = folder / "visible.json"
    if saved.is_file():
        return read(saved)["text"]
    text = ask(folder, core.messages(system, body), purpose, limit)
    if not isinstance(text, str):
        raise TypeError("The model request must return visible text")
    core.save(saved, {"text": text})
    return text


def public_paths(data):
    text = "\n".join([data["init"], *(r["description"] for r in data["requirements"])])
    paths = set(re.findall(r"(?<![\w./-])(?:[\w-]+/)*[\w-]+\.(?:js|css)\b", text))
    return sorted(paths | {name for name in data["starter"] if name.endswith((".js", ".css"))})


def _package(data, design, sources):
    raw = {"design": design["design"], "controls": design["controls"], "anchor": "",
           "fragment": "", "css": "", "script": "",
           "files": [{"path": name, "content": source} for name, source in sources.items()]}
    return core.package(data, normalized(raw))


def parse_design(text, data):
    spec = core.parse(text)
    if not isinstance(spec["design"], str) or not spec["design"].strip():
        raise ValueError("Provide a concise design and interface guide")
    modules = spec["modules"]
    if not isinstance(modules, list) or not 2 <= len(modules) <= 18:
        raise ValueError("Expected 2 to 18 modules")
    files = core.files_map([{"path": m["path"], "content": ""} for m in modules])
    missing = set(public_paths(data)) - set(files)
    if missing:
        raise ValueError("Include these public modules: " + ", ".join(sorted(missing)))
    if any(not k.endswith((".js", ".mjs", ".css")) for k in files):
        raise ValueError("Use local JS or CSS paths; the host preserves index.html")
    edges = {}
    for mod in modules:
        deps = mod["depends_on"]
        if not isinstance(mod["api"], str) or not mod["api"].strip():
            raise ValueError("Every module needs a documented public API")
        if not isinstance(deps, list) or not all(isinstance(p, str) and p in files for p in deps):
            raise ValueError(f"Unknown written dependency in {mod['path']}")
        edges[mod["path"]] = deps
    list(TopologicalSorter(edges).static_order())
    _package(data, spec, {})  # Validate every option before spending calls on implementation.
    return spec


def parse_source(raw, name):
    content = raw.strip()
    fenced = re.fullmatch(r"```(?:javascript|js|css|mjs)?\s*\n(.*?)\n```", content, re.S | re.I)
    if fenced:
        content = fenced[1]
    if not content.strip():
        raise ValueError(f"{name}: empty visible source")
    if name.endswith((".js", ".mjs")):
        check = subprocess.run(["node", "--input-type=module", "--check", "-"], input=content,
                               capture_output=True, text=True, timeout=10)
        if check.returncode:
            raise ValueError(f"{name}: {check.stderr[:750]}")
    return content


def _probe(directory, modules):
    """Exercise public module loading and the original form in a fresh localhost session."""
    errors = []
    with browser.serve("form", directory) as url, sync_playwright() as pw:
        engine = pw.chromium.launch(env=browser.browser_env())
        try:
            ctx = engine.new_context(service_workers="block")
            ctx.route("**/*", lambda r: r.continue_() if urlsplit(r.request.url).netloc == urlsplit(url).netloc
                      else r.abort())
            page = ctx.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)[:450]))
            page.on("dialog", lambda dialog: dialog.dismiss())
            page.goto(url + "/index.html", wait_until="load", timeout=10000)
            obs = page.evaluate("""async paths => {
              const importErrors = [];
              for (const path of paths) {
                try { await import('/' + path); }
                catch (e) { importErrors.push(path + ': ' + String(e)); }
              }
              const form = document.querySelector('form');
              const fields = form ? [...form.querySelectorAll('fieldset')] : [];
              const toggle = form?.querySelector('input[type=checkbox]:not(:disabled),input[type=radio]:not(:checked):not(:disabled)');
              let toggled = null;
              if (toggle) { const before = toggle.checked; toggle.click(); toggled = toggle.checked !== before; }
              return {importErrors, form: !!form, fieldsets: fields.length, toggled};
            }""", [n for n in modules if n.endswith((".js", ".mjs"))])
            errors.extend(obs["importErrors"])
            if not obs["form"] or not obs["fieldsets"]:
                errors.append("The startup entry did not mount a question fieldset in the public form")
            obs["errors"] = errors
            return obs
        finally:
            engine.close()


def _admit(folder, data, spec, sources):
    pkg = _package(data, spec, sources)
    errors = []
    for name, plan in (("default", pkg["defaults"]), ("first", pkg["examples"][0]["plan"])):
        dest = folder / name
        core.materialize("form", pkg, plan, dest)
        observed = _probe(dest, sources)
        core.save(folder / (name + "-public.json"), observed)
        errors.extend(f"{name}: {item}" for item in observed["errors"])
    if errors:
        raise ValueError("\n".join(errors)[:2500])
    return pkg


def build_staged(data, folder, ask):
    """Use the caller's metered visible-response function for one independent build."""
    folder = Path(folder).resolve()
    status = folder / "status.json"
    if status.exists():
        return read(status)
    if data["project"] != "form" or [r["id"] for r in data["requirements"]] != [f"task-{i}" for i in range(1, 21)]:
        raise ValueError("This protocol enrolls the full public question-form brief")
    brief = {k: data[k] for k in ("project", "starter", "assets", "init", "requirements")}
    public_errors = []
    def failure(message):
        state = {"status": "build_failed", "public_errors": [*public_errors, str(message)[:2500]]}
        core.save(status, state)
        return state

    design_input = {"project": brief, "required_paths": public_paths(data),
                    "control_schema": core.CONTROL, "module_fields": ["path", "api", "depends_on"]}
    for attempt in (1, 2):
        raw = _ask(folder / f"design-{attempt}", ask, DESIGN, design_input, "staged/design", 3500)
        try:
            spec = parse_design(raw, data)
            break
        except EXCEPTIONS as exc:
            if attempt == 2:
                return failure(exc)
            public_errors.append(str(exc)[:1000])
            design_input = {**design_input, "previous_visible": raw[:16000], "public_error": str(exc)[:1000]}
    core.save(folder / "manifest.json", spec)
    modules = {m["path"]: m for m in spec["modules"]}
    graph = TopologicalSorter({k: m["depends_on"] for k, m in modules.items()})
    graph.prepare()
    sources = {}
    while graph.is_active():
        ready = list(graph.get_ready())

        def write_module(path):
            mod = modules[path]
            prompt = {"project": brief, "manifest": spec, "write_only": path,
                      "dependency_sources": {k: sources[k] for k in mod["depends_on"]}}
            location = folder / "modules" / path
            for attempt in (1, 2):
                raw = _ask(location / str(attempt), ask, SOURCE, prompt, "staged/source/" + path, 3600)
                try:
                    return parse_source(raw, path), None
                except ValueError as exc:
                    why = str(exc)[:1000]
                    core.save(location / str(attempt) / "public-error.json", why)
                    if attempt == 2:
                        return None, why
                    prompt = {**prompt, "previous_visible": raw[:14000],
                              "public_delivery_error": why, "instruction": "Return one complete corrected file."}

        with ThreadPoolExecutor(max_workers=4) as pool:
            outputs = list(pool.map(write_module, ready))
        for path, (source, error) in zip(ready, outputs):
            if error:
                return failure(error)
            sources[path] = source
        graph.done(*ready)
    for version in ("initial", "repair"):
        candidate = folder / version
        try:
            pkg = _admit(candidate, data, spec, sources)
        except EXCEPTIONS as exc:
            if version == "repair":
                return failure(exc)
            public_errors.append(str(exc)[:2500])
            prompt = {"project": brief, "manifest": spec, "sources": sources, "public_error": str(exc)[:2500]}
            raw = _ask(folder / "patch", ask, PATCH, prompt, "staged/patch", 5000)
            try:
                patch = core.parse(raw)
                if patch["path"] not in sources:
                    raise ValueError("Replacement path was not declared in the library")
                sources[patch["path"]] = parse_source(patch["content"], patch["path"])
            except EXCEPTIONS as exc:
                return failure(exc)
        else:
            core.save(folder / "package.json", pkg)
            state = {"status": "valid", "package_sha256": sha(folder / "package.json"),
                     "fixed": str((candidate / "first").relative_to(ROOT)), "public_errors": public_errors}
            core.save(status, state)
            return state
