"""Validate a candidate and replay a model's proposed event sequence in the immutable shell."""

import re

from playwright.sync_api import Error as PlaywrightError, sync_playwright

from studies.public_library_transfer import browser, core
from studies.public_library_transfer.other_benchmarks import evaluate
from studies.public_library_transfer.self_refinement.todomvc import run as original

S = {"type": "string"}
EVENTS = ("add", "toggle", "toggleAll", "edit", "save", "cancel", "clearCompleted", "route", "destroy")
WATCH = ("visible.length", "visible.titles", "visible.completed", "countText", "allCompleted", "hasCompleted",
         "hasTodos", "editing", "filter")
EVENT = core.obj({"type": {"type":"string","enum":list(EVENTS)}, "subject": {"type":"string","enum":["first","last","none"]},
                  "title": S, "filter": {"type":"string","enum":["all","active","completed"]}})
PROBE = core.obj({"events": core.array(EVENT), "watch": {"type":"string","enum":list(WATCH)}})
OPTION = core.obj({**{k:S for k in ("id","original_fragment","alternative_fragment","original_behavior","alternative_behavior")},
                   "probe": PROBE})
SCHEMA = core.obj({"options":core.array(OPTION)})
DESIGN = """Read the complete existing TodoMVC controller and the public specification. Extract one to three independent binary settings that toggle a real meaningful behavior in this already working application. Preserve its core add, storage and selection contract in both settings. For each setting copy one SHORT EXACT UNIQUE substring from candidate.js. Supply replacement source for the alternative setting. It must actually change the existing event or view behavior, not add test-only signals. Document the original and alternative meaning. Use a lowercase semantic id and nonoverlapping edits, one source site each. Prefer small targeted edits. For each option specify the SAME 1-4 public API event sequence usable in a fresh empty controller before and after changing the option; for an id-bearing event the harness uses the real first/last todo id selected by 'subject'. Use 'none' where id is irrelevant, title '' where unused and filter 'all' where unused. Name the public view field whose final value will DIFFER. editing is observed as whether editing is active. Use only standard public contracts; don't encode task numbers. Return the requested JSON object."""
EVAL = """probe => {
    const ctrl = window.candidate; let state = ctrl.init();
    for (const input of probe.events) {
        const e = {type: input.type};
        if (['add','save','cancel'].includes(e.type)) e.title = input.title;
        if (e.type === 'route') e.filter = input.filter;
        if (input.subject !== 'none') {
            const t = input.subject === 'first' ? state.todos[0] : state.todos[state.todos.length-1];
            if (!t) throw Error('No todo for the selected subject');
            e.id = t.id;
        }
        state = ctrl.reduce(state,e);
    }
    const view = ctrl.select(state);
    switch (probe.watch) {
      case 'visible.length': return view.visible.length;
      case 'visible.titles': return view.visible.map(t => t.title);
      case 'visible.completed': return view.visible.map(t => t.completed);
      case 'editing': return view.editing != null;
      default: if (!(probe.watch in view)) throw Error('Missing view field'); return view[probe.watch];
    }
}"""


def check(code, where, server, probe=None):
    original.source(code)
    app = evaluate.todo.write_app(code, where / "app")
    results = []
    with browser.browser_slot(), sync_playwright() as pw:
        chromium = pw.chromium.launch(env=evaluate.todo.browser_env())
        try:
            for _ in range(2 if probe else 1):
                page = chromium.new_page()
                page.set_default_timeout(2300)
                errors = []
                page.on("pageerror", lambda err: errors.append(str(err)[:450]))
                try:
                    page.goto(server.url(app), timeout=9000)
                    if not page.evaluate("() => ['init','reduce','select'].every(k=>typeof window.candidate?.[k]==='function')"):
                        raise ValueError("Missing public controller methods")
                    if probe:
                        results.append(page.evaluate(EVAL, probe))
                    else:
                        item = "public controller persistence check"
                        page.locator("#new-todo").fill(item)
                        page.locator("#new-todo").press("Enter")
                        if not page.locator(".todo-list label").filter(has_text=item).is_visible():
                            raise ValueError("Added item is not visible in the public shell")
                        exists = page.evaluate("""title => (JSON.parse(localStorage.getItem('react-todos')) || []).some(t => t.title === title
                                && 'id' in t && t.completed === false)""", item)
                        if not exists:
                            raise ValueError("Public storage does not contain the added todo")
                        page.reload(timeout=9000)
                        if not page.locator(".todo-list label").filter(has_text=item).is_visible():
                            raise ValueError("Added item unavailable after shell reload")
                        if not page.evaluate("""t=>window.candidate.select(window.candidate.init()).visible.some(x=>x.title===t)""", item):
                            raise ValueError("select(init()).visible did not restore the added todo")
                    shell_error = (page.locator("#error").text_content() or "").strip()
                    if shell_error or errors:
                        raise ValueError("Public shell error: " + str([shell_error, *errors])[:550])
                except PlaywrightError as exc:
                    raise ValueError("Public host: " + str(exc)[:550]) from None
                finally:
                    page.close()
        finally:
            chromium.close()
    return results


def anchor(c, text, accepted):
    name, old, new, probe = c["id"], c["original_fragment"], c["alternative_fragment"], c["probe"]
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,47}",name) or re.search(r"task-?\d",name) or name in {o["id"] for o in accepted}:
        raise ValueError("Invalid/repeated semantic id")
    if not isinstance(old,str) or not isinstance(new,str) or not 0<len(old.strip())<=1000 or len(new)>1800 or old==new or text.count(old)!=1:
        raise ValueError("Expected one exact unique changed source fragment of at most 1000 characters")
    start=text.index(old); stop=start+len(old)
    if any(start<o["stop"] and o["start"]<stop for o in accepted):
        raise ValueError("Changes overlap")
    if (not all(isinstance(c[k],str) and c[k].strip() for k in ("original_behavior","alternative_behavior"))
            or not 1<=len(probe["events"])<=4 or probe["watch"] not in WATCH
            or any(e["type"] not in EVENTS or e["subject"] not in ("first","last","none") or len(e["title"])>150
                   or e["filter"] not in ("all","active","completed") for e in probe["events"])):
        raise ValueError("Invalid behavior description or public probe")
    return {**c,"file":"candidate.js","start":start,"stop":stop}
