"""Model-proposed finite source edits and a public browser witness per option."""

import json
import re
import subprocess
from pathlib import Path

from studies.public_library_transfer import browser, core
from studies.public_library_transfer.self_refinement import method
from studies.study_io import digest

HERE = Path(__file__).resolve().parent
S = {"type": "string"}
EVENTS = ("click", "contextmenu", "dblclick", "press")
MEASURES = ("count", "visible", "text", "value")
ACTION = core.obj({"selector": S, "event": {"type": "string", "enum": list(EVENTS)}, "key": S})
PROBE = core.obj({"actions": core.array(ACTION), "watch": S, "measure": {"type": "string", "enum": list(MEASURES)}})
OPTION = core.obj({**{k: S for k in ("id", "file", "original_fragment", "alternative_fragment", "original_behavior", "alternative_behavior")}, "probe": PROBE})
SCHEMA = core.obj({"options": core.array(OPTION)})
DESIGN = """Read your existing working GUI code and its public requirements. Extract one to three genuinely switchable USER INTERACTION behaviors from what the code already does. For each option copy exactly one short unique source fragment from a named JS file, and supply the replacement snippet for the alternate setting. Choose a compact local change, such as how an existing handler updates state. Keep the rest intact. Describe what the user will see for original and alternative. Pick a semantic lowercase-hyphenated id. No task numbers, generated UI markers for tests, cosmetic-only changes, fake events, new functions unrelated to existing features, or whole-page choices. Use one nonoverlapping exact literal fragment per option. Include a SMALL check that is executable in the original starting page: same 1-3 actions (click, right-click via contextmenu, double-click or press) against actual selectors, then a watch selector and measurement count, visible, text, or value. We compare its AFTER value on untouched vs modified code. Both versions must permit the same actions; the watched element may be absent. Make the observed change a consequence of the real behavior. For a non-press action use key="". The project and your own source are the entire specification. Return the specified JSON object."""
PLAN = """Choose original or alternative for every frozen behavior option to implement the last request in this public sequence, preserving prerequisite behavior. The descriptions refer to two observed behaviors of the application. Return just the object, without editing source or repeating the inputs."""


def validate(candidate, files, accepted):
    name, path = candidate["id"], candidate["file"]
    if (not re.fullmatch(r"[a-z][a-z0-9-]{0,47}", name) or re.search(r"task-?\d", name)
            or name in {o["id"] for o in accepted}):
        raise ValueError("Invalid or duplicate semantic option ID")
    if path not in files or not path.endswith((".js", ".mjs")):
        raise ValueError("Expected an existing JavaScript source path")
    old, new = candidate["original_fragment"], candidate["alternative_fragment"]
    if not (isinstance(old, str) and isinstance(new, str) and 0 < len(old.strip()) <= 1000 and len(new) <= 1800 and old != new):
        raise ValueError("Invalid or unchanged source edit")
    if files[path].count(old) != 1:
        raise ValueError(f"Original fragment occurs {files[path].count(old)} times in {path}; copy a unique literal")
    start = files[path].index(old)
    stop = start + len(old)
    if any(x["file"] == path and start < x["stop"] and x["start"] < stop for x in accepted):
        raise ValueError("Replacement overlaps an already accepted option")
    if any(not isinstance(candidate[k], str) or not candidate[k].strip() or len(candidate[k]) > 1000
           for k in ("original_behavior", "alternative_behavior")):
        raise ValueError("Missing or overlong behavior description")
    probe = candidate["probe"]
    if (not 1 <= len(probe["actions"]) <= 3 or probe["measure"] not in MEASURES or not 1 <= len(probe["watch"]) <= 300
            or any(a["event"] not in EVENTS or not 1 <= len(a["selector"]) <= 300 or
                   (a["event"] == "press" and not 1 <= len(a["key"]) <= 40) for a in probe["actions"])):
        raise ValueError("Invalid public interaction probe")
    return {**candidate, "start": start, "stop": stop}


def replace(files, options, alternatives):
    result = dict(files)
    for option in sorted((o for o in options if o["id"] in alternatives), key=lambda o: o["start"], reverse=True):
        path, start, stop = option["file"], option["start"], option["stop"]
        text = result[path]
        if text[start:stop] != option["original_fragment"]:
            raise ValueError("Original source span changed")
        result[path] = text[:start] + option["alternative_fragment"] + text[stop:]
    return result


def emit(data, pkg, changes, selected, dest):
    return method.emit(data, replace(pkg["sources"], changes, set(selected)), method.first(pkg["spec"]), dest)


def readings(page, probe):
    _, runtime, _ = browser.contract("table")
    with browser.serve("table", page) as url:
        proc = subprocess.run(["node", str(HERE / "probe.cjs"), str(runtime / "node_modules/@playwright/test"), url,
                               json.dumps(probe)], env=browser.browser_env(), capture_output=True, text=True, timeout=70, check=True)
    return json.loads(proc.stdout)


def verify_option(candidate, accepted, data, pkg, folder, fixed):
    option = validate(candidate, pkg["sources"], accepted)
    alternative = replace(pkg["sources"], [option], {option["id"]})
    source = alternative[option["file"]]
    parsed = subprocess.run(["node", "--input-type=module", "--check", "-"], text=True, input=source, capture_output=True, timeout=15)
    if parsed.returncode:
        raise ValueError("Replacement syntax error: " + parsed.stderr[:500])
    alt = folder / "alternative"
    emit(data, pkg, [option], [option["id"]], alt)
    errors = browser.public_load("table", alt)
    if errors:
        raise ValueError("Alternative did not load: " + str(errors)[:500])
    orig, variant = readings(fixed, option["probe"]), readings(alt, option["probe"])
    core.save(folder / "witness.json", {"original": orig, "alternative": variant})
    if not all("after" in r for r in orig + variant):
        raise ValueError("Public interaction did not complete: " + str(orig + variant)[:800])
    if orig[0]["after"] != orig[1]["after"] or variant[0]["after"] != variant[1]["after"]:
        raise ValueError("Repeated public measurements varied")
    if digest(orig[0]["after"]) == digest(variant[0]["after"]):
        raise ValueError("Both versions gave the same public measurement: " + str(orig[0]["after"])[:250])
    for mask in range(1, 2 ** len(accepted)):
        selected = [o["id"] for i, o in enumerate(accepted) if mask & (1 << i)] + [option["id"]]
        page = folder / f"combo-{mask}"
        emit(data, pkg, accepted + [option], selected, page)
        errors = browser.public_load("table", page)
        if errors:
            raise ValueError("Combined option values did not load: " + str(errors)[:500])
    return option
