"""Parse model-authored workspace edits and the public interaction probe."""

import json
import re

from studies.public_library_transfer import core
from studies.public_library_transfer.self_refinement import method

DESIGN = """Design a small configuration interface for one reusable GUI library covering the supplied public project. Read all of its successive revisions. Implement stable features in the shared code; expose a few genuinely switchable event/state behaviors and document what every value does. Do not invent decorative options, task numbers, one page per target, or numbered stages. The builder will edit the project incrementally. Use string values for all options; specify a fixed, usable initial example for each. Return only JSON: {"controls":[{"id":"lowercase-name","values":["value1","value2"],"example":"value1","description":"when each value is useful and what it changes"}]}. Use 1 through 6 controls with 2 through 8 choices each."""
EDIT = """You own this working browser project. Implement the newly supplied public requirements while preserving all earlier working interactions and selectors. The project is cumulative. Start from the complete current files supplied, reuse working code, and change only what is needed. Read the public descriptions literally, including filenames, CSS selectors, classes, DOM event rules, state sharing and named exports. Allow real interaction end to end. Use the frozen finite options via globalThis.APP_CONFIG; option values are strings. Keep generally applicable behaviors enabled across configurations and use choices for alternative behaviors. No task-number switches, external packages, test files or target-specific pages. The original HTML remains mounted, do not edit it. Write browser JS modules and CSS. Provide a simple model-authored public check for one new or maintained behavior of the fixed initial configuration: a selector, a DOM event, and a selector made visible by that event.

Use these EXACT column-zero markers and no Markdown or commentary. For a new or replacement file:
@@FILE relative/name.js
raw complete file contents, no escapes or fences
@@END
To replace a unique exact substring in an existing file:
@@PATCH relative/name.js
@@OLD
exact previous lines
@@NEW
replacement lines
@@END
Include all necessary edits and exactly one smoke check block:
@@PROBE
{"selector":"CSS selector for an existing target","event":"click|dblclick|contextmenu|input|change|mouseover","visible":"CSS selector visible after the event"}
@@END
Use whole-file writes when uncertain of the exact previous text. Do not restate unchanged files. At least one file edit is required."""
PLAN = """Select data values to implement the last public request while retaining its prerequisites. The implementation already exists. Return the configuration alone, using exactly the keys and string domains in the interface. Match the shape of the example. Do not repeat the input or return source code."""


def controls(raw):
    spec = core.parse(raw)
    values = spec["controls"]
    if not isinstance(values, list) or not 1 <= len(values) <= 6:
        raise ValueError("Expected one to six controls")
    ids = set()
    for c in values:
        name, options = c["id"], c["values"]
        if (not re.fullmatch(r"[a-z][a-z0-9-]{0,49}", name) or name in ids
                or not isinstance(options, list) or not 2 <= len(options) <= 8
                or not all(isinstance(v, str) and re.fullmatch(r"[\w .+-]{1,64}", v) for v in options)
                or len(set(options)) != len(options) or c["example"] not in options
                or not isinstance(c["description"], str) or not c["description"].strip()):
            raise ValueError("Invalid option name, domain, example or description")
        ids.add(name)
    return {"controls": values}


def changed(raw, previous):
    text = method.source(raw)
    chunks = text.splitlines()
    files, probe, i, edits = dict(previous), None, 0, 0
    while i < len(chunks):
        line = chunks[i]
        i += 1
        if not line.strip():
            continue
        if line != "@@PROBE" and not line.startswith(("@@FILE ", "@@PATCH ")):
            raise ValueError(f"Unknown edit header: {line[:120]}")
        try:
            end = chunks.index("@@END", i)
        except ValueError:
            raise ValueError("Unterminated edit block") from None
        body = "\n".join(chunks[i:end])
        i = end + 1
        if line == "@@PROBE":
            if probe is not None:
                raise ValueError("Duplicate public probe")
            probe = json.loads(body)
            if (probe["event"] not in ("click", "dblclick", "contextmenu", "input", "change", "mouseover")
                    or not all(isinstance(probe[k], str) and 0 < len(probe[k]) <= 512 for k in ("selector", "visible"))):
                raise ValueError("Invalid public event or selector")
            continue
        operation, path = line.split(" ", 1)
        if not path.endswith((".js", ".mjs", ".css")):
            raise ValueError("Only local JS modules and CSS may be edited")
        if operation == "@@PATCH":
            if not body.startswith("@@OLD\n") or body.count("\n@@NEW\n") != 1:
                raise ValueError("Expected one OLD/NEW replacement")
            old, new = body[len("@@OLD\n"):].split("\n@@NEW\n", 1)
            if not old or path not in files or files[path].count(old) != 1:
                raise ValueError(f"Replacement anchor not unique in {path}")
            body = files[path].replace(old, new, 1)
        else:
            body += "\n"
        files.update(core.files_map([{"path": path, "content": body}]))
        edits += 1
    if not updates(previous, files) or not edits or probe is None:
        raise ValueError("Expected file changes and one interaction probe")
    return files, probe


def updates(previous, current):
    return [name for name, text in current.items() if previous.get(name) != text]
