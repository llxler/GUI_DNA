"""Locate a public delivery defect in one model-written source before official evaluation."""
from copy import deepcopy
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

from studies.public_library_transfer import browser, core
from studies.study_io import ROOT, digest, sha
from studies.webbench.backbone_matrix.run import normalized


def replace_source(raw, path, content):
    """Return a fresh package with exactly one whole JS source replaced."""
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Empty replacement source")
    new = deepcopy(raw)
    if path == "script":
        new["script"] = content
        return new
    if not isinstance(path, str) or not path.endswith((".js", ".mjs")):
        raise ValueError("The replacement must name a submitted JavaScript source")
    matches = [entry for entry in new["files"] if entry["path"] == path]
    if len(matches) != 1:
        raise ValueError(f"No unique submitted source at {path}")
    matches[0]["content"] = content
    return new


def _node_diagnostic(path, code, module):
    if module:
        command = ["node", "--input-type=module", "--check", "-"]
    else:
        command = ["node", "-e", "new (require('node:vm').Script)(require('node:fs').readFileSync(0,'utf8'),"
                   "{filename:'[stdin]'})"]
    proc = subprocess.run(command, input=code, text=True, capture_output=True, timeout=12)
    if proc.returncode == 0:
        return None
    output = proc.stderr.splitlines()
    line = next((int(m[1]) for s in output if (m := re.search(r"\[stdin\]:(\d+)", s))), None)
    caret = next((s.index("^") + 1 for s in output if re.fullmatch(r"\s*\^+\s*", s)), None)
    reason = next((s.strip() for s in output if s.strip().startswith("SyntaxError:")), "JavaScript syntax error")
    lines = code.splitlines()
    snippet = ""
    if line and line <= len(lines):
        start = max(0, (caret or 1) - 65)
        snippet = lines[line - 1][start:start+160]
    return {"kind": "syntax", "path": path, "line": line, "column": caret, "excerpt": snippet,
            "message": f"{path}:{line or '?'}:{caret or '?'} {reason}. Source: {snippet}"}


def _normalize(text):
    return re.sub(r"https?://(?:127\.0\.0\.1|localhost):\d+", "<origin>", str(text))


def _observe(directory, sources):
    fatal, advisory = [], []
    def issue(message, path=None, line=None, column=None):
        entry = {"kind": "load", "message": _normalize(message)[:700], "path": path,
                 "line": line, "column": column}
        if entry not in fatal:
            fatal.append(entry)
    with browser.serve("form", directory) as url, sync_playwright() as pw:
        engine = pw.chromium.launch(env=browser.browser_env())
        try:
            ctx = engine.new_context(service_workers="block")
            ctx.route("**/*", lambda r: r.continue_() if urlsplit(r.request.url).netloc==urlsplit(url).netloc
                      else r.abort())
            page = ctx.new_page()
            page.on("dialog", lambda dialog: dialog.dismiss())
            def exception(error):
                stack = _normalize(getattr(error, "stack", "") or "")
                frame = re.search(r"<origin>/([^\s():?#]+):(\d+):(\d+)", stack)
                path = frame[1] if frame else None
                if path == "index.html" and "script" in sources:
                    path = "script"
                line = int(frame[2]) if frame else None
                column = int(frame[3]) if frame else None
                issue(_normalize(error) + (f" [{path}:{line}:{column}]" if path else ""), path, line, column)
            page.on("pageerror", exception)
            def response(r):
                path = urlsplit(r.url).path.lstrip("/")
                if r.status >= 400 and r.request.resource_type in ("script", "document", "stylesheet"):
                    issue(f"HTTP {r.status} loading {path}", path)
            page.on("response", response)
            def console(msg):
                if msg.type == "error":
                    loc = msg.location or {}
                    path = urlsplit(loc.get("url", "")).path.lstrip("/") or None
                    issue(msg.text, path, loc.get("lineNumber"), loc.get("columnNumber"))
            page.on("console", console)
            res = page.goto(url + "/index.html", wait_until="load", timeout=15000)
            if res is None:
                issue("Public index.html did not return a response")
            page.wait_for_timeout(200)
            startup = list(fatal)
            # Exercise a representative form action after recording all initial load failures.
            # An intentionally minimal configuration can lack this control.
            obs = page.evaluate("""() => {
              const form = document.querySelector('form');
              if (!form) return {form: false, questions: 0, sample: null, nativeChoice: null};
              const questions = [...form.querySelectorAll('fieldset')];
              const target = form.querySelector('input[type=checkbox]:not(:disabled), input[type=radio]:not(:checked):not(:disabled)');
              let nativeChoice = null;
              if(target) {
                const before=target.checked;
                target.click();
                nativeChoice={kind:target.type, changed:before!==target.checked, name:target.name};
              }
              const first=questions[0];
              return {form:true, questions:questions.length,
                      sample:first ? {id:first.id, legend:!!first.querySelector('legend')} : null,
                      nativeChoice};
            }""")
            if not obs["form"]:
                advisory.append("No form is mounted at the starter entry")
            elif not obs["questions"]:
                advisory.append("No question fieldset is mounted in the starter form")
            elif not obs["sample"]["legend"]:
                advisory.append("The first mounted question does not contain a legend")
            if obs["nativeChoice"] and not obs["nativeChoice"]["changed"]:
                advisory.append("The mounted native choice did not change after a click")
            advisory.extend(x["message"] for x in fatal if x not in startup)
            return {"startup": startup, "interaction": obs, "advisories": advisory}
        finally:
            engine.close()


def diagnose(data, raw, folder):
    """Return mandatory syntax/load errors separately from public interaction observations."""
    folder = Path(folder).resolve()
    if data["project"] != "form":
        raise ValueError("This check applies to public Web-Bench form only")
    issues, checks, notes = [], {}, []
    preferred = None
    fixed = None
    package_sha = None
    pkg = None
    try:
        pkg = core.package(data, normalized(deepcopy(raw)))
    except (ValueError, TypeError, KeyError, AttributeError, IndexError) as exc:
        issues.append({"kind": "contract", "path": None, "message": str(exc)})
    if pkg is not None:
        sources = {name: code for name,code in pkg["files"].items() if name.endswith((".js",".mjs"))}
        if pkg["script"]:
            sources["script"] = pkg["script"]
        for path, content in sources.items():
            found = _node_diagnostic(path, content, module=(path != "script"))
            if found:
                issues.append(found)
        if not issues:
            core.save(folder / "package.json", pkg)
            package_sha = sha(folder / "package.json")
            for mode, plan in (("default", pkg["defaults"]), ("first", pkg["examples"][0]["plan"])):
                here = folder / mode
                page = here / "page"
                files = core.materialize("form", pkg, plan, page)
                obs = _observe(page, sources)
                obs["files_sha256"] = digest(files)
                core.save(here / "observation.json", obs)
                checks[mode] = obs
                issues.extend(obs["startup"])
                notes.extend(f"{mode}: {why}" for why in obs["advisories"])
            if not issues:
                fixed = str((folder / "first/page").relative_to(ROOT))
        preferred = next((r["path"] for r in issues if r.get("path") in sources), None)
        if preferred is None and (issues or notes):
            preferred = next((p for p in ("index.js", "script") if p in sources), None)
    result = {"loadable": not issues, "issues": [r["message"] for r in issues], "locations": issues,
              "preferred_path": preferred, "checks": checks, "advisories": notes, "fixed": fixed,
              "package_sha256": package_sha}
    core.save(folder / "diagnosis.json", result)
    return result
